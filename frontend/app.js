/* K-Rosetta demo SPA */
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const esc = (s) => (s || "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

/* ---- tabs ---- */
$$(".tab").forEach((t) =>
  t.addEventListener("click", () => {
    $$(".tab").forEach((x) => x.classList.remove("active"));
    $$(".view").forEach((v) => v.classList.remove("active"));
    t.classList.add("active");
    $("#view-" + t.dataset.view).classList.add("active");
    if (t.dataset.view === "benchmark") loadBenchmark();
  })
);

/* ---- language / domain segmented controls ---- */
let targetLang = "en";
let domain = "general";
$$("#lang-seg .seg-btn").forEach((b) =>
  b.addEventListener("click", () => {
    $$("#lang-seg .seg-btn").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    targetLang = b.dataset.lang;
  })
);
function setDomain(d) {
  domain = d;
  $$("#domain-seg .seg-btn").forEach((x) => x.classList.toggle("active", x.dataset.domain === d));
}
$$("#domain-seg .seg-btn").forEach((b) => b.addEventListener("click", () => setDomain(b.dataset.domain)));

/* ---- presets ---- */
async function loadScenarios() {
  const r = await fetch("/api/demo/scenarios").then((r) => r.json());
  const box = $("#preset-chips");
  box.innerHTML = "";
  r.scenarios.forEach((s) => {
    const c = document.createElement("button");
    c.className = "chip";
    c.textContent = s.label;
    c.title = s.source;
    c.addEventListener("click", () => {
      $("#src-text").value = s.source;
      setDomain(s.domain || "general");
      doTranslate();
    });
    box.appendChild(c);
  });
}

/* ---- translate ---- */
async function doTranslate() {
  const text = $("#src-text").value.trim();
  if (!text) return;
  const btn = $("#btn-translate");
  btn.disabled = true; btn.textContent = "번역 중…";
  try {
    const d = await fetch("/api/translate", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ text, target_lang: targetLang, domain }),
    }).then((r) => r.json());
    renderTranslation(d);
  } finally {
    btn.disabled = false; btn.textContent = "번역";
  }
}
$("#btn-translate").addEventListener("click", doTranslate);

/* 번역문 안에서 표준 대역(음차 헤드)을 하이라이트 */
function highlightTerms(text, terms) {
  let html = esc(text);
  const heads = terms
    .map((t) => t.subtitle_form)
    .filter(Boolean)
    .sort((a, b) => b.length - a.length);
  for (const h of heads) {
    const re = new RegExp(h.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi");
    html = html.replace(re, (m) => `<mark class="term-hl">${m}</mark>`);
  }
  return html;
}

function renderTranslation(d) {
  $("#translate-result").classList.remove("hidden");
  const grid = $("#result-grid");
  const compare = $("#compare-toggle").checked && d.baseline;
  grid.className = "result-grid" + (compare ? " compare" : "");
  let html = "";
  if (d.translation) {
    const mode = d.domain === "subtitle" ? " · 자막 모드" : "";
    html += `<div class="result-card"><span class="tag ours">K-Rosetta · 용어사전 적용${mode}</span><p>${highlightTerms(d.translation, d.terms)}</p></div>`;
    if (compare)
      html += `<div class="result-card"><span class="tag base">일반 번역기 · 용어사전 미적용</span><p>${esc(d.baseline)}</p></div>`;
  } else {
    html += `<div class="notice">${esc(d.notice || "")}</div>`;
  }
  grid.innerHTML = html;

  $("#term-count").textContent = d.terms.length ? `${d.terms.length}개 탐지` : "탐지된 용어 없음";
  $("#term-cards").innerHTML = d.terms
    .map(
      (t) => `<div class="term-card">
        <span class="t-ko">${esc(t.term_ko)}</span><span class="t-cat">${esc(t.category || "")}</span>
        <div class="t-rend">${esc(t.rendering || "—")}</div>
        <div class="t-def">${esc((t.definition_ko || "").slice(0, 90))}</div>
        ${t.fallback_to_en ? '<div class="t-fallback">※ 선택 언어 대역 준비 중 — 영문 표준 표시</div>' : ""}
        ${(t.evidence || [])
          .slice(0, 2)
          .map((e) => `<div class="t-evi" title="${esc(e.snippet || "")}">📖 ${esc(e.title)} <span class="muted">· ${esc(e.source_label)}${e.published ? " · " + esc(e.published) : ""}</span></div>`)
          .join("")}
        <span class="t-src">${esc(t.source_label)}</span>
      </div>`
    )
    .join("");
}

/* ---- chat ---- */
function addMsg(cls, text, citations) {
  const log = $("#chat-log");
  const m = document.createElement("div");
  m.className = "msg " + cls;
  m.textContent = text;
  if (citations && citations.length) {
    const c = document.createElement("div");
    c.className = "cites";
    c.innerHTML = citations
      .map(
        (x) =>
          `<span class="cite">📄 <b>${esc(x.title)}</b>${x.published ? " · " + esc(x.published) : ""} — ${x.snippet || ""}</span>`
      )
      .join("");
    m.appendChild(c);
  }
  log.appendChild(m);
  log.scrollTop = log.scrollHeight;
}
async function doChat(q) {
  const text = (q || $("#chat-text").value).trim();
  if (!text) return;
  $("#chat-text").value = "";
  addMsg("user", text);
  const d = await fetch("/api/chat", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ message: text }),
  }).then((r) => r.json());
  addMsg("bot", d.answer, d.citations);
}
$("#btn-chat").addEventListener("click", () => doChat());
$("#chat-text").addEventListener("keydown", (e) => e.key === "Enter" && doChat());
$$("#chat-chips .chip").forEach((c) => c.addEventListener("click", () => doChat(c.dataset.q)));

/* ---- benchmark ---- */
let benchData = null;
const LANG_LABEL = { en: "영어", vi: "베트남어", id: "인도네시아어", ru: "러시아어" };
function renderBenchRows(langFilter) {
  const rows = benchData.cases.filter((c) => langFilter === "all" || c.lang === langFilter);
  $("#bench-lang-note").textContent =
    langFilter === "all"
      ? `${rows.length}케이스 (4개 언어)`
      : `${LANG_LABEL[langFilter]} ${rows.length}케이스 · 일반 번역기 충실도 ${Math.round(benchData.summary.vanilla_fidelity_by_lang[langFilter] * 100)}%`;
  $("#bench-table tbody").innerHTML = rows
    .map(
      (c) => `<tr>
      <td><b>${esc(c.term_ko)}</b> <span class="muted">${c.lang.toUpperCase()}</span><br/><span class="muted">${esc(c.category || "")}</span></td>
      <td class="std">${esc(c.standard)}<br/><span class="muted">${esc(c.standard_source)}</span></td>
      <td>${esc(c.vanilla)}<br/><span class="muted">${esc(c.note)}</span></td>
      <td><span class="verdict ${c.vanilla_verdict}">${{ match: "일치", partial: "부분", miss: "불일치" }[c.vanilla_verdict]}</span></td>
      <td class="std">${esc(c.krosetta)}</td>
    </tr>`
    )
    .join("");
}
$$("#bench-lang-seg .seg-btn").forEach((b) =>
  b.addEventListener("click", () => {
    $$("#bench-lang-seg .seg-btn").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    if (benchData) renderBenchRows(b.dataset.blang);
  })
);
async function loadBenchmark() {
  if (benchData) return;
  benchData = await fetch("/api/benchmark/summary").then((r) => r.json());
  const d = benchData;
  const s = d.summary;
  const byLang = Object.entries(s.vanilla_fidelity_by_lang)
    .map(([lg, v]) => `${LANG_LABEL[lg] || lg} ${Math.round(v * 100)}%`)
    .join(" · ");
  $("#bench-method").textContent = `문화 용어 ${d.n_cases}건 × 4개 언어 — 한국 공인 표준 표기 준수율 비교 (${d.version} · ${d.created})`;
  $("#bench-summary").innerHTML =
    `일반 번역기가 한국의 공인 표준 표기(공공데이터 기준)를 따르는 비율은 평균 <b>${Math.round(s.vanilla_fidelity * 100)}%</b>` +
    ` — 언어별로 ${byLang}. <b>저자원 언어일수록 급락</b>합니다.` +
    ` K-Rosetta는 공공데이터 표준을 강제하므로 <b class="ours">전 언어 ${Math.round(s.krosetta_fidelity * 100)}%</b> 준수.` +
    ` <span class="muted">— 방법론: ${esc(d.methodology)}</span>`;
  renderBenchRows("all");
}

/* ---- provenance badges + hero stats ---- */
async function loadProvenance() {
  const d = await fetch("/api/health").then((r) => r.json());
  const c = d.counts;
  $("#hero-stats").textContent =
    `용어 ${c.glossary_terms.toLocaleString()}개 · 다국어 대역 ${c.glossary_renderings.toLocaleString()}개 · ` +
    `근거 코퍼스 ${c.corpus_docs.toLocaleString()}문서(Koreana ${(c.koreana_articles || 0).toLocaleString()}기사 포함) · ` +
    `용어 근거연결 ${(c.evidence_links || 0).toLocaleString()}건`;
  $("#provenance-badges").innerHTML = d.opendata_provenance
    .map((p) => {
      const live = p.status !== "approved_pending";
      const dotColor = live ? "" : ' style="background:#ff9f0a"';
      const cnt = live ? `${p.record_count.toLocaleString()}건` : "승인·연동대기";
      const inner = `<span class="dot"${dotColor}></span>${esc(p.dataset_name)} · ${esc(p.provider)} (${cnt})`;
      return p.portal_url
        ? `<a class="badge" href="${esc(p.portal_url)}" target="_blank" rel="noopener">${inner}</a>`
        : `<span class="badge">${inner}</span>`;
    })
    .join("");
}

loadScenarios();
loadProvenance();
