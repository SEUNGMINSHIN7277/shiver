#!/usr/bin/env python3
"""데모 스크린샷 생성 (기획서·발표자료용) → docs/demo_assets/"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://localhost:8777"
OUT = Path(__file__).resolve().parents[1] / "docs" / "demo_assets"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> None:
    with sync_playwright() as p:
        exe = "/opt/pw-browsers/chromium"  # 프리인스톨 크롬 바이너리 심링크
        browser = p.chromium.launch(executable_path=exe if Path(exe).exists() else None)
        page = browser.new_page(viewport={"width": 1280, "height": 900}, device_scale_factor=2)
        page.goto(BASE, wait_until="networkidle")

        # 1) 번역: 프리셋(떡국) 실행 + 비교 토글
        page.check("#compare-toggle")
        page.click("#preset-chips .chip:nth-child(4)")  # 음식 — 설날 떡국
        page.wait_for_selector(".term-card")
        page.screenshot(path=str(OUT / "01_translate_compare.png"), full_page=True)

        # 1b) 자막 모드: 드라마 대사 (베트남어)
        page.click('#lang-seg .seg-btn[data-lang="vi"]')
        page.click("#preset-chips .chip:nth-child(1)")  # 드라마 자막
        page.wait_for_selector(".term-card")
        page.screenshot(path=str(OUT / "04_subtitle_mode_vi.png"), full_page=True)
        page.click('#lang-seg .seg-btn[data-lang="en"]')

        # 2) 챗봇: 프리셋 2개 질문
        page.click(".tab[data-view=chat]")
        page.click('#chat-chips .chip[data-q="What is pansori?"]')
        page.wait_for_selector(".msg.bot")
        page.click('#chat-chips .chip[data-q="판소리가 뭐야?"]')
        page.wait_for_function("document.querySelectorAll('.msg.bot').length >= 2")
        page.screenshot(path=str(OUT / "02_chat_citations.png"), full_page=True)

        # 3) 벤치마크
        page.click(".tab[data-view=benchmark]")
        page.wait_for_selector("#bench-table tbody tr")
        page.screenshot(path=str(OUT / "03_benchmark.png"), full_page=True)

        browser.close()
    print(f"스크린샷 3장 저장 → {OUT}")


if __name__ == "__main__":
    sys.exit(main())
