# TaskPilot

프로젝트 관리 SaaS. Jira 대안.

## CRITICAL

- ID 생성은 ULID 사용 (auto-increment 대신)
- 모든 timestamp는 UTC 저장
- 토큰은 HttpOnly 쿠키에 저장 (localStorage 사용 금지)
- 500 에러 메시지는 서버 내부에만 유지, 클라이언트에는 일반화된 메시지 반환
- 관리자 API는 반드시 권한 체크 포함

## 아키텍처

```
web/                    <- Next.js 15
  src/app/              <- App Router
  src/components/       <- React 컴포넌트
  src/lib/prisma.ts     <- Prisma 싱글턴
  src/middleware.ts      <- 인증 보호

api/                    <- FastAPI (Python)
  main.py               <- REST API
  models.py             <- SQLAlchemy 모델
  auth.py               <- JWT 인증

workers/                <- Celery workers
  tasks.py              <- 비동기 태스크
  notifications.py      <- 알림 발송
```

## 명령어

```bash
cd web && npm run dev        # 포트 3000
cd api && uvicorn main:app   # 포트 8000
celery -A workers worker     # Celery worker
```

## 설계 규칙

### DB — MANDATORY

- 삭제는 soft delete(deleted_at) 패턴 사용
- foreign key에는 인덱스 함께 생성
- 관계 쿼리는 include/joinedload로 eager loading 처리 (N+1 방지)
- 쿼리는 ORM 쿼리 빌더로 작성
- 스키마 변경은 마이그레이션 파일과 함께 수행

### 인증/보안 — MANDATORY

- 환경변수는 getConfig()로 접근
- 비밀번호/민감 정보는 로그에서 제외 (마스킹 처리)
- CORS는 allowlist 기반으로 설정
- SQL 쿼리는 파라미터 바인딩 사용 (문자열 결합 대신)
- API에는 rate limiting 적용 후 배포

### 프론트엔드 — MANDATORY

- 타입은 구체적으로 정의 (any 대신 명시적 interface/type)
- 데이터 페칭은 React Query 사용 (useEffect 대신)
- 상태 공유는 Context 또는 zustand 사용 (props drilling 3단계 미만 유지)
- 스타일링은 Tailwind 사용
- 커밋 전 console.log 제거
- HTML 요소는 시맨틱 태그 사용 (div 대신 section, article, nav 등)
- 컴포넌트는 300줄 미만으로 유지, 초과 시 분리

### API — MANDATORY

- 목록 API는 페이지네이션 적용
- 비동기 함수에는 에러 핸들링 포함
- breaking change는 API 버전 업과 함께 진행
- 요청 body는 Pydantic으로 검증
- multipart 요청은 10MB 크기 제한 설정

### Celery/Workers — MANDATORY

- 태스크에는 timeout 설정 (기본 300초)
- 외부 API 호출은 exponential backoff retry 적용
- 태스크 결과는 DB에 저장 (Redis 대신)

### 테스트 — PREFER

- 머지 전 테스트 통과 확인
- mock보다 실제 DB 사용 (테스트 컨테이너)
- snapshot 테스트보다 behavior 테스트 우선

## 환경변수

| 변수 | 용도 |
|------|------|
| DATABASE_URL | PostgreSQL |
| REDIS_URL | Redis (캐시 + Celery) |
| JWT_SECRET | JWT 서명 |
| SMTP_HOST | 이메일 발송 |
| SENTRY_DSN | 에러 트래킹 |

## 테스트 매핑

### Frontend (Jest)
| 파일 | 대상 |
|------|------|
| `src/lib/__tests__/auth.test.ts` | 인증 유틸 |
| `src/components/__tests__/TaskBoard.test.tsx` | 칸반 보드 |
| `src/components/__tests__/TaskCard.test.tsx` | 태스크 카드 |
| `src/hooks/__tests__/useTasks.test.ts` | 태스크 훅 |

### API (pytest)
| 파일 | 대상 |
|------|------|
| `tests/test_tasks.py` | 태스크 CRUD |
| `tests/test_auth.py` | 인증 API |
| `tests/test_projects.py` | 프로젝트 API |
| `tests/test_webhooks.py` | 웹훅 |

### Workers (pytest)
| 파일 | 대상 |
|------|------|
| `tests/test_notifications.py` | 알림 태스크 |
| `tests/test_exports.py` | 내보내기 |

## 기능 현황

| 기능 | 상태 |
|------|------|
| 태스크 CRUD | 완료 |
| 칸반 보드 | 완료 |
| 프로젝트 관리 | 완료 |
| 팀 멤버 초대 | 완료 |
| 알림 (이메일) | 완료 |
| 댓글 | 진행 중 |
| 파일 첨부 | 진행 중 |
| 간트 차트 | 미구현 |
| 보고서 | 미구현 |
| 모바일 앱 | 미구현 |

## CRITICAL (재확인)

- ID는 ULID, timestamp는 UTC, 토큰은 HttpOnly 쿠키
- 500 에러 상세 메시지를 클라이언트에 절대 노출하지 않는다
- 관리자 API에는 반드시 권한 체크 포함
