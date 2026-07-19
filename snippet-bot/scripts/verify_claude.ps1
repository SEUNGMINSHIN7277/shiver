# 1단계 검증 (§12-1): Claude Code 헤드리스 모드가 "구독 인증"으로 동작하는지 확인.
# 일반 PowerShell에서 실행: powershell -ExecutionPolicy Bypass -File scripts\verify_claude.ps1

# 한글 출력을 위해 콘솔 인코딩을 UTF-8로 전환
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "== 1) ANTHROPIC_API_KEY 존재 여부 확인 ==" -ForegroundColor Cyan
$found = $false
foreach ($scope in "Process", "User", "Machine") {
    $value = [Environment]::GetEnvironmentVariable("ANTHROPIC_API_KEY", $scope)
    if ($value) {
        Write-Warning "ANTHROPIC_API_KEY가 [$scope] 범위에 설정되어 있습니다!"
        Write-Warning "이 변수가 있으면 Claude Code가 구독 대신 API 과금으로 전환됩니다. 삭제하세요:"
        if ($scope -eq "User")    { Write-Host '  [Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", $null, "User")' }
        if ($scope -eq "Machine") { Write-Host '  관리자 PowerShell: [Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", $null, "Machine")' }
        $found = $true
    }
}
if (-not $found) { Write-Host "ANTHROPIC_API_KEY 없음 — 정상 (구독 사용량으로 처리됨)" -ForegroundColor Green }

Write-Host "`n== 2) claude 명령 경로 확인 ==" -ForegroundColor Cyan
where.exe claude
if ($LASTEXITCODE -ne 0) {
    Write-Error "claude 명령을 찾을 수 없습니다. Claude Code 설치/PATH를 확인하세요."
    exit 1
}

Write-Host "`n== 3) 헤드리스 호출 테스트 ==" -ForegroundColor Cyan
claude -p "안녕이라고만 답해" --output-format text
if ($LASTEXITCODE -eq 0) {
    Write-Host "`n헤드리스 모드 정상 동작 — 검증 통과" -ForegroundColor Green
} else {
    Write-Error "claude -p 호출 실패 (종료 코드 $LASTEXITCODE). 로그인 상태를 확인하세요: claude 실행 후 /login"
    exit 1
}
