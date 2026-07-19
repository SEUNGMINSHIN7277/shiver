import json
from datetime import date

import collect_activity


def _write_session(path, entries):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _user(ts, text):
    return {"type": "user", "timestamp": ts,
            "message": {"role": "user", "content": text}}


def _assistant(ts, text):
    return {"type": "assistant", "timestamp": ts,
            "message": {"role": "assistant",
                        "content": [{"type": "text", "text": text}]}}


TARGET = date(2026, 7, 10)


def test_collects_only_target_date(tmp_path):
    _write_session(tmp_path / "proj-a" / "s1.jsonl", [
        _user("2026-07-09T10:00:00Z", "어제 요청"),
        _user("2026-07-10T01:00:00Z", "오늘 요청"),
        _assistant("2026-07-10T01:01:00Z", "오늘 응답"),
        _user("2026-07-11T02:00:00Z", "내일 요청"),
    ])
    text = collect_activity.collect_today_conversations(TARGET, projects_dir=tmp_path)
    assert "오늘 요청" in text and "오늘 응답" in text
    assert "어제 요청" not in text and "내일 요청" not in text
    assert "프로젝트: proj-a" in text


def test_skips_noise_entries(tmp_path):
    _write_session(tmp_path / "proj-a" / "s1.jsonl", [
        _user("2026-07-10T01:00:00Z", "실제 요청"),
        # 사이드체인(서브에이전트) 제외
        {**_assistant("2026-07-10T01:01:00Z", "사이드체인"), "isSidechain": True},
        # tool_result 블록만 있는 user 항목 제외 (텍스트 블록 없음)
        {"type": "user", "timestamp": "2026-07-10T01:02:00Z",
         "message": {"role": "user", "content": [
             {"type": "tool_result", "content": "도구 출력"}]}},
        # 메타 텍스트 제외
        _user("2026-07-10T01:03:00Z", "Caveat: The messages below..."),
        # summary 타입 제외
        {"type": "summary", "summary": "요약", "timestamp": "2026-07-10T01:04:00Z"},
    ])
    text = collect_activity.collect_today_conversations(TARGET, projects_dir=tmp_path)
    assert "실제 요청" in text
    assert "사이드체인" not in text
    assert "도구 출력" not in text
    assert "Caveat" not in text


def test_none_when_no_conversations(tmp_path):
    _write_session(tmp_path / "proj-a" / "s1.jsonl", [
        _user("2026-07-09T10:00:00Z", "다른 날 대화"),
    ])
    assert collect_activity.collect_today_conversations(TARGET, projects_dir=tmp_path) is None


def test_none_when_dir_missing(tmp_path):
    assert collect_activity.collect_today_conversations(
        TARGET, projects_dir=tmp_path / "없는폴더") is None


def test_messages_sorted_and_grouped(tmp_path):
    _write_session(tmp_path / "proj-b" / "s1.jsonl", [
        _user("2026-07-10T05:00:00Z", "B 프로젝트 요청"),
    ])
    _write_session(tmp_path / "proj-a" / "s1.jsonl", [
        _assistant("2026-07-10T03:00:00Z", "두 번째"),
        _user("2026-07-10T02:00:00Z", "첫 번째"),
    ])
    text = collect_activity.collect_today_conversations(TARGET, projects_dir=tmp_path)
    assert text.index("첫 번째") < text.index("두 번째")
    assert text.index("proj-a") < text.index("proj-b")


def test_long_message_clipped(tmp_path):
    _write_session(tmp_path / "proj-a" / "s1.jsonl", [
        _assistant("2026-07-10T01:00:00Z", "가" * 5000),
    ])
    text = collect_activity.collect_today_conversations(TARGET, projects_dir=tmp_path)
    assert "…(생략)" in text
    assert len(text) < 2000


def test_total_truncation(tmp_path):
    entries = [_user(f"2026-07-10T01:{i:02d}:00Z", f"메시지{i} " + "나" * 500)
               for i in range(50)]
    _write_session(tmp_path / "proj-a" / "s1.jsonl", entries)
    text = collect_activity.collect_today_conversations(
        TARGET, projects_dir=tmp_path, max_total_chars=3000)
    assert len(text) < 3200
    assert "중략" in text


def test_broken_lines_ignored(tmp_path):
    path = tmp_path / "proj-a" / "s1.jsonl"
    path.parent.mkdir(parents=True)
    with path.open("w", encoding="utf-8") as f:
        f.write("{깨진 JSON\n")
        f.write(json.dumps(_user("2026-07-10T01:00:00Z", "정상 요청"),
                           ensure_ascii=False) + "\n")
    text = collect_activity.collect_today_conversations(TARGET, projects_dir=tmp_path)
    assert "정상 요청" in text
