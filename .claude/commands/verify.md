다음 검증을 순서대로 수행하고 결과를 리포트해줘:

## 1. 코드 품질 검사
```bash
ruff check . --fix
ruff format --check .
```

## 2. 타입 검사 (Python 프로젝트인 경우)
```bash
mypy src/ --ignore-missing-imports
```

## 3. 테스트 실행
```bash
pytest tests/ -v --tb=short
```

## 4. 빌드 확인 (해당되는 경우)
- Python: `python -m py_compile` 주요 파일
- Node.js: `npm run build`
- Docker: `docker build .`

## 5. 보안 기본 검사
- .env 파일이 .gitignore에 포함되어 있는지 확인
- 하드코딩된 시크릿이 없는지 확인
- SQL injection 취약점이 없는지 확인

## 결과 리포트
각 단계별 통과/실패를 표로 정리하고:
- 실패한 항목이 있으면 자동으로 수정을 시도
- 수정 불가능한 항목은 원인과 해결 방안 제시
- 모든 항목 통과 시 "검증 완료" 메시지

$ARGUMENTS
