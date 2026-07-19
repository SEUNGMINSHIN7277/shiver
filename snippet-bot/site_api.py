"""스니펫 사이트("1000") API 클라이언트 — Network 캡처 기반 구현 (§6).

2026-07-19 사용자 브라우저 캡처로 확인된 사실:
  - API 베이스: https://api.1000.school (웹앱은 app.1000.school)
  - 일간 데이터 조회: GET /daily-snippets/page-data
  - 일간 저장:       PUT /daily-snippets/{id}  본문 {"content": "<마크다운>"}
                     → 스니펫 레코드가 이미 존재하고 그 id에 PUT하는 구조
  - AI 채점:         GET /daily-snippets/feedback?stream=1 (SSE, text/event-stream)
  - 브라우저 인증:   session 쿠키 + 쓰기 요청에 x-csrf-token (GET /auth/csrf 발급)
  - 사이트에 API 토큰 기능 존재(설정 → API, /auth/tokens) → 발급 토큰은 Bearer로 시도

⚠️ 라이브 검증 필요(원격 개발 환경에서 api.1000.school 접속이 차단되어 미확인):
  - 발급형 API 토큰의 Bearer 인증 수락 여부
    (거부되면 쿠키 모드: .env에 SNIPPET_SITE_SESSION=<session 쿠키 값> 설정)
  - page-data 응답 JSON의 정확한 구조 — 스니펫 id 탐색은 휴리스틱이며,
    실패 시 원본 응답을 logs/에 저장하고 중단한다 (§10)
  - weekly-snippets 계열 엔드포인트(일간과 대칭이라고 가정)
사용자 PC에서 `python scripts\\test_site_api.py check` 로 검증한다.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import requests

import config

DEFAULT_BASE_URL = "https://api.1000.school"
# SSE 채점 스트림은 청크 사이 간격이 길 수 있어 읽기 타임아웃을 넉넉히 준다
SSE_READ_TIMEOUT_SECONDS = 180

_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


class SiteApiError(RuntimeError):
    """사이트 API 호출 실패."""


class SiteApiAuthError(SiteApiError):
    """401/403 — 토큰/세션 만료 등 재시도로 해결되지 않는 인증 오류."""


class SiteApiNotImplemented(SiteApiError):
    """아직 확인되지 않은 엔드포인트에 대한 자리표시자 오류."""


class UnexpectedResponse(SiteApiError):
    """응답이 예상 형식과 다름 — 원본을 logs/에 저장하고 중단한다 (§10)."""


def _base_url() -> str:
    return (config.SITE_BASE_URL or DEFAULT_BASE_URL).rstrip("/")


def _session() -> requests.Session:
    """인증이 설정된 세션을 만든다.

    1순위: 발급형 API 토큰(Bearer). 2순위(토큰이 거부될 때): 브라우저 session 쿠키.
    쿠키 모드에서는 쓰기 요청 전에 _csrf_token()으로 x-csrf-token을 받아 붙인다.
    """
    if not config.SITE_TOKEN and not config.SITE_SESSION:
        raise SiteApiError(
            ".env에 SNIPPET_SITE_TOKEN(권장) 또는 SNIPPET_SITE_SESSION이 필요합니다"
        )
    session = requests.Session()
    session.headers["accept"] = "application/json"
    if config.SITE_SESSION:
        session.cookies.set("session", config.SITE_SESSION)
    else:
        session.headers["Authorization"] = f"Bearer {config.SITE_TOKEN}"
    return session


def _csrf_headers(session: requests.Session,
                  logger: logging.Logger | None = None) -> dict:
    """쿠키 모드일 때만 GET /auth/csrf 로 토큰을 받아 x-csrf-token 헤더를 만든다."""
    if not config.SITE_SESSION:
        return {}
    resp = session.get(f"{_base_url()}/auth/csrf",
                       timeout=config.HTTP_TIMEOUT_SECONDS)
    resp.raise_for_status()
    try:
        data = resp.json()
    except ValueError as exc:
        raise UnexpectedResponse(f"/auth/csrf 응답이 JSON이 아닙니다: {resp.text[:200]}") from exc
    token = data.get("csrf_token") or data.get("token") or data.get("csrf")
    if not token:
        raise UnexpectedResponse(f"/auth/csrf 응답에서 토큰을 찾지 못했습니다: {list(data)}")
    return {"x-csrf-token": token}


def _request(method: str, path: str, *, json_body=None, params=None,
             extra_headers: dict | None = None, stream: bool = False,
             logger: logging.Logger | None = None) -> requests.Response:
    """공통 요청 래퍼: 3회 재시도(§10), 401/403은 즉시 인증 오류로 중단."""
    session = _session()
    headers = dict(extra_headers or {})
    if method.upper() in ("POST", "PUT", "PATCH", "DELETE"):
        headers.update(_csrf_headers(session, logger))
    url = f"{_base_url()}{path}"
    timeout = (config.HTTP_TIMEOUT_SECONDS,
               SSE_READ_TIMEOUT_SECONDS if stream else config.HTTP_TIMEOUT_SECONDS)

    def _do() -> requests.Response:
        resp = session.request(method, url, json=json_body, params=params,
                               headers=headers, timeout=timeout, stream=stream)
        if resp.status_code in (401, 403):
            raise SiteApiAuthError(
                f"{method} {path} 인증 실패({resp.status_code}) — 토큰/세션이 유효한지 "
                f"확인하세요: {resp.text[:200]}"
            )
        resp.raise_for_status()
        return resp

    return config.with_retries(_do, desc=f"{method} {path}", logger=logger,
                               fatal=(SiteApiAuthError, UnexpectedResponse))


def _dump_unexpected(name: str, payload, logger: logging.Logger | None) -> Path:
    """예상과 다른 응답의 원본을 logs/에 저장한다 (§10)."""
    config.RUN_LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = config.RUN_LOG_DIR / f"unexpected_{name}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
    if logger:
        logger.error("예상과 다른 응답 — 원본을 저장했습니다: %s", path)
    return path


def _iter_dicts(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _iter_dicts(value)
    elif isinstance(node, list):
        for value in node:
            yield from _iter_dicts(value)


def _find_snippet_id_for_date(page_data, date_str: str):
    """page-data JSON에서 date_str(YYYY-MM-DD)에 해당하는 스니펫 id를 찾는다.

    구조를 모르는 상태의 휴리스틱: id 키가 있고 값 중에 날짜 문자열을 포함하는 dict를
    후보로 모은 뒤, content 키까지 가진 후보를 우선한다. 유일하게 특정되지 않으면 None.
    """
    candidates = []
    for d in _iter_dicts(page_data):
        if "id" not in d:
            continue
        if any(isinstance(v, str) and date_str in v for v in d.values()):
            candidates.append(d)
    preferred = [d for d in candidates if "content" in d]
    pool = preferred or candidates
    ids = {d["id"] for d in pool}
    if len(ids) == 1:
        return pool[0]["id"]
    return None


def _extract_date(item: dict) -> str | None:
    for value in item.values():
        if isinstance(value, str):
            match = _DATE_RE.search(value)
            if match:
                return match.group(0)
    return None


# --- 공개 API ---------------------------------------------------------------

def check_auth(*, logger: logging.Logger | None = None) -> dict:
    """GET /auth/me — 인증이 동작하는지 확인한다 (검증 스크립트용)."""
    resp = _request("GET", "/auth/me", logger=logger)
    try:
        return resp.json()
    except ValueError as exc:
        raise UnexpectedResponse(f"/auth/me 응답이 JSON이 아닙니다: {resp.text[:200]}") from exc


def get_page_data(kind: str = "daily", *, logger: logging.Logger | None = None) -> dict:
    """GET /{kind}-snippets/page-data — 스니펫 목록·id가 담긴 페이지 데이터."""
    resp = _request("GET", f"/{kind}-snippets/page-data", logger=logger)
    try:
        return resp.json()
    except ValueError as exc:
        raise UnexpectedResponse(
            f"/{kind}-snippets/page-data 응답이 JSON이 아닙니다: {resp.text[:200]}"
        ) from exc


def post_daily_snippet(date: str, content: str, *,
                       logger: logging.Logger | None = None) -> str:
    """일간 스니펫 저장: page-data에서 해당 날짜의 id를 찾아 PUT. 반환: snippet_id."""
    page = get_page_data("daily", logger=logger)
    snippet_id = _find_snippet_id_for_date(page, date)
    if snippet_id is None:
        dump = _dump_unexpected("daily_page_data", page, logger)
        raise UnexpectedResponse(
            f"page-data에서 {date}의 스니펫 id를 특정하지 못했습니다. "
            f"원본 응답({dump})을 확인/공유해 주세요."
        )
    _request("PUT", f"/daily-snippets/{snippet_id}",
             json_body={"content": content}, logger=logger)
    if logger:
        logger.info("일간 스니펫 저장 완료: PUT /daily-snippets/%s", snippet_id)
    return str(snippet_id)


def post_weekly_snippet(week_range: str, content: str, *,
                        logger: logging.Logger | None = None) -> str:
    """주간 스니펫 저장 — 일간과 대칭 구조라고 가정(라이브 검증 필요).

    week_range 예: "2026-07-13 ~ 2026-07-19". 주간 page-data에서 주 시작일(월) →
    종료일(일) 순으로 id를 찾는다.
    """
    dates = _DATE_RE.findall(week_range)
    if not dates:
        raise ValueError(f"week_range에서 날짜를 찾지 못했습니다: {week_range!r}")
    page = get_page_data("weekly", logger=logger)
    snippet_id = None
    for target in dates:
        snippet_id = _find_snippet_id_for_date(page, target)
        if snippet_id is not None:
            break
    if snippet_id is None:
        dump = _dump_unexpected("weekly_page_data", page, logger)
        raise UnexpectedResponse(
            f"weekly page-data에서 {week_range}의 스니펫 id를 특정하지 못했습니다. "
            f"원본 응답({dump})을 확인/공유해 주세요."
        )
    _request("PUT", f"/weekly-snippets/{snippet_id}",
             json_body={"content": content}, logger=logger)
    if logger:
        logger.info("주간 스니펫 저장 완료: PUT /weekly-snippets/%s", snippet_id)
    return str(snippet_id)


def run_ai_grading(snippet_id: str, *, kind: str = "daily",
                   logger: logging.Logger | None = None) -> dict:
    """AI 채점 실행: GET /{kind}-snippets/feedback?stream=1 (SSE) 스트림을 끝까지 수신.

    캡처상 URL에 스니펫 id가 없다 — 로그인 사용자의 현재(오늘/이번 주) 스니펫을
    채점하는 것으로 보인다. snippet_id는 결과 기록용으로만 사용한다.
    """
    resp = _request("GET", f"/{kind}-snippets/feedback", params={"stream": "1"},
                    extra_headers={"accept": "text/event-stream"},
                    stream=True, logger=logger)
    resp.encoding = "utf-8"
    chunks = []
    try:
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            if line.startswith("data:"):
                data = line[len("data:"):].strip()
                if data == "[DONE]":
                    break
                chunks.append(data)
    finally:
        resp.close()
    if not chunks:
        raise UnexpectedResponse("AI 채점 스트림에서 데이터를 받지 못했습니다")
    feedback = "\n".join(chunks)
    if logger:
        logger.info("AI 채점 수신 완료 (%d개 이벤트, %d자)", len(chunks), len(feedback))
    return {"snippet_id": str(snippet_id), "feedback": feedback}


def get_daily_snippets(start_date: str, end_date: str, *,
                       logger: logging.Logger | None = None) -> list:
    """기간(YYYY-MM-DD ~ YYYY-MM-DD) 내 일간 스니펫 목록 (주간 자료원, §8-1).

    page-data에서 id·content를 가진 dict를 날짜로 걸러 반환한다.
    구조가 예상과 다르면 빈 리스트를 반환하고 weekly.py가 log/archive/로 폴백한다.
    """
    page = get_page_data("daily", logger=logger)
    items = []
    for d in _iter_dicts(page):
        if "id" not in d or "content" not in d:
            continue
        item_date = _extract_date(d)
        if item_date and start_date <= item_date <= end_date:
            items.append(d)
    if not items and logger:
        logger.warning("page-data에서 %s~%s 일간 스니펫을 찾지 못했습니다 — "
                       "archive 폴백 예정", start_date, end_date)
    return items
