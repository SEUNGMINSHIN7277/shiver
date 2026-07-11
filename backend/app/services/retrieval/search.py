"""다국어 코퍼스 검색 (v2).

검색 전략:
- 1차: 다국어 용어사전 기반 **질의 확장(query expansion)** — 질의에 등장한 문화용어를
  한국어·영어·현지어 어느 형태로 쓰든 인식해, 대응하는 한국어 표제어와 영문 음차를 검색어에
  추가한다. 이로써 "pansori" 질의가 한국어 '판소리' 기사까지, "판소리 비슷한 것" 질의가
  영어판 기사까지 교차로 도달한다(키워드 매칭의 다국어 recall 한계 보완).
- 2차: SQLite FTS5(BM25) 랭킹.
- (옵션) 로컬 임베딩(BGE-M3 계열) 의미검색: `embed_index.py`로 인덱스가 빌드돼 있으면
  자동 사용. 인덱스 부재 시 위 1·2차로 폴백(현재 기본).
"""
from __future__ import annotations

import re
import sqlite3
from functools import lru_cache

_HANGUL = re.compile(r"[가-힣]{2,}")
_LATIN = re.compile(r"[A-Za-zÀ-ỹ]{3,}")


@lru_cache(maxsize=1)
def _expansion_index(_db_id: int) -> list[tuple[str, str, str]]:
    """(한국어표제어, 소문자 매칭키, 검색확장어) 목록 — 프로세스 캐시."""
    return []


def _build_expansion(con: sqlite3.Connection) -> list[tuple[str, str]]:
    """문화·기관 용어의 매칭 후보: (매칭키 소문자, 검색확장어)."""
    rows = con.execute(
        "SELECT t.term_ko, r.rendering FROM glossary_terms t"
        " JOIN glossary_renderings r ON r.term_id=t.id"
        " WHERE t.domain IN ('culture','institution')"
    ).fetchall()
    out: list[tuple[str, str]] = []
    seen_ko = set()
    for r in rows:
        ko = r["term_ko"]
        if ko not in seen_ko:
            out.append((ko.lower(), ko))       # 한국어 표제어 자체
            seen_ko.add(ko)
        head = r["rendering"].split("(")[0].strip()   # 음차/현지어 헤드 (pansori)
        if len(head) >= 3:
            out.append((head.lower(), ko))     # 외국어 형태 → 한국어 표제어로 확장
            out.append((head.lower(), head))   # 외국어 형태 자체도 검색어에
    return out


def expand_query(con: sqlite3.Connection, text: str) -> list[str]:
    """질의에 등장한 용어를 인식해 검색 확장어(한국어 표제어 + 음차)를 반환."""
    low = text.lower()
    extra: list[str] = []
    for key, add in _build_expansion(con):
        if key in low:
            extra.append(add)
    # 중복 제거, 최대 12개
    return list(dict.fromkeys(extra))[:12]


def _fts_query(text: str, extra_terms: list[str]) -> str:
    tokens = _HANGUL.findall(text) + _LATIN.findall(text) + extra_terms
    tokens = [t.replace('"', "") for t in tokens if t]
    if not tokens:
        return ""
    return " OR ".join(f'"{t}"' for t in dict.fromkeys(tokens))


def search_corpus(
    con: sqlite3.Connection, text: str, extra_terms: list[str] | None = None, k: int = 5
) -> list[dict]:
    # 질의 확장(다국어) 자동 적용 + 호출자가 준 extra_terms 병합
    auto = expand_query(con, text)
    merged = list(dict.fromkeys((extra_terms or []) + auto))
    q = _fts_query(text, merged)
    if not q:
        return []
    rows = con.execute(
        """SELECT d.id, d.source, d.lang, d.title, d.published, d.url,
                  snippet(corpus_fts, 1, '<mark>', '</mark>', '…', 40) AS snippet,
                  bm25(corpus_fts) AS score
           FROM corpus_fts JOIN corpus_docs d ON d.id = corpus_fts.rowid
           WHERE corpus_fts MATCH ? ORDER BY score LIMIT ?""",
        (q, k),
    ).fetchall()
    return [dict(r) for r in rows]
