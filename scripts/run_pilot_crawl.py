#!/usr/bin/env python3
"""Koreana 파일럿 크롤러 실행 스크립트 (사용자 로컬 PC에서 실행).

사용법:
    pip install -r pipeline/requirements.txt
    python scripts/run_pilot_crawl.py                       # 기본: ko,en,vi,id × 120건
    python scripts/run_pilot_crawl.py --langs ko,en --limit 60
완료 후:
    git add data/pilot && git commit -m "pilot corpus" && git push
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.crawler.pilot_crawler import PilotConfig, run_pilot  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Koreana pilot crawler")
    ap.add_argument("--langs", default="ko,en,vi,id",
                    help="쉼표 구분 언어 (ko,en,ja,zh,fr,de,es,ru,ar,id,vi)")
    ap.add_argument("--limit", type=int, default=120, help="언어당 최대 기사 수")
    ap.add_argument("--interval", type=float, default=1.0, help="요청 간격(초), 1.0 미만 금지")
    ap.add_argument("--out", default="data/pilot/koreana")
    args = ap.parse_args()

    cfg = PilotConfig(
        languages=[x.strip() for x in args.langs.split(",") if x.strip()],
        per_lang_limit=args.limit,
        request_interval=max(args.interval, 1.0),
        out_dir=Path(args.out),
    )
    stats = run_pilot(cfg)
    fetched = stats.get("fetched", {})
    if not fetched or sum(fetched.values()) == 0:
        print("\n⚠️ 수집 0건 — data/pilot/koreana/probe/ 와 list_samples/ 의 HTML을 커밋해 주세요.")
        print("   (원격 세션이 HTML 구조를 보고 파서를 수정합니다)")
        sys.exit(2)


if __name__ == "__main__":
    main()
