import logging
from datetime import date, datetime

import config
import generate
import site_api
import weekly


def _setup_paths(tmp_path, monkeypatch):
    log_dir = tmp_path / "log"
    (log_dir / "archive").mkdir(parents=True)
    monkeypatch.setattr(config, "TODAY_MD", log_dir / "today.md")
    monkeypatch.setattr(config, "ARCHIVE_DIR", log_dir / "archive")
    monkeypatch.setattr(config, "RUN_LOG_DIR", tmp_path / "logs")
    # 테스트가 실수로도 실제 사이트에 접근하지 못하게 자격증명을 비운다
    # (_session()이 즉시 SiteApiError를 던지고 archive 폴백을 타게 된다)
    monkeypatch.setattr(config, "SITE_TOKEN", "")
    monkeypatch.setattr(config, "SITE_SESSION", "")


# --- week_range_for --------------------------------------------------------

def test_week_range_on_sunday():
    monday, sunday = weekly.week_range_for(date(2026, 7, 19))  # 일요일
    assert monday == date(2026, 7, 13)
    assert sunday == date(2026, 7, 19)


def test_week_range_midweek():
    monday, sunday = weekly.week_range_for(date(2026, 7, 15))  # 수요일
    assert monday == date(2026, 7, 13)
    assert sunday == date(2026, 7, 19)


# --- default_target_date (보충 실행 주간 보정, §9/§13) ------------------------

def test_default_target_regular_sunday():
    assert weekly.default_target_date(datetime(2026, 7, 19, 23, 30)) == date(2026, 7, 19)


def test_default_target_catchup_monday_targets_last_week():
    # 일요일 23:30을 놓치고 월요일 부팅 → 직전 일요일 기준(지난주 요약)
    assert weekly.default_target_date(datetime(2026, 7, 20, 9, 0)) == date(2026, 7, 19)


def test_default_target_catchup_midweek_targets_last_week():
    assert weekly.default_target_date(datetime(2026, 7, 22, 14, 0)) == date(2026, 7, 19)


# --- collect ---------------------------------------------------------------

def test_collect_from_archive_filters_week(tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)
    (config.ARCHIVE_DIR / "2026-07-13.md").write_text("월요일 기록", encoding="utf-8")
    (config.ARCHIVE_DIR / "2026-07-13_2.md").write_text("월요일 추가", encoding="utf-8")
    (config.ARCHIVE_DIR / "2026-07-15.md").write_text("수요일 기록", encoding="utf-8")
    (config.ARCHIVE_DIR / "2026-07-20.md").write_text("다음 주 기록", encoding="utf-8")

    logger = logging.getLogger("test")
    text = weekly.collect_from_archive(date(2026, 7, 13), date(2026, 7, 19), logger)
    assert "월요일 기록" in text
    assert "월요일 추가" in text
    assert "수요일 기록" in text
    assert "다음 주 기록" not in text


def test_collect_from_archive_empty(tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)
    logger = logging.getLogger("test")
    assert weekly.collect_from_archive(date(2026, 7, 13), date(2026, 7, 19), logger) is None


def test_collect_material_falls_back_to_archive(tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)
    (config.ARCHIVE_DIR / "2026-07-14.md").write_text("화요일 기록", encoding="utf-8")

    def boom(*a, **k):
        raise site_api.SiteApiError("조회 실패")

    monkeypatch.setattr(site_api, "get_daily_snippets", boom)
    logger = logging.getLogger("test")
    text = weekly.collect_weekly_material(date(2026, 7, 13), date(2026, 7, 19), logger)
    assert "화요일 기록" in text


def test_collect_material_prefers_site(tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)
    monkeypatch.setattr(site_api, "get_daily_snippets",
                        lambda s, e, logger=None: [{"date": "2026-07-13", "content": "사이트 기록"}])
    logger = logging.getLogger("test")
    text = weekly.collect_weekly_material(date(2026, 7, 13), date(2026, 7, 19), logger)
    assert "사이트 기록" in text


# --- main ------------------------------------------------------------------

def test_main_no_material_exits_zero(tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)

    def must_not_call(*a, **k):
        raise AssertionError("자료가 없으면 생성하면 안 된다")

    monkeypatch.setattr(generate, "generate_weekly_snippet", must_not_call)
    assert weekly.main(["--date", "2026-07-19"]) == 0


def test_main_dry_run(tmp_path, monkeypatch, capsys):
    _setup_paths(tmp_path, monkeypatch)
    (config.ARCHIVE_DIR / "2026-07-14.md").write_text("화요일 기록", encoding="utf-8")
    monkeypatch.setattr(generate, "generate_weekly_snippet",
                        lambda material, label, logger=None: "## 주간 요약 스니펫")

    assert weekly.main(["--dry-run", "--date", "2026-07-19"]) == 0
    assert "주간 요약 스니펫" in capsys.readouterr().out


def test_main_full_success(tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)
    (config.ARCHIVE_DIR / "2026-07-14.md").write_text("화요일 기록", encoding="utf-8")
    monkeypatch.setattr(generate, "generate_weekly_snippet",
                        lambda material, label, logger=None: "주간 스니펫")
    monkeypatch.setattr(site_api, "post_weekly_snippet",
                        lambda wr, c, logger=None: "wid-1")
    monkeypatch.setattr(site_api, "run_ai_grading",
                        lambda sid, kind="daily", logger=None: {"score": 4})

    assert weekly.main(["--date", "2026-07-19"]) == 0
