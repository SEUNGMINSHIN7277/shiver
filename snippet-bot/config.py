"""snippet-bot 공통 설정·유틸리티.

모든 경로는 이 파일의 위치를 기준으로 계산하므로, C:\\snippet-bot 외의 위치에
클론/복사해도 그대로 동작한다.
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv 미설치 환경에서도 임포트 자체는 가능하게
    load_dotenv = None

BASE_DIR = Path(__file__).resolve().parent

# 사용자가 하루 기록을 적는 곳
LOG_INPUT_DIR = BASE_DIR / "log"
TODAY_MD = LOG_INPUT_DIR / "today.md"
# 처리 완료된 기록 보관 (YYYY-MM-DD.md)
ARCHIVE_DIR = LOG_INPUT_DIR / "archive"
# 파이프라인 실행 로그
RUN_LOG_DIR = BASE_DIR / "logs"

ENV_PATH = BASE_DIR / ".env"
if load_dotenv is not None:
    load_dotenv(ENV_PATH)

SITE_TOKEN = os.getenv("SNIPPET_SITE_TOKEN", "")
SITE_BASE_URL = os.getenv("SNIPPET_SITE_BASE_URL", "").rstrip("/")

# claude -p 호출 타임아웃(초) — 개발명세서 §5
CLAUDE_TIMEOUT_SECONDS = 180
# 모든 API·claude 호출 공통: 실패 시 3회 재시도(지수 백오프 2s/4s/8s) — §10
RETRY_COUNT = 3
BACKOFF_BASE_SECONDS = 2
HTTP_TIMEOUT_SECONDS = 30


def mask_secret(text: str) -> str:
    """로그에 사이트 토큰이 노출되지 않도록 마스킹한다 — §11."""
    if not text:
        return text
    if SITE_TOKEN:
        text = text.replace(SITE_TOKEN, "***TOKEN***")
    return text


class _SecretMaskFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = mask_secret(str(record.msg))
        if record.args:
            record.args = tuple(
                mask_secret(a) if isinstance(a, str) else a for a in record.args
            )
        return True


def setup_logging(log_filename: str) -> logging.Logger:
    """logs/<log_filename> 파일 + 콘솔에 동시 기록하는 로거를 만든다."""
    RUN_LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(f"snippet-bot.{log_filename}")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    file_handler = logging.FileHandler(RUN_LOG_DIR / log_filename, encoding="utf-8")
    stream_handler = logging.StreamHandler()
    for handler in (file_handler, stream_handler):
        handler.setFormatter(fmt)
        handler.addFilter(_SecretMaskFilter())
        logger.addHandler(handler)
    return logger


def strip_anthropic_api_key(logger: logging.Logger | None = None) -> bool:
    """ANTHROPIC_API_KEY가 설정되어 있으면 경고 후 현재 프로세스 환경에서 제거한다.

    이 변수가 있으면 Claude Code가 구독 대신 API 과금으로 전환되므로(§4),
    파이프라인 시작 시 반드시 제거하고 진행한다. 제거했으면 True를 반환한다.
    """
    if "ANTHROPIC_API_KEY" in os.environ:
        if logger:
            logger.warning(
                "ANTHROPIC_API_KEY 환경변수가 설정되어 있습니다. 구독 대신 API 과금으로 "
                "전환되는 것을 막기 위해 이 프로세스에서 제거하고 진행합니다. "
                "시스템 환경변수에서도 삭제하는 것을 권장합니다."
            )
        del os.environ["ANTHROPIC_API_KEY"]
        return True
    return False


def with_retries(func, *, desc: str = "작업", logger: logging.Logger | None = None,
                 attempts: int | None = None, base_delay: float | None = None,
                 fatal: tuple[type[BaseException], ...] = ()):
    """func()를 최대 attempts회 시도한다(기본: 최초 1회 + 재시도 3회, 백오프 2s/4s/8s).

    fatal에 해당하는 예외(인증 만료 등 재시도로 해결되지 않는 오류)는 즉시 전파한다.
    """
    attempts = attempts or (RETRY_COUNT + 1)
    base_delay = base_delay if base_delay is not None else BACKOFF_BASE_SECONDS
    for attempt in range(1, attempts + 1):
        try:
            return func()
        except fatal:
            raise
        except Exception as exc:
            if attempt == attempts:
                raise
            delay = base_delay * (2 ** (attempt - 1))
            if logger:
                logger.warning("%s 실패(%d/%d): %s — %s초 후 재시도",
                               desc, attempt, attempts, exc, delay)
            time.sleep(delay)
