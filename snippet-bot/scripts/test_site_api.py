"""사이트 API 라이브 검증 스크립트 — 사용자 PC(Windows)에서 실행 (§12-3).

원격 개발 환경에서는 api.1000.school 접속이 차단되어, 실제 인증·응답 구조 확인은
이 스크립트로 사용자 PC에서 수행한다.

사용법 (C:\\snippet-bot 에서):
  venv\\Scripts\\python scripts\\test_site_api.py check         # 인증 + 일간 page-data 구조 확인
  venv\\Scripts\\python scripts\\test_site_api.py weekly-check  # 주간 page-data 구조 확인
  venv\\Scripts\\python scripts\\test_site_api.py save-test     # 오늘 일간 스니펫 저장 테스트(PUT, 확인 입력 필요)
  venv\\Scripts\\python scripts\\test_site_api.py grade         # AI 채점 실행(SSE) 테스트
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
import site_api  # noqa: E402


def _print_json(name: str, data, limit: int = 3000) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2, default=str)
    print(f"\n== {name} (앞 {limit}자) ==")
    print(config.mask_secret(text[:limit]))
    config.RUN_LOG_DIR.mkdir(parents=True, exist_ok=True)
    out = config.RUN_LOG_DIR / f"dump_{name}.json"
    out.write_text(text, encoding="utf-8")
    print(f"[전체 내용 저장: {out}]")


def cmd_check() -> int:
    print("== 1) 인증 확인: GET /auth/me ==")
    me = site_api.check_auth()
    _print_json("auth_me", me, limit=500)
    print("\n== 2) 일간 page-data 조회 ==")
    page = site_api.get_page_data("daily")
    _print_json("daily_page_data", page)
    today = date.today().isoformat()
    snippet_id = site_api._find_snippet_id_for_date(page, today)
    print(f"\n== 3) 오늘({today}) 스니펫 id 탐색 결과: {snippet_id!r} ==")
    if snippet_id is None:
        print("→ id를 특정하지 못했습니다. 위 dump_daily_page_data.json 을 공유해 주세요.")
        return 1
    print("→ 정상! post_daily_snippet이 이 id로 PUT하게 됩니다.")
    return 0


def cmd_weekly_check() -> int:
    page = site_api.get_page_data("weekly")
    _print_json("weekly_page_data", page)
    return 0


def cmd_save_test() -> int:
    today = date.today().isoformat()
    print(f"⚠️ 오늘({today}) 일간 스니펫의 content를 아래 테스트 문구로 '덮어씁니다'.")
    print("   사이트에 이미 작성해 둔 내용이 있으면 지워지니 주의하세요.")
    answer = input("계속하려면 yes 입력: ").strip().lower()
    if answer != "yes":
        print("취소했습니다.")
        return 1
    content = f"SnippetBot 연결 테스트입니다 ({today}). 이 문구가 보이면 API 연동 성공."
    snippet_id = site_api.post_daily_snippet(today, content)
    print(f"저장 성공: snippet_id={snippet_id} — 사이트 UI에서 표시를 확인하세요.")
    return 0


def cmd_grade() -> int:
    print("AI 채점 실행(SSE 스트림 수신, 최대 수 분 소요)...")
    result = site_api.run_ai_grading("manual-test")
    _print_json("grading_result", result)
    return 0


COMMANDS = {
    "check": cmd_check,
    "weekly-check": cmd_weekly_check,
    "save-test": cmd_save_test,
    "grade": cmd_grade,
}


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        return 2
    try:
        return COMMANDS[sys.argv[1]]()
    except site_api.SiteApiAuthError as exc:
        print(f"\n인증 실패: {config.mask_secret(str(exc))}")
        print("→ Bearer 토큰이 거부된 경우 .env의 SNIPPET_SITE_SESSION에 브라우저 session "
              "쿠키 값을 넣고 다시 시도하세요 (.env.example 참고).")
        return 1
    except site_api.SiteApiError as exc:
        print(f"\nAPI 오류: {config.mask_secret(str(exc))}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
