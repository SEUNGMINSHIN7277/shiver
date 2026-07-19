# snippet-bot — 일간/주간 스니펫 자동화 파이프라인

팀 스니펫 사이트("1000")에 일간/주간 스니펫을 자동으로 **작성 → 업로드 → AI채점 → 저장**하는
Windows 자동화 파이프라인입니다. **사용자 개입 0**이 목표입니다.

- **일간**: 매일 23:30, **그날 로컬 Claude Code에서 나눈 대화 기록을 자동 수집**
  (`%USERPROFILE%\.claude\projects\`)해 7항목 스니펫 작성. `log\today.md`에 메모를
  적어두면 보조 자료로 함께 사용(선택 사항 — 없어도 동작).
- **주간**: 매주 일요일 23:50(일간 완료 후), 그 주의 일간 스니펫들을 요약해 주간 스니펫 작성
- **LLM**: Anthropic API 키를 쓰지 않습니다. 이 PC에 로그인된 **Claude Code 헤드리스 모드**
  (`claude -p`)를 서브프로세스로 호출해 **구독 사용량**으로 처리합니다(추가 과금 0원).

> ⚠️ 수집 범위 한계: claude.ai **웹/모바일** 대화는 PC에 저장되지 않아 수집할 수 없습니다.
> **로컬 Claude Code(CLI·IDE 확장)** 에서 작업한 대화만 자동 수집됩니다. 웹에서만 작업한
> 날은 `log\today.md`에 메모를 남기면 그것으로 스니펫이 생성됩니다.

## 현재 상태

| 구성요소 | 상태 |
|---|---|
| `config.py` / `notify.py` | ✅ 완료 (토큰 마스킹, ANTHROPIC_API_KEY 제거 가드, 재시도 유틸, 토스트 알림) |
| `generate.py` | ✅ 완료 (`claude -p` 호출, 180초 타임아웃, 3회 재시도, 본문 추출) |
| `daily.py` / `weekly.py` | ✅ 완료 (`--dry-run` 포함) |
| `site_api.py` | ✅ **캡처 기반 구현 완료** — 사용자 PC에서 라이브 검증 필요 (`scripts\test_site_api.py`, 아래 §사이트 API 참고) |
| 스케줄러 등록 스크립트 | ✅ `scripts/register_scheduler.ps1` |

## 설치 (Windows)

```powershell
# 1) 프로젝트를 C:\snippet-bot 에 배치 (클론 후 snippet-bot 폴더를 복사하거나, 직접 클론)
#    이 코드는 경로를 파일 위치 기준으로 계산하므로 다른 경로에 둬도 동작합니다.

cd C:\snippet-bot

# 2) 가상환경 + 의존성
python -m venv venv
venv\Scripts\pip install -r requirements.txt

# 3) 환경변수
copy .env.example .env
notepad .env   # 재발급받은 새 토큰과 사이트 베이스 URL 입력
```

> ⚠️ **보안**: 기존에 노출된 적 있는 토큰은 쓰지 말고 **재발급받은 새 토큰**만 `.env`에
> 넣으세요. `.env`는 `.gitignore`에 포함되어 커밋되지 않으며, 로그에는 토큰이 자동
> 마스킹됩니다.

## 1단계 검증 — claude 헤드리스 모드 확인 (§12-1)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\verify_claude.ps1
```

이 스크립트는 ① `ANTHROPIC_API_KEY`가 Process/User/Machine 어느 범위에도 없는지 확인하고
(있으면 삭제 명령 안내), ② `where claude`로 경로를 확인한 뒤, ③
`claude -p "안녕이라고만 답해" --output-format text`로 구독 인증 동작을 검증합니다.

## 사용법

```powershell
# 평소: 아무것도 안 해도 됩니다. 로컬 Claude Code로 작업만 하면
# 그날 대화가 자동 수집되어 23:30에 스니펫이 올라갑니다.
# (선택) log\today.md 에 메모를 적어두면 보조 자료로 함께 사용됩니다.

# dry-run: 사이트 API 호출 없이 스니펫 생성 결과만 콘솔에 출력 (§12-2)
venv\Scripts\python daily.py --dry-run
venv\Scripts\python weekly.py --dry-run

# 실제 실행
venv\Scripts\python daily.py
venv\Scripts\python weekly.py
```

- 그날 Claude 대화도 `today.md` 메모도 없으면 빈 스니펫을 올리지 않고 "오늘 기록이 없습니다"
  알림 후 종료합니다.
- 성공 시 생성된 스니펫이 `log\archive\YYYY-MM-DD.md`로 저장되고(주간 요약의 폴백 자료),
  `today.md`가 있었다면 `log\archive\YYYY-MM-DD_memo.md`로 보관 후 빈 파일로 재생성됩니다.
- 실행 로그: `logs\daily_YYYY-MM-DD.log`, `logs\weekly_YYYY-WW.log`
- 실패 시(생성 실패·로그인 만료·한도 초과·API 오류) Windows 토스트 알림이 뜹니다.
  LLM 생성이 실패하면 **업로드하지 않습니다**(불완전한 내용 업로드 금지).

## 사이트 API (§6 — 2026-07-19 Network 캡처 기반 구현)

캡처로 확인된 API 구조 (베이스: `https://api.1000.school`):

| 동작 | 엔드포인트 |
|---|---|
| 일간 데이터/목록 조회 | `GET /daily-snippets/page-data` |
| 일간 스니펫 저장 | `PUT /daily-snippets/{id}` — 본문 `{"content": "<마크다운>"}` (이미 존재하는 레코드의 id에 PUT) |
| AI 채점 | `GET /daily-snippets/feedback?stream=1` — SSE(text/event-stream) 스트리밍 |
| 주간 계열 | `/weekly-snippets/...` — 일간과 대칭 구조로 가정(라이브 검증 필요) |
| 인증(브라우저 기준) | `session` 쿠키 + 쓰기 요청에 `x-csrf-token`(`GET /auth/csrf`) |

**인증 전략**: 사이트 설정(설정 → API)에서 발급한 API 토큰을 `Authorization: Bearer`로
1순위 시도합니다. 거부(401/403)되면 `.env`의 `SNIPPET_SITE_SESSION`에 브라우저 `session`
쿠키 값을 넣는 쿠키 모드로 전환하세요 (`.env.example` 참고).

**라이브 검증** (원격 개발 환경은 이 도메인 접속이 차단되어 있어 PC에서 실행해야 합니다):

```powershell
venv\Scripts\python scripts\test_site_api.py check         # 인증 + page-data 구조 + 오늘 id 탐색
venv\Scripts\python scripts\test_site_api.py weekly-check  # 주간 page-data 구조
venv\Scripts\python scripts\test_site_api.py save-test     # 일간 저장 테스트(⚠️ 오늘 내용 덮어씀, 확인 입력 필요)
venv\Scripts\python scripts\test_site_api.py grade         # AI 채점(SSE) 테스트
```

`check`에서 id 탐색이 실패하거나 응답 구조가 다르면, `logs\dump_*.json` 파일을 공유해
주세요 — 그 구조에 맞게 코드를 조정합니다.

## 스케줄러 등록 (§9)

`site_api.py` 구현과 수동 검증(§12)이 끝난 뒤, **관리자 PowerShell**에서:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\register_scheduler.ps1
```

등록 내용:
- `SnippetBot-Daily`: 매일 23:30 / `SnippetBot-Weekly`: 매주 일요일 **23:50**
  (명세 §9는 둘 다 23:30이지만, 동시 실행 시 주간 요약이 일요일 기록을 항상 놓치므로
  주간을 20분 늦춤 — 일간이 생성·업로드를 마친 뒤 수집되도록)
- "예약 시간을 놓친 경우 가능한 한 빨리 시작" 활성화 (PC가 꺼져 있었으면 다음 부팅 시 보충 실행)
  - 보충 실행 날짜 보정: 일간은 23시 이전 실행이면 **전날** 날짜로, 주간은 일요일이 아니면
    **직전 일요일의 주**로 처리 (같은 날짜 중복 업로드는 archive 존재 확인으로 차단)
- 배터리 제한 해제 (노트북에서도 실행)
- 현재 사용자 계정, "로그온한 경우에만 실행" → Claude Code 로그인 세션 공유

## 검증 절차 (§12)

1. ✅ `scripts\verify_claude.ps1` — 헤드리스 모드·구독 인증 확인
2. `daily.py --dry-run` / `weekly.py --dry-run` — 생성 결과 콘솔 확인
3. (site_api 구현 후) 테스트 스니펫 1건 실제 업로드 → 사이트 UI 표시 확인 → AI채점 동작 확인
4. `python daily.py` 수동 실행으로 전체 흐름 확인
5. 스케줄러 등록 후 실행 시각을 2분 뒤로 임시 변경해 자동 실행 검증 → 23:30 복원
   (`schtasks /change /tn "SnippetBot-Daily" /st HH:mm`)
6. `weekly.py`도 동일 절차 반복

## 개발자용 단위 테스트

사이트/claude 호출을 모킹한 단위 테스트가 `tests/`에 있습니다 (Windows 불필요, 어느 OS에서든 실행 가능):

```bash
python -m pytest tests/ -q
```

## 동작 세부사항·설계 메모

- **과금 방지 가드**: `daily.py`/`weekly.py` 시작 시 `ANTHROPIC_API_KEY`가 있으면 경고
  로그 + 알림 후 프로세스 환경에서 제거하고 진행합니다. `claude` 서브프로세스에도 이 변수를
  제거한 환경을 전달합니다.
- **긴 입력 처리**: `today.md` 본문은 명령줄 인자가 아니라 **stdin**으로 전달합니다
  (Windows 명령줄 8191자 제한 회피).
- **본문 추출**: 프롬프트가 스니펫을 `<<<SNIPPET_START>>>`/`<<<SNIPPET_END>>>` 마커 사이에
  출력하도록 지시하고, 코드가 마커 사이만 추출합니다(마커 누락 시 전체 출력을 정리해 사용).
- **재시도**: 모든 claude/API 호출은 3회 재시도(백오프 2s/4s/8s). 로그인 만료·사용량 한도
  오류는 재시도하지 않고 즉시 알림으로 표시합니다.
- **채점 실패 시**: 업로드는 됐지만 채점이 실패하면 `today.md`를 보관하지 않고 남겨둡니다
  (재실행 시 중복 업로드 가능성이 있으므로 알림을 확인하고 수동 정리하세요).
