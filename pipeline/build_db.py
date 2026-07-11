"""K-Rosetta DB 빌드 (S0).

입력 (전부 실데이터 — R1 요건 증빙):
  - data/pilot/opendata/한국국제교류재단_한국음식정보_영어_*.csv   → 용어사전 시드(음식, 공인 영문 표준명)
  - data/pilot/opendata/한국국제협력단_ODA용어사전_*.csv          → 용어사전(외교·개발협력 도메인)
  - data/pilot/opendata/한국국제교류재단_디지털아카이브기사목록_*.csv → RAG 코퍼스
  - data/pilot/derived/cultural_terms_v0.json                     → 큐레이션 문화용어 (세션 생성)
  - data/pilot/koreana/articles/*.jsonl (있으면)                   → Koreana 파일럿 코퍼스

실행: python pipeline/build_db.py   → data/krosetta.db
"""
from __future__ import annotations

import csv
import json
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "krosetta.db"
OPENDATA = ROOT / "data" / "pilot" / "opendata"
DERIVED = ROOT / "data" / "pilot" / "derived"
KOREANA = ROOT / "data" / "pilot" / "koreana" / "articles"

SCHEMA = """
DROP TABLE IF EXISTS glossary_terms;
DROP TABLE IF EXISTS glossary_renderings;
DROP TABLE IF EXISTS corpus_docs;
DROP TABLE IF EXISTS opendata_provenance;
DROP TABLE IF EXISTS corpus_fts;

CREATE TABLE glossary_terms (
  id INTEGER PRIMARY KEY,
  term_ko TEXT NOT NULL UNIQUE,
  category TEXT,
  domain TEXT NOT NULL,            -- culture | food | oda
  definition_ko TEXT,
  source TEXT NOT NULL             -- provenance key
);
CREATE TABLE glossary_renderings (
  id INTEGER PRIMARY KEY,
  term_id INTEGER NOT NULL REFERENCES glossary_terms(id),
  lang TEXT NOT NULL,
  rendering TEXT NOT NULL,
  strategy TEXT,
  gloss TEXT,                      -- 설명(있으면)
  source TEXT NOT NULL
);
CREATE INDEX idx_rend_term ON glossary_renderings(term_id, lang);

CREATE TABLE corpus_docs (
  id INTEGER PRIMARY KEY,
  source TEXT NOT NULL,            -- kf_archive | kf_food | koica_oda | koreana_pilot
  lang TEXT NOT NULL,
  title TEXT,
  body TEXT,
  published TEXT,
  url TEXT
);
CREATE VIRTUAL TABLE corpus_fts USING fts5(
  title, body, content='corpus_docs', content_rowid='id',
  tokenize='unicode61 remove_diacritics 2'
);
CREATE TABLE opendata_provenance (
  dataset_name TEXT PRIMARY KEY,
  provider TEXT, portal_url TEXT, license TEXT,
  fetched_at TEXT, record_count INTEGER, used_for TEXT
);
"""

PROVENANCE = {
    "kf_food": {
        "dataset_name": "한국국제교류재단_한국음식정보_영어",
        "provider": "한국국제교류재단(KF)",
        "portal_url": "https://www.data.go.kr/data/15044203/fileData.do",
        "license": "공공데이터포털 이용허락범위 준수(출처표시)",
        "used_for": "문화용어(음식) 표준 영문 대역 시드 사전 + RAG 문화 설명",
    },
    "koica_oda": {
        "dataset_name": "한국국제협력단_ODA용어사전",
        "provider": "한국국제협력단(KOICA)",
        "portal_url": "https://www.data.go.kr/data/15052909/openapi.do",
        "license": "공공데이터포털 이용허락범위 준수(출처표시)",
        "used_for": "외교·개발협력 도메인 용어사전 모듈",
    },
    "kf_archive": {
        "dataset_name": "한국국제교류재단_디지털 아카이브 기사 목록",
        "provider": "한국국제교류재단(KF)",
        "portal_url": "https://www.data.go.kr/data/15139278/fileData.do",
        "license": "공공데이터포털 이용허락범위 준수(출처표시)",
        "used_for": "문화·공공외교 도메인 RAG 코퍼스",
    },
    "curated_v0": {
        "dataset_name": "K-Rosetta 큐레이션 문화용어 v0",
        "provider": "K-Rosetta (Koreana 정렬 대기)",
        "portal_url": "",
        "license": "자체 생성",
        "used_for": "핵심 문화용어 다국어 대역 (v1에서 Koreana 근거 연결)",
    },
}


def find_one(dirp: Path, pattern: str) -> Path | None:
    hits = sorted(dirp.glob(pattern))
    return hits[0] if hits else None


def load_food(con: sqlite3.Connection) -> int:
    f = find_one(OPENDATA, "*한국음식정보*.csv")
    if not f:
        print("  [skip] 한국음식정보 CSV 없음")
        return 0
    n = 0
    with f.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            name = (row.get("음식명") or "").strip()
            en = (row.get("영문") or "").strip()
            desc = (row.get("음식설명") or "").strip()
            cat = (row.get("구분") or "").strip()
            if not name or not en:
                continue
            cur = con.execute(
                "INSERT OR IGNORE INTO glossary_terms(term_ko, category, domain, definition_ko, source)"
                " VALUES(?,?,?,?,?)",
                (name, f"음식({cat})", "food", desc, "kf_food"),
            )
            term_id = cur.lastrowid or con.execute(
                "SELECT id FROM glossary_terms WHERE term_ko=?", (name,)
            ).fetchone()[0]
            con.execute(
                "INSERT INTO glossary_renderings(term_id, lang, rendering, strategy, gloss, source)"
                " VALUES(?,?,?,?,?,?)",
                (term_id, "en", en, "kf_standard", desc, "kf_food"),
            )
            # 음식 설명도 검색 코퍼스에 편입 (챗봇이 음식 질문에 근거 인용 가능)
            con.execute(
                "INSERT INTO corpus_docs(source, lang, title, body, published, url) VALUES(?,?,?,?,?,?)",
                ("kf_food", "en", f"{name} ({en})", desc, "", PROVENANCE["kf_food"]["portal_url"]),
            )
            n += 1
    return n


def load_oda(con: sqlite3.Connection) -> int:
    f = find_one(OPENDATA, "*ODA용어사전*.csv")
    if not f:
        print("  [skip] ODA 용어사전 CSV 없음")
        return 0
    n = 0
    with f.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            ko = (row.get("한글명") or "").strip()
            en = (row.get("영문명") or "").strip()
            abbr = (row.get("약어") or "").strip()
            desc = (row.get("설명") or "").strip()
            if not ko or not en:
                continue
            rendering = f"{en} ({abbr})" if abbr else en
            cur = con.execute(
                "INSERT OR IGNORE INTO glossary_terms(term_ko, category, domain, definition_ko, source)"
                " VALUES(?,?,?,?,?)",
                (ko, "외교·개발협력", "oda", desc, "koica_oda"),
            )
            term_id = cur.lastrowid or con.execute(
                "SELECT id FROM glossary_terms WHERE term_ko=?", (ko,)
            ).fetchone()[0]
            con.execute(
                "INSERT INTO glossary_renderings(term_id, lang, rendering, strategy, gloss, source)"
                " VALUES(?,?,?,?,?,?)",
                (term_id, "en", rendering, "koica_standard", desc[:500], "koica_oda"),
            )
            n += 1
    return n


def load_archive(con: sqlite3.Connection) -> int:
    f = find_one(OPENDATA, "*디지털아카이브기사목록*.csv")
    if not f:
        print("  [skip] 디지털아카이브 CSV 없음")
        return 0
    n = 0
    with f.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            title = (row.get("게시물제목명") or "").strip()
            body = (row.get("내용") or "").strip()
            date = (row.get("게시일자") or "").strip()
            if not title:
                continue
            con.execute(
                "INSERT INTO corpus_docs(source, lang, title, body, published, url) VALUES(?,?,?,?,?,?)",
                ("kf_archive", "ko", title, body, date, PROVENANCE["kf_archive"]["portal_url"]),
            )
            n += 1
    return n


def load_curated(con: sqlite3.Connection) -> int:
    f = DERIVED / "cultural_terms_v0.json"
    if not f.exists():
        print("  [skip] 큐레이션 용어 없음")
        return 0
    data = json.loads(f.read_text(encoding="utf-8"))
    n = 0
    for t in data["terms"]:
        cur = con.execute(
            "INSERT OR IGNORE INTO glossary_terms(term_ko, category, domain, definition_ko, source)"
            " VALUES(?,?,?,?,?)",
            (t["term_ko"], t["category"], "culture", t["definition_ko"], "curated_v0"),
        )
        term_id = cur.lastrowid or con.execute(
            "SELECT id FROM glossary_terms WHERE term_ko=?", (t["term_ko"],)
        ).fetchone()[0]
        for lang, r in t["renderings"].items():
            con.execute(
                "INSERT INTO glossary_renderings(term_id, lang, rendering, strategy, gloss, source)"
                " VALUES(?,?,?,?,?,?)",
                (term_id, lang, r["text"], r["strategy"], t["definition_ko"], "curated_v0"),
            )
        con.execute(
            "INSERT INTO corpus_docs(source, lang, title, body, published, url) VALUES(?,?,?,?,?,?)",
            ("curated_v0", "ko", t["term_ko"], t["definition_ko"], "", ""),
        )
        n += 1
    return n


def load_koreana_pilot(con: sqlite3.Connection) -> int:
    if not KOREANA.exists():
        return 0
    n = 0
    for jl in sorted(KOREANA.glob("*.jsonl")):
        lang = jl.stem
        for line in jl.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("body_chars", 0) < 200:
                continue
            con.execute(
                "INSERT INTO corpus_docs(source, lang, title, body, published, url) VALUES(?,?,?,?,?,?)",
                ("koreana_pilot", lang, rec.get("title", ""), rec.get("body_text", ""), "", rec.get("url", "")),
            )
            n += 1
    return n


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.executescript(SCHEMA)
    counts = {
        "kf_food(음식 용어)": load_food(con),
        "koica_oda(ODA 용어)": load_oda(con),
        "kf_archive(RAG 기사)": load_archive(con),
        "curated_v0(문화 용어)": load_curated(con),
        "koreana_pilot(파일럿 기사)": load_koreana_pilot(con),
    }
    con.execute("INSERT INTO corpus_fts(rowid, title, body) SELECT id, title, body FROM corpus_docs")
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    for key, p in PROVENANCE.items():
        rc = con.execute(
            "SELECT count(*) FROM glossary_terms WHERE source=?", (key,)
        ).fetchone()[0] or con.execute(
            "SELECT count(*) FROM corpus_docs WHERE source=?", (key,)
        ).fetchone()[0]
        con.execute(
            "INSERT OR REPLACE INTO opendata_provenance VALUES(?,?,?,?,?,?,?)",
            (p["dataset_name"], p["provider"], p["portal_url"], p["license"], now, rc, p["used_for"]),
        )
    con.commit()
    for k, v in counts.items():
        print(f"  {k}: {v}건")
    total_terms = con.execute("SELECT count(*) FROM glossary_terms").fetchone()[0]
    total_rend = con.execute("SELECT count(*) FROM glossary_renderings").fetchone()[0]
    total_docs = con.execute("SELECT count(*) FROM corpus_docs").fetchone()[0]
    print(f"용어 {total_terms} / 대역 {total_rend} / 코퍼스 문서 {total_docs} → {DB_PATH}")
    con.close()


if __name__ == "__main__":
    main()
