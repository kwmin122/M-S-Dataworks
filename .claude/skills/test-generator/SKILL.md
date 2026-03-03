# 테스트 생성 스킬

새 코드에 대한 테스트 작성이 필요할 때 활성화됩니다.

## 테스트 작성 원칙

### 구조: Arrange-Act-Assert (AAA)
```python
def test_something():
    # Arrange: 테스트 데이터 준비
    input_data = {...}

    # Act: 테스트 대상 실행
    result = function_under_test(input_data)

    # Assert: 결과 검증
    assert result == expected_value
```

### 네이밍 규칙
- 테스트 함수: `test_{기능}_{시나리오}_{예상결과}`
- 예: `test_create_user_with_valid_data_returns_201`
- 예: `test_login_with_wrong_password_raises_auth_error`

### 필수 테스트 케이스
1. **Happy Path**: 정상 입력에 대한 정상 동작
2. **Edge Cases**: 경계값, 빈 값, null, 최대/최소값
3. **Error Cases**: 잘못된 입력, 예외 상황
4. **권한 검사**: 인증/인가가 필요한 경우

### 테스트 종류별 가이드

#### 단위 테스트 (Unit)
- 외부 의존성은 mock/stub 사용
- 하나의 함수/메서드만 테스트
- 빠르게 실행되어야 함 (DB, 네트워크 호출 없음)

#### 통합 테스트 (Integration)
- 실제 DB 연동 테스트 (테스트 DB 사용)
- API 엔드포인트 테스트
- 서비스 간 연동 테스트

#### 픽스처 (Fixtures)
```python
@pytest.fixture
def sample_user():
    return User(name="테스트유저", email="test@example.com")

@pytest.fixture
def db_session():
    # 테스트 DB 세션 설정
    session = create_test_session()
    yield session
    session.rollback()
```

### 테스트 파일 구조
```
tests/
├── conftest.py          # 공유 fixture
├── unit/
│   ├── test_models.py
│   └── test_services.py
├── integration/
│   ├── test_api.py
│   └── test_repositories.py
└── fixtures/
    └── sample_data.json
```

### 실행 & 검증
```bash
# 전체 테스트
pytest tests/ -v

# 특정 테스트만
pytest tests/unit/test_models.py -v

# 커버리지 포함
pytest tests/ -v --cov=src --cov-report=term-missing
```

## 원칙
- 테스트는 독립적이어야 함 (순서에 의존하지 않음)
- 테스트 데이터는 테스트 내에서 생성 (외부 상태에 의존하지 않음)
- 한 테스트에 하나의 assert 원칙 (가능한 한)
- 테스트 코드도 깨끗하게 유지
