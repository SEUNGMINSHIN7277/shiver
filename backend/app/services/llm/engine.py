"""번역·챗 엔진 추상화.

DEMO_MODE=cached (기본, 비용 0원 — CLAUDE.md §3.5):
  - 프리셋 시나리오는 사전 생성된 고품질 결과를 서빙
  - 그 외 입력은 용어사전 탐지 + 검색 기반 추출형 응답으로 폴백 (LLM 미호출)
DEMO_MODE=live: Anthropic API 사용 (키·사용자 승인 필요 — 코드 골격만, S0에서는 미사용)
"""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from ...config import REPO_ROOT, get_settings

CACHE_DIR = REPO_ROOT / "data" / "demo_cache"

LANG_NAMES = {"en": "영어", "vi": "베트남어", "id": "인도네시아어", "ar": "아랍어", "ko": "한국어"}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", s)).strip().lower()


@lru_cache(maxsize=1)
def _translations() -> dict:
    p = CACHE_DIR / "translations.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"scenarios": []}


@lru_cache(maxsize=1)
def _chats() -> dict:
    p = CACHE_DIR / "chats.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"presets": []}


def demo_scenarios() -> list[dict]:
    return [
        {"id": s["id"], "label": s["label"], "source": s["source"],
         "domain": s.get("domain", "general"), "targets": sorted(s["targets"].keys())}
        for s in _translations()["scenarios"]
    ]


def cached_translation(text: str, target_lang: str) -> dict | None:
    key = _norm(text)
    for s in _translations()["scenarios"]:
        if _norm(s["source"]) == key and target_lang in s["targets"]:
            t = s["targets"][target_lang]
            return {"translation": t["krosetta"], "baseline": t.get("vanilla"),
                    "scenario_id": s["id"], "domain": s.get("domain", "general")}
    return None


def cached_chat(question: str) -> dict | None:
    key = _norm(question)
    for p in _chats()["presets"]:
        if any(kw in key for kw in p["match_keywords"]) or _norm(p["question"]) == key:
            return p
    return None


def detect_lang(text: str) -> str:
    # 한글 용어가 섞인 외국어 질문("Что такое 온돌?")이 흔하므로 비한글 문자를 먼저 판정
    if re.search(r"[؀-ۿ]", text):
        return "ar"
    if re.search(r"[А-яЁё]", text):
        return "ru"
    hangul = len(re.findall(r"[가-힣]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    if hangul and hangul >= latin:
        return "ko"
    if re.search(r"[ăâđêôơưĂÂĐÊÔƠƯàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ]", text):
        return "vi"
    words = set(re.findall(r"[a-z]+", text.lower()))
    if words & {"apa", "yang", "adalah", "bagaimana", "kenapa", "dimana", "siapa"}:
        return "id"
    return "en"


def live_available() -> bool:
    st = get_settings()
    return st.demo_mode == "live" and bool(st.anthropic_api_key)


def live_translate(text: str, target_lang: str, term_context: list[dict]) -> dict:
    """DEMO_MODE=live 전용 (S0에서는 호출되지 않음 — 비용 0원 원칙)."""
    import anthropic  # 지연 임포트: cached 모드에서는 의존성 불필요

    client = anthropic.Anthropic()
    glossary_block = "\n".join(
        f"- {t['term_ko']} → {t['rendering']['rendering']}" for t in term_context if t.get("rendering")
    )
    system = (
        "You are K-Rosetta, a Korean cultural localization engine built on 39 years of KF Koreana "
        "parallel corpora. Translate faithfully. For each cultural term below, you MUST use the "
        "given standard rendering (transliteration + short gloss convention).\n"
        f"Glossary:\n{glossary_block}"
    )
    resp = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=2000,
        thinking={"type": "adaptive"},
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": f"Translate into {LANG_NAMES.get(target_lang, target_lang)}:\n{text}"}],
    )
    out = next(b.text for b in resp.content if b.type == "text")
    return {"translation": out, "baseline": None, "scenario_id": None}
