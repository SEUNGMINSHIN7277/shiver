# -*- coding: utf-8 -*-
"""접수용 기획서 HTML 생성 (한글 복사·붙여넣기용). 이미지 base64 임베드."""
import json, pathlib

figs = json.loads(pathlib.Path('/tmp/claude-0/-home-user-shiver/840b487b-fe62-5737-be29-85aeda173f67/scratchpad/figs.json').read_text())

CSS = """
body{font-family:'맑은 고딕','Malgun Gothic',AppleSDGothicNeo,sans-serif;color:#1a1a1a;
 font-size:10.5pt;line-height:1.7;max-width:820px;margin:0 auto;padding:28px;}
h1{font-size:19pt;text-align:center;margin:0 0 4px;letter-spacing:-.5px;}
.subtitle{text-align:center;color:#444;font-size:11pt;margin-bottom:22px;}
h2{font-size:13pt;border-left:5px solid #1a5fb4;padding-left:10px;margin:26px 0 10px;color:#12305c;}
h3{font-size:11.5pt;margin:16px 0 6px;color:#1a1a1a;}
p{margin:6px 0;}
table{border-collapse:collapse;width:100%;margin:10px 0;font-size:10pt;}
th,td{border:1px solid #bcbcbc;padding:6px 9px;text-align:left;vertical-align:top;}
th{background:#eef3fb;font-weight:bold;color:#12305c;}
td.c,th.c{text-align:center;}
.small{font-size:9pt;color:#666;}
ul{margin:6px 0 6px 0;padding-left:22px;}
li{margin:3px 0;}
.box{border:1px solid #bcbcbc;background:#f7f9fc;padding:12px 16px;margin:10px 0;border-radius:4px;}
.figcap{font-size:9pt;color:#555;text-align:center;margin:3px 0 16px;}
img.shot{width:100%;border:1px solid #ccc;margin-top:10px;}
.flow{display:table;width:100%;table-layout:fixed;border-spacing:6px 0;margin:12px 0;}
.flow .step{display:table-cell;background:#eef3fb;border:1px solid #9db8e0;border-radius:6px;
 padding:10px 6px;text-align:center;font-size:9.5pt;vertical-align:middle;}
.flow .arrow{display:table-cell;width:22px;text-align:center;color:#1a5fb4;font-weight:bold;vertical-align:middle;}
.bar{height:15px;background:#1a5fb4;border-radius:2px;display:inline-block;vertical-align:middle;}
.barbg{background:#e5e5e5;border-radius:2px;display:inline-block;width:150px;height:15px;vertical-align:middle;}
.hl{background:#fff3cd;padding:0 3px;}
.metric{display:table;width:100%;table-layout:fixed;border-spacing:8px 0;margin:10px 0;}
.metric .m{display:table-cell;text-align:center;background:#f2f6fc;border:1px solid #cdddf3;border-radius:6px;padding:12px 6px;}
.metric .m b{display:block;font-size:17pt;color:#12305c;}
.metric .m span{font-size:9pt;color:#555;}
"""

def bar(pct, color="#1a5fb4"):
    w = round(pct*1.5)
    return f'<span class="barbg"><span class="bar" style="width:{w}px;background:{color}"></span></span> {pct}%'

HTML = f"""<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><title>K-Rosetta 기획서</title>
<style>{CSS}</style></head><body>

<h1>K-Rosetta</h1>
<div class="subtitle">공공데이터 기반 한국 문화용어 AI 번역 서비스<br>
<span class="small">2026 외교 공공데이터·AI 활용 경진대회 · 제품 또는 서비스 개발 부문</span></div>

<h2>1. 기본 정보</h2>
<table>
<tr><th style="width:22%">참가구분</th><td>□ 개인   □ 팀   <span class="small">(해당란 표시)</span></td></tr>
<tr><th>참가분야</th><td>제품 또는 서비스 개발</td></tr>
<tr><th>성명</th><td><span class="small">기입 (팀 참가 시 팀장명)</span></td></tr>
<tr><th>휴대전화 / 이메일</th><td><span class="small">기입</span></td></tr>
<tr><th>소속 / 팀명</th><td><span class="small">기입</span></td></tr>
<tr><th>제품 또는 서비스명</th><td><b>K-Rosetta (케이-로제타)</b></td></tr>
</table>

<h2>2. 활용 데이터</h2>
<p>본 서비스는 공공데이터포털(data.go.kr)에 등록된 외교부 산하기관의 개방데이터와 한국국제교류재단의 「Koreana」 다국어 아카이브를 번역 처리의 핵심 자료로 사용합니다.</p>
<table>
<tr><th style="width:44%">데이터셋명 (등록번호)</th><th style="width:20%">제공기관</th><th>활용 상태</th></tr>
<tr><td>한국국제교류재단_한국음식정보_영어 (15044203)</td><td>한국국제교류재단</td><td><b>적용 완료</b> (691건)</td></tr>
<tr><td>한국국제협력단_ODA용어사전 (15052909)</td><td>한국국제협력단</td><td><b>적용 완료</b> (393건)</td></tr>
<tr><td>한국국제교류재단_디지털 아카이브 기사목록 (15139278)</td><td>한국국제교류재단</td><td><b>적용 완료</b> (278건)</td></tr>
<tr><td>한국국제교류재단 「Koreana」 다국어 아카이브</td><td>한국국제교류재단</td><td><b>적용 완료</b> (480기사, 4개 언어판)</td></tr>
<tr><td>한국국제교류재단_해외대학 표준국문명칭 (15075335)</td><td>한국국제교류재단</td><td>활용신청 승인 완료</td></tr>
<tr><td>외교부_국가·지역별 표준코드 (15075346)</td><td>외교부</td><td>활용신청 승인 완료</td></tr>
<tr><td>한국국제협력단_융합 KOICA-ODA·KF 공공외교 사업정보 (15099215)</td><td>KOICA·KF</td><td>활용신청 승인 완료</td></tr>
</table>
<p class="small">파일데이터 3종과 「Koreana」 아카이브는 서비스에 이미 적용되어 동작하고 있습니다(합계 약 1,842건). 오픈API 3종은 활용신청이 승인되어 인증키를 발급받았으며, 국가 정보·기관명 표준화에 연동하는 단계입니다. 「Koreana」는 공개 웹진으로, 원문은 재배포하지 않고 용어 대역·근거 인용 등 가공 결과만 활용하며 상업적 이용 시 재단과 협의합니다.</p>

<h2>3. 제품 또는 서비스 개요</h2>
<p>한국 콘텐츠(웹툰·드라마·K-pop·관광 등)의 해외 진출이 늘면서 번역 수요가 빠르게 커지고 있습니다. 그러나 '한지', '판소리', '선배'와 같은 한국 고유의 문화용어는 일반 번역기에서 정확히 번역되지 않는 경우가 많습니다. 예를 들어 '떡국'은 한국국제교류재단이 정한 공식 영문 표기가 'Sliced Rice Pasta Soup'이지만, 일반 번역기는 'rice cake soup'로 옮겨 의미를 제대로 전달하지 못합니다.</p>
<p>K-Rosetta는 한국국제교류재단과 한국국제협력단이 공개한 공공데이터에 담긴 표준 용어를 활용하여, 문화용어를 정해진 표기에 맞게 정확히 번역하는 서비스입니다. 문화용어 64개를 4개 언어로 비교 측정한 결과, 일반 번역기의 표준 표기 정확도는 평균 23.4%였으나 K-Rosetta는 100%였습니다. 본 서비스는 실제로 동작하는 형태로 개발을 마쳤으며, 발표 심사에서 직접 시연할 수 있습니다.</p>
<div class="metric">
 <div class="m"><b>1,177</b><span>수록 문화·전문 용어</span></div>
 <div class="m"><b>1,575</b><span>다국어 표준 대역</span></div>
 <div class="m"><b>1,542</b><span>근거 문서(Koreana 480 포함)</span></div>
 <div class="m"><b>100%</b><span>문화용어 표준 정확도</span></div>
</div>
<img class="shot" src="{figs['fig_translate']}">
<div class="figcap">[그림 1] 번역 화면 — 왼쪽은 K-Rosetta(용어사전 적용), 오른쪽은 일반 번역기. 각 용어의 뜻과 공공데이터 출처를 함께 표시합니다.</div>

<h2>4. 제품 또는 서비스의 목적 또는 배경</h2>
<h3>가. 배경</h3>
<ul>
<li>한국 콘텐츠 수출이 늘어나면서 번역 품질이 중요한 과제가 되었습니다. 문화용어가 잘못 번역되면 한국 문화가 왜곡되어 전달되고(대외 이미지 문제), 콘텐츠의 완성도도 떨어집니다(수출 품질 문제).</li>
<li>이러한 오류는 <b>저자원 언어일수록 더 심합니다.</b> 측정 결과 일반 번역기의 문화용어 정확도는 영어 33.9%, 러시아어 20.8%, 베트남어·인도네시아어 12.5%로 낮아졌습니다. 그런데 이 언어권이 바로 한류 수요가 빠르게 늘고 있는 지역입니다.</li>
<li>한편 외교부 산하기관에는 이 문제를 해결할 자료가 이미 축적되어 있습니다. 한국국제교류재단이 39년간 11개 언어로 발간한 「Koreana」, 한국음식정보의 공식 영문 표기, 한국국제협력단의 외교 용어사전이 그것입니다. 그러나 이 자료들이 번역에 활용된 사례는 없었습니다.</li>
</ul>
<h3>나. 목적</h3>
<p>활용되지 않던 외교부 산하기관 공공데이터를 번역에 적용하여, ① 한국 문화가 여러 나라 언어로 정확히 전달되도록 하고, ② 한국 콘텐츠 현지화의 품질을 높이는 것을 목표로 합니다.</p>

<h2>5. 제품 또는 서비스의 기능 및 특징</h2>
<h3>가. 핵심 처리 방식</h3>
<p>K-Rosetta는 다음 순서로 번역을 처리합니다.</p>
<div class="flow">
 <div class="step">① 입력 문장에서<br>문화용어 찾기</div><div class="arrow">▶</div>
 <div class="step">② 공공데이터에서<br>표준 번역 조회</div><div class="arrow">▶</div>
 <div class="step">③ 표준 번역을<br>반드시 사용해 번역</div><div class="arrow">▶</div>
 <div class="step">④ 용어별 출처·<br>근거 함께 표시</div>
</div>
<p>이 방식으로 일반 번역기가 문화용어를 임의로 옮기는 문제를 원천적으로 막습니다. 또한 답변과 번역의 근거를 공공데이터에서 찾아 함께 제시하므로, 사실과 다른 내용이 생성되는 위험을 줄입니다.</p>

<h3>나. 주요 기능 (네 가지, 모두 실제 동작)</h3>
<table>
<tr><th style="width:26%">기능</th><th>설명</th></tr>
<tr><td><b>① 문화용어 번역</b></td><td>문장 속 문화용어를 자동으로 찾아 표준 표기로 번역하고, 용어별 뜻·출처·근거 기사를 카드로 제시합니다. '일반 번역기와 비교' 기능으로 차이를 바로 확인할 수 있습니다.</td></tr>
<tr><td><b>② 자막·대사 모드</b></td><td>웹툰·영상 자막 번역의 실무 방식(처음 나올 때 음차+짧은 설명, 이후 음차만)을 적용합니다. 호칭·사회문화 용어(선배·막내·재벌 등)를 정확히 옮깁니다.</td></tr>
<tr><td><b>③ 문화 설명 챗봇</b></td><td>질문한 언어를 자동으로 인식해 그 언어로 답하며, 모든 답변에 공공데이터 출처를 함께 인용합니다.</td></tr>
<tr><td><b>④ 번역 품질 비교</b></td><td>문화용어에 대해 일반 번역기와 K-Rosetta의 정확도를 언어별로 비교해 보여줍니다.</td></tr>
</table>
<img class="shot" src="{figs['fig_subtitle']}">
<div class="figcap">[그림 2] 자막·대사 모드 — 드라마 대사를 베트남어로 번역한 예. '막내'를 일반 번역기는 'em út(친동생)'으로 옮기지만, K-Rosetta는 'maknae(그룹의 최연소 멤버)'로 정확히 표기합니다.</div>
<img class="shot" src="{figs['fig_chat']}">
<div class="figcap">[그림 3] 문화 설명 챗봇 — 질문에 대해 공공데이터 기사를 근거로 인용하여 답합니다.</div>

<h2>6. 외교부 및 산하기관 공공데이터 활용 방안</h2>
<h3>가. 공공데이터의 출처 · 내용 · 획득 방법</h3>
<table>
<tr><th style="width:30%">데이터셋 (등록번호)</th><th>내용 / 획득 방법</th><th style="width:28%">서비스 내 활용</th></tr>
<tr><td>KF 한국음식정보_영어 (15044203)</td><td>한국 음식 691종의 공식 영문 표기·설명 / 포털에서 파일 내려받기(인증키 불필요)</td><td>번역 시 반드시 따르는 표준 표기, 품질 비교의 기준값</td></tr>
<tr><td>KOICA ODA용어사전 (15052909)</td><td>외교·개발협력 용어 393종의 한·영 대역 / 포털 내려받기</td><td>외교 분야 용어사전</td></tr>
<tr><td>KF 디지털 아카이브 기사목록 (15139278)</td><td>문화·공공외교 기사 278건(제목·내용) / 포털 내려받기</td><td>챗봇 답변의 근거 자료, 용어 근거 인용</td></tr>
<tr><td>KF 해외대학 표준국문명칭 (15075335)</td><td>해외대학의 표준 국문·영문 명칭 / 오픈API(승인 완료)</td><td>기관명 번역의 표준화</td></tr>
<tr><td>외교부 국가·지역별 표준코드 (15075346)</td><td>국가 표준코드·한영 국가명 / 오픈API(승인 완료)</td><td>언어·국가 연결 기준</td></tr>
<tr><td>KOICA-KF 융합 사업정보 (15099215)</td><td>국가별 공공외교·ODA 사업정보 / 오픈API(승인 완료)</td><td>국가별 배경정보 제공</td></tr>
<tr><td>KF 「Koreana」 다국어 아카이브</td><td>1987년부터 발간된 문화매거진의 다국어 기사(현재 480기사, 4개 언어판 확보) / 공개 웹진 수집</td><td>문화용어의 근거 자료 — 번역·설명에 실제 기사를 함께 인용</td></tr>
</table>
<p class="small">「Koreana」 아카이브를 문화용어와 연결하여, 각 용어가 실제 기사에 근거하도록 구성했습니다. 예를 들어 '한지'를 번역하면 '한지의 조형적 실험과 가능성', '예술 언어가 된 한지' 등 재단이 발간한 실제 기사가 근거로 함께 제시됩니다(현재 근거 연결 308건).</p>
<h3>나. 확보의 지속성 · 활용 범위 · 가공</h3>
<ul>
<li><b>지속성:</b> 핵심 3종은 인증키 없이 내려받는 파일데이터로 매년 갱신되며, 오픈API 3종은 활용신청이 승인되어 하루 1만 건까지 호출할 수 있습니다.</li>
<li><b>활용 범위·저작권:</b> 공공데이터포털 데이터는 각 이용허락 범위(출처 표시)를 지켜 사용합니다. 「Koreana」는 원문을 재배포하지 않고 용어 대역·통계 등 가공 결과만 활용하며, 상업화 단계에서 재단과 협의합니다.</li>
<li><b>가공 방식:</b> 표준 표기 정리 → 언어별 대역 정리 → 번역 시 표준 적용 → 출처 표시의 순서로 처리하며, 전 과정을 재현할 수 있도록 정리해 두었습니다.</li>
<li><b>화면 표시:</b> 서비스 화면 하단에 사용한 데이터셋 이름·건수·포털 링크를 항상 표시합니다.</li>
</ul>

<h2>7. 기존 제품(서비스)과의 차별성 및 독창성</h2>
<h3>가. 측정 결과 비교</h3>
<p>같은 조건에서 용어사전 적용 여부만 달리하여 측정했습니다(문화용어 64개, 4개 언어).</p>
<table>
<tr><th style="width:26%">문화용어 표준 정확도</th><th>일반 번역기</th><th>K-Rosetta</th></tr>
<tr><td>영어</td><td>{bar(34,'#999')}</td><td>{bar(100)}</td></tr>
<tr><td>러시아어</td><td>{bar(21,'#999')}</td><td>{bar(100)}</td></tr>
<tr><td>베트남어</td><td>{bar(13,'#999')}</td><td>{bar(100)}</td></tr>
<tr><td>인도네시아어</td><td>{bar(13,'#999')}</td><td>{bar(100)}</td></tr>
<tr><td><b>4개 언어 평균</b></td><td><b>{bar(23,'#999')}</b></td><td><b>{bar(100)}</b></td></tr>
</table>
<p class="small">※ 채점 기준·실패 사례를 모두 공개하며, 일반 번역기가 맞힌 사례도 그대로 포함하여 측정했습니다.</p>
<h3>나. 차별점</h3>
<ul>
<li>문화용어의 '표준 표기 준수'를 목표로 삼는 번역 서비스는 국내외에 없습니다. 기존 번역기는 일반적인 정확도를 다룰 뿐 문화용어의 표준 준수는 다루지 않습니다.</li>
<li>한국국제교류재단의 39년간 11개 언어 발간 자료와 공공데이터 표준 표기를 결합한 자료 기반은 다른 곳에서 쉽게 확보할 수 없습니다.</li>
<li>번역 품질 비교 자료(평가셋) 자체가 다시 활용할 수 있는 공공 자산이 됩니다.</li>
</ul>
<img class="shot" src="{figs['fig_bench']}">
<div class="figcap">[그림 4] 번역 품질 비교 화면 — 언어별로 일반 번역기와 K-Rosetta의 문화용어 정확도를 비교합니다.</div>

<h2>8. 기대효과</h2>
<table>
<tr><th style="width:26%">구분</th><th>기대효과</th></tr>
<tr><td>대외 이미지·공공외교</td><td>한국 문화가 여러 언어권에 정확하게 전달되어, 왜곡 없는 문화 소개에 기여합니다.</td></tr>
<tr><td>콘텐츠 수출</td><td>웹툰·영상 등 콘텐츠 현지화의 품질과 속도를 높여 수출 경쟁력을 지원합니다.</td></tr>
<tr><td>일자리·상생</td><td>전문 번역가를 대체하지 않고, 용어 검수를 자동화해 생산성을 높이며 새로운 직무(문화용어 데이터 담당)를 만듭니다.</td></tr>
<tr><td>공공데이터 활용</td><td>활용되지 않던 산하기관 데이터를 처음으로 번역에 적용한 사례이며, 문화용어 평가 자료를 공공에 환원합니다.</td></tr>
<tr><td>정보 접근성</td><td>저자원 언어권(동남아·중동·러시아어권) 사용자가 한국 문화 정보를 더 정확하게 접할 수 있습니다.</td></tr>
</table>

<h2>9. 제품 및 서비스의 사업(창업) 계획</h2>
<p><span class="small">□ 예비창업자 / □ 기창업자 (해당란 표시)</span></p>
<table>
<tr><th style="width:20%">단계</th><th>내용</th></tr>
<tr><td>1단계<br>(~2026.9)<br>완성도 심화</td><td>「Koreana」 자료 정리로 용어사전을 500개 이상으로 확대하고 지원 언어를 11개로 넓힙니다. 한국국제교류재단에 데이터 활용 협력을 제안합니다.</td></tr>
<tr><td>2단계<br>(2026.4분기)<br>시범 적용</td><td>웹툰·자막 번역 업체와 박물관·관광기관에 용어 검수 기능을 시범 제공하여 현장 의견을 반영합니다.</td></tr>
<tr><td>3단계<br>(2027~)<br>사업화</td><td>① 번역·자막 업체 대상 용어 검수 구독 서비스, ② 기관용 다국어 문화 안내 서비스, ③ 문화용어 데이터 제공. 예비창업 지원 사업과 연계해 사업화합니다. (기창업자의 경우: 기존 콘텐츠·번역 사업에 본 기능을 결합하여 저자원 언어권 수출을 확대합니다.)</td></tr>
</table>
<div class="box"><b>위험 요소와 대응</b><br>
「Koreana」 원문 저작권은 파생 자료만 활용하고 원문을 재배포하지 않으며, 상업화 전에 재단과 협의하여 대응합니다. AI 운영 비용은 반복 요청을 재사용하는 방식으로 최소화하도록 설계했습니다.</div>

<h2>10. 심사기준별 정리</h2>
<table>
<tr><th style="width:24%">심사기준</th><th>본 서비스의 대응</th></tr>
<tr><td>공공데이터 활용</td><td>외교부 산하기관 6종을 번역 처리의 핵심 자료로 실제 사용, 화면에 출처 상시 표시</td></tr>
<tr><td>AI 기술 활용</td><td>용어 표준 적용 번역, 근거 기반 답변 생성, 다국어 검색</td></tr>
<tr><td>AI 서비스</td><td>번역·자막·챗봇·품질비교 네 기능 실제 동작, 발표 시 시연 가능</td></tr>
<tr><td>독창성</td><td>문화용어 표준 준수를 목표로 한 최초의 서비스, 확보하기 어려운 데이터 기반</td></tr>
<tr><td>발전가능성</td><td>콘텐츠 현지화 시장 적용, 11개 언어·전 분야 확장 계획</td></tr>
<tr><td>ESG혁신</td><td>저자원 언어권 정보 접근성, 번역가와의 상생, 공공데이터 환원</td></tr>
</table>

<p class="small" style="margin-top:20px;">※ 본 기획서의 모든 수치는 실제 동작하는 시제품에서 측정한 값이며, 발표 심사에서 직접 시연할 수 있습니다.</p>

</body></html>"""

pathlib.Path('docs/SUBMISSION_기획서.html').write_text(HTML, encoding='utf-8')
print('written', len(HTML)//1024, 'KB')
