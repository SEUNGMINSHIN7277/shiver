"""Koreana 파일럿 크롤러 (S0).

목적: 본 크롤링 전에 (1) 언어 코드(langTy) 실측, (2) 게시판(bbsId) 목록 발견,
(3) 페이지네이션 파라미터 확정, (4) 언어판 간 기사 정렬 단서 수집, (5) 소량 코퍼스
(언어당 기본 120건) 확보를 한 번의 실행으로 수행한다.

이 원격 개발 환경에서는 koreana.or.kr 접속이 차단되므로, 사용자가 로컬 PC에서
`python scripts/run_pilot_crawl.py` 로 실행한다. 산출물은 data/pilot/koreana/ 에 저장되며
git 커밋으로 원격 세션과 공유한다 (CLAUDE.md §3 예외 규약).

주의: robots.txt를 먼저 확인하고, 요청 간격(기본 1초)을 지킨다. 이미지·PDF는 수집하지
않는다(저작권, DEV_SPEC §4.4). HTML 원문은 gzip으로 보존해 재파싱 가능하게 한다.
"""

from __future__ import annotations

import gzip
import json
import re
import time
import urllib.parse
from dataclasses import dataclass, field, asdict
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

BASE = "https://www.koreana.or.kr"
MAIN_PATH = "/koreana/main.do"
LIST_PATH = "/koreana/na/ntt/selectNttList.do"
DETAIL_PATH = "/koreana/na/ntt/selectNttInfo.do"

# 리서치(DEV_SPEC §4.1)에서 확인/추정된 언어 코드. ENG/RUS/VIE는 추정이므로 변형도 프로브.
CANDIDATE_LANG_CODES: dict[str, list[str]] = {
    "ko": ["KOR"],
    "en": ["ENG", "EN", ""],  # ""=파라미터 없는 기본판일 가능성
    "ja": ["JPN"],
    "zh": ["CHN"],
    "fr": ["FRA"],
    "de": ["GER"],
    "es": ["ESP"],
    "ru": ["RUS", "RUS0"],
    "ar": ["ARE", "ARA"],
    "id": ["IDN"],
    "vi": ["VIE", "VNM"],
}

# 리서치에서 확인된 게시판 시드 (발견 실패 시 폴백)
SEED_BOARDS = [
    {"bbsId": "1114", "mi": "1544", "label": "Features"},
    {"bbsId": "1116", "mi": "1074", "label": "K-uisine"},
    {"bbsId": "1120", "mi": "1547", "label": ""},
    {"bbsId": "1122", "mi": "1081", "label": "In Love with Korea"},
    {"bbsId": "1126", "mi": "", "label": ""},
    {"bbsId": "1130", "mi": "1586", "label": "Another Day"},
    {"bbsId": "1850", "mi": "15630", "label": "Brick by Brick"},
]

PAGINATION_PARAM_CANDIDATES = ["pageIndex", "currPage", "pageNo", "page"]

USER_AGENT = (
    "K-Rosetta-pilot-crawler/0.1 (public data research for MOFA open-data contest; "
    "polite: 1 req/sec; contact: see repository)"
)


@dataclass
class PilotConfig:
    languages: list[str] = field(default_factory=lambda: ["ko", "en", "vi", "id"])
    per_lang_limit: int = 120
    request_interval: float = 1.0
    max_list_pages: int = 30
    out_dir: Path = Path("data/pilot/koreana")
    timeout: float = 20.0


class PoliteClient:
    """1초 간격을 강제하는 얇은 httpx 래퍼. 실패 시 2/4/8초 백오프 3회 재시도."""

    def __init__(self, cfg: PilotConfig):
        self.cfg = cfg
        self._last_request = 0.0
        self.client = httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept-Language": "*"},
            timeout=cfg.timeout,
            follow_redirects=True,
        )
        self.request_count = 0

    def get(self, url: str, params: dict | None = None) -> httpx.Response | None:
        for attempt in range(4):
            wait = self._last_request + self.cfg.request_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            try:
                self._last_request = time.monotonic()
                self.request_count += 1
                resp = self.client.get(url, params=params)
                if resp.status_code < 500:
                    return resp
            except httpx.HTTPError as e:
                print(f"    [재시도 {attempt+1}/3] {url} — {type(e).__name__}: {e}")
            if attempt < 3:
                time.sleep(2 ** (attempt + 1))
        return None


def check_robots(pc: PoliteClient) -> str:
    """robots.txt를 가져와 저장하고, 수집 경로가 차단되면 경고를 반환."""
    resp = pc.get(f"{BASE}/robots.txt")
    if resp is None or resp.status_code != 200:
        return "robots.txt 없음/접근불가 — 표준 관례(공개 페이지 수집 + 예의) 준수로 진행"
    text = resp.text[:20000]
    blocked = []
    ua_all = False
    for line in text.splitlines():
        line = line.strip()
        if re.match(r"(?i)user-agent:\s*\*", line):
            ua_all = True
        elif re.match(r"(?i)user-agent:", line):
            ua_all = False
        elif ua_all and re.match(r"(?i)disallow:", line):
            path = line.split(":", 1)[1].strip()
            if path and ("/koreana" in path or path == "/"):
                blocked.append(path)
    if blocked:
        return f"⚠️ robots.txt가 수집 경로를 차단: {blocked} — 수집 중단하고 보고할 것"
    return "robots.txt 확인 — 수집 경로 차단 없음"


def probe_languages(pc: PoliteClient, cfg: PilotConfig, out: Path) -> dict[str, dict]:
    """언어 코드 후보를 실측: 상태코드, 응답 언어 힌트, 페이지 제목을 기록."""
    probe_dir = out / "probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict] = {}
    for lang, codes in CANDIDATE_LANG_CODES.items():
        for code in codes:
            params = {"langTy": code} if code else None
            resp = pc.get(f"{BASE}{MAIN_PATH}", params=params)
            if resp is None:
                results.setdefault(lang, {})[code or "(none)"] = {"status": "error"}
                continue
            soup = BeautifulSoup(resp.text, "lxml")
            html_lang = (soup.find("html") or {}).get("lang", "") if soup.find("html") else ""
            title = soup.title.get_text(strip=True) if soup.title else ""
            (probe_dir / f"main_{code or 'default'}.html").write_text(
                resp.text[:80000], encoding="utf-8"
            )
            results.setdefault(lang, {})[code or "(none)"] = {
                "status": resp.status_code,
                "html_lang": html_lang,
                "title": title[:120],
                "final_url": str(resp.url),
            }
            print(f"  프로브 {lang}/{code or '(기본)'}: HTTP {resp.status_code} lang={html_lang!r} title={title[:60]!r}")
    return results


def discover_boards(pc: PoliteClient, lang_code: str) -> list[dict]:
    """언어별 메인 페이지에서 selectNttList.do 링크를 파싱해 게시판 목록을 발견."""
    params = {"langTy": lang_code} if lang_code else None
    resp = pc.get(f"{BASE}{MAIN_PATH}", params=params)
    boards: dict[str, dict] = {}
    if resp is not None and resp.status_code == 200:
        soup = BeautifulSoup(resp.text, "lxml")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "selectNttList.do" not in href:
                continue
            q = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
            bbs = q.get("bbsId", [""])[0]
            if bbs:
                boards[bbs] = {
                    "bbsId": bbs,
                    "mi": q.get("mi", [""])[0],
                    "label": a.get_text(strip=True)[:60],
                }
    found = list(boards.values())
    if not found:
        print(f"  [폴백] 메인에서 게시판 발견 실패(langTy={lang_code!r}) → 시드 게시판 사용")
        return SEED_BOARDS
    return found


def parse_list_page(html: str) -> list[dict]:
    """목록 페이지에서 기사 링크(nttSn) 추출. onclick 방식(eGovFrame 관례)도 처리."""
    soup = BeautifulSoup(html, "lxml")
    items: dict[str, dict] = {}
    for a in soup.find_all("a"):
        # href/onclick/data-* 등 모든 속성값을 스캔 (eGovFrame은 목록 링크 방식이 다양)
        blob = " ".join(str(v) for v in a.attrs.values())
        m = re.search(r"nttSn[=:'\"\s(]+(\d+)", blob)
        if not m:
            continue
        ntt = m.group(1)
        items[ntt] = {"nttSn": ntt, "title": a.get_text(" ", strip=True)[:200]}
    return list(items.values())


def detect_pagination(pc: PoliteClient, board: dict, lang_code: str) -> tuple[str | None, str]:
    """페이지네이션 파라미터 실측: 후보 파라미터로 2페이지를 요청해 1페이지와 내용이
    달라지는 첫 파라미터를 채택."""
    base_params = {"bbsId": board["bbsId"]}
    if board.get("mi"):
        base_params["mi"] = board["mi"]
    if lang_code:
        base_params["langTy"] = lang_code
    r1 = pc.get(f"{BASE}{LIST_PATH}", params=base_params)
    if r1 is None or r1.status_code != 200:
        return None, "목록 1페이지 접근 실패"
    first = {i["nttSn"] for i in parse_list_page(r1.text)}
    if not first:
        return None, "목록 파싱 결과 0건 — list_samples HTML 확인 필요"
    for param in PAGINATION_PARAM_CANDIDATES:
        r2 = pc.get(f"{BASE}{LIST_PATH}", params={**base_params, param: "2"})
        if r2 is None:
            continue
        second = {i["nttSn"] for i in parse_list_page(r2.text)}
        if second and second != first:
            return param, f"페이지네이션 파라미터 확정: {param}"
    return None, "2페이지 전환 파라미터 미확정 (1페이지만 수집)"


def extract_article(html: str) -> dict:
    """기사 상세 페이지에서 제목/본문/메타를 휴리스틱으로 추출.
    파싱이 불완전해도 raw HTML이 보존되므로 재파싱 가능."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    og_title = soup.find("meta", property="og:title")
    title = (og_title.get("content", "") if og_title else "") or (
        soup.title.get_text(strip=True) if soup.title else ""
    )
    # eGovFrame 게시판 본문 후보 셀렉터 → 실패 시 최대 텍스트 블록
    body = ""
    for sel in [".bbs_view", ".view_con", ".nttViewCn", "#nttViewForm", ".board_view", "#contents", ".contents"]:
        node = soup.select_one(sel)
        if node:
            body = node.get_text("\n", strip=True)
            if len(body) > 200:
                break
    if len(body) < 200:
        candidates = sorted(
            (len(d.get_text(strip=True)), d) for d in soup.find_all("div")
        )
        if candidates:
            body = candidates[-1][1].get_text("\n", strip=True)
    return {"title": title[:300], "body_text": body, "body_chars": len(body)}


def run_pilot(cfg: PilotConfig) -> dict:
    out = cfg.out_dir
    out.mkdir(parents=True, exist_ok=True)
    pc = PoliteClient(cfg)
    stats: dict = {"started_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "config": {
        "languages": cfg.languages, "per_lang_limit": cfg.per_lang_limit}}

    print("[1/4] robots.txt 확인")
    robots_msg = check_robots(pc)
    print(f"  {robots_msg}")
    stats["robots"] = robots_msg
    if robots_msg.startswith("⚠️"):
        (out / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2))
        return stats

    print("[2/4] 언어 코드 프로브")
    stats["language_probe"] = probe_languages(pc, cfg, out)

    print("[3/4] 게시판 발견 + 페이지네이션 실측 + 목록 수집")
    lang_code_map: dict[str, str] = {}
    for lang in cfg.languages:
        # 프로브에서 200이고 제목이 있는 첫 코드를 채택
        for code, info in stats["language_probe"].get(lang, {}).items():
            if isinstance(info, dict) and info.get("status") == 200:
                lang_code_map[lang] = "" if code == "(none)" else code
                break
    stats["lang_code_map"] = lang_code_map
    print(f"  채택된 언어 코드: {lang_code_map}")

    list_samples = out / "list_samples"
    list_samples.mkdir(exist_ok=True)
    index_all: dict[str, list[dict]] = {}
    stats["boards"] = {}
    stats["pagination"] = {}

    for lang, code in lang_code_map.items():
        boards = discover_boards(pc, code)
        stats["boards"][lang] = boards
        print(f"  [{lang}] 게시판 {len(boards)}개")
        collected: dict[str, dict] = {}
        for board in boards:
            if len(collected) >= cfg.per_lang_limit:
                break
            page_param, page_msg = detect_pagination(pc, board, code)
            stats["pagination"][f"{lang}/{board['bbsId']}"] = page_msg
            base_params = {"bbsId": board["bbsId"], **({"mi": board["mi"]} if board.get("mi") else {}),
                           **({"langTy": code} if code else {})}
            for page in range(1, cfg.max_list_pages + 1):
                params = dict(base_params)
                if page > 1:
                    if not page_param:
                        break
                    params[page_param] = str(page)
                resp = pc.get(f"{BASE}{LIST_PATH}", params=params)
                if resp is None or resp.status_code != 200:
                    break
                if page == 1:
                    (list_samples / f"{lang}_{board['bbsId']}_p1.html").write_text(
                        resp.text[:150000], encoding="utf-8")
                items = parse_list_page(resp.text)
                new = [i for i in items if i["nttSn"] not in collected]
                if not new:
                    break
                for i in new:
                    i["bbsId"] = board["bbsId"]
                    i["mi"] = board.get("mi", "")
                    collected[i["nttSn"]] = i
                if len(collected) >= cfg.per_lang_limit:
                    break
        index_all[lang] = list(collected.values())[: cfg.per_lang_limit]
        print(f"  [{lang}] 목록 수집 {len(index_all[lang])}건")

    print("[4/4] 본문 수집 (raw HTML gzip 보존 + 텍스트 추출)")
    articles_dir = out / "articles"
    raw_dir = out / "raw_html"
    stats["fetched"] = {}
    for lang, items in index_all.items():
        (raw_dir / lang).mkdir(parents=True, exist_ok=True)
        jsonl = (articles_dir / f"{lang}.jsonl")
        jsonl.parent.mkdir(parents=True, exist_ok=True)
        n_ok = 0
        with jsonl.open("w", encoding="utf-8") as f:
            for it in items:
                raw_path = raw_dir / lang / f"{it['nttSn']}.html.gz"
                params = {"nttSn": it["nttSn"], "bbsId": it["bbsId"],
                          **({"mi": it["mi"]} if it.get("mi") else {}),
                          **({"langTy": lang_code_map[lang]} if lang_code_map[lang] else {})}
                if raw_path.exists():  # 재실행(resume) 지원
                    html = gzip.decompress(raw_path.read_bytes()).decode("utf-8", "replace")
                else:
                    resp = pc.get(f"{BASE}{DETAIL_PATH}", params=params)
                    if resp is None or resp.status_code != 200:
                        continue
                    html = resp.text
                    raw_path.write_bytes(gzip.compress(html.encode("utf-8")))
                rec = {"lang": lang, **it, **extract_article(html),
                       "url": f"{BASE}{DETAIL_PATH}?" + urllib.parse.urlencode(params)}
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n_ok += 1
        stats["fetched"][lang] = n_ok
        print(f"  [{lang}] 본문 {n_ok}건 저장")

    stats["total_requests"] = pc.request_count
    stats["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    (out / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n완료. 산출물: {out}/ (stats.json 참조)")
    print("다음 단계: git add data/pilot && git commit && git push  → 원격 세션이 이어받습니다.")
    return stats
