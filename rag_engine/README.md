# RAG Engine Microservice (Phase 2)

이 폴더는 Python 기반의 RAG 평가 엔진을 모아놓은 디렉터리입니다.
공고문 텍스트를 분석하고, 기업의 제원을 대조하여 입찰 가능 여부를 결정론적으로 판단합니다.

## Next Steps
- [ ] FastAPI 애플리케이션 초기화 (main.py, requirements.txt)
- [ ] `POST /api/analyze-bid` 리스너 생성
- [ ] 기존 로직(`rfx_analyzer.py`, `matcher.py`) 결합
