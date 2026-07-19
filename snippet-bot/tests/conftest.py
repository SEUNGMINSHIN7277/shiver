import sys
from pathlib import Path

# snippet-bot 모듈들을 패키지화 없이 임포트할 수 있게 경로 추가
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
