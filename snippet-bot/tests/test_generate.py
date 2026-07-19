import time
from types import SimpleNamespace

import pytest

import generate


# --- extract_snippet -------------------------------------------------------

def test_extract_between_markers():
    raw = (f"네, 작성했습니다.\n{generate.SNIPPET_START}\n## 1. what\n내용\n"
           f"{generate.SNIPPET_END}\n확인 부탁드립니다.")
    assert generate.extract_snippet(raw) == "## 1. what\n내용"


def test_extract_without_markers():
    assert generate.extract_snippet("  ## 1. what\n내용  ") == "## 1. what\n내용"


def test_extract_with_orphan_marker():
    raw = f"{generate.SNIPPET_START}\n## 1. what\n내용"
    assert generate.extract_snippet(raw) == "## 1. what\n내용"


def test_extract_end_before_start_falls_back():
    raw = f"{generate.SNIPPET_END} 앞뒤가 꼬인 출력 {generate.SNIPPET_START}"
    assert generate.extract_snippet(raw) == "앞뒤가 꼬인 출력"


# --- 인증/한도 오류 감지 ---------------------------------------------------

def test_auth_error_detection():
    assert generate._looks_like_auth_error("Error: Please run /login")
    assert generate._looks_like_auth_error("You have hit your USAGE LIMIT")
    assert not generate._looks_like_auth_error("정상적인 스니펫 본문입니다")


# --- run_claude ------------------------------------------------------------

def _fake_proc(returncode=0, stdout="", stderr=""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def test_run_claude_success_and_env(monkeypatch):
    monkeypatch.setattr(generate, "find_claude", lambda: "/usr/bin/claude")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-should-be-removed")
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["env"] = kwargs["env"]
        captured["input"] = kwargs["input"]
        return _fake_proc(stdout="응답 텍스트")

    monkeypatch.setattr(generate.subprocess, "run", fake_run)
    out = generate.run_claude("지시문", stdin_text="오늘 기록")
    assert out == "응답 텍스트"
    assert captured["cmd"] == ["/usr/bin/claude", "-p", "지시문",
                               "--output-format", "text"]
    assert "ANTHROPIC_API_KEY" not in captured["env"]  # 과금 방지 (§4)
    assert captured["input"] == "오늘 기록"


def test_run_claude_cmd_shim_wrapped(monkeypatch):
    monkeypatch.setattr(generate, "find_claude",
                        lambda: r"C:\Users\me\AppData\Roaming\npm\claude.CMD")
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _fake_proc(stdout="ok")

    monkeypatch.setattr(generate.subprocess, "run", fake_run)
    generate.run_claude("지시문")
    assert captured["cmd"][:2] == ["cmd", "/c"]


def test_run_claude_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr(generate, "find_claude", lambda: "/usr/bin/claude")
    monkeypatch.setattr(time, "sleep", lambda s: None)
    calls = {"n": 0}

    def fake_run(cmd, **kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            return _fake_proc(returncode=1, stderr="transient network error")
        return _fake_proc(stdout="성공")

    monkeypatch.setattr(generate.subprocess, "run", fake_run)
    assert generate.run_claude("지시문") == "성공"
    assert calls["n"] == 3


def test_run_claude_auth_error_no_retry(monkeypatch):
    monkeypatch.setattr(generate, "find_claude", lambda: "/usr/bin/claude")
    monkeypatch.setattr(time, "sleep", lambda s: None)
    calls = {"n": 0}

    def fake_run(cmd, **kwargs):
        calls["n"] += 1
        return _fake_proc(returncode=1, stderr="Invalid API key · Please run /login")

    monkeypatch.setattr(generate.subprocess, "run", fake_run)
    with pytest.raises(generate.ClaudeAuthError):
        generate.run_claude("지시문")
    assert calls["n"] == 1  # 인증 오류는 재시도하지 않는다


def test_run_claude_empty_output_retries(monkeypatch):
    monkeypatch.setattr(generate, "find_claude", lambda: "/usr/bin/claude")
    monkeypatch.setattr(time, "sleep", lambda s: None)
    calls = {"n": 0}

    def fake_run(cmd, **kwargs):
        calls["n"] += 1
        return _fake_proc(stdout="   ")

    monkeypatch.setattr(generate.subprocess, "run", fake_run)
    with pytest.raises(generate.ClaudeError):
        generate.run_claude("지시문")
    assert calls["n"] == 4  # 최초 1회 + 재시도 3회


# --- 상위 생성 함수 --------------------------------------------------------

def test_generate_daily_snippet_extracts(monkeypatch):
    def fake_run_claude(instruction, stdin_text=None, **kwargs):
        assert "2026-07-19" in instruction
        assert stdin_text == "오늘 기록"
        return (f"작성 결과입니다.\n{generate.SNIPPET_START}\n"
                f"## 1. what\n오늘은 A를 했습니다.\n{generate.SNIPPET_END}")

    monkeypatch.setattr(generate, "run_claude", fake_run_claude)
    snippet = generate.generate_daily_snippet("오늘 기록", "2026-07-19")
    assert snippet == "## 1. what\n오늘은 A를 했습니다."


def test_generate_weekly_snippet_extracts(monkeypatch):
    def fake_run_claude(instruction, stdin_text=None, **kwargs):
        assert "2026-07-13 ~ 2026-07-19" in instruction
        return f"{generate.SNIPPET_START}주간 요약{generate.SNIPPET_END}"

    monkeypatch.setattr(generate, "run_claude", fake_run_claude)
    assert generate.generate_weekly_snippet("자료", "2026-07-13 ~ 2026-07-19") == "주간 요약"
