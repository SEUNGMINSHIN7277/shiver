import sqlite3
from functools import lru_cache

from .config import get_settings


@lru_cache
def get_db() -> sqlite3.Connection:
    con = sqlite3.connect(get_settings().db_path, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con
