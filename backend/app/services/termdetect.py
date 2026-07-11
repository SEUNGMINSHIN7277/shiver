"""입력 텍스트에서 용어사전 용어를 탐지 (v0: 최장일치 우선 부분문자열 매칭).

- 길이 1 용어(정, 한, 갓 등)는 오탐이 많아 자동 탐지에서 제외 (사전 검색으로는 조회 가능)
- 겹치는 매치는 더 긴 용어 우선 (예: '사물놀이'가 '놀이'보다 우선)
"""
from __future__ import annotations

import sqlite3
from functools import lru_cache


@lru_cache(maxsize=1)
def _term_index_cache_key() -> int:
    return 0  # 프로세스 수명 동안 사전은 불변 (빌드 시점 고정)


def load_terms(con: sqlite3.Connection) -> list[dict]:
    rows = con.execute(
        "SELECT id, term_ko, category, domain, definition_ko, source FROM glossary_terms"
        " WHERE length(term_ko) >= 2 ORDER BY length(term_ko) DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def detect_terms(con: sqlite3.Connection, text: str, target_lang: str) -> list[dict]:
    """텍스트에 등장하는 용어를 (위치 겹침 없이) 최장일치로 찾고 대역을 붙인다."""
    terms = load_terms(con)
    taken: list[tuple[int, int]] = []
    found: list[dict] = []
    for t in terms:  # 이미 길이 내림차순
        start = text.find(t["term_ko"])
        while start != -1:
            end = start + len(t["term_ko"])
            if not any(s < end and start < e for s, e in taken):
                taken.append((start, end))
                found.append({**t, "position": start})
                break
            start = text.find(t["term_ko"], end)
    for f in found:
        rends = con.execute(
            "SELECT lang, rendering, strategy, gloss, source FROM glossary_renderings WHERE term_id=?",
            (f["id"],),
        ).fetchall()
        by_lang = {r["lang"]: dict(r) for r in rends}
        f["rendering"] = by_lang.get(target_lang) or by_lang.get("en")
        f["renderings_available"] = sorted(by_lang.keys())
        f["fallback_to_en"] = target_lang not in by_lang and "en" in by_lang
    found.sort(key=lambda x: x["position"])
    return found
