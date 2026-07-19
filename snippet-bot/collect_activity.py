"""오늘의 Claude Code 대화 기록 자동 수집 — "사용자 개입 0" 자동화의 원천 자료.

Claude Code는 로컬 대화 내역을 %USERPROFILE%\\.claude\\projects\\<프로젝트>\\*.jsonl
에 세션 단위로 저장한다. 이 모듈은 지정 날짜(로컬 시간 기준)에 오간 사용자↔Claude
메시지를 모아 스니펫 생성용 텍스트로 정리한다.

한계(정직하게): claude.ai 웹/모바일에서의 대화는 PC에 저장되지 않으므로 수집할 수
없다. 로컬 Claude Code(CLI/IDE 확장)에서 작업한 대화만 수집된다.
"""
from __future__ import annotations

import json
import logging
from datetime import date as date_cls, datetime
from pathlib import Path

CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"

# claude -p 입력 컨텍스트 보호용 상한
MAX_TOTAL_CHARS = 60_000
MAX_USER_MSG_CHARS = 1_500
MAX_ASSISTANT_MSG_CHARS = 700

# 대화가 아닌 메타/시스템성 텍스트는 제외
_SKIP_PREFIXES = ("Caveat:", "<command-name>", "<local-command", "<system-reminder>",
                  "<task-notification>")


def _extract_text(content) -> str:
    """message.content(문자열 또는 블록 리스트)에서 순수 텍스트만 추출한다.

    tool_use/tool_result 블록은 버린다 — 도구 출력이 아니라 대화 흐름만 필요하다.
    """
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = str(block.get("text", "")).strip()
                if text:
                    parts.append(text)
        return "\n".join(parts)
    return ""


def _entry_local_dt(entry: dict) -> datetime | None:
    ts = entry.get("timestamp")
    if not isinstance(ts, str):
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.astimezone()  # 저장은 UTC — 로컬 시간대로 변환해 날짜를 판정한다


def _iter_day_messages(jsonl_path: Path, target_date: date_cls):
    """세션 JSONL에서 target_date(로컬)의 (시각, 역할, 텍스트)를 시간순으로 낸다."""
    with jsonl_path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if entry.get("type") not in ("user", "assistant"):
                continue
            if entry.get("isSidechain"):
                continue  # 서브에이전트 대화는 잡음이 많아 제외
            dt = _entry_local_dt(entry)
            if dt is None or dt.date() != target_date:
                continue
            message = entry.get("message") or {}
            text = _extract_text(message.get("content"))
            if not text or text.startswith(_SKIP_PREFIXES):
                continue
            yield dt, entry["type"], text


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + " …(생략)"


def collect_today_conversations(target_date: date_cls, *,
                                projects_dir: Path | None = None,
                                max_total_chars: int = MAX_TOTAL_CHARS,
                                logger: logging.Logger | None = None) -> str | None:
    """target_date의 로컬 Claude Code 대화를 프로젝트별로 모아 하나의 텍스트로 만든다.

    대화가 전혀 없으면 None. 분량이 상한을 넘으면 가운데를 잘라낸다.
    """
    root = projects_dir if projects_dir is not None else CLAUDE_PROJECTS_DIR
    if not root.is_dir():
        if logger:
            logger.info("Claude 대화 저장소가 없습니다: %s", root)
        return None

    projects: dict[str, list] = {}
    scanned = 0
    for jsonl_path in root.glob("*/*.jsonl"):
        try:
            mtime_date = datetime.fromtimestamp(jsonl_path.stat().st_mtime).date()
            if mtime_date < target_date:
                continue  # 파일 전체가 대상 날짜 이전 — 열 필요 없음
            scanned += 1
            for item in _iter_day_messages(jsonl_path, target_date):
                projects.setdefault(jsonl_path.parent.name, []).append(item)
        except OSError as exc:
            if logger:
                logger.warning("대화 파일 읽기 실패(무시): %s — %s", jsonl_path, exc)

    if not projects:
        if logger:
            logger.info("%s의 Claude 대화가 없습니다 (세션 파일 %d개 확인)",
                        target_date.isoformat(), scanned)
        return None

    sections = []
    for project, messages in sorted(projects.items()):
        messages.sort(key=lambda m: m[0])
        lines = [f"### 프로젝트: {project}"]
        for dt, role, text in messages:
            if role == "user":
                lines.append(f"[{dt:%H:%M}] 사용자: {_clip(text, MAX_USER_MSG_CHARS)}")
            else:
                lines.append(f"[{dt:%H:%M}] Claude: {_clip(text, MAX_ASSISTANT_MSG_CHARS)}")
        sections.append("\n".join(lines))

    combined = "\n\n".join(sections)
    if len(combined) > max_total_chars:
        half = max_total_chars // 2
        combined = (combined[:half].rstrip()
                    + "\n\n…(중략: 분량 제한으로 중간 대화 생략)…\n\n"
                    + combined[-half:].lstrip())
    if logger:
        message_count = sum(len(m) for m in projects.values())
        logger.info("Claude 대화 수집: 프로젝트 %d개, 메시지 %d개, %d자",
                    len(projects), message_count, len(combined))
    return combined
