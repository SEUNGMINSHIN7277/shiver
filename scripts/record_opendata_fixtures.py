#!/usr/bin/env python3
"""오픈API 3종 라이브 응답 기록 (사용자 한국 PC에서 실행, 약 1분).

승인된 오픈API를 실제로 호출해 응답을 저장한다. 이 개발 환경(해외 서버)에서는
apis.data.go.kr 접속이 차단되므로 반드시 한국 IP의 PC에서 실행한다(크롤과 동일).

준비:
    1) shiver 폴더로 이동
    2) shiver/.env 파일에 아래 한 줄 (data.go.kr 마이페이지의 '일반 인증키')
         DATA_GO_KR_API_KEY=여기에_인증키
    3) pip install httpx   (크롤 때 설치했으면 생략 가능)
실행:
    python scripts/record_opendata_fixtures.py
성공 후:
    git add backend/tests/fixtures data/pilot/opendata_api
    git commit -m "opendata API 라이브 응답"
    git push
그리고 채팅에 "API 응답 올렸어" 라고 알려주세요. 재빌드 시 서비스에 자동 통합됩니다.

전부 또는 일부 실패 시: 아무것도 지우지 말고 그대로
    git add backend/tests/fixtures && git commit -m "api debug" && git push
해주시면, 저장된 응답 원문(_debug 파일)을 보고 제가 파라미터를 고쳐 드립니다.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "backend" / "tests" / "fixtures" / "opendata"
DERIVED = ROOT / "data" / "pilot" / "opendata_api"
FIX.mkdir(parents=True, exist_ok=True)
DERIVED.mkdir(parents=True, exist_ok=True)

try:
    import httpx
except ImportError:
    print("✗ httpx가 없습니다. 먼저:  pip install httpx")
    sys.exit(1)


def load_key() -> str:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("DATA_GO_KR_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return os.environ.get("DATA_GO_KR_API_KEY", "")


# 각 API마다 시도할 파라미터 조합(위에서부터 순서대로, 첫 성공 채택)
APIS = {
    "country_code": {
        "dataset": "외교부_국가·지역별 표준코드 (15075346)",
        "url": "https://apis.data.go.kr/1262000/CountryCodeService3/getCountryCodeList3",
        "trials": [
            {"numOfRows": 300, "pageNo": 1, "returnType": "JSON"},
            {"numOfRows": 300, "pageNo": 1, "type": "json"},
            {"numOfRows": 300, "pageNo": 1, "returnType": "json", "cond[country_iso_alp2::EQ]": "VN"},
            {"numOfRows": 300, "pageNo": 1},
        ],
    },
    "univ_korname": {
        "dataset": "한국국제교류재단_해외대학 표준국문명칭 (15075335)",
        "url": "https://apis.data.go.kr/B260004/OverseaUnivKornameService2/getKornameList2",
        "trials": [
            {"numOfRows": 100, "pageNo": 1, "returnType": "JSON", "cond[country_iso_alp2::EQ]": "VN"},
            {"numOfRows": 100, "pageNo": 1, "returnType": "JSON"},
            {"numOfRows": 100, "pageNo": 1, "type": "json"},
            {"numOfRows": 100, "pageNo": 1},
        ],
    },
    "oda_business": {
        "dataset": "한국국제협력단_융합 KOICA-ODA·KF 공공외교 사업정보 (15099215)",
        "url": "https://apis.data.go.kr/B260003/OdaBusinessInfoService/getOdaBusinessInfoList",
        "trials": [
            {"numOfRows": 100, "pageNo": 1, "returnType": "JSON"},
            {"numOfRows": 100, "pageNo": 1, "type": "json"},
            {"numOfRows": 100, "pageNo": 1, "returnType": "JSON", "cond[country_nm::EQ]": "베트남"},
            {"numOfRows": 100, "pageNo": 1},
        ],
    },
}


def is_success(status: int, text: str) -> bool:
    if status != 200:
        return False
    up = text.upper()
    if any(x in up for x in ("SERVICE KEY IS NOT REGISTERED", "SERVICE_KEY_IS_NOT",
                             "LIMITED_NUMBER", "NO_OPENAPI_SERVICE_ERROR",
                             "SERVICE ERROR", "APPLICATION_ERROR", "HTTP ROUTING ERROR")):
        return False
    # 정상 응답 신호: resultCode 00 또는 item 존재
    return ("<resultCode>00</resultCode>" in text or '"resultCode":"00"' in text
            or '"resultCode": "00"' in text or '"item"' in text or "<item>" in text)


def main() -> None:
    key = load_key()
    if not key:
        print("✗ DATA_GO_KR_API_KEY를 찾을 수 없습니다.")
        print("  shiver/.env 파일에 아래 한 줄을 넣어주세요(마이페이지의 '일반 인증키'):")
        print("    DATA_GO_KR_API_KEY=발급받은_인증키")
        sys.exit(1)

    ok = 0
    for name, spec in APIS.items():
        saved = False
        last_status, last_text = None, ""
        for params in spec["trials"]:
            try:
                r = httpx.get(spec["url"], params={"serviceKey": key, **params},
                              timeout=30, follow_redirects=True)
                last_status, last_text = r.status_code, r.text
            except Exception as e:  # noqa: BLE001
                last_status, last_text = -1, f"{type(e).__name__}: {e}"
                continue
            if is_success(r.status_code, r.text):
                try:
                    data = r.json()
                except Exception:  # noqa: BLE001
                    data = {"_format": "xml", "_body": r.text}
                (FIX / f"{name}.json").write_text(
                    json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                (DERIVED / f"{name}.json").write_text(
                    json.dumps(data, ensure_ascii=False), encoding="utf-8")
                print(f"  ✓ {spec['dataset']} — 성공, 응답 저장")
                ok += 1
                saved = True
                break
        if not saved:
            # 실패 원문을 디버그 파일로 남겨 원인 분석 가능하게
            (FIX / f"{name}_debug.txt").write_text(
                f"status={last_status}\n\n{(last_text or '')[:3000]}", encoding="utf-8")
            print(f"  ✗ {spec['dataset']} — 실패 (status={last_status})")
            print(f"    원문 일부: {(last_text or '')[:160]}")

    print(f"\n결과: {len(APIS)}종 중 {ok}종 성공.")
    if ok < len(APIS):
        print("실패분은 backend/tests/fixtures/opendata/*_debug.txt 에 응답이 저장됐습니다.")
        print("그 파일까지 커밋·푸시하고 '실패했어'라고 알려주시면 파라미터를 고쳐 드립니다.")
    if ok:
        print("성공분을 git add/commit/push 후 'API 응답 올렸어'라고 알려주세요.")


if __name__ == "__main__":
    main()
