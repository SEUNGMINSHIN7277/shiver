"""claude -p 서브프로세스 호출로 스니펫을 생성한다 (§5).

Anthropic API 키를 사용하지 않는다. 이 PC에 설치·로그인된 Claude Code의
헤드리스 모드(claude -p --output-format text)를 서브프로세스로 호출해
구독 사용량으로 처리한다(추가 과금 없음).

긴 입력(today.md 본문·주간 자료)은 명령줄 인자 길이 제한을 피하기 위해
stdin으로 전달하고, -p 인자에는 형식 지시만 담는다.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys

import config

# 출력에서 스니펫 본문만 안정적으로 추출하기 위한 마커
SNIPPET_START = "<<<SNIPPET_START>>>"
SNIPPET_END = "<<<SNIPPET_END>>>"


class ClaudeError(RuntimeError):
    """claude -p 호출 실패."""


class ClaudeAuthError(ClaudeError):
    """로그인 만료·사용량 한도 등 재시도로 해결되지 않는 오류 (§10)."""


_AUTH_ERROR_PATTERNS = (
    "please run /login",
    "not logged in",
    "login expired",
    "session expired",
    "invalid api key",
    "authentication",
    "unauthorized",
    "usage limit",
    "rate limit",
    "credit balance",
    "out of credits",
    "oauth token",
)


def _looks_like_auth_error(text: str) -> bool:
    lowered = text.lower()
    return any(pattern in lowered for pattern in _AUTH_ERROR_PATTERNS)


def find_claude() -> str:
    """claude 실행 파일의 절대경로를 찾는다. PATH 실패 시 Windows에서는 where로 재탐색."""
    path = shutil.which("claude")
    if path:
        return path
    if sys.platform == "win32":
        try:
            result = subprocess.run(["where", "claude"], capture_output=True,
                                    text=True, timeout=10)
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if line:
                        return line
        except Exception:
            pass
    raise ClaudeError(
        "claude 명령을 찾을 수 없습니다. Claude Code가 설치되어 있는지, "
        "PATH에 등록되어 있는지 확인하세요 (where claude)."
    )


def run_claude(instruction: str, stdin_text: str | None = None, *,
               timeout: int = config.CLAUDE_TIMEOUT_SECONDS,
               logger: logging.Logger | None = None) -> str:
    """claude -p <instruction> --output-format text 를 호출해 표준출력을 반환한다.

    - stdin_text가 있으면 표준 입력으로 전달한다(긴 원천 기록용).
    - ANTHROPIC_API_KEY는 자식 프로세스 환경에서 항상 제거한다(과금 방지, §4).
    - 실패 시 3회 재시도(2s/4s/8s). 인증·한도 오류(ClaudeAuthError)는 즉시 중단.
    """
    claude_path = find_claude()
    cmd = [claude_path, "-p", instruction, "--output-format", "text"]
    # npm 전역 설치 시 claude는 .cmd 셔틀 스크립트일 수 있어 cmd /c 로 감싼다
    if claude_path.lower().endswith((".cmd", ".bat")):
        cmd = ["cmd", "/c", *cmd]

    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)

    def _call() -> str:
        proc = subprocess.run(
            cmd,
            input=stdin_text if stdin_text is not None else "",
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, env=env,
        )
        combined = f"{proc.stdout}\n{proc.stderr}".strip()
        if proc.returncode != 0:
            if _looks_like_auth_error(combined):
                raise ClaudeAuthError(
                    f"claude 로그인/사용량 오류(종료 코드 {proc.returncode}): {combined[:500]}"
                )
            raise ClaudeError(
                f"claude 호출 실패(종료 코드 {proc.returncode}): {combined[:500]}"
            )
        output = proc.stdout.strip()
        if not output:
            raise ClaudeError("claude가 빈 출력을 반환했습니다")
        if _looks_like_auth_error(output) and SNIPPET_START not in output:
            raise ClaudeAuthError(f"claude 인증/한도 관련 응답: {output[:500]}")
        return output

    return config.with_retries(_call, desc="claude 호출", logger=logger,
                               fatal=(ClaudeAuthError,))


def extract_snippet(raw: str) -> str:
    """claude 출력에서 스니펫 본문만 추출한다(앞뒤 불필요 문구 제거, §5).

    마커 쌍이 있으면 그 사이만, 없으면 마커 잔여물을 제거한 전체를 반환한다.
    """
    try:
        start = raw.index(SNIPPET_START) + len(SNIPPET_START)
        end = raw.index(SNIPPET_END, start)
        return raw[start:end].strip()
    except ValueError:
        return raw.replace(SNIPPET_START, "").replace(SNIPPET_END, "").strip()


_FORMAT_SPEC = f"""아래 7항목 형식의 스니펫을 한국어 마크다운, 격식체로 작성하십시오.
각 항목은 2~5문장으로 작성합니다.

## 1. what — 무엇을 했는가
## 2. why — 왜 했는가
## 3. what value added — 어떤 가치를 더했는가
## 4. highlight — 하이라이트
## 5. lowlight — 로우라이트
## 6. Tomorrow — 앞으로 할 일
## 7. feelings — 소감

작성 원칙:
- 전달된 기록에 적힌 사실만 사용하고, 기록에 없는 내용은 창작하지 않습니다.
- 기록이 부족한 항목은 기록된 범위 안에서 짧게 작성합니다.

출력 규칙: 인사말·설명 등 다른 문구 없이, 스니펫 본문만
{SNIPPET_START} 와 {SNIPPET_END} 마커 사이에 넣어 출력하십시오."""


def generate_daily_snippet(today_text: str, date_str: str, *,
                           logger: logging.Logger | None = None) -> str:
    """today.md 내용으로 일간 스니펫을 생성한다 (§7-2)."""
    instruction = (
        f"당신은 팀 스니펫 작성 도우미입니다. 표준 입력으로 전달되는 내용은 "
        f"사용자가 {date_str} 하루 동안 적은 원천 기록(today.md)입니다.\n\n"
        f"이 기록을 바탕으로 오늘({date_str})의 일간 스니펫을 작성하십시오. "
        f"6번 항목(Tomorrow)은 '내일 할 일' 관점으로 작성합니다.\n\n{_FORMAT_SPEC}"
    )
    raw = run_claude(instruction, stdin_text=today_text, logger=logger)
    snippet = extract_snippet(raw)
    if not snippet:
        raise ClaudeError("생성된 스니펫이 비어 있습니다")
    if logger and "what" not in snippet.lower():
        logger.warning("생성 결과에 7항목 형식이 보이지 않습니다 — 내용을 확인하세요")
    return snippet


def generate_weekly_snippet(weekly_source: str, week_label: str, *,
                            logger: logging.Logger | None = None) -> str:
    """한 주의 일간 스니펫 모음으로 주간 요약 스니펫을 생성한다 (§8-2)."""
    instruction = (
        f"당신은 팀 스니펫 작성 도우미입니다. 표준 입력으로 전달되는 내용은 "
        f"{week_label} 한 주 동안의 일간 스니펫(또는 일간 기록) 모음입니다.\n\n"
        f"이를 요약해 주간 스니펫을 작성하십시오. 일간과 동일한 7항목 틀을 주간 관점으로 "
        f"작성합니다: 한 주의 핵심 성과 요약(what/why/value), 주간 하이라이트/로우라이트, "
        f"다음 주 계획(Tomorrow 항목은 '다음 주 할 일'로), 주간 소감.\n\n{_FORMAT_SPEC}"
    )
    raw = run_claude(instruction, stdin_text=weekly_source, logger=logger)
    snippet = extract_snippet(raw)
    if not snippet:
        raise ClaudeError("생성된 스니펫이 비어 있습니다")
    return snippet
