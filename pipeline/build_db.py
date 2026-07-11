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
import re
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
DROP TABLE IF EXISTS glossary_evidence;
DROP TABLE IF EXISTS countries;
DROP TABLE IF EXISTS oda_projects;
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
  url TEXT,
  group_key TEXT                   -- 병렬 정렬 키 (Koreana: nttSn) — 동일 기사 언어판 묶음
);
CREATE VIRTUAL TABLE corpus_fts USING fts5(
  title, body, content='corpus_docs', content_rowid='id',
  tokenize='unicode61 remove_diacritics 2'
);
CREATE TABLE glossary_evidence (
  id INTEGER PRIMARY KEY,
  term_id INTEGER NOT NULL REFERENCES glossary_terms(id),
  doc_id INTEGER NOT NULL REFERENCES corpus_docs(id),
  lang TEXT NOT NULL,
  snippet TEXT
);
CREATE INDEX idx_ev_term ON glossary_evidence(term_id);
CREATE TABLE opendata_provenance (
  dataset_name TEXT PRIMARY KEY,
  provider TEXT, portal_url TEXT, license TEXT,
  fetched_at TEXT, record_count INTEGER, used_for TEXT,
  status TEXT                       -- live(적용) | approved_pending(승인·기록대기)
);
CREATE TABLE countries (
  iso2 TEXT, iso3 TEXT, name_ko TEXT, name_en TEXT
);
CREATE TABLE oda_projects (
  country_ko TEXT, country_iso TEXT, continent TEXT,
  kor_name TEXT, eng_name TEXT, year TEXT, agency TEXT
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
        "dataset_name": "K-Rosetta 큐레이션 문화용어",
        "provider": "K-Rosetta (Koreana 근거 연결)",
        "portal_url": "",
        "license": "자체 생성",
        "used_for": "핵심 문화용어 다국어 대역 + Koreana 원문 근거 연결",
    },
    "koreana_pilot": {
        "dataset_name": "한국국제교류재단 《Koreana》 다국어 아카이브",
        "provider": "한국국제교류재단(KF)",
        "portal_url": "https://www.koreana.or.kr",
        "license": "공개 웹진 — 파생 데이터만 활용, 원문 미재배포",
        "used_for": "문화용어 다국어 근거 코퍼스 + RAG 검색 대상",
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
    files = [DERIVED / "cultural_terms_v0.json", DERIVED / "cultural_terms_v1_add.json"]
    terms: list[dict] = []
    for f in files:
        if f.exists():
            terms += json.loads(f.read_text(encoding="utf-8"))["terms"]
    if not terms:
        print("  [skip] 큐레이션 용어 없음")
        return 0
    # ru 패치 병합 (v0 용어에 러시아어 대역 추가)
    patch_f = DERIVED / "ru_patch_v1.json"
    if patch_f.exists():
        patch = json.loads(patch_f.read_text(encoding="utf-8"))["renderings"]
        for t in terms:
            if "ru" not in t["renderings"] and t["term_ko"] in patch:
                t["renderings"]["ru"] = {"text": patch[t["term_ko"]], "strategy": "translit_gloss"}
    n = 0
    for t in terms:
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


_ISSUE_RE = re.compile(r"^\d{4}\s+(SPRING|SUMMER|AUTUMN|FALL|WINTER)$", re.I)
_LANG_MENU = {
    "korean", "english", "japanese", "chinese", "french", "german", "spanish",
    "russian", "arabic", "indonesia", "indonesian", "vietnamese", "한국어",
}


def _clean_koreana_body(body: str) -> tuple[str, str]:
    """앞부분 사이트 메뉴(호수 라벨 + 언어 목록)를 제거하고 (제목추정, 본문) 반환."""
    lines = [ln.strip() for ln in (body or "").splitlines()]
    i = 0
    while i < len(lines):
        ln = lines[i]
        if not ln or _ISSUE_RE.match(ln) or ln.lower() in _LANG_MENU or len(ln) <= 2:
            i += 1
            continue
        break
    rest = [ln for ln in lines[i:] if ln]
    if not rest:
        return "", ""
    title = rest[0]
    text = "\n".join(rest[1:]) if len(rest) > 1 else rest[0]
    return title, text


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
            clean_title, body = _clean_koreana_body(rec.get("body_text", ""))
            body = body or rec.get("body_text", "")
            if len(body) < 200:
                continue
            # 사이트명(og:title)은 무의미 → 본문에서 뽑은 실제 제목 우선
            raw_title = rec.get("title", "")
            title = clean_title if clean_title and "한국국제교류재단" not in clean_title else (
                clean_title or raw_title)
            con.execute(
                "INSERT INTO corpus_docs(source, lang, title, body, published, url, group_key)"
                " VALUES(?,?,?,?,?,?,?)",
                ("koreana_pilot", lang, title, body, "", rec.get("url", ""), rec.get("nttSn")),
            )
            n += 1
    return n


OPENDATA_API = ROOT / "data" / "pilot" / "opendata_api"

# 활용신청 승인 완료 오픈API 3종 (사용자 record_opendata_fixtures.py 실행 시 fixture 도착)
API_DATASETS = {
    "country_code": {
        "dataset_name": "외교부_국가·지역별 표준코드",
        "provider": "외교부", "portal_url": "https://www.data.go.kr/data/15075346/openapi.do",
        "license": "공공데이터포털 이용허락범위 준수(출처표시)",
        "used_for": "언어↔국가↔로케일 매핑 기준(오픈API)",
    },
    "univ_korname": {
        "dataset_name": "한국국제교류재단_해외대학 표준국문명칭",
        "provider": "한국국제교류재단(KF)", "portal_url": "https://www.data.go.kr/data/15075335/openapi.do",
        "license": "공공데이터포털 이용허락범위 준수(출처표시)",
        "used_for": "해외 기관명 표준 국문명칭 정규화(오픈API)",
    },
    "oda_business": {
        "dataset_name": "한국국제협력단_융합 KOICA-ODA·KF 공공외교 사업정보",
        "provider": "한국국제협력단(KOICA)·KF", "portal_url": "https://www.data.go.kr/data/15099215/openapi.do",
        "license": "공공데이터포털 이용허락범위 준수(출처표시)",
        "used_for": "국가별 공공외교·ODA 사업 컨텍스트(오픈API)",
    },
}


def _find_items(obj) -> list:
    """data.go.kr JSON 어디에 있든 item 배열을 재귀 탐색."""
    if isinstance(obj, dict):
        if "item" in obj:
            it = obj["item"]
            return it if isinstance(it, list) else [it]
        for v in obj.values():
            r = _find_items(v)
            if r:
                return r
    elif isinstance(obj, list):
        return obj
    return []


def load_opendata_api(con: sqlite3.Connection) -> dict:
    """오픈API 응답 fixture가 있으면 로드(적용), 없으면 승인·대기 상태로 기록."""
    status = {}
    for key, meta in API_DATASETS.items():
        f = OPENDATA_API / f"{key}.json"
        if f.exists():
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                items = _find_items(data)
            except Exception:  # noqa: BLE001
                items = []
            status[key] = ("live", len(items))
            _load_api_items(con, key, items)
        else:
            status[key] = ("approved_pending", 0)
    return status


# 국가 ISO2 → 서비스 지원 언어 (현지어 대역 부여용)
_ISO2_LANG = {"VN": "vi", "ID": "id", "RU": "ru"}


def _load_api_items(con: sqlite3.Connection, key: str, items: list) -> None:
    def g(it, *ks):
        return next((str(it[k]).strip() for k in ks if it.get(k)), "")

    if key == "country_code":
        for it in items:
            if isinstance(it, dict):
                con.execute(
                    "INSERT INTO countries(iso2, iso3, name_ko, name_en) VALUES(?,?,?,?)",
                    (g(it, "country_iso_alp2", "iso_alp2"), g(it, "iso_alp3"),
                     g(it, "country_nm"), g(it, "country_eng_nm")))
    elif key == "univ_korname":
        # 해외대학 표준 국문명칭 → 기관명 번역 정규화 용어로 편입(도메인=institution)
        for it in items:
            if not isinstance(it, dict):
                continue
            ko = g(it, "univ_nm")          # 껀터대학교
            en = g(it, "univ_eng_nm")      # Can Tho University
            loc = g(it, "univ_loc_nm")     # Trường Đại học Cần Thơ (현지어)
            iso2 = g(it, "country_iso_alp2")
            country = g(it, "country_nm")
            if not ko or not en:
                continue
            cur = con.execute(
                "INSERT OR IGNORE INTO glossary_terms(term_ko, category, domain, definition_ko, source)"
                " VALUES(?,?,?,?,?)",
                (ko, f"기관명({country})", "institution",
                 f"{country} 소재 대학의 외교부·KF 표준 국문명칭", "univ_korname"))
            tid = cur.lastrowid or con.execute(
                "SELECT id FROM glossary_terms WHERE term_ko=?", (ko,)).fetchone()[0]
            con.execute(
                "INSERT INTO glossary_renderings(term_id, lang, rendering, strategy, gloss, source)"
                " VALUES(?,?,?,?,?,?)",
                (tid, "en", en, "kf_standard", "", "univ_korname"))
            lang = _ISO2_LANG.get(iso2)
            if lang and loc:
                con.execute(
                    "INSERT INTO glossary_renderings(term_id, lang, rendering, strategy, gloss, source)"
                    " VALUES(?,?,?,?,?,?)",
                    (tid, lang, loc, "local_official", "", "univ_korname"))
    elif key == "oda_business":
        for it in items:
            if isinstance(it, dict):
                con.execute(
                    "INSERT INTO oda_projects(country_ko, country_iso, continent, kor_name, eng_name, year, agency)"
                    " VALUES(?,?,?,?,?,?,?)",
                    (g(it, "country_nm"), g(it, "country_iso_alp2"), g(it, "continent_nm"),
                     g(it, "kor_business_nm"), g(it, "eng_business_nm"),
                     g(it, "business_year"), g(it, "business_type_cd_nm")))


def koreana_parallel_stats(con: sqlite3.Connection) -> dict:
    """동일 기사(nttSn)가 몇 개 언어판에 존재하는지 — 병렬 코퍼스 입증 지표."""
    rows = con.execute(
        "SELECT group_key, count(DISTINCT lang) c FROM corpus_docs"
        " WHERE source='koreana_pilot' AND group_key IS NOT NULL GROUP BY group_key"
    ).fetchall()
    if not rows:
        return {}
    multi = sum(1 for r in rows if r["c"] >= 2)
    return {"total_articles": sum(1 for _ in rows), "parallel_2plus": multi,
            "max_langs": max(r["c"] for r in rows)}


def _snippet(body: str, needle: str, width: int = 70) -> str:
    i = body.find(needle)
    if i < 0:
        return body[:width * 2]
    s, e = max(0, i - width), min(len(body), i + len(needle) + width)
    return ("…" if s > 0 else "") + body[s:e] + ("…" if e < len(body) else "")


def link_evidence(con: sqlite3.Connection) -> int:
    """문화 용어 ↔ 근거 기사 자동 연결.

    - 한국어 문서(kf_archive, koreana_pilot ko판): 용어 원문 매칭
    - 외국어 문서(koreana_pilot 타 언어판): 대역의 음차 헤드(예: 'pansori') 매칭
    Koreana 파일럿 코퍼스가 도착하면 재빌드만으로 다국어 근거가 자동 확장된다.
    """
    n = 0
    terms = con.execute(
        "SELECT id, term_ko FROM glossary_terms WHERE domain='culture'"
    ).fetchall()
    for t in terms:
        # 한국어 근거 (제목 우선, 최대 3건)
        rows = con.execute(
            """SELECT id, title, body FROM corpus_docs
               WHERE source IN ('kf_archive','koreana_pilot') AND lang='ko'
                 AND (title LIKE '%'||?||'%' OR body LIKE '%'||?||'%')
               ORDER BY (title LIKE '%'||?||'%') DESC LIMIT 3""",
            (t["term_ko"], t["term_ko"], t["term_ko"]),
        ).fetchall()
        for r in rows:
            con.execute(
                "INSERT INTO glossary_evidence(term_id, doc_id, lang, snippet) VALUES(?,?,?,?)",
                (t["id"], r["id"], "ko", _snippet(r["body"] or r["title"], t["term_ko"])),
            )
            n += 1
        # 외국어 근거 (Koreana 파일럿 언어판 — 음차 헤드 매칭)
        for rend in con.execute(
            "SELECT lang, rendering FROM glossary_renderings WHERE term_id=?", (t["id"],)
        ).fetchall():
            head = rend["rendering"].split("(")[0].strip()
            if len(head) < 3:
                continue
            for r in con.execute(
                """SELECT id, title, body FROM corpus_docs
                   WHERE source='koreana_pilot' AND lang=? AND body LIKE '%'||?||'%' LIMIT 2""",
                (rend["lang"], head),
            ).fetchall():
                con.execute(
                    "INSERT INTO glossary_evidence(term_id, doc_id, lang, snippet) VALUES(?,?,?,?)",
                    (t["id"], r["id"], rend["lang"], _snippet(r["body"], head)),
                )
                n += 1
    return n


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    counts = {
        "kf_food(음식 용어)": load_food(con),
        "koica_oda(ODA 용어)": load_oda(con),
        "kf_archive(RAG 기사)": load_archive(con),
        "curated_v0(문화 용어)": load_curated(con),
        "koreana_pilot(파일럿 기사)": load_koreana_pilot(con),
    }
    con.execute("INSERT INTO corpus_fts(rowid, title, body) SELECT id, title, body FROM corpus_docs")
    counts["glossary_evidence(용어→근거 연결)"] = link_evidence(con)
    api_status = load_opendata_api(con)
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    for key, p in PROVENANCE.items():
        rc = con.execute(
            "SELECT count(*) FROM glossary_terms WHERE source=?", (key,)
        ).fetchone()[0] or con.execute(
            "SELECT count(*) FROM corpus_docs WHERE source=?", (key,)
        ).fetchone()[0]
        con.execute(
            "INSERT OR REPLACE INTO opendata_provenance VALUES(?,?,?,?,?,?,?,?)",
            (p["dataset_name"], p["provider"], p["portal_url"], p["license"], now, rc,
             p["used_for"], "live"),
        )
    for key, meta in API_DATASETS.items():
        st, rc = api_status.get(key, ("approved_pending", 0))
        con.execute(
            "INSERT OR REPLACE INTO opendata_provenance VALUES(?,?,?,?,?,?,?,?)",
            (meta["dataset_name"], meta["provider"], meta["portal_url"], meta["license"],
             now, rc, meta["used_for"], st),
        )
    counts["opendata_api(오픈API 상태)"] = ", ".join(f"{k}:{v[0]}" for k, v in api_status.items())
    con.commit()
    for k, v in counts.items():
        print(f"  {k}: {v}건")
    total_terms = con.execute("SELECT count(*) FROM glossary_terms").fetchone()[0]
    total_rend = con.execute("SELECT count(*) FROM glossary_renderings").fetchone()[0]
    total_docs = con.execute("SELECT count(*) FROM corpus_docs").fetchone()[0]
    print(f"용어 {total_terms} / 대역 {total_rend} / 코퍼스 문서 {total_docs} → {DB_PATH}")
    ps = koreana_parallel_stats(con)
    if ps:
        print(f"Koreana 병렬: 기사 {ps['total_articles']}개, 2개 언어판+ {ps['parallel_2plus']}개, "
              f"최대 {ps['max_langs']}개 언어판")
    con.close()


if __name__ == "__main__":
    main()
