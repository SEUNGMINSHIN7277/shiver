"""스니펫 사이트("1000") API 클라이언트 — ⚠️ 리버스 엔지니어링 대기 중 (§6).

사이트에 공식 API 문서가 없으므로, 브라우저 로그인 → F12 개발자도구 → Network 탭에서
아래 4가지 동작의 요청을 캡처한 뒤 실제 구현으로 교체한다. 각 요청에서 필요한 정보:
URL, HTTP 메서드, 요청 헤더의 인증 방식(Bearer 토큰 vs 쿠키/세션), 페이로드 JSON 구조,
응답 JSON 구조.

  a. 일간 스니펫 "저장하기" 클릭   → post_daily_snippet
  b. "AI 채점" 클릭               → run_ai_grading
  c. 주간 스니펫 저장             → post_weekly_snippet
  d. 일간 스니펫 목록/상세 조회   → get_daily_snippets

인증이 세션(쿠키) 방식이면 만료 시 갱신 방법도 함께 파악해 반영한다.
캡처를 받기 전까지 모든 함수는 SiteApiNotImplemented를 던진다.
"""
from __future__ import annotations

import logging

import requests

import config


class SiteApiError(RuntimeError):
    """사이트 API 호출 실패."""


class SiteApiNotImplemented(SiteApiError):
    """Network 캡처 수령 전까지의 자리표시자 오류."""


class UnexpectedResponse(SiteApiError):
    """응답이 예상 형식과 다름 — 원본 응답을 로그에 남기고 중단한다 (§10)."""


_NOT_IMPLEMENTED_MSG = (
    "site_api 미구현: 사이트 Network 탭 캡처(개발명세서 §6)를 받은 뒤 구현됩니다. "
    "그 전까지는 --dry-run 으로 스니펫 생성만 확인하세요."
)


def _session() -> requests.Session:
    """공통 세션. 인증 방식(Bearer/쿠키)이 확정되면 완성한다."""
    if not config.SITE_BASE_URL:
        raise SiteApiError(".env의 SNIPPET_SITE_BASE_URL이 비어 있습니다")
    if not config.SITE_TOKEN:
        raise SiteApiError(".env의 SNIPPET_SITE_TOKEN이 비어 있습니다 (재발급받은 새 토큰 필요)")
    session = requests.Session()
    # TODO(캡처 후): 실제 인증 방식으로 교체 — Bearer 헤더인지, 쿠키/세션인지 확인
    session.headers["Authorization"] = f"Bearer {config.SITE_TOKEN}"
    return session


def post_daily_snippet(date: str, content: str, *,
                       logger: logging.Logger | None = None) -> str:
    """일간 스니펫 업로드. 반환: snippet_id.

    TODO(캡처 a — 일간 스니펫 "저장하기"):
      - method/URL: 예) POST {base}/api/...
      - payload: 예) {"date": ..., "content": ...} 실제 필드명으로 교체
      - 응답에서 snippet_id 추출. 형식이 다르면 UnexpectedResponse로 원본 로그 후 중단.
      - 호출은 config.with_retries(...)로 감싸 3회 재시도(§10).
    """
    raise SiteApiNotImplemented(_NOT_IMPLEMENTED_MSG)


def post_weekly_snippet(week_range: str, content: str, *,
                        logger: logging.Logger | None = None) -> str:
    """주간 스니펫 업로드. 반환: snippet_id.

    TODO(캡처 c — 주간 스니펫 저장): 일간과 엔드포인트/페이로드가 어떻게 다른지 확인 후 구현.
    """
    raise SiteApiNotImplemented(_NOT_IMPLEMENTED_MSG)


def run_ai_grading(snippet_id: str, *,
                   logger: logging.Logger | None = None) -> dict:
    """업로드된 스니펫에 대해 사이트의 AI 채점을 실행하고 결과를 반환한다.

    TODO(캡처 b — "AI 채점" 클릭): 채점이 비동기(폴링 필요)인지 동기 응답인지 확인 후 구현.
    """
    raise SiteApiNotImplemented(_NOT_IMPLEMENTED_MSG)


def get_daily_snippets(start_date: str, end_date: str, *,
                       logger: logging.Logger | None = None) -> list:
    """기간 내 일간 스니펫 목록 조회 (주간 파이프라인 1순위 자료원, §8-1).

    TODO(캡처 d — 목록/상세 조회 GET): 조회 API가 없으면 이 함수는
    SiteApiNotImplemented를 유지하고, weekly.py가 log/archive/ 폴백을 사용한다.
    """
    raise SiteApiNotImplemented(_NOT_IMPLEMENTED_MSG)
