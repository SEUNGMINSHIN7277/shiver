"""claude -p 서브프로세스 호출로 스니펫을 생성한다 (§5).

Anthropic API 키를 사용하지 않는다. 이 PC에 설치·로그인된 Claude Code의
헤드리스 모드(claude -p --output-format text)를 서브프로세스로 호출해
구독 사용량으로 처리한다(추가 과금 없음).

프롬프트 전문(지시문+원천 자료)은 **stdin으로만** 전달한다. 명령줄 인자에
개행이 들어가면 npm .cmd 셔틀 경유 시 cmd.exe가 개행을 명령 구분자로
해석해 프롬프트가 깨지기 때문이다(BatBadBut/CVE-2024-24576과 동일 계열).
claude -p는 위치 인자가 없으면 stdin을 프롬프트로 읽는다.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

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
    """claude 실행 파일의 절대경로를 찾는다.

    npm 전역 설치의 .cmd 셔틀이 잡히면, 같은 위치의 네이티브 claude.exe를
    우선 사용한다 — cmd.exe를 거치지 않아 타임아웃 시 프로세스 정리가 확실하고
    인자 처리도 안전하다.
    """
    path = shutil.which("claude")
    if not path and sys.platform == "win32":
        # PATH 문제로 못 찾으면 where 로 재탐색
        try:
            result = subprocess.run(["where", "claude"], capture_output=True,
                                    text=True, timeout=10)
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if line:
                        path = line
                        break
        except Exception:
            pass
    if not path:
        raise ClaudeError(
            "claude 명령을 찾을 수 없습니다. Claude Code가 설치되어 있는지, "
            "PATH에 등록되어 있는지 확인하세요 (where claude)."
        )
    if path.lower().endswith((".cmd", ".bat")):
        native = (Path(path).parent / "node_modules" / "@anthropic-ai"
                  / "claude-code" / "bin" / "claude.exe")
        if native.exists():
            return str(native)
    return path


def run_claude(prompt: str, *,
               timeout: int = config.CLAUDE_TIMEOUT_SECONDS,
               logger: logging.Logger | None = None) -> str:
    """claude -p --output-format text 를 호출한다. 프롬프트 전문은 stdin으로 전달.

    - ANTHROPIC_API_KEY는 자식 프로세스 환경에서 항상 제거한다(과금 방지, §4).
    - 실패 시 3회 재시도(2s/4s/8s). 인증·한도 오류(ClaudeAuthError)는 즉시 중단.
    """
    claude_path = find_claude()
    cmd = [claude_path, "-p", "--output-format", "text"]
    # 네이티브 exe를 못 찾은 .cmd/.bat 폴백 — 인자에 개행이 없으므로 안전하다.
    # (단, 이 경로에서는 타임아웃 시 손자 프로세스가 남을 수 있다)
    if claude_path.lower().endswith((".cmd", ".bat")):
        cmd = ["cmd", "/c", *cmd]

    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)
    env.pop("ANTHROPIC_AUTH_TOKEN", None)

    def _call() -> str:
        proc = subprocess.run(
            cmd, input=prompt,
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
        # 성공 종료인데 짧은 오류성 문구만 있는 경우(마커 없음)만 인증 오류로 본다.
        # 긴 정상 스니펫에 'rate limit' 같은 용어가 들어가는 오탐을 막기 위한 조건.
        if (len(output) < 300 and SNIPPET_START not in output
                and _looks_like_auth_error(output)):
            raise ClaudeAuthError(f"claude 인증/한도 관련 응답: {output[:500]}")
        return output

    return config.with_retries(_call, desc="claude 호출", logger=logger,
                               fatal=(ClaudeAuthError,))


def extract_snippet(raw: str) -> str:
    """claude 출력에서 스니펫 본문만 추출한다(앞뒤 불필요 문구 제거, §5)."""
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

_SOURCE_DELIMITER = "\n\n========== 아래는 원천 자료 ==========\n\n"


def generate_daily_snippet(source_text: str, date_str: str, *,
                           logger: logging.Logger | None = None) -> str:
    """하루 활동 원천 자료(메모·Claude 대화 기록)로 일간 스니펫을 생성한다 (§7-2)."""
    instruction = (
        f"당신은 팀 스니펫 작성 도우미입니다. 구분선 아래는 사용자의 {date_str} "
        f"하루 활동 원천 자료입니다 — 사용자 메모(today.md), 그리고/또는 사용자가 "
        f"오늘 Claude와 나눈 대화 기록입니다.\n\n"
        f"대화 기록이 포함된 경우: 대화를 그대로 옮기지 말고, 대화에서 사용자가 실제로 "
        f"수행한 작업·목적·진행 결과를 파악해 사용자 1인칭 관점으로 정리하십시오.\n\n"
        f"이 자료를 바탕으로 오늘({date_str})의 일간 스니펫을 작성하십시오. "
        f"6번 항목(Tomorrow)은 '내일 할 일' 관점으로 작성합니다.\n\n{_FORMAT_SPEC}"
    )
    raw = run_claude(instruction + _SOURCE_DELIMITER + source_text, logger=logger)
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
        f"당신은 팀 스니펫 작성 도우미입니다. 구분선 아래는 {week_label} 한 주 동안의 "
        f"일간 스니펫(또는 일간 기록) 모음입니다.\n\n"
        f"이를 요약해 주간 스니펫을 작성하십시오. 일간과 동일한 7항목 틀을 주간 관점으로 "
        f"작성합니다: 한 주의 핵심 성과 요약(what/why/value), 주간 하이라이트/로우라이트, "
        f"다음 주 계획(Tomorrow 항목은 '다음 주 할 일'로), 주간 소감.\n\n{_FORMAT_SPEC}"
    )
    raw = run_claude(instruction + _SOURCE_DELIMITER + weekly_source, logger=logger)
    snippet = extract_snippet(raw)
    if not snippet:
        raise ClaudeError("생성된 스니펫이 비어 있습니다")
    return snippet
