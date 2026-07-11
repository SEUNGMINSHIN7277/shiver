from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    demo_mode: str = "cached"  # cached | live  (비용 0원 원칙 — CLAUDE.md §3.5)
    database_path: str = "data/krosetta.db"
    data_go_kr_api_key: str = ""
    anthropic_api_key: str = ""

    @property
    def db_path(self) -> Path:
        p = Path(self.database_path)
        return p if p.is_absolute() else REPO_ROOT / p


@lru_cache
def get_settings() -> Settings:
    return Settings()
