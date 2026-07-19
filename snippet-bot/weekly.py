"""주간 스니펫 파이프라인 — 매주 일요일 23:30 Windows 작업 스케줄러로 실행 (§8).

흐름: 이번 주(월~일) 일간 스니펫 수집(1순위: 사이트 조회 API, 폴백: log/archive/)
→ claude -p로 주간 요약 스니펫 생성 → 업로드 → AI 채점.
logs/weekly_YYYY-WW.log에 기록한다.

사용법:
  python weekly.py             # 실제 실행
  python weekly.py --dry-run   # 사이트 API 호출 없이 생성 결과만 콘솔 출력
  python weekly.py --date 2026-07-19   # 기준 날짜 지정(그 날짜가 속한 월~일 주간)
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date as date_cls, datetime, timedelta

import config
import generate
import notify
import site_api


def week_range_for(run_date: date_cls) -> tuple[date_cls, date_cls]:
    """run_date가 속한 주의 (월요일, 일요일)을 반환한다."""
    monday = run_date - timedelta(days=run_date.weekday())
    return monday, monday + timedelta(days=6)


def default_target_date(now: datetime) -> date_cls:
    """요약 대상 주를 정하는 기준 날짜.

    정규 실행(일요일 밤)이면 오늘이 속한 주. 그 외(놓친 일요일 실행의 보충,
    §9/§13)는 '직전 일요일'을 기준으로 삼아 지난주가 요약되게 한다.
    """
    d = now.date()
    if d.weekday() == 6:  # 일요일
        return d
    return d - timedelta(days=(d.weekday() + 1) % 7)


def _format_site_snippets(items: list) -> str:
    parts = []
    for item in items:
        if isinstance(item, dict):
            parts.append(json.dumps(item, ensure_ascii=False, indent=2))
        else:
            parts.append(str(item))
    return "\n\n---\n\n".join(parts)


def collect_from_archive(monday: date_cls, sunday: date_cls,
                         logger: logging.Logger) -> str | None:
    """log/archive/에서 해당 주(월~일)의 일간 기록 파일들을 모아 하나의 텍스트로 만든다."""
    sections = []
    day = monday
    while day <= sunday:
        # 같은 날짜의 보관본이 여러 개면(YYYY-MM-DD.md, YYYY-MM-DD_2.md …) 모두 포함
        for path in sorted(config.ARCHIVE_DIR.glob(f"{day.isoformat()}*.md")):
            text = path.read_text(encoding="utf-8", errors="replace").strip()
            if text:
                sections.append(f"## {day.isoformat()} ({path.name})\n\n{text}")
        day += timedelta(days=1)
    if not sections:
        return None
    logger.info("log/archive/에서 %d개 파일 수집", len(sections))
    return "\n\n".join(sections)


def collect_weekly_material(monday: date_cls, sunday: date_cls,
                            logger: logging.Logger) -> str | None:
    """1순위: 사이트 조회 API. 조회 API 미구현/실패 시 log/archive/ 폴백 (§8-1)."""
    try:
        items = site_api.get_daily_snippets(
            monday.isoformat(), sunday.isoformat(), logger=logger)
        if items:
            logger.info("사이트 조회 API에서 일간 스니펫 %d건 수집", len(items))
            return _format_site_snippets(items)
        logger.info("사이트 조회 결과가 비어 있어 log/archive/ 폴백을 사용합니다.")
    except site_api.SiteApiNotImplemented:
        logger.info("사이트 조회 API 미구현 — log/archive/ 폴백을 사용합니다.")
    except Exception as exc:
        logger.warning("사이트 조회 실패(%s) — log/archive/ 폴백을 사용합니다.", exc)
    return collect_from_archive(monday, sunday, logger)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="주간 스니펫 자동화 파이프라인")
    parser.add_argument("--dry-run", action="store_true",
                        help="사이트 API 호출 없이 스니펫 생성 결과만 콘솔에 출력")
    parser.add_argument("--date", help="YYYY-MM-DD 형식 기준 날짜(기본: 오늘)")
    args = parser.parse_args(argv)

    now = datetime.now()
    run_date = (date_cls.fromisoformat(args.date) if args.date
                else default_target_date(now))
    iso = run_date.isocalendar()
    logger = config.setup_logging(f"weekly_{iso.year}-W{iso.week:02d}.log")
    monday, sunday = week_range_for(run_date)
    week_label = f"{monday.isoformat()} ~ {sunday.isoformat()}"
    logger.info("=== 주간 파이프라인 시작 (주간=%s, dry_run=%s) ===",
                week_label, args.dry_run)
    if not args.date and run_date != now.date():
        logger.info("일요일이 아닌 시점의 실행 → 놓친 주간 실행의 보충으로 판단해 "
                    "지난주(%s)를 요약합니다", week_label)

    if config.strip_anthropic_api_key(logger):
        notify.notify("SnippetBot 경고",
                      "ANTHROPIC_API_KEY가 감지되어 이번 실행에서 제거했습니다. "
                      "시스템 환경변수에서도 삭제하세요.", logger)

    material = collect_weekly_material(monday, sunday, logger)
    if not material:
        logger.info("이번 주 일간 스니펫/기록이 없어 종료합니다.")
        notify.notify("SnippetBot", f"이번 주({week_label}) 기록이 없어 주간 스니펫을 "
                                    "올리지 않았습니다.", logger)
        return 0

    try:
        snippet = generate.generate_weekly_snippet(material, week_label, logger=logger)
        logger.info("주간 스니펫 생성 완료 (%d자)", len(snippet))
    except generate.ClaudeAuthError as exc:
        logger.error("Claude 로그인/사용량 오류: %s", exc)
        notify.notify("SnippetBot 실패", f"Claude 로그인/사용량 오류: {exc}", logger)
        return 1
    except Exception as exc:
        logger.exception("주간 스니펫 생성 실패 — 불완전한 내용을 업로드하지 않습니다 (§10)")
        notify.notify("SnippetBot 실패", f"주간 스니펫 생성 실패: {exc}", logger)
        return 1

    if args.dry_run:
        print(snippet)
        logger.info("dry-run 완료 — 업로드·채점을 생략합니다.")
        return 0

    try:
        snippet_id = site_api.post_weekly_snippet(week_label, snippet, logger=logger)
        logger.info("업로드 완료: snippet_id=%s", snippet_id)
        grading = site_api.run_ai_grading(snippet_id, kind="weekly", logger=logger)
        logger.info("AI 채점 완료: %s", grading)
    except site_api.SiteApiError as exc:
        logger.error("%s", exc)
        notify.notify("SnippetBot", str(exc), logger)
        return 1
    except Exception as exc:
        logger.exception("사이트 업로드/채점 실패")
        notify.notify("SnippetBot 실패", f"사이트 업로드/채점 실패: {exc}", logger)
        return 1

    logger.info("=== 주간 파이프라인 정상 종료 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
