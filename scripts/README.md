# scripts/ — 사용자 로컬 실행 가이드

원격 개발 환경은 한국 도메인(koreana.or.kr, data.go.kr) 접속이 차단되어 있어,
**데이터 수집 스크립트는 사용자 PC에서 실행**하고 산출물을 git으로 공유합니다.

## 1. 파일럿 크롤러 (S0 — 7/12 아침 실행)

```bash
# 저장소 루트에서 (Python 3.10+)
pip install -r pipeline/requirements.txt
python scripts/run_pilot_crawl.py            # 기본: ko,en,vi,id × 언어당 120건, 약 30~60분
```

- 진행 로그가 단계별로 출력됩니다. 중단돼도 재실행하면 이어받습니다(resume).
- 완료(또는 부분 실패) 후 **산출물을 그대로 커밋**해 주세요:

```bash
git add data/pilot
git commit -m "[S0] Koreana 파일럿 크롤 산출물"
git push
```

- ⚠️ 수집이 0건이어도 `data/pilot/koreana/probe/`, `list_samples/`에 저장된 HTML만 커밋해
  주시면 원격 세션(Claude)이 실제 페이지 구조를 보고 파서를 고칩니다.
- robots.txt가 수집을 차단하는 것으로 확인되면 스크립트가 스스로 중단하고 stats.json에
  기록합니다 — 그대로 커밋해 주시면 대응 방안(전자책 아카이브/KF 문의)으로 전환합니다.

## 2. 공공데이터 파일 다운로드 (S0 — 오늘 밤)

브라우저에서 아래 2개를 내려받아 `data/pilot/opendata/`에 넣고 커밋:

| 파일 | 다운로드 위치 |
|---|---|
| 한국음식정보_영어 (CSV) | https://www.data.go.kr/data/15044203/fileData.do |
| 디지털 아카이브 기사 목록 (CSV) | https://www.data.go.kr/data/15139278/fileData.do |

파일명은 바꾸지 말고 그대로 저장 (인코딩 자동 감지 처리함).
