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

/* ---- language segmented control ---- */
let targetLang = "en";
$$("#lang-seg .seg-btn").forEach((b) =>
  b.addEventListener("click", () => {
    $$("#lang-seg .seg-btn").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    targetLang = b.dataset.lang;
  })
);

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
      body: JSON.stringify({ text, target_lang: targetLang }),
    }).then((r) => r.json());
    renderTranslation(d);
  } finally {
    btn.disabled = false; btn.textContent = "번역";
  }
}
$("#btn-translate").addEventListener("click", doTranslate);

function renderTranslation(d) {
  $("#translate-result").classList.remove("hidden");
  const grid = $("#result-grid");
  const compare = $("#compare-toggle").checked && d.baseline;
  grid.className = "result-grid" + (compare ? " compare" : "");
  let html = "";
  if (d.translation) {
    html += `<div class="result-card"><span class="tag ours">K-Rosetta · 용어사전 적용</span><p>${esc(d.translation)}</p></div>`;
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
let benchLoaded = false;
async function loadBenchmark() {
  if (benchLoaded) return;
  const d = await fetch("/api/benchmark/summary").then((r) => r.json());
  benchLoaded = true;
  const s = d.summary;
  $("#bench-method").textContent = `문화 용어 ${d.n_cases}건 — 공공데이터 공인 표준 대비 충실도 비교 (v0 · ${d.created})`;
  $("#bench-summary").innerHTML =
    `일반 번역기의 표준 용어 충실도는 <b>${Math.round(s.vanilla_fidelity * 100)}%</b>` +
    ` (완전일치 ${s.vanilla_verdicts.match} · 부분 ${s.vanilla_verdicts.partial} · 불일치 ${s.vanilla_verdicts.miss}건)에 그친 반면,` +
    ` 용어사전을 강제한 <b class="ours">K-Rosetta는 ${Math.round(s.krosetta_fidelity * 100)}%</b>를 기록했습니다.` +
    ` <span class="muted">— 동일 조건 ablation. 방법론: ${esc(d.methodology)}</span>`;
  $("#bench-table tbody").innerHTML = d.cases
    .map(
      (c) => `<tr>
      <td><b>${esc(c.term_ko)}</b><br/><span class="muted">${esc(c.category || "")}</span></td>
      <td class="std">${esc(c.standard)}<br/><span class="muted">${esc(c.standard_source)}</span></td>
      <td>${esc(c.vanilla)}<br/><span class="muted">${esc(c.note)}</span></td>
      <td><span class="verdict ${c.vanilla_verdict}">${{ match: "일치", partial: "부분", miss: "불일치" }[c.vanilla_verdict]}</span></td>
      <td class="std">${esc(c.krosetta)}</td>
    </tr>`
    )
    .join("");
}

/* ---- provenance badges ---- */
async function loadProvenance() {
  const d = await fetch("/api/health").then((r) => r.json());
  $("#provenance-badges").innerHTML = d.opendata_provenance
    .map((p) => {
      const inner = `<span class="dot"></span>${esc(p.dataset_name)} · ${esc(p.provider)} (${p.record_count}건)`;
      return p.portal_url
        ? `<a class="badge" href="${esc(p.portal_url)}" target="_blank" rel="noopener">${inner}</a>`
        : `<span class="badge">${inner}</span>`;
    })
    .join("");
}

loadScenarios();
loadProvenance();
