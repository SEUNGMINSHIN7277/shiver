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


# --- find_claude -----------------------------------------------------------

def test_find_claude_prefers_native_exe(tmp_path, monkeypatch):
    """npm .cmd 셔틀 대신 같은 위치의 네이티브 claude.exe를 우선 사용한다."""
    shim = tmp_path / "claude.CMD"
    shim.write_text("@echo off", encoding="utf-8")
    native = (tmp_path / "node_modules" / "@anthropic-ai" / "claude-code"
              / "bin" / "claude.exe")
    native.parent.mkdir(parents=True)
    native.write_bytes(b"MZ")
    monkeypatch.setattr(generate.shutil, "which", lambda name: str(shim))
    assert generate.find_claude() == str(native)


def test_find_claude_cmd_without_native(tmp_path, monkeypatch):
    shim = tmp_path / "claude.cmd"
    shim.write_text("@echo off", encoding="utf-8")
    monkeypatch.setattr(generate.shutil, "which", lambda name: str(shim))
    assert generate.find_claude() == str(shim)


# --- run_claude ------------------------------------------------------------

def _fake_proc(returncode=0, stdout="", stderr=""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def test_run_claude_prompt_via_stdin_only(monkeypatch):
    """프롬프트 전문은 stdin으로만 전달하고 인자에는 절대 넣지 않는다 (cmd.exe 개행 문제)."""
    monkeypatch.setattr(generate, "find_claude", lambda: "/usr/bin/claude")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-should-be-removed")
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["env"] = kwargs["env"]
        captured["input"] = kwargs["input"]
        return _fake_proc(stdout="응답 텍스트")

    monkeypatch.setattr(generate.subprocess, "run", fake_run)
    multiline_prompt = "지시문 1행\n지시문 2행\n\n원천 자료"
    out = generate.run_claude(multiline_prompt)
    assert out == "응답 텍스트"
    assert captured["cmd"] == ["/usr/bin/claude", "-p", "--output-format", "text"]
    assert captured["input"] == multiline_prompt
    assert "ANTHROPIC_API_KEY" not in captured["env"]  # 과금 방지 (§4)
    # 어떤 인자에도 개행이 없어야 .cmd 폴백에서도 안전하다
    assert all("\n" not in arg for arg in captured["cmd"])


def test_run_claude_cmd_shim_wrapped(monkeypatch):
    monkeypatch.setattr(generate, "find_claude",
                        lambda: r"C:\Users\me\AppData\Roaming\npm\claude.CMD")
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _fake_proc(stdout="ok")

    monkeypatch.setattr(generate.subprocess, "run", fake_run)
    generate.run_claude("여러 줄\n프롬프트")
    assert captured["cmd"][:2] == ["cmd", "/c"]
    assert all("\n" not in arg for arg in captured["cmd"])


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
    assert generate.run_claude("프롬프트") == "성공"
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
        generate.run_claude("프롬프트")
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
        generate.run_claude("프롬프트")
    assert calls["n"] == 4  # 최초 1회 + 재시도 3회


def test_run_claude_success_with_auth_keyword_in_long_output(monkeypatch):
    """긴 정상 출력에 'rate limit' 같은 용어가 있어도 인증 오류로 오분류하지 않는다."""
    monkeypatch.setattr(generate, "find_claude", lambda: "/usr/bin/claude")
    long_output = "오늘은 rate limit 버그를 수정했습니다. " * 30  # 300자 초과

    monkeypatch.setattr(generate.subprocess, "run",
                        lambda *a, **k: _fake_proc(stdout=long_output))
    assert generate.run_claude("프롬프트") == long_output.strip()


def test_run_claude_short_auth_message_raises(monkeypatch):
    monkeypatch.setattr(generate, "find_claude", lambda: "/usr/bin/claude")
    monkeypatch.setattr(generate.subprocess, "run",
                        lambda *a, **k: _fake_proc(stdout="Please run /login"))
    with pytest.raises(generate.ClaudeAuthError):
        generate.run_claude("프롬프트")


# --- 상위 생성 함수 --------------------------------------------------------

def test_generate_daily_snippet_extracts(monkeypatch):
    def fake_run_claude(prompt, logger=None):
        assert "2026-07-19" in prompt
        assert "오늘 기록" in prompt  # 원천 자료가 프롬프트에 포함됨
        return (f"작성 결과입니다.\n{generate.SNIPPET_START}\n"
                f"## 1. what\n오늘은 A를 했습니다.\n{generate.SNIPPET_END}")

    monkeypatch.setattr(generate, "run_claude", fake_run_claude)
    snippet = generate.generate_daily_snippet("오늘 기록", "2026-07-19")
    assert snippet == "## 1. what\n오늘은 A를 했습니다."


def test_generate_weekly_snippet_extracts(monkeypatch):
    def fake_run_claude(prompt, logger=None):
        assert "2026-07-13 ~ 2026-07-19" in prompt
        assert "자료" in prompt
        return f"{generate.SNIPPET_START}주간 요약{generate.SNIPPET_END}"

    monkeypatch.setattr(generate, "run_claude", fake_run_claude)
    assert generate.generate_weekly_snippet("자료", "2026-07-13 ~ 2026-07-19") == "주간 요약"
