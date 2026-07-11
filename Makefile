.PHONY: setup db bench demo test shots

setup:            ## 의존성 설치
	pip install -r backend/requirements.txt -r pipeline/requirements.txt

db:               ## 데이터셋 → SQLite 빌드
	python3 pipeline/build_db.py

bench:            ## 벤치마크 v0 생성
	python3 pipeline/build_benchmark.py

demo: db bench    ## 데모 서버 실행 (http://localhost:8777)
	python3 -m uvicorn backend.app.main:app --port 8777

test:             ## 전체 테스트
	python3 -m pytest backend/tests/ pipeline/tests/ -q

shots:            ## 데모 스크린샷 생성 (서버 실행 중이어야 함)
	python3 scripts/capture_demo_assets.py
