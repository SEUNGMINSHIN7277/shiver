from datetime import date

import config
import daily
import generate


def _setup_paths(tmp_path, monkeypatch):
    log_dir = tmp_path / "log"
    log_dir.mkdir()
    monkeypatch.setattr(config, "TODAY_MD", log_dir / "today.md")
    monkeypatch.setattr(config, "ARCHIVE_DIR", log_dir / "archive")
    monkeypatch.setattr(config, "RUN_LOG_DIR", tmp_path / "logs")


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


# --- archive_today_md ------------------------------------------------------

def test_archive_moves_and_recreates(tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)
    config.TODAY_MD.write_text("기록 1", encoding="utf-8")
    target = daily.archive_today_md(date(2026, 7, 19))
    assert target.name == "2026-07-19.md"
    assert target.read_text(encoding="utf-8") == "기록 1"
    assert config.TODAY_MD.exists()
    assert config.TODAY_MD.read_text(encoding="utf-8") == ""

    # 같은 날 재실행 시 덮어쓰지 않고 접미사를 붙인다
    config.TODAY_MD.write_text("기록 2", encoding="utf-8")
    target2 = daily.archive_today_md(date(2026, 7, 19))
    assert target2.name == "2026-07-19_2.md"
    assert target.read_text(encoding="utf-8") == "기록 1"


# --- main ------------------------------------------------------------------

def test_main_no_record_exits_zero(tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)

    def must_not_call(*a, **k):
        raise AssertionError("기록이 없으면 생성/업로드를 호출하면 안 된다")

    monkeypatch.setattr(generate, "generate_daily_snippet", must_not_call)
    assert daily.main(["--date", "2026-07-19"]) == 0


def test_main_dry_run_prints_and_keeps_today(tmp_path, monkeypatch, capsys):
    _setup_paths(tmp_path, monkeypatch)
    config.TODAY_MD.write_text("오늘 한 일", encoding="utf-8")
    monkeypatch.setattr(generate, "generate_daily_snippet",
                        lambda text, d, logger=None: "## 1. what\n생성된 스니펫")

    assert daily.main(["--dry-run", "--date", "2026-07-19"]) == 0
    assert "생성된 스니펫" in capsys.readouterr().out
    # dry-run은 보관하지 않는다
    assert config.TODAY_MD.read_text(encoding="utf-8") == "오늘 한 일"
    assert not (config.ARCHIVE_DIR / "2026-07-19.md").exists()


def test_main_site_api_not_implemented_keeps_today(tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)
    config.TODAY_MD.write_text("오늘 한 일", encoding="utf-8")
    monkeypatch.setattr(generate, "generate_daily_snippet",
                        lambda text, d, logger=None: "스니펫")

    # site_api는 기본적으로 SiteApiNotImplemented를 던진다 → 실패 종료 + today.md 유지
    assert daily.main(["--date", "2026-07-19"]) == 1
    assert config.TODAY_MD.read_text(encoding="utf-8") == "오늘 한 일"


def test_main_full_success_archives(tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)
    config.TODAY_MD.write_text("오늘 한 일", encoding="utf-8")
    monkeypatch.setattr(generate, "generate_daily_snippet",
                        lambda text, d, logger=None: "스니펫")

    import site_api
    monkeypatch.setattr(site_api, "post_daily_snippet",
                        lambda d, c, logger=None: "id-123")
    monkeypatch.setattr(site_api, "run_ai_grading",
                        lambda sid, logger=None: {"score": 5})

    assert daily.main(["--date", "2026-07-19"]) == 0
    archived = config.ARCHIVE_DIR / "2026-07-19.md"
    assert archived.read_text(encoding="utf-8") == "오늘 한 일"
    assert config.TODAY_MD.read_text(encoding="utf-8") == ""


def test_main_strips_anthropic_key(tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-dummy")
    daily.main(["--dry-run", "--date", "2026-07-19"])  # 기록 없음 → 조기 종료여도 가드는 먼저 돈다
    import os
    assert "ANTHROPIC_API_KEY" not in os.environ
