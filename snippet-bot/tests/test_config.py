import logging
import time

import pytest

import config


def test_mask_secret(monkeypatch):
    monkeypatch.setattr(config, "SITE_TOKEN", "sekrit-token-123")
    assert config.mask_secret("Bearer sekrit-token-123 전송") == "Bearer ***TOKEN*** 전송"
    assert config.mask_secret("토큰 없음") == "토큰 없음"
    assert config.mask_secret("") == ""


def test_mask_secret_no_token(monkeypatch):
    monkeypatch.setattr(config, "SITE_TOKEN", "")
    assert config.mask_secret("아무거나 sekrit") == "아무거나 sekrit"


def test_strip_anthropic_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-dummy")
    assert config.strip_anthropic_api_key() is True
    import os
    assert "ANTHROPIC_API_KEY" not in os.environ
    assert config.strip_anthropic_api_key() is False


def test_with_retries_succeeds_after_failures(monkeypatch):
    sleeps = []
    monkeypatch.setattr(time, "sleep", sleeps.append)
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ValueError("일시 오류")
        return "ok"

    assert config.with_retries(flaky) == "ok"
    assert calls["n"] == 3
    assert sleeps == [2, 4]  # 지수 백오프


def test_with_retries_exhausts(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda s: None)
    calls = {"n": 0}

    def always_fail():
        calls["n"] += 1
        raise ValueError("계속 실패")

    with pytest.raises(ValueError):
        config.with_retries(always_fail)
    assert calls["n"] == config.RETRY_COUNT + 1  # 최초 1회 + 재시도 3회


def test_with_retries_fatal_no_retry(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda s: None)
    calls = {"n": 0}

    class Fatal(RuntimeError):
        pass

    def fatal():
        calls["n"] += 1
        raise Fatal("인증 만료")

    with pytest.raises(Fatal):
        config.with_retries(fatal, fatal=(Fatal,))
    assert calls["n"] == 1


def test_setup_logging_masks_token(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RUN_LOG_DIR", tmp_path)
    monkeypatch.setattr(config, "SITE_TOKEN", "sekrit-token-123")
    logger = config.setup_logging("test_mask.log")
    logger.info("요청 헤더: Bearer sekrit-token-123")
    logger.info("포맷 인자: %s", "sekrit-token-123")
    for handler in logger.handlers:
        handler.flush()
        if isinstance(handler, logging.FileHandler):
            handler.close()
    content = (tmp_path / "test_mask.log").read_text(encoding="utf-8")
    assert "sekrit-token-123" not in content
    assert content.count("***TOKEN***") == 2
