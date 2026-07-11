#!/usr/bin/env python3
"""오픈API 라이브 응답 기록 (사용자 로컬 PC에서 실행 — 1분 소요).

사용법:
    # .env에 DATA_GO_KR_API_KEY가 있어야 함
    python scripts/record_opendata_fixtures.py
    git add backend/tests/fixtures data/pilot/derived && git commit -m "opendata live fixtures" && git push
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.services.opendata.clients import ENDPOINTS, fetch  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "backend" / "tests" / "fixtures" / "opendata"
OUT.mkdir(parents=True, exist_ok=True)

SAMPLES = {
    "univ_korname": {"cond[country_nm::EQ]": "베트남"},
    "country_code": {},
    "oda_business": {"cond[country_nm::EQ]": "베트남"},
}


def main() -> None:
    ok = 0
    for service, params in SAMPLES.items():
        try:
            data = fetch(service, **params)
            (OUT / f"{service}.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            n = data.get("totalCount") or data.get("response", {}).get("body", {}).get("totalCount", "?")
            print(f"  ✓ {ENDPOINTS[service]['dataset']} — 응답 저장 (totalCount={n})")
            ok += 1
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ {service}: {type(e).__name__}: {e}")
            print(f"    → 파라미터 형식이 다르면 브라우저에서 {ENDPOINTS[service]['portal']} 의 '미리보기'로 확인")
    print(f"\n{ok}/{len(SAMPLES)} 성공. 성공 파일을 커밋해 주세요 (라이브 연동 증빙 + 테스트 fixture).")


if __name__ == "__main__":
    main()
