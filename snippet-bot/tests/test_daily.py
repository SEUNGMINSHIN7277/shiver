from datetime import date, datetime

import collect_activity
import config
import daily
import generate


def _setup_paths(tmp_path, monkeypatch):
    log_dir = tmp_path / "log"
    log_dir.mkdir()
    monkeypatch.setattr(config, "TODAY_MD", log_dir / "today.md")
    monkeypatch.setattr(config, "ARCHIVE_DIR", log_dir / "archive")
    monkeypatch.setattr(config, "RUN_LOG_DIR", tmp_path / "logs")
    # 테스트가 실수로도 실제 사이트/실제 대화 저장소에 접근하지 못하게 격리
    monkeypatch.setattr(config, "SITE_TOKEN", "")
    monkeypatch.setattr(config, "SITE_SESSION", "")
    monkeypatch.setattr(collect_activity, "CLAUDE_PROJECTS_DIR",
                        tmp_path / "no-claude-dir")


# --- default_run_date (보충 실행 날짜 보정, §9/§13) --------------------------

def test_default_run_date_regular_night_run():
    now = datetime(2026, 7, 19, 23, 30)
    assert daily.default_run_date(now) == date(2026, 7, 19)


def test_default_run_date_catchup_next_morning():
    # PC가 꺼져 23:30을 놓치고 다음날 아침 부팅 → 전날 날짜로 보충 실행
    now = datetime(2026, 7, 20, 9, 15)
    assert daily.default_run_date(now) == date(2026, 7, 19)


# --- read_today_md ---------------------------------------------------------

def test_read_today_md_missing(tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)
    assert daily.read_today_md() is None


def test_read_today_md_blank(tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)
    config.TODAY_MD.write_text("  \n\t\n", encoding="utf-8")
    assert daily.read_today_md() is None


def test_read_today_md_content(tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)
    config.TODAY_MD.write_text("오늘 한 일", encoding="utf-8")
    assert daily.read_today_md() == "오늘 한 일"


def test_read_today_md_cp949(tmp_path, monkeypatch):
    """구형 메모장 ANSI(CP949) 저장도 한글이 깨지지 않고 읽혀야 한다."""
    _setup_paths(tmp_path, monkeypatch)
    config.TODAY_MD.write_bytes("한글 메모입니다".encode("cp949"))
    assert daily.read_today_md() == "한글 메모입니다"


# --- build_daily_source ----------------------------------------------------

def test_source_none_when_no_material(tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)
    import logging
    assert daily.build_daily_source(date(2026, 7, 19), logging.getLogger("t")) is None


def test_source_memo_only(tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)
    config.TODAY_MD.write_text("메모 내용", encoding="utf-8")
    import logging
    source = daily.build_daily_source(date(2026, 7, 19), logging.getLogger("t"))
    assert "사용자 메모" in source and "메모 내용" in source


def test_source_conversations_only(tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)
    monkeypatch.setattr(collect_activity, "collect_today_conversations",
                        lambda d, logger=None: "[10:00] 사용자: 작업 요청")
    import logging
    source = daily.build_daily_source(date(2026, 7, 19), logging.getLogger("t"))
    assert "Claude Code 대화 기록" in source and "작업 요청" in source


def test_source_merges_both(tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)
    config.TODAY_MD.write_text("메모", encoding="utf-8")
    monkeypatch.setattr(collect_activity, "collect_today_conversations",
                        lambda d, logger=None: "대화 기록")
    import logging
    source = daily.build_daily_source(date(2026, 7, 19), logging.getLogger("t"))
    assert "메모" in source and "대화 기록" in source


# --- 보관 -------------------------------------------------------------------

def test_save_snippet_and_archive_memo(tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)
    config.TODAY_MD.write_text("기록 1", encoding="utf-8")

    snippet_path = daily.save_snippet_to_archive(date(2026, 7, 19), "## 스니펫")
    assert snippet_path.name == "2026-07-19.md"
    assert snippet_path.read_text(encoding="utf-8") == "## 스니펫"

    memo_path = daily.archive_today_md(date(2026, 7, 19))
    assert memo_path.name == "2026-07-19_memo.md"
    assert memo_path.read_text(encoding="utf-8") == "기록 1"
    assert config.TODAY_MD.read_text(encoding="utf-8") == ""

    # 같은 날 재실행 시 덮어쓰지 않고 접미사를 붙인다
    snippet_path2 = daily.save_snippet_to_archive(date(2026, 7, 19), "## 스니펫2")
    assert snippet_path2.name == "2026-07-19_2.md"


def test_archive_today_md_absent_returns_none(tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)
    assert daily.archive_today_md(date(2026, 7, 19)) is None


# --- main ------------------------------------------------------------------

def test_main_no_record_exits_zero(tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)

    def must_not_call(*a, **k):
        raise AssertionError("기록이 없으면 생성/업로드를 호출하면 안 된다")

    monkeypatch.setattr(generate, "generate_daily_snippet", must_not_call)
    assert daily.main(["--date", "2026-07-19"]) == 0


def test_main_dry_run_zero_touch(tmp_path, monkeypatch, capsys):
    """today.md 없이 Claude 대화만으로 스니펫이 생성되는 '개입 0' 경로."""
    _setup_paths(tmp_path, monkeypatch)
    monkeypatch.setattr(collect_activity, "collect_today_conversations",
                        lambda d, logger=None: "[10:00] 사용자: 오늘 작업")
    monkeypatch.setattr(generate, "generate_daily_snippet",
                        lambda text, d, logger=None: "## 1. what\n생성된 스니펫")

    assert daily.main(["--dry-run", "--date", "2026-07-19"]) == 0
    assert "생성된 스니펫" in capsys.readouterr().out
    assert not (config.ARCHIVE_DIR / "2026-07-19.md").exists()  # dry-run은 보관 안 함


def test_main_site_api_error_keeps_today(tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)
    config.TODAY_MD.write_text("오늘 한 일", encoding="utf-8")
    monkeypatch.setattr(generate, "generate_daily_snippet",
                        lambda text, d, logger=None: "스니펫")

    import site_api

    def boom(*a, **k):
        raise site_api.SiteApiError("업로드 실패")

    monkeypatch.setattr(site_api, "post_daily_snippet", boom)
    # 업로드 실패 → 실패 종료 + today.md는 보관하지 않고 유지
    assert daily.main(["--date", "2026-07-19"]) == 1
    assert config.TODAY_MD.read_text(encoding="utf-8") == "오늘 한 일"
    assert not (config.ARCHIVE_DIR / "2026-07-19.md").exists()


def test_main_full_success_archives(tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)
    config.TODAY_MD.write_text("오늘 한 일", encoding="utf-8")
    monkeypatch.setattr(generate, "generate_daily_snippet",
                        lambda text, d, logger=None: "## 스니펫 본문")

    import site_api
    monkeypatch.setattr(site_api, "post_daily_snippet",
                        lambda d, c, logger=None: "id-123")
    monkeypatch.setattr(site_api, "run_ai_grading",
                        lambda sid, kind="daily", logger=None: {"score": 5})

    assert daily.main(["--date", "2026-07-19"]) == 0
    snippet_file = config.ARCHIVE_DIR / "2026-07-19.md"
    memo_file = config.ARCHIVE_DIR / "2026-07-19_memo.md"
    assert snippet_file.read_text(encoding="utf-8") == "## 스니펫 본문"
    assert memo_file.read_text(encoding="utf-8") == "오늘 한 일"
    assert config.TODAY_MD.read_text(encoding="utf-8") == ""


def test_main_idempotent_skip_when_already_archived(tmp_path, monkeypatch):
    """보충 실행과 정규 실행이 겹쳐도 같은 날짜를 두 번 올리지 않는다."""
    _setup_paths(tmp_path, monkeypatch)
    config.ARCHIVE_DIR.mkdir(parents=True)
    (config.ARCHIVE_DIR / "2026-07-19.md").write_text("이미 처리됨", encoding="utf-8")
    config.TODAY_MD.write_text("새 기록", encoding="utf-8")

    def must_not_call(*a, **k):
        raise AssertionError("이미 처리된 날짜는 생성/업로드하면 안 된다")

    monkeypatch.setattr(generate, "generate_daily_snippet", must_not_call)
    assert daily.main(["--date", "2026-07-19"]) == 0
    assert config.TODAY_MD.read_text(encoding="utf-8") == "새 기록"  # 유지


def test_main_strips_anthropic_key(tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-dummy")
    daily.main(["--dry-run", "--date", "2026-07-19"])  # 기록 없음 → 조기 종료여도 가드는 먼저 돈다
    import os
    assert "ANTHROPIC_API_KEY" not in os.environ
