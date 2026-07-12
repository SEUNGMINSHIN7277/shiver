"""K-Rosetta 자체 완결형(오프라인) 데모 번들 생성.

실행 중인 데모 서버(localhost:8777)와 DB를 읽어, 프리셋 응답 + 용어사전을
단일 JS 번들로 임베드한 self-contained HTML을 만든다. Artifact로 게시해
사용자가 브라우저에서 직접 클릭·조작할 수 있게 한다.
"""
from __future__ import annotations

import json
import sqlite3
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8777"
ROOT = Path(__file__).resolve().parents[1]
FE = ROOT / "frontend"
DB = ROOT / "data" / "krosetta.db"
LANGS = ["en", "vi", "id", "ar", "ru"]


def api_get(path: str) -> dict:
    with urllib.request.urlopen(f"{BASE}{path}", timeout=20) as r:
        return json.load(r)


def api_post(path: str, body: dict) -> dict:
    req = urllib.request.Request(
        f"{BASE}{path}", data=json.dumps(body).encode(),
        headers={"content-type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def norm(s: str) -> str:
    return " ".join(s.split()).strip()


def build_bundle() -> dict:
    scenarios = api_get("/api/demo/scenarios")
    health = api_get("/api/health")
    benchmark = api_get("/api/benchmark/summary")

    # 프리셋 번역: 각 시나리오 × 5개 언어 프리페치 (키: norm(text)|lang)
    translations: dict[str, dict] = {}
    for s in scenarios["scenarios"]:
        for lang in LANGS:
            resp = api_post("/api/translate", {
                "text": s["source"], "target_lang": lang,
                "domain": s.get("domain", "general")})
            translations[f"{norm(s['source'])}|{lang}"] = resp

    # 챗봇 프리셋 질문 (칩 4개 + 자주 물을 법한 것들)
    chat_qs = [
        "판소리가 뭐야?", "What is pansori?", "Hanji là gì?", "Apa itu gimjang?",
        "Tell me about hanji paper craft", "김치가 뭐야?", "온돌이 뭐야?",
        "What is hanbok?", "떡국에 대해 알려줘", "Что такое ондоль?",
    ]
    chats: dict[str, dict] = {}
    for q in chat_qs:
        chats[norm(q).lower()] = api_post("/api/chat", {"message": q})

    # 용어사전 export (임의 입력 클라이언트측 탐지용) — _term_card 구조 재현
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    label_map = {
        "kf_food": "KF 한국음식정보 (공공데이터포털 15044203)",
        "koica_oda": "KOICA ODA 용어사전 (공공데이터포털 15052909)",
        "curated_v0": "K-Rosetta 문화용어 (Koreana 근거 연결)",
        "univ_korname": "KF 해외대학 표준국문명칭 (공공데이터포털 15075335)",
    }
    evi_label = {"kf_archive": "KF 디지털 아카이브", "koreana_pilot": "Koreana"}

    terms = []
    for t in con.execute(
        "SELECT id, term_ko, category, domain, definition_ko, source FROM glossary_terms"
    ):
        rends = {
            r["lang"]: {"rendering": r["rendering"], "strategy": r["strategy"]}
            for r in con.execute(
                "SELECT lang, rendering, strategy FROM glossary_renderings WHERE term_id=?",
                (t["id"],))
        }
        if not rends:
            continue
        evidence = [
            {"lang": e["lang"], "title": e["title"], "snippet": e["snippet"],
             "source_label": evi_label.get(e["source"], e["source"]),
             "published": e["published"]}
            for e in con.execute(
                "SELECT e.lang, e.snippet, d.title, d.source, d.published "
                "FROM glossary_evidence e JOIN corpus_docs d ON d.id=e.doc_id "
                "WHERE e.term_id=? LIMIT 2", (t["id"],))
        ]
        terms.append({
            "term_ko": t["term_ko"], "category": t["category"], "domain": t["domain"],
            "definition_ko": (t["definition_ko"] or "")[:160], "source": t["source"],
            "source_label": label_map.get(t["source"], t["source"]),
            "rendings": rends, "evidence": evidence,
        })
    con.close()
    terms.sort(key=lambda x: len(x["term_ko"]), reverse=True)  # longest-match 우선

    return {
        "scenarios": scenarios, "health": health, "benchmark": benchmark,
        "translations": translations, "chats": chats, "terms": terms,
    }


def build_html(bundle: dict) -> str:
    css = (FE / "styles.css").read_text(encoding="utf-8")
    app = (FE / "app.js").read_text(encoding="utf-8")
    body = (FE / "index.html").read_text(encoding="utf-8")
    # <body>...</body> 사이만 추출 (artifact는 head/body 스켈레톤을 씌움)
    inner = body.split("<body>", 1)[1].split("</body>", 1)[0]
    inner = inner.replace('<script src="app.js"></script>', "")

    shim = SHIM_TEMPLATE.replace("__BUNDLE__", json.dumps(bundle, ensure_ascii=False))
    return (
        f"<title>K-Rosetta 데모 — 한국 문화를 세계 언어로, 정확하게</title>\n"
        f"<style>\n{css}\n</style>\n"
        f"{inner}\n"
        f"<script>\n{shim}\n</script>\n"
        f"<script>\n{app}\n</script>\n"
    )


# fetch() 셰임: 임베드 번들로 /api/* 응답을 대신 반환
SHIM_TEMPLATE = r"""
const KR = __BUNDLE__;
const _norm = (s) => (s || "").split(/\s+/).join(" ").trim();

function detectTermsClient(text, lang) {
  const found = [], used = [];
  for (const t of KR.terms) {
    const tk = t.term_ko;
    let idx = text.indexOf(tk);
    while (idx !== -1) {
      const span = [idx, idx + tk.length];
      if (!used.some((u) => span[0] < u[1] && u[0] < span[1])) {
        used.push(span);
        const r = t.rendings[lang] || t.rendings["en"];
        const fallback = !t.rendings[lang] && !!t.rendings["en"];
        found.push({
          evidence: t.evidence || [],
          term_ko: t.term_ko,
          subtitle_form: r ? String(r.rendering).split("(")[0].trim() : null,
          category: t.category, domain: t.domain, definition_ko: t.definition_ko,
          rendering: r ? r.rendering : null, strategy: r ? r.strategy : null,
          fallback_to_en: fallback, source: t.source, source_label: t.source_label,
          _pos: idx,
        });
        break;
      }
      idx = text.indexOf(tk, idx + 1);
    }
  }
  return found.sort((a, b) => a._pos - b._pos);
}

const _origFetch = window.fetch;
window.fetch = async function (url, opts) {
  const u = typeof url === "string" ? url : url.url;
  const body = opts && opts.body ? JSON.parse(opts.body) : {};
  const J = (o) => ({ ok: true, json: async () => o });

  if (u.includes("/api/demo/scenarios")) return J(KR.scenarios);
  if (u.includes("/api/health")) return J(KR.health);
  if (u.includes("/api/benchmark/summary")) return J(KR.benchmark);

  if (u.includes("/api/translate")) {
    const key = `${_norm(body.text)}|${body.target_lang}`;
    if (KR.translations[key]) return J(KR.translations[key]);
    const cards = detectTermsClient(body.text, body.target_lang);
    return J({
      mode: "glossary_only", translation: null, baseline: null, terms: cards,
      notice: cards.length
        ? "입력 문장에서 문화 용어를 탐지해 표준 대역 카드를 표시합니다. 전문 완역은 프리셋 문장(예시 칩)에서 시연되며, 임의 문장 완역은 라이브(유료) 모드에서 활성화됩니다."
        : "탐지된 문화 용어가 없습니다. 예시 칩의 문장을 눌러 전문 번역 비교를 확인해 보세요.",
    });
  }

  if (u.includes("/api/chat")) {
    const key = _norm(body.message).toLowerCase();
    if (KR.chats[key]) return J(KR.chats[key]);
    const terms = detectTermsClient(body.message, "en");
    let answer, citations = [];
    if (terms.length) {
      const t0 = terms[0];
      answer = `'${t0.term_ko}' — ${t0.rendering || ""}\n(${t0.definition_ko})\n\n(추출형 응답 — 근거 문서를 함께 확인하세요. 자유 질문 생성형 답변은 라이브 모드에서 제공됩니다.)`;
      citations = (t0.evidence || []).map((e) => ({
        title: e.title, snippet: e.snippet, source: e.source_label, published: e.published,
      }));
    } else {
      answer = "코퍼스에서 관련 근거를 찾지 못했습니다. 예시 칩(판소리·한지·김장 등)으로 질문해 보세요.";
    }
    return J({ mode: "extractive", lang: "ko", answer, citations,
               term_refs: terms.slice(0, 5).map((t) => t.term_ko) });
  }

  return _origFetch(url, opts);
};
"""


def main() -> None:
    bundle = build_bundle()
    html = build_html(bundle)
    out = ROOT / "docs" / "demo_standalone.html"
    out.write_text(html, encoding="utf-8")
    kb = len(html.encode()) // 1024
    print(f"용어 {len(bundle['terms'])}개 · 번역 프리셋 {len(bundle['translations'])} · "
          f"챗 {len(bundle['chats'])} → {out} ({kb} KB)")


if __name__ == "__main__":
    main()
