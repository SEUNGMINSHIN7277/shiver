"""일간 스니펫 파이프라인 — 매일 23:30 Windows 작업 스케줄러로 실행 (§7).

흐름: log/today.md 읽기 → claude -p로 7항목 스니펫 생성 → 사이트 업로드 →
AI 채점 → today.md를 log/archive/YYYY-MM-DD.md로 보관 후 빈 today.md 재생성.
전 과정을 logs/daily_YYYY-MM-DD.log에 기록한다.

사용법:
  python daily.py             # 실제 실행
  python daily.py --dry-run   # 사이트 API 호출 없이 생성 결과만 콘솔 출력 (§12-2)
  python daily.py --date 2026-07-19   # 날짜 지정(테스트용)
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import date as date_cls
from pathlib import Path

import config
import generate
import notify
import site_api


def read_today_md() -> str | None:
    """today.md 내용을 반환한다. 파일이 없거나 공백뿐이면 None (§7-1)."""
    if not config.TODAY_MD.exists():
        return None
    text = config.TODAY_MD.read_text(encoding="utf-8", errors="replace")
    return text if text.strip() else None


def archive_today_md(run_date: date_cls) -> Path:
    """today.md를 log/archive/YYYY-MM-DD.md로 옮기고 빈 today.md를 재생성한다 (§7-5).

    같은 날짜 파일이 이미 있으면 _2, _3 … 접미사를 붙여 덮어쓰기를 피한다.
    """
    config.ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    target = config.ARCHIVE_DIR / f"{run_date.isoformat()}.md"
    suffix = 2
    while target.exists():
        target = config.ARCHIVE_DIR / f"{run_date.isoformat()}_{suffix}.md"
        suffix += 1
    shutil.move(str(config.TODAY_MD), str(target))
    config.TODAY_MD.write_text("", encoding="utf-8")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="일간 스니펫 자동화 파이프라인")
    parser.add_argument("--dry-run", action="store_true",
                        help="사이트 API 호출 없이 스니펫 생성 결과만 콘솔에 출력")
    parser.add_argument("--date", help="YYYY-MM-DD 형식 실행 날짜(기본: 오늘)")
    args = parser.parse_args(argv)

    run_date = date_cls.fromisoformat(args.date) if args.date else date_cls.today()
    logger = config.setup_logging(f"daily_{run_date.isoformat()}.log")
    logger.info("=== 일간 파이프라인 시작 (date=%s, dry_run=%s) ===",
                run_date.isoformat(), args.dry_run)

    # §4: ANTHROPIC_API_KEY가 있으면 구독 대신 API 과금으로 전환되므로 제거
    if config.strip_anthropic_api_key(logger):
        notify.notify("SnippetBot 경고",
                      "ANTHROPIC_API_KEY가 감지되어 이번 실행에서 제거했습니다. "
                      "시스템 환경변수에서도 삭제하세요.", logger)

    today_text = read_today_md()
    if not today_text:
        logger.info("log/today.md가 없거나 비어 있어 스니펫을 올리지 않고 종료합니다.")
        notify.notify("SnippetBot", "오늘 기록이 없습니다", logger)
        return 0
    logger.info("today.md 읽기 완료 (%d자)", len(today_text))

    try:
        snippet = generate.generate_daily_snippet(
            today_text, run_date.isoformat(), logger=logger)
        logger.info("스니펫 생성 완료 (%d자)", len(snippet))
    except generate.ClaudeAuthError as exc:
        logger.error("Claude 로그인/사용량 오류: %s", exc)
        notify.notify("SnippetBot 실패", f"Claude 로그인/사용량 오류: {exc}", logger)
        return 1
    except Exception as exc:
        logger.exception("스니펫 생성 실패 — 불완전한 내용을 업로드하지 않습니다 (§10)")
        notify.notify("SnippetBot 실패", f"일간 스니펫 생성 실패: {exc}", logger)
        return 1

    if args.dry_run:
        print(snippet)
        logger.info("dry-run 완료 — 업로드·채점·보관을 생략합니다.")
        return 0

    try:
        snippet_id = site_api.post_daily_snippet(
            run_date.isoformat(), snippet, logger=logger)
        logger.info("업로드 완료: snippet_id=%s", snippet_id)
        grading = site_api.run_ai_grading(snippet_id, logger=logger)
        logger.info("AI 채점 완료: %s", grading)
    except site_api.SiteApiError as exc:
        logger.error("%s", exc)
        notify.notify("SnippetBot 실패", str(exc), logger)
        return 1
    except Exception as exc:
        logger.exception("사이트 업로드/채점 실패 — today.md는 보관하지 않고 유지합니다")
        notify.notify("SnippetBot 실패", f"사이트 업로드/채점 실패: {exc}", logger)
        return 1

    archived = archive_today_md(run_date)
    logger.info("보관 완료: %s → 빈 today.md 재생성", archived)
    logger.info("=== 일간 파이프라인 정상 종료 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
