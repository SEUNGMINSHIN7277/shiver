"""Windows 토스트 알림 — plyer 우선, 실패 시 PowerShell 폴백 (§10).

알림은 최선 노력(best-effort)으로만 시도한다. 알림 실패가 파이프라인 자체를
중단시키지 않도록 모든 예외를 삼키고 로그만 남긴다.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys


def notify(title: str, message: str, logger: logging.Logger | None = None) -> None:
    if sys.platform != "win32":
        if logger:
            logger.info("[알림 생략(비 Windows)] %s: %s", title, message)
        return

    try:
        from plyer import notification
        notification.notify(title=title, message=message[:250],
                            app_name="SnippetBot", timeout=10)
        return
    except Exception as exc:
        if logger:
            logger.warning("plyer 알림 실패(%s) — PowerShell 폴백 시도", exc)

    try:
        # 제목/본문은 명령 문자열에 절대 삽입하지 않고 환경변수로만 전달한다.
        # (오류 메시지에는 외부 유래 텍스트가 섞이므로, 문자열 이스케이프 방식은
        #  유니코드 인용부호 등을 통한 PowerShell 인젝션 여지가 있다)
        script = (
            "[void][System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms');"
            "[void][System.Reflection.Assembly]::LoadWithPartialName('System.Drawing');"
            "$n = New-Object System.Windows.Forms.NotifyIcon;"
            "$n.Icon = [System.Drawing.SystemIcons]::Information;"
            "$n.Visible = $true;"
            "$n.ShowBalloonTip(10000, $env:SNIPPETBOT_NOTIFY_TITLE, "
            "$env:SNIPPETBOT_NOTIFY_MESSAGE, 'Info');"
            "Start-Sleep -Seconds 8;"
            "$n.Dispose()"
        )
        env = dict(os.environ)
        env["SNIPPETBOT_NOTIFY_TITLE"] = title[:100]
        env["SNIPPETBOT_NOTIFY_MESSAGE"] = message[:250]
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, timeout=30, env=env,
        )
    except Exception as exc:
        if logger:
            logger.error("PowerShell 알림도 실패: %s (알림 내용: %s — %s)", exc, title, message)
