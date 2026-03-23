# TaskPilot

프로젝트 관리 SaaS. Jira 대안.

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

### DB
- auto-increment ID 사용하지 마 — ULID 사용
- UTC가 아닌 타임존 사용하지 마
- DELETE 쿼리 직접 쓰지 마 — soft delete (deleted_at)
- 인덱스 없이 foreign key 만들지 마
- N+1 쿼리 허용하지 마 — include/joinedload 사용
- raw SQL 사용하지 마 — ORM 쿼리 빌더 사용
- 마이그레이션 없이 스키마 수정하지 마

### 인증/보안
- process.env 직접 접근하지 마 — getConfig() 사용
- localStorage에 토큰 저장하지 마 — HttpOnly 쿠키
- 비밀번호를 로그에 출력하지 마
- CORS를 *로 설정하지 마 — allowlist 사용
- SQL injection 가능한 문자열 결합 하지 마
- rate limiting 없이 API 배포하지 마
- 관리자 API에 권한 체크 빼먹지 마

### 프론트엔드
- any 타입 사용하지 마 — 구체적 타입 정의
- useEffect 안에서 데이터 fetch하지 마 — React Query 사용
- props drilling 3단계 이상 하지 마 — Context 또는 zustand
- 인라인 스타일 사용하지 마 — Tailwind
- console.log 커밋하지 마
- div 남발하지 마 — 시맨틱 HTML 사용
- 컴포넌트 300줄 넘기지 마 — 분리

### API
- 500 에러 메시지를 클라이언트에 노출하지 마
- 페이지네이션 없이 전체 목록 반환하지 마
- 에러 핸들링 없는 비동기 함수 만들지 마
- API 버전 없이 breaking change 하지 마
- 요청 body를 검증 없이 사용하지 마 — Pydantic
- multipart 요청 크기 제한 설정 안 하지 마 — 10MB 제한

### Celery/Workers
- 태스크에 timeout 설정하지 않으면 안 됨 — 300초 기본
- retry 없이 외부 API 호출하지 마 — exponential backoff
- 태스크 결과를 DB 대신 Redis에 저장하지 마

### 테스트
- 테스트 없이 머지하지 마
- mock 남발하지 마 — 실제 DB 사용 (테스트 컨테이너)
- snapshot 테스트에 의존하지 마 — behavior 테스트

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
