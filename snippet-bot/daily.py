"""일간 스니펫 파이프라인 — 매일 23:30 Windows 작업 스케줄러로 실행 (§7).

"사용자 개입 0" 흐름: 그날 로컬 Claude Code에서 나눈 대화 기록을 자동 수집하고
(collect_activity.py), 선택적으로 log/today.md 메모가 있으면 함께 사용해
7항목 스니펫 생성 → 사이트 업로드 → AI 채점 → 보관까지 자동으로 수행한다.
today.md는 이제 필수가 아니라 보조 메모다.

성공 시 생성된 스니펫을 log/archive/YYYY-MM-DD.md 로 저장하고(주간 요약의 폴백
자료원), today.md가 있었다면 log/archive/YYYY-MM-DD_memo.md 로 보관 후 비운다.

사용법:
  python daily.py             # 실제 실행
  python daily.py --dry-run   # 사이트 API 호출 없이 생성 결과만 콘솔 출력 (§12-2)
  python daily.py --date 2026-07-19   # 날짜 지정(테스트용)
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import date as date_cls, datetime, timedelta
from pathlib import Path

import collect_activity
import config
import generate
import notify
import site_api


def default_run_date(now: datetime) -> date_cls:
    """예정 시각(23:30) 기준 논리적 실행 날짜를 정한다.

    23시 이전 실행은 PC가 꺼져 있어 놓친 전날 23:30 실행의 보충(StartWhenAvailable,
    §9/§13)으로 보고 전날을 대상으로 한다. 오늘 날짜로 강제하려면 --date를 사용.
    """
    if now.hour >= 23:
        return now.date()
    return now.date() - timedelta(days=1)


def read_today_md() -> str | None:
    """today.md 내용을 반환한다. 파일이 없거나 공백뿐이면 None.

    한국어 Windows에서 ANSI(CP949)로 저장된 경우도 조용히 깨뜨리지 않고 읽는다.
    """
    if not config.TODAY_MD.exists():
        return None
    raw = config.TODAY_MD.read_bytes()
    for encoding in ("utf-8-sig", "cp949"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("utf-8", errors="replace")
    return text if text.strip() else None


def build_daily_source(run_date: date_cls, logger) -> str | None:
    """스니펫 원천 자료를 만든다: 사용자 메모(선택) + 오늘의 Claude 대화(자동)."""
    parts = []
    memo = read_today_md()
    if memo:
        logger.info("today.md 메모 사용 (%d자)", len(memo))
        parts.append(f"## 사용자 메모 (today.md)\n\n{memo}")
    conversations = collect_activity.collect_today_conversations(run_date, logger=logger)
    if conversations:
        parts.append(f"## 오늘의 Claude Code 대화 기록\n\n{conversations}")
    if not parts:
        return None
    return "\n\n".join(parts)


def _archive_target(stem: str) -> Path:
    """log/archive/<stem>.md 경로를 만들되, 이미 있으면 _2, _3… 접미사를 붙인다."""
    config.ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    target = config.ARCHIVE_DIR / f"{stem}.md"
    suffix = 2
    while target.exists():
        target = config.ARCHIVE_DIR / f"{stem}_{suffix}.md"
        suffix += 1
    return target


def save_snippet_to_archive(run_date: date_cls, snippet: str) -> Path:
    """생성된 스니펫을 log/archive/YYYY-MM-DD.md 로 저장한다(주간 폴백 자료원)."""
    target = _archive_target(run_date.isoformat())
    target.write_text(snippet, encoding="utf-8")
    return target


def archive_today_md(run_date: date_cls) -> Path | None:
    """today.md가 있으면 log/archive/YYYY-MM-DD_memo.md 로 옮기고 빈 파일을 재생성한다."""
    if not config.TODAY_MD.exists():
        return None
    target = _archive_target(f"{run_date.isoformat()}_memo")
    shutil.move(str(config.TODAY_MD), str(target))
    config.TODAY_MD.write_text("", encoding="utf-8")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="일간 스니펫 자동화 파이프라인")
    parser.add_argument("--dry-run", action="store_true",
                        help="사이트 API 호출 없이 스니펫 생성 결과만 콘솔에 출력")
    parser.add_argument("--date", help="YYYY-MM-DD 형식 실행 날짜(기본: 오늘)")
    args = parser.parse_args(argv)

    now = datetime.now()
    run_date = date_cls.fromisoformat(args.date) if args.date else default_run_date(now)
    logger = config.setup_logging(f"daily_{run_date.isoformat()}.log")
    logger.info("=== 일간 파이프라인 시작 (date=%s, dry_run=%s) ===",
                run_date.isoformat(), args.dry_run)
    if not args.date and run_date != now.date():
        logger.info("23시 이전 실행 → 놓친 전날 실행의 보충으로 판단해 %s 날짜로 "
                    "진행합니다 (오늘 날짜로 하려면 --date %s)",
                    run_date.isoformat(), now.date().isoformat())

    # 보충 실행과 정규 실행이 겹쳐도 같은 날짜를 두 번 올리지 않게 멱등성 확인
    if not args.dry_run and (config.ARCHIVE_DIR / f"{run_date.isoformat()}.md").exists():
        logger.info("%s 스니펫은 이미 처리되어 있습니다(archive 존재) — 종료합니다.",
                    run_date.isoformat())
        return 0

    # §4: ANTHROPIC_API_KEY가 있으면 구독 대신 API 과금으로 전환되므로 제거
    if config.strip_anthropic_api_key(logger):
        notify.notify("SnippetBot 경고",
                      "ANTHROPIC_API_KEY가 감지되어 이번 실행에서 제거했습니다. "
                      "시스템 환경변수에서도 삭제하세요.", logger)

    source = build_daily_source(run_date, logger)
    if not source:
        logger.info("오늘 기록이 없습니다(Claude 대화도 today.md 메모도 없음) — "
                    "스니펫을 올리지 않고 종료합니다.")
        notify.notify("SnippetBot", "오늘 기록이 없습니다", logger)
        return 0
    logger.info("원천 자료 준비 완료 (%d자)", len(source))

    try:
        snippet = generate.generate_daily_snippet(
            source, run_date.isoformat(), logger=logger)
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

    archived_snippet = save_snippet_to_archive(run_date, snippet)
    logger.info("스니펫 보관: %s", archived_snippet)
    archived_memo = archive_today_md(run_date)
    if archived_memo:
        logger.info("메모 보관: %s → 빈 today.md 재생성", archived_memo)
    logger.info("=== 일간 파이프라인 정상 종료 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
