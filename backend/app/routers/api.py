"""K-Rosetta API 라우터 (v0)."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..config import REPO_ROOT, get_settings
from ..db import get_db
from ..services.llm import engine
from ..services.retrieval.search import search_corpus
from ..services.termdetect import detect_terms

router = APIRouter(prefix="/api")

SUPPORTED_TARGETS = ["en", "vi", "id", "ar", "ru"]


class TranslateReq(BaseModel):
    text: str = Field(min_length=1, max_length=3000)
    target_lang: str = "en"
    domain: str = "general"  # general | subtitle (자막·대사 모드: 첫 등장 음차+주석, 재등장 음차만)


class ChatReq(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


def _subtitle_form(rendering: str | None) -> str | None:
    """자막 모드: 재등장 시 사용할 짧은 형태(음차 헤드)를 추출."""
    if not rendering:
        return None
    return rendering.split("(")[0].strip()


def _term_evidence(term_id: int) -> list[dict]:
    con = get_db()
    rows = con.execute(
        """SELECT e.lang, e.snippet, d.title, d.source, d.published, d.url
           FROM glossary_evidence e JOIN corpus_docs d ON d.id = e.doc_id
           WHERE e.term_id=? LIMIT 4""",
        (term_id,),
    ).fetchall()
    label = {"kf_archive": "KF 디지털 아카이브", "koreana_pilot": "Koreana"}
    return [
        {"lang": r["lang"], "title": r["title"], "snippet": r["snippet"],
         "source_label": label.get(r["source"], r["source"]),
         "published": r["published"], "url": r["url"]}
        for r in rows
    ]


def _term_card(t: dict) -> dict:
    r = t.get("rendering") or {}
    return {
        "evidence": _term_evidence(t["id"]) if t.get("id") else [],
        "term_ko": t["term_ko"],
        "subtitle_form": _subtitle_form(r.get("rendering")),
        "category": t["category"],
        "domain": t["domain"],
        "definition_ko": t["definition_ko"],
        "rendering": r.get("rendering"),
        "strategy": r.get("strategy"),
        "fallback_to_en": t.get("fallback_to_en", False),
        "source": t["source"],
        "source_label": {
            "kf_food": "KF 한국음식정보 (공공데이터포털 15044203)",
            "koica_oda": "KOICA ODA 용어사전 (공공데이터포털 15052909)",
            "curated_v0": "K-Rosetta 문화용어 v0 (Koreana 정렬 예정)",
        }.get(t["source"], t["source"]),
    }


@router.post("/translate")
def translate(req: TranslateReq) -> dict:
    if req.target_lang not in SUPPORTED_TARGETS:
        raise HTTPException(400, f"target_lang must be one of {SUPPORTED_TARGETS}")
    con = get_db()
    terms = detect_terms(con, req.text, req.target_lang)
    cards = [_term_card(t) for t in terms]

    cached = engine.cached_translation(req.text, req.target_lang)
    if cached:
        return {"mode": "cached", **cached, "terms": cards}
    if engine.live_available():
        result = engine.live_translate(req.text, req.target_lang, terms)
        return {"mode": "live", **result, "terms": cards}
    return {
        "mode": "glossary_only",
        "translation": None,
        "baseline": None,
        "terms": cards,
        "notice": "데모 v0는 프리셋 문장의 전문 번역을 제공합니다. 임의 문장은 문화용어 탐지·표준 대역 카드가 제공되며, 전문 번역은 라이브 모드에서 활성화됩니다.",
    }


@router.get("/demo/scenarios")
def scenarios() -> dict:
    return {"scenarios": engine.demo_scenarios(), "targets": SUPPORTED_TARGETS}


@router.post("/chat")
def chat(req: ChatReq) -> dict:
    con = get_db()
    lang = engine.detect_lang(req.message)
    preset = engine.cached_chat(req.message)
    # 용어사전 역인덱스: 질문 속 로마자 용어(pansori 등)를 한국어 용어로 확장해 검색 recall 확보
    extra = []
    q_lower = req.message.lower()
    for row in con.execute(
        "SELECT t.term_ko, r.rendering FROM glossary_terms t JOIN glossary_renderings r ON r.term_id=t.id"
        " WHERE t.domain='culture' AND r.lang='en'"
    ):
        head = row["rendering"].split("(")[0].strip().lower()
        if head and head in q_lower:
            extra.append(row["term_ko"])
    hits = search_corpus(con, req.message, extra_terms=extra, k=4)
    citations = [
        {"title": h["title"], "snippet": h["snippet"], "source": h["source"],
         "published": h["published"], "url": h["url"]}
        for h in hits
    ]
    if preset:
        return {"mode": "cached", "lang": preset["lang"], "answer": preset["answer"],
                "citations": citations, "term_refs": preset.get("term_refs", [])}
    terms = detect_terms(con, req.message, "en")
    for ko in extra:
        row = con.execute(
            "SELECT t.*, r.rendering, r.gloss FROM glossary_terms t JOIN glossary_renderings r"
            " ON r.term_id=t.id AND r.lang='en' WHERE t.term_ko=?", (ko,)
        ).fetchone()
        if row and all(t["term_ko"] != ko for t in terms):
            terms.append({**dict(row), "rendering": {"rendering": row["rendering"]},
                          "position": 0, "fallback_to_en": False})
    if terms:
        t0 = terms[0]
        if lang == "ko":
            lead = t0["definition_ko"]
        else:
            # 질문 언어의 대역(음차+현지어 설명)을 우선 사용 — 다국어 카드 응답
            q_lang = lang if lang in SUPPORTED_TARGETS else "en"
            rends = {
                r["lang"]: r["rendering"]
                for r in con.execute(
                    "SELECT lang, rendering FROM glossary_renderings WHERE term_id=?", (t0["id"],)
                )
            } if "id" in t0 else {}
            lead = rends.get(q_lang) or (t0.get("rendering") or {}).get("rendering", "")
        answer = (
            f"'{t0['term_ko']}' — {lead}"
            + ("" if lang == "ko" else f"\n({t0['definition_ko']})")
            + "\n\n(추출형 응답 — 아래 근거 문서를 함께 확인하세요. 자유 질문 생성형 답변은 라이브 모드에서 제공됩니다.)"
        )
    elif citations:
        answer = "질문과 관련된 근거 문서를 찾았습니다. 아래 출처를 확인하세요.\n(생성형 답변은 라이브 모드에서 제공됩니다.)"
    else:
        answer = "코퍼스에서 관련 근거를 찾지 못했습니다. 다른 문화 키워드로 질문해 보세요."
    return {"mode": "extractive", "lang": lang, "answer": answer, "citations": citations,
            "term_refs": [t["term_ko"] for t in terms[:5]]}


@router.get("/glossary/search")
def glossary_search(q: str, lang: str = "en", limit: int = 20) -> dict:
    con = get_db()
    like = f"%{q}%"
    rows = con.execute(
        """SELECT t.term_ko, t.category, t.domain, t.definition_ko, t.source,
                  r.lang, r.rendering, r.strategy
           FROM glossary_terms t JOIN glossary_renderings r ON r.term_id = t.id
           WHERE (t.term_ko LIKE ? OR r.rendering LIKE ?) AND r.lang = ?
           ORDER BY length(t.term_ko) LIMIT ?""",
        (like, like, lang, limit),
    ).fetchall()
    return {"results": [dict(r) for r in rows]}


@router.get("/benchmark/summary")
def benchmark_summary() -> dict:
    p = REPO_ROOT / "data" / "pilot" / "derived" / "benchmark_v0.json"
    if not p.exists():
        raise HTTPException(404, "벤치마크 v0 미생성")
    return json.loads(p.read_text(encoding="utf-8"))


@router.get("/health")
def health() -> dict:
    con = get_db()
    prov = [dict(r) for r in con.execute("SELECT * FROM opendata_provenance").fetchall()]
    counts = {
        "glossary_terms": con.execute("SELECT count(*) FROM glossary_terms").fetchone()[0],
        "glossary_renderings": con.execute("SELECT count(*) FROM glossary_renderings").fetchone()[0],
        "corpus_docs": con.execute("SELECT count(*) FROM corpus_docs").fetchone()[0],
    }
    return {"status": "ok", "demo_mode": get_settings().demo_mode,
            "counts": counts, "opendata_provenance": prov}
