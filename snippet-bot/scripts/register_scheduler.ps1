# Windows 작업 스케줄러 등록 (§9) — 관리자 PowerShell에서 실행:
#   powershell -ExecutionPolicy Bypass -File scripts\register_scheduler.ps1
#
# schtasks를 /ru 없이 사용하므로 두 작업 모두 "현재 로그인한 사용자" 계정으로,
# "사용자가 로그온한 경우에만 실행"으로 등록된다 → Claude Code 로그인 세션을 공유한다.

$Base   = "C:\snippet-bot"
$Python = Join-Path $Base "venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    Write-Error "venv가 없습니다: $Python — 먼저 README의 설치 절차대로 venv를 만드세요."
    exit 1
}

schtasks /create /tn "SnippetBot-Daily"  /tr "`"$Python`" `"$Base\daily.py`""  /sc daily /st 23:30 /f
schtasks /create /tn "SnippetBot-Weekly" /tr "`"$Python`" `"$Base\weekly.py`"" /sc weekly /d SUN /st 23:30 /f

# 추가 설정: 놓친 실행 보충(StartWhenAvailable), 배터리 제한 해제
foreach ($name in "SnippetBot-Daily", "SnippetBot-Weekly") {
    $task = Get-ScheduledTask -TaskName $name
    $task.Settings.StartWhenAvailable        = $true    # PC가 꺼져 있었으면 다음 부팅 시 실행
    $task.Settings.DisallowStartIfOnBatteries = $false  # 배터리 상태에서도 시작
    $task.Settings.StopIfGoingOnBatteries     = $false
    $task.Settings.ExecutionTimeLimit         = "PT1H"
    Set-ScheduledTask -InputObject $task | Out-Null
    Write-Host "$name 등록·설정 완료" -ForegroundColor Green
}

Write-Host "`n등록 확인:" -ForegroundColor Cyan
schtasks /query /tn "SnippetBot-Daily" /fo LIST | Select-String "작업 이름|다음 실행|TaskName|Next Run"
schtasks /query /tn "SnippetBot-Weekly" /fo LIST | Select-String "작업 이름|다음 실행|TaskName|Next Run"

Write-Host "`n[검증 팁 §12-5] 자동 실행 테스트: 실행 시각을 2분 뒤로 잠시 바꿨다가 복원하세요:" -ForegroundColor Yellow
Write-Host '  schtasks /change /tn "SnippetBot-Daily" /st HH:mm   (2분 뒤 시각)'
Write-Host '  → 실행 확인 후: schtasks /change /tn "SnippetBot-Daily" /st 23:30'
