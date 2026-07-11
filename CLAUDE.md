# K-Rosetta — Claude Code 자율 개발 운영 지침

이 저장소는 「2026년 외교 공공데이터·AI 활용 경진대회」(제품·서비스 개발 부문) 출품작
**K-Rosetta**의 코드베이스입니다. Claude Code가 사용자 부재 중에도 자율적으로 개발을
진행할 수 있도록 설계되었습니다. **모든 세션은 이 문서의 규칙을 따릅니다.**

## 0. 최우선 원칙 (절대 위반 금지)

1. **공모전 필수요건**: 공공데이터포털(data.go.kr)에 등록된 외교부/산하기관 공공데이터
   1건 이상이 서비스에서 *실제로 호출·사용*되어야 한다. 이 연동을 제거하거나 mock으로
   대체한 채 커밋하지 않는다. 관련 코드: `backend/app/services/opendata/` (미활용 시 심사 제외).
2. **비밀키 커밋 금지**: API 키(Anthropic, data.go.kr, OpenAI 등)는 `.env`로만 관리.
   `.env`는 `.gitignore`에 반드시 포함. 커밋 전 `git diff --staged`에서 키 패턴
   (`sk-`, `ntn_`, `serviceKey=` 등) 검사.
3. **정직한 진행 보고**: `docs/PROGRESS.md`에 실제 검증된 것만 "완료"로 기록.
   테스트가 실패하면 실패로 기록한다.
4. **명세서가 진실의 원천**: 기능·범위 판단이 애매하면 `docs/DEV_SPEC.md`를 따른다.
   명세서와 충돌하는 구현을 하게 될 경우 명세서를 먼저 수정하고 사유를 커밋 메시지에 남긴다.

## 1. 작업 루프 (매 세션 공통)

1. `docs/PROGRESS.md`를 읽고 현재 마일스톤과 미완료 태스크를 파악한다.
2. `docs/DEV_SPEC.md`의 해당 마일스톤 섹션에서 태스크 정의와 완료 기준(DoD)을 확인한다.
3. 태스크 단위로 구현 → 검증 → 커밋. 커밋은 작게, 자주.
4. 세션 종료 전:
   - `docs/PROGRESS.md` 갱신 (완료/진행중/블로커, 타임스탬프 포함)
   - 사용자 입력이 필요한 블로커는 `docs/PROGRESS.md` 최상단 `## ⚠️ 사용자 확인 필요` 섹션에 기록
   - `git push -u origin <현재 브랜치>` (네트워크 실패 시 2s/4s/8s/16s 백오프로 4회 재시도)

## 2. 검증 규칙 (완료 선언의 조건)

- **Python 백엔드**: `cd backend && pytest -x -q` 통과 + `ruff check .` 클린.
- **크롤러/파이프라인**: 실제 대상 1건 이상에 대한 스모크 테스트가 통과해야 완료.
  (네트워크 차단 환경이면 저장된 fixture로 파서 테스트를 통과시키고, PROGRESS에
  "라이브 검증 필요"로 표기.)
- **API 엔드포인트**: 서버 기동 후 `httpx`로 실제 요청/응답 검증하는 테스트 포함.
- **프론트엔드**: `npm run build` 성공 + 핵심 플로우 Playwright 테스트
  (Chromium은 `/opt/pw-browsers/chromium`에 프리인스톨, `playwright install` 금지).
- **LLM 호출 코드**: 실 API 키가 없으면 record/replay fixture 기반 테스트로 검증하고
  라이브 검증 필요 표시를 남긴다.

## 3. 기술 스택 (변경 시 DEV_SPEC.md 갱신 필수)

- 백엔드: Python 3.11+, FastAPI, SQLite(+sqlite-vec), Pydantic v2
- 크롤러: httpx(+asyncio) 기본, AJAX/JS 렌더링 필요 시 Playwright
- LLM: Anthropic Claude API — 기본 `claude-opus-4-8`(번역·용어추출 등 품질 크리티컬),
  `claude-haiku-4-5`(대량 분류·전처리), 대량 배치는 Batches API(50% 할인) 사용
- 임베딩: `BAAI/bge-m3` (sentence-transformers, 로컬 CPU) — 다국어 지원 필수 요건
- 프론트: Next.js(App Router) + Tailwind, 데모용 단일 앱
- 저장 규약: 원시 크롤링 데이터 `data/raw/`(git 제외), 정제 데이터 `data/processed/`(git 제외),
  소량 fixture만 `backend/tests/fixtures/`에 커밋

## 4. Claude API 사용 규약

- 항상 공식 `anthropic` Python SDK 사용. 모델 ID는 정확히 `claude-opus-4-8` / `claude-haiku-4-5`.
- 사고 모드: `thinking={"type": "adaptive"}`. `budget_tokens`/`temperature` 등은 사용 금지(400 에러).
- 대량 코퍼스 처리(용어 추출, 정렬 검증 등)는 `client.messages.batches.create` 사용.
- 시스템 프롬프트(문화용어 사전 컨텍스트 등)는 `cache_control: {"type": "ephemeral"}`로 캐싱.
- 구조화 출력이 필요하면 `output_config={"format": {"type": "json_schema", ...}}` 사용.

## 5. 커밋/브랜치 규칙

- 개발 브랜치: `claude/foreign-ministry-competition-spec-hulyr3` (지시 없이 다른 브랜치에 푸시 금지)
- 커밋 메시지: 한국어 또는 영어, `[M<마일스톤>] <무엇을> — <검증 상태>` 형식 권장
  예: `[M2] Koreana 기사 11개 언어 정렬 파이프라인 — pytest 14건 통과`
- 모델 ID·내부 세션 정보를 커밋 메시지/코드 주석에 남기지 않는다.

## 6. 네트워크/환경 주의사항

- 이 원격 환경의 프록시는 일부 한국 도메인(data.go.kr, kf.or.kr, koreana.or.kr)으로의
  직접 접속을 차단할 수 있다. 크롤러·API 연동 코드는 **어디서든 실행 가능하게** 작성하되,
  라이브 실행이 차단되면: (a) 코드+테스트(fixture)로 완성도 확보, (b) PROGRESS에
  "사용자 로컬 실행 필요" 태스크로 등록하고 실행 스크립트(`scripts/`)와 사용법을 남긴다.
- 디스크 할당량 주의: 대용량 크롤링 데이터는 필요한 만큼만 저장, 중간 산출물은 정리.

## 7. 하지 말 것

- 공공데이터 연동을 "나중에" 로 미루는 것 (M1 필수 범위)
- 검증 없는 대규모 리팩터링
- 사용자 확인 없이 외부 서비스에 데이터 업로드/배포
- Koreana 원문 전체를 저장소에 커밋 (저작권 — 파생 산출물인 용어사전·인덱스·통계만 커밋 가능,
  그마저 발표용 범위로 최소화)
