import time
from types import SimpleNamespace

import pytest

import config
import site_api


# 캡처된 실제 구조를 모사한 가상의 page-data
PAGE_DATA = {
    "user": {"id": 7, "name": "홍길동", "joined": "2025-03-02T10:00:00"},
    "snippets": [
        {"id": 6021, "date": "2026-07-18", "content": "어제 스니펫"},
        {"id": 6022, "date": "2026-07-19", "content": "오늘 스니펫"},
    ],
    "stats": {"id": 1, "updated_at": "2026-07-19T09:00:00"},
}


# --- id 탐색 휴리스틱 -------------------------------------------------------

def test_find_id_prefers_content_dict():
    # stats dict도 2026-07-19를 포함하지만 content 키가 있는 스니펫 dict가 우선
    assert site_api._find_snippet_id_for_date(PAGE_DATA, "2026-07-19") == 6022
    assert site_api._find_snippet_id_for_date(PAGE_DATA, "2026-07-18") == 6021


def test_find_id_none_when_absent():
    assert site_api._find_snippet_id_for_date(PAGE_DATA, "2026-07-01") is None


def test_find_id_none_when_ambiguous():
    data = {"a": [{"id": 1, "date": "2026-07-19", "content": "x"},
                  {"id": 2, "date": "2026-07-19", "content": "y"}]}
    assert site_api._find_snippet_id_for_date(data, "2026-07-19") is None


# --- post_daily_snippet ----------------------------------------------------

def test_post_daily_snippet_puts_to_found_id(monkeypatch):
    calls = []
    monkeypatch.setattr(site_api, "get_page_data",
                        lambda kind, logger=None: PAGE_DATA)

    def fake_request(method, path, **kwargs):
        calls.append((method, path, kwargs.get("json_body")))
        return SimpleNamespace(status_code=200)

    monkeypatch.setattr(site_api, "_request", fake_request)
    snippet_id = site_api.post_daily_snippet("2026-07-19", "새 내용")
    assert snippet_id == "6022"
    assert calls == [("PUT", "/daily-snippets/6022", {"content": "새 내용"})]


def test_post_daily_snippet_unexpected_dumps(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RUN_LOG_DIR", tmp_path)
    monkeypatch.setattr(site_api, "get_page_data",
                        lambda kind, logger=None: {"nothing": True})
    with pytest.raises(site_api.UnexpectedResponse):
        site_api.post_daily_snippet("2026-07-19", "내용")
    assert (tmp_path / "unexpected_daily_page_data.json").exists()


def test_post_weekly_snippet_tries_monday_then_sunday(monkeypatch):
    weekly_page = {"snippets": [{"id": 88, "week_end": "2026-07-19", "content": "w"}]}
    calls = []
    monkeypatch.setattr(site_api, "get_page_data",
                        lambda kind, logger=None: weekly_page)
    monkeypatch.setattr(site_api, "_request",
                        lambda m, p, **kw: calls.append((m, p)) or SimpleNamespace())
    snippet_id = site_api.post_weekly_snippet("2026-07-13 ~ 2026-07-19", "주간")
    assert snippet_id == "88"
    assert calls == [("PUT", "/weekly-snippets/88")]


# --- run_ai_grading (SSE) --------------------------------------------------

class FakeStreamResponse:
    def __init__(self, lines):
        self._lines = lines
        self.closed = False
        self.encoding = None

    def iter_lines(self, decode_unicode=True):
        yield from self._lines

    def close(self):
        self.closed = True


def test_run_ai_grading_collects_sse(monkeypatch):
    fake = FakeStreamResponse([
        "event: message", "data: 점수는", "", "data: 5점입니다", "data: [DONE]",
        "data: 이후는 무시",
    ])
    monkeypatch.setattr(site_api, "_request", lambda *a, **kw: fake)
    result = site_api.run_ai_grading("6022")
    assert result["snippet_id"] == "6022"
    assert result["feedback"] == "점수는\n5점입니다"
    assert fake.closed


def test_run_ai_grading_empty_stream_raises(monkeypatch):
    fake = FakeStreamResponse(["event: ping", ""])
    monkeypatch.setattr(site_api, "_request", lambda *a, **kw: fake)
    with pytest.raises(site_api.UnexpectedResponse):
        site_api.run_ai_grading("6022")


# --- get_daily_snippets ----------------------------------------------------

def test_get_daily_snippets_filters_range(monkeypatch):
    monkeypatch.setattr(site_api, "get_page_data",
                        lambda kind, logger=None: PAGE_DATA)
    items = site_api.get_daily_snippets("2026-07-13", "2026-07-18")
    assert [i["id"] for i in items] == [6021]
    items = site_api.get_daily_snippets("2026-07-13", "2026-07-19")
    assert [i["id"] for i in items] == [6021, 6022]


def test_get_daily_snippets_empty_on_unknown_shape(monkeypatch):
    monkeypatch.setattr(site_api, "get_page_data",
                        lambda kind, logger=None: {"foo": "bar"})
    assert site_api.get_daily_snippets("2026-07-13", "2026-07-19") == []


# --- _request 인증/재시도 ---------------------------------------------------

def _fake_session_returning(status_code, text="err"):
    def fake_request(method, url, **kwargs):
        return SimpleNamespace(
            status_code=status_code, text=text,
            raise_for_status=lambda: (_ for _ in ()).throw(
                site_api.requests.HTTPError(f"{status_code}")
            ) if status_code >= 400 else None,
        )
    session = SimpleNamespace(request=fake_request,
                              headers={}, cookies=None)
    return session


def test_request_auth_error_no_retry(monkeypatch):
    monkeypatch.setattr(config, "SITE_TOKEN", "tok")
    monkeypatch.setattr(config, "SITE_SESSION", "")
    monkeypatch.setattr(time, "sleep", lambda s: None)
    calls = {"n": 0}

    def fake_request(method, url, **kwargs):
        calls["n"] += 1
        return SimpleNamespace(status_code=401, text="unauthorized")

    monkeypatch.setattr(site_api, "_session",
                        lambda: SimpleNamespace(request=fake_request))
    with pytest.raises(site_api.SiteApiAuthError):
        site_api._request("GET", "/auth/me")
    assert calls["n"] == 1  # 인증 오류는 재시도하지 않는다


def test_request_retries_server_error(monkeypatch):
    monkeypatch.setattr(config, "SITE_TOKEN", "tok")
    monkeypatch.setattr(config, "SITE_SESSION", "")
    monkeypatch.setattr(time, "sleep", lambda s: None)
    calls = {"n": 0}

    def fake_request(method, url, **kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            resp = SimpleNamespace(status_code=500, text="oops")
            def boom():
                raise site_api.requests.HTTPError("500")
            resp.raise_for_status = boom
            return resp
        return SimpleNamespace(status_code=200, text="ok",
                               raise_for_status=lambda: None)

    monkeypatch.setattr(site_api, "_session",
                        lambda: SimpleNamespace(request=fake_request))
    resp = site_api._request("GET", "/daily-snippets/page-data")
    assert resp.status_code == 200
    assert calls["n"] == 3


def test_session_requires_credentials(monkeypatch):
    monkeypatch.setattr(config, "SITE_TOKEN", "")
    monkeypatch.setattr(config, "SITE_SESSION", "")
    with pytest.raises(site_api.SiteApiError):
        site_api._session()
