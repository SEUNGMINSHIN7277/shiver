"""파일럿 크롤러 파서 단위테스트 — eGovFrame 게시판 관례 HTML fixture 기반.

라이브 사이트는 개발 환경에서 접속 불가하므로, 실제 크롤 후 list_samples/의 실HTML로
fixture를 교체·보강한다 (S0-B3).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.crawler.pilot_crawler import extract_article, parse_list_page

LIST_HTML = """
<html><body>
<table class="bbs_list">
  <tr><td><a href="/koreana/na/ntt/selectNttInfo.do?mi=1544&nttSn=118663&bbsId=1114">한지, 천년의 종이</a></td></tr>
  <tr><td><a href="#" onclick="fn_egov_select('118700'); nttSn=118700">판소리의 세계</a></td></tr>
  <tr><td><a href="javascript:fnView('1114','118722')" data-id="nttSn=118722">옹기와 발효</a></td></tr>
  <tr><td><a href="/koreana/cm/cntnts/cntntsView.do?mi=1068">About</a></td></tr>
</table>
</body></html>
"""

DETAIL_HTML = """
<html><head><title>Koreana</title>
<meta property="og:title" content="Hanji: Paper of a Thousand Years"/></head>
<body>
<header>menu menu</header>
<div class="bbs_view">
  <h2>Hanji: Paper of a Thousand Years</h2>
  <p>{}</p>
</div>
<footer>copyright</footer>
</body></html>
""".format("Hanji is traditional Korean paper handmade from mulberry bark. " * 20)


def test_parse_list_page_extracts_nttsn_from_href_and_onclick():
    items = parse_list_page(LIST_HTML)
    ids = {i["nttSn"] for i in items}
    assert "118663" in ids
    assert "118700" in ids  # onclick 방식
    assert "118722" in ids  # data 속성/스크립트 방식
    assert len(ids) == 3    # 비기사 링크는 제외
    by_id = {i["nttSn"]: i for i in items}
    assert "한지" in by_id["118663"]["title"]


def test_extract_article_title_and_body():
    rec = extract_article(DETAIL_HTML)
    assert rec["title"] == "Hanji: Paper of a Thousand Years"
    assert "mulberry" in rec["body_text"]
    assert rec["body_chars"] > 500
    # 내비/푸터 텍스트가 본문에 섞이지 않아야 함
    assert "copyright" not in rec["body_text"]


def test_extract_article_fallback_when_no_known_selector():
    html = "<html><body><div>short</div><div>" + ("본문 문장. " * 100) + "</div></body></html>"
    rec = extract_article(html)
    assert rec["body_chars"] > 300
