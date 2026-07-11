#!/usr/bin/env python3
"""오픈API 3종 라이브 응답 기록 (사용자 한국 PC에서 실행, 약 1분).

승인된 오픈API를 실제로 호출해 응답 JSON을 저장한다. 이 개발 환경(해외 서버)에서는
apis.data.go.kr 접속이 차단되므로 반드시 한국 IP의 PC에서 실행해야 한다(크롤과 동일).

사전 준비: 저장소 루트에 .env 파일, 안에 아래 한 줄 (data.go.kr 마이페이지의 '일반 인증키'):
    DATA_GO_KR_API_KEY=여기에_인증키

실행:
    python scripts/record_opendata_fixtures.py
성공 후:
    git add backend/tests/fixtures data/pilot/opendata_api
    git commit -m "opendata API 라이브 응답"
    git push
그다음 채팅에 "API 응답 올렸어" 라고 알려주세요. 재빌드하면 서비스에 자동 통합됩니다.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "backend" / "tests" / "fixtures" / "opendata"
DERIVED = ROOT / "data" / "pilot" / "opendata_api"
FIX.mkdir(parents=True, exist_ok=True)
DERIVED.mkdir(parents=True, exist_ok=True)


def load_key() -> str:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("DATA_GO_KR_API_KEY="):
                return line.split("=", 1)[1].strip()
    return os.environ.get("DATA_GO_KR_API_KEY", "")


# (이름, 엔드포인트, 시도할 파라미터 세트들 — 첫 성공을 채택)
APIS = {
    "country_code": {
        "dataset": "외교부_국가·지역별 표준코드 (15075346)",
        "url": "https://apis.data.go.kr/1262000/CountryCodeService3/getCountryCodeList3",
        "params": [{"numOfRows": 300, "pageNo": 1, "returnType": "JSON"},
                   {"numOfRows": 300, "pageNo": 1, "type": "json"}],
    },
    "univ_korname": {
        "dataset": "한국국제교류재단_해외대학 표준국문명칭 (15075335)",
        "url": "https://apis.data.go.kr/B260004/OverseaUnivKornameService2/getKornameList2",
        "params": [{"numOfRows": 100, "pageNo": 1, "returnType": "JSON", "cond[country_iso_alp2::EQ]": "VN"},
                   {"numOfRows": 100, "pageNo": 1, "type": "json"}],
    },
    "oda_business": {
        "dataset": "한국국제협력단_융합 KOICA-ODA·KF 공공외교 사업정보 (15099215)",
        "url": "https://apis.data.go.kr/B260003/OdaBusinessInfoService/getOdaBusinessInfoList",
        "params": [{"numOfRows": 100, "pageNo": 1, "returnType": "JSON"},
                   {"numOfRows": 100, "pageNo": 1, "type": "json"}],
    },
}


def looks_ok(data) -> bool:
    s = json.dumps(data)[:2000]
    return ("totalCount" in s or '"item"' in s or "resultCode" in s) and "SERVICE_KEY" not in s.upper()


def main() -> None:
    key = load_key()
    if not key:
        print("✗ DATA_GO_KR_API_KEY를 찾을 수 없습니다. 저장소 루트 .env에 아래 한 줄을 넣어주세요:")
        print("    DATA_GO_KR_API_KEY=<data.go.kr 마이페이지의 일반 인증키>")
        sys.exit(1)
    ok = 0
    for name, spec in APIS.items():
        saved = False
        for params in spec["params"]:
            try:
                r = httpx.get(spec["url"], params={"serviceKey": key, **params}, timeout=25)
                # JSON 우선, 실패 시 XML 원문이라도 저장
                try:
                    data = r.json()
                except Exception:  # noqa: BLE001
                    data = {"_raw_xml": r.text[:5000], "_status": r.status_code}
                if r.status_code == 200 and (isinstance(data, dict) and looks_ok(data)):
                    (FIX / f"{name}.json").write_text(
                        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                    (DERIVED / f"{name}.json").write_text(
                        json.dumps(data, ensure_ascii=False), encoding="utf-8")
                    print(f"  ✓ {spec['dataset']} — 응답 저장 완료")
                    ok += 1
                    saved = True
                    break
            except Exception as e:  # noqa: BLE001
                last = f"{type(e).__name__}: {e}"
        if not saved:
            print(f"  ✗ {spec['dataset']} — 실패")
            print(f"    브라우저에서 상세페이지의 '미리보기'로 파라미터를 확인해 주세요.")
    print(f"\n{ok}/{len(APIS)} 성공. 성공 파일을 커밋·푸시한 뒤 채팅에 알려주세요.")
    if ok == 0:
        print("전부 실패 시: 인증키가 '일반 인증키(Encoding 아님)'인지, 승인 상태인지 확인해 주세요.")


if __name__ == "__main__":
    main()
