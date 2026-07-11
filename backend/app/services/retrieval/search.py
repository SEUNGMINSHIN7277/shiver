"""FTS5 기반 코퍼스 검색 (v0). 임베딩(BGE-M3) 업그레이드는 M1'에서."""
from __future__ import annotations

import re
import sqlite3

_HANGUL = re.compile(r"[가-힣]{2,}")
_LATIN = re.compile(r"[A-Za-zÀ-ỹ]{3,}")


def _fts_query(text: str, extra_terms: list[str]) -> str:
    tokens = _HANGUL.findall(text) + _LATIN.findall(text) + extra_terms
    tokens = [t.replace('"', "") for t in tokens][:12]
    if not tokens:
        return ""
    return " OR ".join(f'"{t}"' for t in dict.fromkeys(tokens))


def search_corpus(
    con: sqlite3.Connection, text: str, extra_terms: list[str] | None = None, k: int = 5
) -> list[dict]:
    q = _fts_query(text, extra_terms or [])
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
