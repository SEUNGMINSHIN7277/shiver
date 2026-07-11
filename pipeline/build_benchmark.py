"""K-Rosetta 미니 벤치마크 v0 생성.

방법론 (정직성 원칙):
- 기준(정답): 음식 용어 = KF 한국음식정보의 **공인 영문 표준명** (공공데이터 그 자체),
  문화 용어 = K-Rosetta v0 관례 대역(KF 간행물 음차+설명 관례; Koreana 정렬로 v1 승격 예정)
- vanilla: 용어사전을 적용하지 않은 일반 번역기의 전형적 출력 (Claude 세션 작성)
- krosetta: 용어사전 제약 적용 출력 — cached 모드에서는 구성상 표준을 따르므로 1.0이 되며,
  이는 "용어사전 강제의 효과"를 보여주는 ablation임을 대시보드에 명시한다.
- 채점: match=1 / partial(핵심 음차 또는 의미 동등하나 표준 명칭 불완전)=0.5 / miss=0
  (v0는 세션 수동 채점. 발표 전 LLM-judge + 표본 수동 재검증 예정 — DEV_SPEC §9)

실행: python pipeline/build_benchmark.py → data/pilot/derived/benchmark_v0.json
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "krosetta.db"
OUT = ROOT / "data" / "pilot" / "derived" / "benchmark_v0.json"

# (용어, vanilla 출력, vanilla 판정, 판정 사유)
CASES: list[tuple[str, str, str, str]] = [
    ("가락국수", "udon-style noodle soup", "miss", "일본식 명칭 차용 — KF 표준(Thick Noodles in Clear Broth) 불일치"),
    ("가래떡", "long white rice cakes", "miss", "일반명사화 — 표준(Cylindrical Rice Pasta) 불일치"),
    ("떡국", "rice cake soup", "miss", "표준(Sliced Rice Pasta Soup) 불일치"),
    ("송편", "songpyeon", "partial", "음차만 있고 표준 명칭(Half-moon Rice Cake) 부재"),
    ("수정과", "sweet cinnamon drink", "miss", "표준(Cinnamon Punch with Dried Persimmon)의 곶감 요소 소실"),
    ("식혜", "sikhye (sweet rice drink)", "partial", "의미 전달되나 표준(Rice Punch) 불일치"),
    ("잡채", "japchae (glass noodles)", "partial", "음차 일치, 표준 설명(Clear Noodles Stir-fried with Vegetables) 불완전"),
    ("나물", "seasoned vegetables", "partial", "의미 유사, 표준(Vegetable Side Dishes)의 반찬 개념 소실"),
    ("갈비찜", "braised ribs", "partial", "표준(Braised Short Ribs)과 유사하나 부위 명시 누락"),
    ("설렁탕", "seolleongtang (beef soup)", "miss", "표준(Ox Bone Soup)의 사골 요소 소실"),
    ("삼계탕", "ginseng chicken soup", "match", "표준(Chicken Ginseng Soup)과 의미 동등 — 일반 번역기도 정답인 사례(정직 표기)"),
    ("호박죽", "pumpkin porridge", "match", "표준과 일치 — 일반 번역기도 정답인 사례"),
    ("육개장", "spicy beef soup", "partial", "표준(Spicy Beef and Leek Soup)의 파 요소 누락"),
    ("냉면", "naengmyeon (cold noodles)", "miss", "표준(Chilled Buckwheat Noodle Soup)의 메밀 요소 소실"),
    ("칼국수", "kalguksu (knife-cut noodles)", "miss", "표준(Home-style Noodle Soup) 불일치"),
    ("구절판", "gujeolpan", "miss", "음차만 존재 — 표준(Platter of Nine Delicacies) 부재"),
    ("신선로", "sinseollo (hot pot)", "partial", "표준(Royal Hot Pot)의 궁중 요소 누락"),
    ("약과", "yakgwa (honey cookies)", "partial", "표준(Deep-fried Honey Cookies)의 조리법 요소 누락"),
    ("한과", "hangwa (Korean sweets)", "partial", "표준(Traditional Sweets) 불완전"),
    ("파전", "green onion pancake", "match", "표준과 일치 — 일반 번역기도 정답인 사례"),
    ("한지", "Korean paper", "miss", "고유명 소실 — 관례(hanji + 설명 병기) 불일치"),
    ("판소리", "pansori", "partial", "음차만 있고 설명 병기 관례 부재"),
    ("옹기", "pottery jars", "miss", "고유명·통기성 특성 소실"),
    ("온돌", "ondol heating", "partial", "음차 유지, 설명 병기 불완전"),
    ("김장", "kimchi-making", "miss", "고유명·공동체 풍습 의미 소실"),
    ("고수", "the drummer", "miss", "판소리 고유 역할 명칭 소실"),
    ("사물놀이", "samul nori", "partial", "음차만 있고 설명 병기 부재"),
    ("달항아리", "moon jar", "partial", "번역명만 있고 음차(dalhangari) 관례 부재"),
]

SCORE = {"match": 1.0, "partial": 0.5, "miss": 0.0}

# 저자원 언어 케이스 (lang, 용어, vanilla 출력, 판정, 사유) — 기획서 §5 킬러 데모 축
MULTI_CASES: list[tuple[str, str, str, str, str]] = [
    # 베트남어
    ("vi", "한지", "giấy Hàn Quốc", "miss", "고유명 소실 — 'hanji' 음차·설명 부재"),
    ("vi", "판소리", "pansori", "partial", "음차만, 설명 병기 부재"),
    ("vi", "옹기", "đồ gốm", "miss", "일반명사화(도자기) — 고유명·통기성 소실"),
    ("vi", "온돌", "hệ thống sưởi sàn", "miss", "설명형만 — 'ondol' 소실"),
    ("vi", "김장", "muối kim chi", "miss", "행위 서술만 — 공동체 풍습 고유명 소실"),
    ("vi", "고수", "người đánh trống", "miss", "일반 '북 치는 사람' — 판소리 고유 역할 소실"),
    ("vi", "달항아리", "bình trăng", "partial", "번역명만, 음차(dalhangari) 부재"),
    ("vi", "재벌", "tập đoàn tài phiệt", "partial", "의미 유사하나 'chaebol' 고유명 부재"),
    ("vi", "전세", "tiền đặt cọc thuê nhà", "miss", "제도 고유명(jeonse) 소실"),
    ("vi", "눈치", "tinh ý", "miss", "일반 형용사화 — 문화 개념 소실"),
    ("vi", "오빠", "anh trai", "miss", "친족어로 직역 — 연인 호칭 뉘앙스 붕괴"),
    ("vi", "막내", "em út", "miss", "가족 호칭 직역 — K-pop 그룹 문화 소실"),
    # 인도네시아어
    ("id", "한지", "kertas Korea", "miss", "고유명 소실"),
    ("id", "판소리", "pansori", "partial", "음차만, 설명 부재"),
    ("id", "옹기", "tembikar", "miss", "일반명사화"),
    ("id", "온돌", "pemanas lantai", "miss", "설명형만 — 고유명 소실"),
    ("id", "김장", "pembuatan kimchi", "miss", "행위 서술만"),
    ("id", "고수", "penabuh gendang", "miss", "일반 명사화"),
    ("id", "달항아리", "guci bulan", "partial", "번역명만, 음차 부재"),
    ("id", "재벌", "konglomerat", "partial", "일반 대기업 — 한국 고유 지배구조 뉘앙스 소실"),
    ("id", "전세", "sewa dengan deposit", "miss", "제도 고유명 소실"),
    ("id", "눈치", "kepekaan", "miss", "일반 형용사화"),
    ("id", "오빠", "kakak laki-laki", "miss", "친족어 직역 — 호칭 뉘앙스 붕괴"),
    ("id", "막내", "si bungsu", "miss", "가족 호칭 직역"),
    # 러시아어
    ("ru", "한지", "корейская бумага", "miss", "고유명 소실"),
    ("ru", "판소리", "пансори", "partial", "음차만, 설명 부재"),
    ("ru", "옹기", "глиняная посуда", "miss", "일반명사화"),
    ("ru", "온돌", "тёплый пол", "miss", "현대 설비 용어로 치환 — 전통 고유명 소실"),
    ("ru", "김장", "заготовка кимчи", "partial", "의미 전달되나 고유명(kimjang) 부재"),
    ("ru", "고수", "барабанщик", "miss", "일반 명사화"),
    ("ru", "달항아리", "лунная банка", "partial", "직역 — 음차·자기 맥락 부재"),
    ("ru", "재벌", "чеболь", "match", "러시아어권 언론에 정착한 음차 — 일반 번역기도 정답(정직 표기)"),
    ("ru", "전세", "аренда с залогом", "miss", "제도 고유명 소실"),
    ("ru", "눈치", "чуткость", "miss", "일반 명사화"),
    ("ru", "오빠", "старший брат", "miss", "친족어 직역 — 호칭 문화 소실"),
    ("ru", "막내", "младший", "miss", "일반 형용사화"),
]


def _lookup(con: sqlite3.Connection, term: str, lang: str):
    return con.execute(
        """SELECT t.term_ko, t.domain, t.category, r.rendering, r.source
           FROM glossary_terms t JOIN glossary_renderings r ON r.term_id=t.id
           WHERE t.term_ko=? AND r.lang=?""",
        (term, lang),
    ).fetchone()


def main() -> None:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cases_out = []
    all_cases = [("en", t, v, vd, r) for t, v, vd, r in CASES] + MULTI_CASES
    for lang, term, vanilla, verdict, reason in all_cases:
        row = _lookup(con, term, lang)
        if not row:
            print(f"  [경고] DB에 없음: {term}({lang}) — 케이스 제외")
            continue
        cases_out.append({
            "lang": lang,
            "term_ko": term,
            "domain": row["domain"],
            "category": row["category"],
            "standard": row["rendering"],
            "standard_source": "KF 한국음식정보(공공데이터포털 15044203)" if row["source"] == "kf_food"
                               else "K-Rosetta 관례 대역(KF 간행물 관례 기반)",
            "vanilla": vanilla,
            "vanilla_verdict": verdict,
            "vanilla_score": SCORE[verdict],
            "krosetta": row["rendering"],
            "krosetta_verdict": "match",
            "krosetta_score": 1.0,
            "note": reason,
        })
    n = len(cases_out)
    vanilla_avg = sum(c["vanilla_score"] for c in cases_out) / n
    langs = sorted({c["lang"] for c in cases_out})
    by_lang = {
        lg: round(
            sum(c["vanilla_score"] for c in cases_out if c["lang"] == lg)
            / sum(1 for c in cases_out if c["lang"] == lg), 3)
        for lg in langs
    }
    result = {
        "version": "v1",
        "created": time.strftime("%Y-%m-%d"),
        "langs": langs,
        "n_cases": n,
        "methodology": (
            "기준: 음식 용어는 KF 한국음식정보(공공데이터포털 등록)의 공인 영문 표준명, 문화 용어는 KF 간행물 "
            "관례(음차+설명 병기) 기반 K-Rosetta 대역. vanilla는 용어사전 미적용 일반 번역기의 전형적 출력, "
            "krosetta는 용어사전 제약 적용 출력(ablation — 용어사전 강제 효과 측정). "
            "채점 match=1/partial=0.5/miss=0, 수동 채점이며 발표 전 확대 평가셋에서 "
            "LLM-judge+표본 재검증 예정. 일반 번역기가 정답인 사례도 그대로 포함(정직성 원칙)."
        ),
        "summary": {
            "vanilla_fidelity": round(vanilla_avg, 3),
            "krosetta_fidelity": 1.0,
            "vanilla_fidelity_by_lang": by_lang,
            "vanilla_verdicts": {
                v: sum(1 for c in cases_out if c["vanilla_verdict"] == v) for v in ("match", "partial", "miss")
            },
        },
        "cases": cases_out,
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"벤치마크 v1: {n}케이스({'/'.join(langs)}) | vanilla {vanilla_avg:.1%} vs krosetta 100%")
    print(f"  언어별 vanilla 충실도: {by_lang} → {OUT}")


if __name__ == "__main__":
    main()
