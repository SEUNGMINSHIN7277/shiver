# snippet-bot — 일간/주간 스니펫 자동화 파이프라인

팀 스니펫 사이트("1000")에 일간/주간 스니펫을 자동으로 **작성 → 업로드 → AI채점 → 저장**하는
Windows 자동화 파이프라인입니다.

- **일간**: 매일 23:30, `log\today.md`의 하루 기록으로 7항목 스니펫 작성
- **주간**: 매주 일요일 23:30, 그 주의 일간 스니펫들을 요약해 주간 스니펫 작성
- **LLM**: Anthropic API 키를 쓰지 않습니다. 이 PC에 로그인된 **Claude Code 헤드리스 모드**
  (`claude -p`)를 서브프로세스로 호출해 **구독 사용량**으로 처리합니다(추가 과금 0원).

## 현재 상태

| 구성요소 | 상태 |
|---|---|
| `config.py` / `notify.py` | ✅ 완료 (토큰 마스킹, ANTHROPIC_API_KEY 제거 가드, 재시도 유틸, 토스트 알림) |
| `generate.py` | ✅ 완료 (`claude -p` 호출, 180초 타임아웃, 3회 재시도, 본문 추출) |
| `daily.py` / `weekly.py` | ✅ 완료 (`--dry-run` 포함) |
| `site_api.py` | ⚠️ **시그니처만 구현** — 사이트 Network 탭 캡처 수령 후 실제 구현 (아래 §사이트 API 참고) |
| 스케줄러 등록 스크립트 | ✅ `scripts/register_scheduler.ps1` |

`site_api.py`가 구현되기 전까지는 `--dry-run`으로 스니펫 생성까지만 동작합니다.

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
# 하루 동안 log\today.md 에 자유롭게 기록을 적어둔다 (형식 무관)

# dry-run: 사이트 API 호출 없이 스니펫 생성 결과만 콘솔에 출력 (§12-2)
venv\Scripts\python daily.py --dry-run
venv\Scripts\python weekly.py --dry-run

# 실제 실행 (site_api.py 구현 후)
venv\Scripts\python daily.py
venv\Scripts\python weekly.py
```

- `today.md`가 없거나 비어 있으면 빈 스니펫을 올리지 않고 "오늘 기록이 없습니다" 알림 후 종료합니다.
- 성공 시 `today.md`는 `log\archive\YYYY-MM-DD.md`로 이동하고 빈 `today.md`가 재생성됩니다.
- 실행 로그: `logs\daily_YYYY-MM-DD.log`, `logs\weekly_YYYY-WW.log`
- 실패 시(생성 실패·로그인 만료·한도 초과·API 오류) Windows 토스트 알림이 뜹니다.
  LLM 생성이 실패하면 **업로드하지 않습니다**(불완전한 내용 업로드 금지).

## 사이트 API 리버스 엔지니어링 (§6 — 구현 대기 중)

사이트에 공식 API 문서가 없어, 브라우저 캡처를 받아야 `site_api.py`를 완성할 수 있습니다.

**진행 방법**: 브라우저에서 사이트 로그인 → `F12` → **Network** 탭을 연 뒤, 아래 4가지 동작을
수행하면서 각 요청의 ① URL ② 메서드 ③ 요청 헤더(특히 인증: `Authorization: Bearer …`인지
쿠키/세션인지) ④ 페이로드 JSON ⑤ 응답 JSON을 캡처해 공유해 주세요
(Network 탭에서 요청 우클릭 → *Copy as cURL* 이 가장 정확합니다. **토큰/쿠키 값은 가려도
됩니다 — 구조만 필요합니다**):

| 동작 | 구현될 함수 |
|---|---|
| a. 일간 스니펫 "저장하기" 클릭 | `post_daily_snippet(date, content) -> snippet_id` |
| b. "AI 채점" 클릭 | `run_ai_grading(snippet_id) -> grading_result` |
| c. 주간 스니펫 저장 | `post_weekly_snippet(week_range, content) -> snippet_id` |
| d. 일간 스니펫 목록/상세 조회(GET) | `get_daily_snippets(start, end) -> list` |

조회 API(d)가 없으면 주간 파이프라인은 자동으로 `log\archive\`의 해당 주 파일들을 사용합니다.

## 스케줄러 등록 (§9)

`site_api.py` 구현과 수동 검증(§12)이 끝난 뒤, **관리자 PowerShell**에서:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\register_scheduler.ps1
```

등록 내용:
- `SnippetBot-Daily`: 매일 23:30 / `SnippetBot-Weekly`: 매주 일요일 23:30
- "예약 시간을 놓친 경우 가능한 한 빨리 시작" 활성화 (PC가 꺼져 있었으면 다음 부팅 시 보충 실행)
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
