"""Koreana 파일럿 산출물 자동 결합 경로의 end-to-end 검증.

실 크롤 데이터는 한국 IP에서만 수집 가능하므로(사이트가 해외 트래픽 차단), 여기서는
**합성 fixture**(테스트 전용, 실데이터 아님)로 '산출물이 도착하면 재빌드 한 번에
코퍼스 편입 + 다국어 근거 연결까지 자동'임을 보증한다.
"""
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pipeline.build_db as bdb  # noqa: E402

KO_BODY = ("전주에서 열린 소리 축제에서 젊은 소리꾼이 판소리 춘향가를 완창했다. " * 8)
EN_BODY = ("At the festival in Jeonju, a young singer performed a full pansori rendition "
           "of Chunhyangga, accompanied by a drummer. " * 5)


def test_pilot_ingestion_and_multilingual_evidence(tmp_path, monkeypatch):
    articles = tmp_path / "articles"
    articles.mkdir()
    (articles / "ko.jsonl").write_text(json.dumps({
        "lang": "ko", "nttSn": "1", "title": "[테스트픽스처] 판소리 완창 무대",
        "body_text": KO_BODY, "body_chars": len(KO_BODY), "url": "http://example.test/ko/1",
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    (articles / "en.jsonl").write_text(json.dumps({
        "lang": "en", "nttSn": "2", "title": "[test-fixture] A Full Pansori Performance",
        "body_text": EN_BODY, "body_chars": len(EN_BODY), "url": "http://example.test/en/2",
    }, ensure_ascii=False) + "\n", encoding="utf-8")

    monkeypatch.setattr(bdb, "KOREANA", articles)
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(bdb.SCHEMA)
    assert bdb.load_curated(con) > 0
    assert bdb.load_koreana_pilot(con) == 2  # ko+en 기사 편입

    n_ev = bdb.link_evidence(con)
    assert n_ev >= 2
    rows = con.execute(
        """SELECT e.lang, d.source FROM glossary_evidence e
           JOIN glossary_terms t ON t.id=e.term_id
           JOIN corpus_docs d ON d.id=e.doc_id WHERE t.term_ko='판소리'"""
    ).fetchall()
    langs = {(r["lang"], r["source"]) for r in rows}
    assert ("ko", "koreana_pilot") in langs   # 한국어판 근거 연결
    assert ("en", "koreana_pilot") in langs   # 영어판 'pansori' 음차 매칭 근거 연결
