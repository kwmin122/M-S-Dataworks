배포를 준비하고 실행해줘.

$ARGUMENTS

## 배포 전 체크리스트

### 1. 코드 검증
```bash
ruff check . --fix
pytest tests/ -v
```

### 2. 브랜치 상태 확인
```bash
git status
git log --oneline main..HEAD
```

### 3. 환경 확인
- [ ] 환경변수가 모두 설정되어 있는가?
- [ ] DB 마이그레이션이 필요한가?
- [ ] 외부 서비스 의존성에 변경이 있는가?
- [ ] breaking change가 있는가?

### 4. 배포 실행
- 프로젝트의 배포 방법에 따라 실행
- Docker: `docker-compose up --build -d`
- 서버: 배포 스크립트 실행
- 클라우드: CI/CD 파이프라인 트리거

### 5. 배포 후 검증
- Health check 엔드포인트 확인
- 주요 기능 스모크 테스트
- 에러 로그 모니터링
- 롤백 절차 확인

문제 발견 시 즉시 롤백 절차를 안내해줘.
