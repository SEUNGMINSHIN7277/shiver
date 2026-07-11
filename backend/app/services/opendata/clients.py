"""공공데이터포털 오픈API 클라이언트 (활용신청 승인 완료 3종, 2026-07-12).

이 원격 개발 환경에서는 apis.data.go.kr 접속이 차단되어 있으므로, 라이브 응답 기록은
사용자 PC에서 `python scripts/record_opendata_fixtures.py` 로 수행한다.
기록된 fixture(backend/tests/fixtures/opendata/*.json)는 테스트와 cached 데모에 사용된다.
"""
from __future__ import annotations

import httpx

from ...config import get_settings

# 승인된 엔드포인트 (개발계정 상세보기 화면 실측, 일일 트래픽 10,000)
ENDPOINTS = {
    "univ_korname": {
        "dataset": "한국국제교류재단_해외대학 표준국문명칭",
        "portal": "https://www.data.go.kr/data/15075335/openapi.do",
        "url": "https://apis.data.go.kr/B260004/OverseaUnivKornameService2/getKornameList2",
    },
    "country_code": {
        "dataset": "외교부_국가·지역별 표준코드",
        "portal": "https://www.data.go.kr/data/15075346/openapi.do",
        "url": "https://apis.data.go.kr/1262000/CountryCodeService3/getCountryCodeList3",
    },
    "oda_business": {
        "dataset": "한국국제협력단_융합_KOICA-ODA 사업정보_KF-공공외교 사업 정보",
        "portal": "https://www.data.go.kr/data/15099215/openapi.do",
        "url": "https://apis.data.go.kr/B260003/OdaBusinessInfoService/getOdaBusinessInfoList",
    },
}


def fetch(service: str, **params) -> dict:
    """오픈API 단건 호출. serviceKey는 .env의 DATA_GO_KR_API_KEY."""
    ep = ENDPOINTS[service]
    key = get_settings().data_go_kr_api_key
    if not key:
        raise RuntimeError("DATA_GO_KR_API_KEY 미설정 (.env)")
    q = {"serviceKey": key, "returnType": "JSON", "numOfRows": 100, "pageNo": 1, **params}
    resp = httpx.get(ep["url"], params=q, timeout=20)
    resp.raise_for_status()
    return resp.json()
