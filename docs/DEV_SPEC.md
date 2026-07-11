# K-Rosetta 개발명세서 (Development Specification)

- 대상 공모전: 「2026년 외교 공공데이터·AI 활용 경진대회」 — **제품 또는 서비스 개발 부문**
- 주최/주관: 외교부 / 한국국제협력단(KOICA), 한국국제교류재단(KF), 한·아프리카재단
- 버전: v1.0 (2026-07-11)
- 관련 문서: `CLAUDE.md`(자율 개발 운영 지침), `docs/PROGRESS.md`(진행 현황),
  `docs/USER_ACTION_ITEMS.md`(사용자 준비 사항)

---

## 1. 공모전 요건 분석 및 준수 매트릭스

공고문(HWP) 원문 기준 필수 요건과 본 프로젝트의 대응:

| # | 공고 요건 (원문 근거) | K-Rosetta 대응 | 구현 위치 |
|---|---|---|---|
| R1 | **"공공데이터 포털에 등록된 외교부 공공데이터 1건 이상 활용 필수"** — 미활용 시 **심사대상 제외** | data.go.kr 등록 데이터셋을 서비스 런타임에서 실제 호출 (§4.2). 최소 2종 이중화 | `backend/app/services/opendata/` |
| R2 | 활용 가능 데이터 범위: "외교부, 한국국제협력단, 한국국제교류재단, 한·아프리카재단 개방데이터" | 핵심 코퍼스 = KF 《Koreana》 (주최기관 개방데이터) + data.go.kr 등록분 | §4.1, §4.2 |
| R3 | "제품 또는 서비스가 개발 중인 경우 **발표 심사 전까지 데모 또는 시제품 개발 완료**" (발표평가: 7월 말~8월 중순) | 마일스톤 M5 완료 시점을 7월 말로 설정, 8월 초순까지 버퍼 (§12) | 전체 |
| R4 | 심사기준: **공공데이터 활용, AI 기술 활용, AI 서비스, 독창성, 발전가능성, ESG혁신** | §1.1 심사기준-기능 매핑 | 전체 |
| R5 | 접수: '26.5.18 ~ **7.13(월) 18:00**, 국민생각함 또는 이메일 | 서류 제출은 사용자 액션 (개발 범위 아님) | `docs/USER_ACTION_ITEMS.md` |
| R6 | 저작권: 출품작 저작권은 저작자 소유, 주최·주관기관이 사용권 보유. 타인 지식재산권 침해 시 입상 취소 | Koreana 원문 재배포 금지 원칙, 파생 산출물만 사용 (§4.4) | 전체 |

### 1.1 심사기준 → 기능 매핑 (발표 스토리의 뼈대)

| 심사기준 | K-Rosetta에서 보여줄 것 |
|---|---|
| 공공데이터 활용 | ① 39년×11개 언어 Koreana 병렬 코퍼스를 **최초로** AI 자원화 ② data.go.kr 등록 데이터 실시간 연동 (UI에 출처 배지 표시) |
| AI 기술 활용 | RAG + LLM 번역 + 용어사전 강제(constrained translation) + 다국어 임베딩 검색 |
| AI 서비스 | 실동작 웹 데모 3종: 문화 로컬라이제이션 번역기 / 다국어 문화 설명 챗봇 / 벤치마크 대시보드 |
| 독창성 | "문화 용어 충실도(Cultural Term Fidelity)"라는 신규 평가축 + 전용 벤치마크 공개 |
| 발전가능성 | B2B 로컬라이제이션 API (웹툰·OTT·관광·박물관), 저자원 언어 확장 |
| ESG혁신 | 문화 다양성 보존(저자원 언어권 정보 접근성), 공공데이터 개방 생태계 기여(벤치마크 데이터셋 공개) |

---

## 2. 제품 정의

**한 줄 정의**: KF가 1987년부터 11개 언어로 발간한 《Koreana》 병렬 코퍼스를 기반으로,
한국 문화 콘텐츠를 문화 용어까지 정확하게 다국어로 옮기는 AI 로컬라이제이션 서비스.

3개 서브 제품(모두 하나의 웹 앱에서 데모):

### P1. 문화 로컬라이제이션 번역 엔진
- 입력: 한국어(또는 영어) 텍스트 + 타깃 언어(11개 언어 중 선택) + 도메인(일반/관광/공연·전시/콘텐츠 자막)
- 처리: (1) 입력에서 문화 용어 탐지 → (2) 병렬 용어사전에서 타깃 언어의 검증된 역어·설명 검색(RAG)
  → (3) 용어 제약을 걸어 Claude로 번역 생성 → (4) 용어별 근거(Koreana 출처 연도/호) 표시
- 출력: 번역문 + 사용된 문화 용어 카드(용어, 채택 역어, 근거 문헌, 대안 역어)
- 차별점: 일반 MT는 '한지'를 "Korean paper"로 뭉개지만, K-Rosetta는 KF 전문 번역가들이
  39년간 확립한 역어 관례("hanji (traditional Korean mulberry paper)")를 근거와 함께 적용

### P2. 다국어 문화 설명 RAG 챗봇
- 입력: 임의 언어의 질문 (예: "¿Qué es pansori?")
- 처리: 질문 언어 감지 → 다국어 임베딩으로 Koreana 코퍼스 검색(질문 언어 에디션 우선)
  → 검색 문서 근거로 답변 생성(질문 언어로) → 출처(기사 제목/연도/호) 인용
- 부가: 질문자 언어권 국가에 대한 **외교부 공공데이터 기반 컨텍스트**(§4.2) 결합
  — 예: 해당 국가의 한국 관련 교류 정보·문화행사·공관 안내를 답변에 연계
- 출력: 근거 인용이 달린 모국어 답변

### P3. K-Rosetta 벤치마크 (발표 킬러 데모)
- 문화 용어 N개(목표 300+)에 대해 [한국어 원문, 11개 언어 전문가 역어] 병렬 평가셋 구축
  (Koreana에서 자동 추출 + 검수)
- 동일 입력을 일반 번역기(GPT-4급 LLM 직접 번역, Google Translate)와 K-Rosetta에 투입,
  용어 충실도 자동 채점(LLM-judge + 용어 일치)
- 대시보드: 언어별(특히 아랍·인니·베트남·러시아 저자원 언어) 정확도 비교 차트,
  실패 사례 갤러리("GPT는 이렇게 틀렸고, 우리는 이렇게 맞혔다")

### 명시적 비범위 (이번 대회 데모에서 하지 않는 것)
- 사용자 계정/결제/과금 시스템
- 11개 언어 전부의 완전한 프로덕션 품질 보장 — **데모 집중 언어: 영어, 베트남어, 인도네시아어, 아랍어**
  (+가능하면 러시아어). 나머지는 "지원"으로 표시하되 벤치마크 수치는 집중 언어만 발표
- 파인튜닝(초기엔 RAG+용어 제약으로 충분, 발전가능성 슬라이드에서 로드맵으로 언급)

---

## 3. 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│  [오프라인 파이프라인 — scripts/]                                  │
│                                                                   │
│  Koreana 크롤러 ──▶ data/raw/ ──▶ 정제·병렬정렬 ──▶ data/processed/ │
│                                        │                          │
│                          문화용어 추출(Claude Batch)               │
│                                        │                          │
│                     병렬 문화용어 사전(glossary) + 문서 청크        │
│                                        │                          │
│                     임베딩(BGE-M3) ──▶ SQLite + sqlite-vec 인덱스  │
└─────────────────────────────────────────────────────────────────┘
                                         │ (빌드 산출물: krosetta.db)
┌─────────────────────────────────────────────────────────────────┐
│  [런타임 — backend/ FastAPI]                                      │
│                                                                   │
│  /api/translate ── 용어탐지 → 사전검색 → Claude 번역(용어제약)      │
│  /api/chat ─────── 다국어 RAG (검색 + 생성 + 인용)                 │
│  /api/benchmark ── 벤치마크 결과 조회                              │
│  /api/country ──── 공공데이터포털 연동 (외교부계열 API, R1 요건)    │
│  /api/glossary ─── 용어사전 조회/검색                              │
└─────────────────────────────────────────────────────────────────┘
                                         │ REST
┌─────────────────────────────────────────────────────────────────┐
│  [프론트 — frontend/ Next.js]                                     │
│  ① 번역 데모  ② 문화 챗봇  ③ 벤치마크 대시보드  (+데이터 출처 배지) │
└─────────────────────────────────────────────────────────────────┘
```

### 저장소 디렉터리 구조

```
shiver/
├─ CLAUDE.md                  # 자율 개발 운영 지침
├─ docs/
│  ├─ DEV_SPEC.md             # 본 문서
│  ├─ PROGRESS.md             # 진행 현황 (매 세션 갱신)
│  ├─ USER_ACTION_ITEMS.md    # 사용자 준비 사항
│  └─ BENCHMARK_REPORT.md     # M5에서 생성
├─ backend/
│  ├─ app/
│  │  ├─ main.py              # FastAPI 엔트리
│  │  ├─ config.py            # 설정/환경변수 (pydantic-settings)
│  │  ├─ routers/             # translate, chat, benchmark, country, glossary
│  │  ├─ services/
│  │  │  ├─ llm/              # Claude 클라이언트, 프롬프트, 배치
│  │  │  ├─ retrieval/        # 임베딩·벡터검색·용어사전 검색
│  │  │  └─ opendata/         # ★ data.go.kr 연동 (R1 필수요건)
│  │  └─ models/              # Pydantic 스키마, DB 모델
│  └─ tests/                  # pytest + fixtures
├─ pipeline/
│  ├─ crawler/                # Koreana 크롤러
│  ├─ align/                  # 병렬 정렬
│  ├─ glossary/               # 문화용어 추출·사전 구축
│  └─ index/                  # 임베딩·인덱스 빌드
├─ scripts/                   # 단계별 실행 스크립트 (사용자 로컬 실행 가능하게)
├─ frontend/                  # Next.js 데모 앱
├─ data/                      # raw/ processed/ cache/ (git 제외)
└─ .env.example
```

---

## 4. 데이터 명세

### 4.1 핵심 코퍼스: KF 《Koreana》 매거진

- 성격: KF(주최기관)가 1987년부터 발간한 한국 문화·예술 계간지. 11개 언어 에디션
  (한국어·영어·일본어·중국어·프랑스어·독일어·스페인어·러시아어·아랍어·인도네시아어·베트남어).
  기획서 사전 실측으로 "11개 언어 에디션 실재, 아카이브 1987~2026, 무인증 공개 열람"까지 확인됨.
- 활용 형태: 기사 단위 병렬 코퍼스(동일 기사에 대한 언어별 대응판) → 문화 용어 병렬 사전
  + RAG용 문서 청크.
- 수집 방법: §5.1 크롤러 명세 참조. 목록/본문이 AJAX 로딩임이 확인되었으므로
  네트워크 탭 기반 JSON 엔드포인트 우선, 실패 시 Playwright 헤드리스.
- **수집 범위 원칙(M1에서 확정)**: 처음부터 39년 전체를 노리지 않는다.
  1단계 = 최근 10년(2016~2026) × 집중 언어 4종 + 한국어·영어. 파이프라인 검증 후 확대.

### 4.2 공공데이터포털(data.go.kr) 등록 데이터 — R1 필수요건

> **원칙**: 아래 데이터 중 **최소 1건은 반드시 런타임에서 실제 호출**되어야 하며(심사 제외 방지),
> 안전을 위해 핵심 1건 + 백업 2건을 모두 연동한다. 각 데이터셋은 M1에서
> data.go.kr 상세페이지 URL·활용신청 승인까지 확인 후 이 표를 갱신한다.

<!-- RESEARCH_RESULTS_PLACEHOLDER: M0 리서치 결과로 갱신 -->

**연동 설계 공통 사항**
- 모든 data.go.kr 오픈API는 `serviceKey`(인증키) 필요 → 사용자 발급, `.env`의 `DATA_GO_KR_API_KEY`
- `backend/app/services/opendata/`에 데이터셋별 클라이언트 모듈 + 응답 캐시(TTL 24h, SQLite)
- 파일데이터(CSV/JSON)로 제공되는 데이터셋은 `scripts/fetch_opendata.py`로 내려받아
  DB 테이블로 적재하고, 데이터셋명·수정일·출처 URL을 `opendata_provenance` 테이블에 기록
- **UI 요건**: 데모 화면 하단에 "본 서비스는 공공데이터포털의 [데이터셋명](URL)을 활용합니다"
  출처 배지를 상시 노출 — 심사위원이 즉시 확인 가능하게

### 4.3 데이터 모델 (SQLite)

```sql
-- 기사 원본 (언어별 1행)
CREATE TABLE articles (
  id INTEGER PRIMARY KEY,
  article_group_id TEXT NOT NULL,   -- 동일 기사 묶음 키 (병렬 정렬 결과)
  lang TEXT NOT NULL,               -- ko, en, ja, zh, fr, de, es, ru, ar, id, vi
  year INTEGER, issue TEXT,
  title TEXT, author TEXT,
  body TEXT,                        -- 정제된 본문
  source_url TEXT,
  crawled_at TEXT
);

-- 문화 용어 병렬 사전 (핵심 자산)
CREATE TABLE glossary_terms (
  id INTEGER PRIMARY KEY,
  term_ko TEXT NOT NULL,            -- 예: '판소리'
  category TEXT,                    -- 음악/공예/음식/의례/복식/건축/문학/기타
  definition_ko TEXT
);
CREATE TABLE glossary_renderings (
  id INTEGER PRIMARY KEY,
  term_id INTEGER REFERENCES glossary_terms(id),
  lang TEXT NOT NULL,
  rendering TEXT NOT NULL,          -- 채택 역어 (예: 'pansori (epic chant)')
  strategy TEXT,                    -- 음차/음차+설명/의역/대체어
  evidence_article_id INTEGER REFERENCES articles(id),  -- 근거 기사
  frequency INTEGER DEFAULT 1,      -- 코퍼스 내 출현 횟수
  confidence REAL                   -- 추출 신뢰도
);

-- RAG 청크 + 벡터 (sqlite-vec)
CREATE TABLE chunks (
  id INTEGER PRIMARY KEY,
  article_id INTEGER REFERENCES articles(id),
  lang TEXT, seq INTEGER, text TEXT
);
-- vec0 가상 테이블: chunk_embeddings(embedding float[1024])

-- 공공데이터 출처 기록 (R1 증빙)
CREATE TABLE opendata_provenance (
  dataset_name TEXT, provider TEXT, source_url TEXT,
  fetched_at TEXT, record_count INTEGER
);
```

### 4.4 저작권·법적 고려 (발표 시 명시할 것)

- Koreana는 공개 발간물이나, **원문 전체의 상업적 재배포 권리는 별도** — 서비스는 원문을
  재배포하지 않고 (a) 용어 수준 파생 데이터(병렬 용어사전), (b) 검색 결과의 짧은 인용+출처 링크만 노출
- 수상 후 사업화 시 KF와 콘텐츠 이용 협의 필요함을 발표자료에 정직하게 명시 (기획서 리스크 §3과 일치)
- data.go.kr 데이터는 각 데이터셋의 이용허락범위(대부분 KOGL 제1유형) 준수, 출처 표기
- 크롤러는 robots.txt 준수, 요청 간격 제한(기본 1 req/sec), User-Agent에 연락처 명시

---

## 5. 오프라인 파이프라인 명세

### 5.1 Koreana 크롤러 (`pipeline/crawler/`)

1. **정찰 단계** (`recon.py`): 아카이브 페이지의 XHR/fetch 요청을 Playwright로 캡처하여
   기사 목록 JSON 엔드포인트·파라미터(언어코드 `langTy`, 연도, 호수, 페이지네이션)를 규명하고
   `crawler/endpoints.json`에 기록. — *이 단계 산출물이 이후 모든 수집의 기반.*
2. **목록 수집** (`list_articles.py`): 언어×연도별 기사 메타데이터(제목, URL, 호수) 전량 수집
   → `data/raw/index/{lang}.jsonl`
3. **본문 수집** (`fetch_articles.py`): asyncio + httpx, 동시성 4, 1 req/sec/호스트 제한,
   재시도(백오프), 실패 목록 재실행 가능(idempotent) → `data/raw/articles/{lang}/{id}.json`
4. **정제** (`clean.py`): HTML → 본문 텍스트, 이미지 캡션 보존, 광고/내비 제거
5. **스키마**: `{id, lang, year, issue, title, author, body_html, body_text, url, crawled_at}`

- 완료 기준(DoD): 집중 언어 6종(ko, en, vi, id, ar, ru)의 최근 10년 기사 수집률 ≥ 95%,
  파서 단위테스트(고정 fixture) 통과, `data/raw/stats.json`에 언어×연도 매트릭스 리포트 생성
- **환경 제약**: 원격 개발 환경에서 한국 사이트 접속이 차단될 수 있음 → 크롤러는 CLI 스크립트로
  완성하고, 차단 시 사용자 로컬 실행 가이드(`scripts/README.md`)를 제공 (CLAUDE.md §6)

### 5.2 병렬 정렬 (`pipeline/align/`)

- 목표: 언어별 기사들을 "같은 원 기사" 단위(`article_group_id`)로 묶기
- 방법(순차 적용, 비용 낮은 것부터):
  1. 메타데이터 정렬: 연도+호수+기사 순번/URL 패턴이 일치하면 동일 그룹 (Koreana는 호 단위
     동일 구성 번역이므로 대부분 여기서 해결될 것으로 예상 — M1 정찰에서 검증)
  2. 임베딩 정렬: 남는 것은 BGE-M3 문서 임베딩 코사인 유사도 + 헝가리안 매칭
  3. LLM 검증: 낮은 신뢰도 쌍만 Claude Haiku 배치로 동일 기사 여부 판정
- DoD: 정렬 정밀도 표본 검사(무작위 50쌍 수동/LLM 검증) ≥ 98%, 그룹 통계 리포트

### 5.3 문화용어 추출 & 병렬 사전 (`pipeline/glossary/`)

- 1단계 후보 추출: 한국어판 기사에서 문화 고유명사 후보 추출
  — 규칙(음차 패턴, 고유명사) + Claude Batch(기사당 1건, `claude-haiku-4-5`,
  구조화 출력으로 `{term, category, context_sentence}` 배열)
- 2단계 역어 정렬: 후보 용어별로 병렬 기사(그룹 내 타 언어판)에서 대응 역어 구간 탐색
  — Claude(`claude-opus-4-8`, 배치)로 "이 한국어 용어가 이 영어/베트남어 문단에서 어떻게
  번역되었는가" 추출, 근거 문장 저장
- 3단계 정규화·집계: 동일 용어 변형 통합(한지/韓紙), 언어별 역어 빈도 집계, 대표 역어 선정
- 목표 규모: **v1 = 용어 500개 × 집중 언어 4종 이상의 역어** (발표 데모에 충분),
  v2 = 1,500개 (시간 허용 시)
- DoD: 표본 100용어 수동 검수 정확도 ≥ 90%, `glossary_renderings` 커버리지 리포트

### 5.4 임베딩 & 인덱스 (`pipeline/index/`)

- 모델: `BAAI/bge-m3` (다국어 100+개 언어, 1024차원, 로컬 CPU 실행)
- 청킹: 문단 기준 300~500 토큰, 기사 메타(제목/연도/언어) 프리픽스
- 저장: SQLite + `sqlite-vec` 확장 (별도 인프라 불필요, 데모 배포 단순화)
- DoD: 다국어 검색 스모크 테스트 — "판소리"(ko), "pansori"(en), "판소리 관련 베트남어 질문"이
  모두 관련 기사 top-5에 도달

---

## 6. 백엔드 API 명세 (FastAPI)

공통: JSON, 에러는 `{error: {code, message}}`, 요청 로깅, CORS는 프론트 도메인만.

| 엔드포인트 | 메서드 | 요청 | 응답 (요지) |
|---|---|---|---|
| `/api/translate` | POST | `{text, source_lang, target_lang, domain?}` | `{translation, terms: [{term_ko, rendering, strategy, evidence: {title, year, issue, url}, alternatives[]}], model_meta}` |
| `/api/translate/compare` | POST | `{text, target_lang}` | `{krosetta, baseline_llm, google?}` — 벤치마크 데모용 나란히 비교 |
| `/api/chat` | POST | `{messages[], lang?}` | SSE 스트리밍, 최종 메시지에 `citations[]` (기사 출처) |
| `/api/glossary/search` | GET | `?q=&lang=` | 용어 카드 목록 |
| `/api/benchmark/summary` | GET | — | 언어별 점수 매트릭스, 사례 목록 (M5 산출물 정적 서빙) |
| `/api/country/{iso}` | GET | — | **공공데이터포털 연동 결과** (R1): 국가별 정보 + `provenance` (데이터셋명/출처 URL 포함 필수) |
| `/api/health` | GET | — | 파이프라인 산출물 버전, 인덱스 통계, 연동 데이터셋 상태 |

### 6.1 번역 엔진 상세 흐름 (`/api/translate`)

1. 용어 탐지: 입력 텍스트에서 `glossary_terms` 매칭(형태소 대응 포함) + 임베딩 유사 용어 후보
2. 컨텍스트 조립: 매칭 용어의 타깃 언어 역어·전략·근거 문장 (프롬프트 캐시 활용)
3. 생성: `claude-opus-4-8`, adaptive thinking, 시스템 프롬프트 =
   "KF 39년 관례 역어를 우선 채택, 음차+짧은 설명 병기 원칙, 용어카드 근거 준수" + 용어사전 컨텍스트
4. 후검증: 응답에서 지정 역어 미사용 시 1회 재생성(용어 제약 강조), 최종 용어 사용 여부 플래그
5. 응답 조립: 용어 카드에 Koreana 근거(기사 제목/연도/URL) 첨부

### 6.2 RAG 챗봇 상세 흐름 (`/api/chat`)

1. 언어 감지(경량 라이브러리 + LLM 폴백) → 검색 쿼리 확장(한국어+질문 언어)
2. 하이브리드 검색: sqlite-vec 벡터 top-20 → 언어 필터/재랭킹 → top-5
3. 국가 컨텍스트: 질문 언어권 국가에 대해 `/api/country` 데이터(공공데이터) 요약 결합
4. 생성: 질문 언어로 답변, 문장 단위 인용 `[1]`, 근거 없으면 "코퍼스에 근거 없음" 명시
5. SSE 스트리밍 응답

---

## 7. LLM 사용 명세

| 용도 | 모델 | 방식 | 비고 |
|---|---|---|---|
| 번역 생성, 역어 정렬(2단계) | `claude-opus-4-8` | Messages API, adaptive thinking | 품질 크리티컬 |
| 용어 후보 추출, 기사 분류, 정렬 검증 | `claude-haiku-4-5` | **Batches API** (50% 할인) | 대량 오프라인 |
| LLM-judge (벤치마크 채점) | `claude-opus-4-8` | Batches API | 채점 편향 방지 위해 루브릭 고정 |

- 프롬프트 캐싱: 번역 시스템 프롬프트+용어사전 공통부는 `cache_control: ephemeral` 1h TTL
- 구조화 출력: 추출/채점은 `output_config.format` (json_schema) 사용, 파싱 실패 재시도 1회
- 스트리밍: 챗봇 응답은 `messages.stream()`
- 금지: `temperature`/`top_p`/`budget_tokens` (Opus 4.8에서 400), 모델 ID에 날짜 접미사 부착
- **비용 추정(승인용)**: 용어 추출 파이프라인(기사 3,000건 × ~2K tok, Haiku 배치) ≈ $5~10,
  역어 정렬(용어 500 × 4개 언어, Opus 배치) ≈ $15~30, 벤치마크 채점 ≈ $10~20.
  전체 개발 기간 총 예상 **$50~120** 수준. 상한 초과 예상 시 PROGRESS에 보고 후 사용자 승인 대기.

---

## 8. 프론트엔드 명세 (Next.js)

공통 레이아웃: 상단 탭(번역/챗봇/벤치마크), 하단 고정 푸터에 **공공데이터 출처 배지**(R1 증빙)
+ "데이터: 한국국제교류재단 《Koreana》 1987–2026" 표기. 다크/라이트 대응, 반응형.

1. **번역 데모** (`/`): 좌측 입력(언어 선택, 예시 문장 프리셋 — 발표용 시나리오 3개 내장),
   우측 결과. 결과 아래 문화 용어 카드 리스트(근거 팝오버). "일반 번역기와 비교" 토글 시
   `/api/translate/compare` 결과를 나란히 표시하고 차이 나는 용어 하이라이트.
2. **문화 챗봇** (`/chat`): 채팅 UI, 언어 자동 감지 배지, 답변 인용 각주(호버 시 원문 발췌),
   질문 언어권 국가 정보 카드(공공데이터 출처 표시).
3. **벤치마크 대시보드** (`/benchmark`): 언어×시스템 정확도 히트맵/막대 차트,
   사례 브라우저(원문/전문가 역어/GPT 출력/K-Rosetta 출력 4단 비교), 방법론 설명 섹션.

- DoD: `npm run build` 성공, Playwright e2e(3개 화면 핵심 플로우), 발표장 오프라인 대비
  로컬 실행 원커맨드(`docker compose up` 또는 `make demo`)

---

## 9. 벤치마크 명세 (K-Rosetta Bench)

1. **평가셋 구축** (M5): `glossary_renderings`에서 신뢰도 상위 용어를 문장 컨텍스트와 함께 추출
   → `bench/dataset.jsonl` `{id, ko_sentence, term_ko, lang, expert_rendering, source}` 300+건
   (집중 언어 4종 × 75건 이상). 평가셋은 학습(용어사전)과 **출처 기사를 분리**(leakage 방지):
   짝수 연도 기사 → 사전 구축, 홀수 연도 기사 → 평가셋.
2. **비교 시스템**: (a) K-Rosetta, (b) 베이스라인 LLM 직접 번역(GPT-4급 — 키는 사용자 제공,
   미제공 시 Claude 바닐라 번역을 베이스라인으로 하고 발표에서 명시), (c) Google Translate(선택)
3. **채점**: 1차 자동 — 전문가 역어와의 정규화 일치/포함 여부. 2차 LLM-judge —
   "음차 보존, 의미 정확성, 설명 병기 적절성" 3축 0-2점 루브릭, 시스템명 블라인드 처리
4. **산출물**: `docs/BENCHMARK_REPORT.md`(방법론+결과+한계 정직 기술) + 대시보드용 JSON
- DoD: 전 과정 재현 스크립트 1개(`scripts/run_benchmark.py`), 표본 30건 수동 검수로 채점 타당성 확인

---

## 10. 비기능 요구사항

- **성능**: 번역 응답 < 15s(스트리밍 시작 < 3s), 챗봇 첫 토큰 < 5s, 데모 동시 사용자 ~10명 기준
- **보안**: API 키 서버 사이드 전용, rate limit(IP당 30 req/min), 입력 길이 상한(3,000자)
- **재현성**: 파이프라인 전 단계가 `scripts/`의 idempotent CLI로 실행 가능, 산출물 버전 태깅
- **오프라인 데모 대비**: 외부 API 장애 시를 대비해 발표 시나리오 3개의 응답 캐시를 내장하는
  `DEMO_MODE=cached` 지원 (발표장 네트워크 리스크 대응)

## 11. 테스트/검증 계획

- 단위: 파서·정렬·용어탐지·프롬프트 조립 (pytest, fixture 기반, 네트워크 불필요)
- 통합: FastAPI TestClient로 전 엔드포인트, LLM은 record/replay
- e2e: Playwright — 번역 플로우, 챗봇 1문답, 벤치마크 렌더
- 데이터 품질 게이트: 각 파이프라인 단계 종료 시 통계 리포트 생성 + 임계치 미달 시 실패 처리
- CI(선택): GitHub Actions에서 pytest+build (LLM 테스트는 replay만)

---

## 12. 마일스톤 & 태스크 분해 (2026-07-11 기준)

> 발표평가가 "7월 말~8월 중순"이므로 **7/31을 데모 완성 목표일**로 잡고 8월 초순을 버퍼로 둔다.
> 각 태스크는 독립 Claude Code 세션 1~2회 분량으로 분해되어 있다.

### M0. 셋업 & 명세 (7/11 ~ 7/12) — 본 세션
- [x] 공고 분석, CLAUDE.md, DEV_SPEC.md, PROGRESS.md, .gitignore
- [ ] `.env.example`, 백엔드/파이프라인 스캐폴딩, 의존성 정의

### M1. 데이터 수집 (7/12 ~ 7/16)
- T1.1 Koreana 아카이브 정찰(recon) → `endpoints.json` (Playwright)
- T1.2 목록 크롤러 + 본문 크롤러 + 정제기 (fixture 테스트 포함)
- T1.3 집중 언어 6종 × 최근 10년 수집 실행 (환경 차단 시 사용자 로컬 실행 가이드)
- T1.4 ★ data.go.kr 데이터셋 연동 모듈 + provenance 기록 (R1 — **최우선**)
- T1.5 수집 통계 리포트

### M2. 코퍼스 가공 (7/16 ~ 7/20)
- T2.1 병렬 정렬(메타→임베딩→LLM 검증)
- T2.2 문화용어 후보 추출 (Haiku 배치)
- T2.3 역어 정렬·사전 구축 v1 (Opus 배치, 500 용어)
- T2.4 임베딩·인덱스 빌드 + 다국어 검색 스모크

### M3. 백엔드 (7/19 ~ 7/24, M2와 부분 병행)
- T3.1 FastAPI 스캐폴딩 + config + health
- T3.2 `/api/translate` (+compare) — 용어 제약 번역
- T3.3 `/api/chat` — 다국어 RAG + 공공데이터 국가 컨텍스트
- T3.4 `/api/glossary`, `/api/country`, `/api/benchmark`
- T3.5 record/replay 테스트 하네스

### M4. 프론트 (7/22 ~ 7/27, 병행)
- T4.1 Next.js 셋업 + 공통 레이아웃(출처 배지)
- T4.2 번역 데모 화면 (+비교 토글)
- T4.3 챗봇 화면 (SSE)
- T4.4 벤치마크 대시보드
- T4.5 Playwright e2e + `make demo` 원커맨드

### M5. 벤치마크 & 폴리싱 (7/27 ~ 7/31)
- T5.1 평가셋 구축(leakage 분리) + 비교 시스템 실행
- T5.2 채점 + `BENCHMARK_REPORT.md` + 대시보드 데이터
- T5.3 발표 시나리오 3종 확정 + DEMO_MODE 캐시
- T5.4 (선택) 배포 — 사용자 계정 필요, 미정 시 로컬 데모로 확정

### 버퍼 (8/1 ~ 발표일): 심사 피드백 반영, 리허설, 안정화

---

## 13. 리스크 & 대응

| 리스크 | 확률 | 영향 | 대응 |
|---|---|---|---|
| Koreana 병렬 완전성이 기대 이하 (일부 기사만 다국어) | 중 | 중 | 정렬 단계에서 실측 후 "병렬 존재 기사만" 사전 구축. 용어 500개 목표는 부분 병렬로도 달성 가능 |
| 개발 환경에서 한국 사이트 접속 차단 | 높음(확인됨) | 중 | 크롤러를 CLI로 완성 + 사용자 로컬 실행 (USER_ACTION_ITEMS 참조) |
| data.go.kr 활용신청 승인 지연 | 중 | **높음(R1)** | 자동승인형 데이터셋 우선 선정 + 파일데이터 병행(즉시 다운로드 가능) |
| LLM 비용 초과 | 낮음 | 낮음 | §7 비용 상한, Haiku/배치 우선 |
| 벤치마크에서 기대만큼 격차가 안 벌어짐 | 중 | 높음 | 저자원 언어(ar, vi, id)와 희귀 용어에 집중 — 격차가 구조적으로 큰 지점. 결과는 정직하게 보고하되 사례 큐레이션으로 서사 확보 |
| 발표장 네트워크 장애 | 중 | 중 | DEMO_MODE=cached + 로컬 전체 스택 |

## 14. 사용자 액션 아이템

`docs/USER_ACTION_ITEMS.md` 참조 (API 키, 공모 접수, 데이터 활용신청 등).
