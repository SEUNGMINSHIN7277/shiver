import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.main import app  # noqa: E402

client = TestClient(app)


def test_health_provenance():
    d = client.get("/api/health").json()
    assert d["status"] == "ok"
    assert d["counts"]["glossary_terms"] > 1000
    names = [p["dataset_name"] for p in d["opendata_provenance"]]
    # R1 요건: 공공데이터포털 등록 데이터셋이 실제 적재되어 있어야 한다
    assert any("한국음식정보" in n for n in names)
    assert any("ODA용어사전" in n for n in names)
    assert any("디지털 아카이브" in n for n in names)


def test_translate_preset_cached():
    d = client.post("/api/translate", json={
        "text": "설날 아침에는 가래떡을 어슷하게 썰어 넣고 끓인 떡국을 먹으며 새해 첫날을 맞이한다.",
        "target_lang": "en"}).json()
    assert d["mode"] == "cached"
    assert "Sliced Rice Pasta Soup" in d["translation"]  # KF 공인 표준 준수
    detected = {t["term_ko"] for t in d["terms"]}
    assert {"설날", "가래떡", "떡국"} <= detected


def test_translate_arbitrary_glossary_only():
    d = client.post("/api/translate", json={"text": "박물관에서 나전칠기를 봤다.", "target_lang": "vi"}).json()
    assert d["mode"] == "glossary_only"
    t = next(x for x in d["terms"] if x["term_ko"] == "나전칠기")
    assert "sơn mài" in t["rendering"]  # 베트남어 대역 존재


def test_translate_longest_match():
    d = client.post("/api/translate", json={"text": "사물놀이 공연을 봤다.", "target_lang": "en"}).json()
    detected = {t["term_ko"] for t in d["terms"]}
    assert "사물놀이" in detected  # '놀이'가 아닌 최장일치


def test_chat_preset_and_citations():
    d = client.post("/api/chat", json={"message": "What is pansori?"}).json()
    assert d["mode"] == "cached" and d["lang"] == "en"
    assert "sorikkun" in d["answer"]


def test_chat_extractive_finds_archive():
    d = client.post("/api/chat", json={"message": "프린스턴대 한국학 소식 알려줘"}).json()
    assert any("프린스턴" in c["title"] for c in d["citations"])  # KF 아카이브 실데이터 인용


def test_benchmark_summary():
    d = client.get("/api/benchmark/summary").json()
    assert d["n_cases"] >= 25
    assert d["summary"]["krosetta_fidelity"] == 1.0
    assert 0 < d["summary"]["vanilla_fidelity"] < 1


def test_glossary_search():
    d = client.get("/api/glossary/search", params={"q": "판소리", "lang": "vi"}).json()
    assert any("pansori" in r["rendering"] for r in d["results"])
