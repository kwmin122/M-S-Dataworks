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

> 중요도 분류:
> - **CRITICAL** — 위반 시 보안 사고, 데이터 유실, 장애 직결. 절대 예외 없음.
> - **REQUIRED** — 코드 품질과 유지보수성의 핵심. PR 머지 조건.
> - **STANDARD** — 팀 컨벤션. 일관성을 위해 준수.

---

### CRITICAL — 보안/데이터 무결성

| 영역 | 규칙 |
|------|------|
| 보안 | 환경변수는 `getConfig()`를 통해서만 접근한다 (`process.env` 직접 접근 금지) |
| 보안 | 토큰은 HttpOnly 쿠키에 저장한다 |
| 보안 | 비밀번호, 시크릿 등 민감 정보는 로그에서 마스킹한다 |
| 보안 | CORS는 허용 도메인 allowlist로 설정한다 |
| 보안 | SQL 쿼리는 ORM 쿼리 빌더 또는 파라미터 바인딩으로 작성한다 (문자열 결합 금지) |
| 보안 | 모든 API 엔드포인트에 rate limiting을 적용한다 |
| 보안 | 관리자 API는 반드시 권한 체크를 포함한다 |
| API | 500 에러의 내부 메시지는 클라이언트에 노출하지 않는다 — 일반화된 에러 응답 반환 |
| API | 요청 body는 Pydantic 모델로 검증한 뒤 사용한다 |
| API | multipart 요청은 10MB 크기 제한을 설정한다 |

### REQUIRED — 데이터 설계/아키텍처

| 영역 | 규칙 |
|------|------|
| DB | ID는 ULID을 사용한다 |
| DB | 타임스탬프는 항상 UTC로 저장한다 |
| DB | 삭제는 soft delete (`deleted_at` 컬럼)로 처리한다 |
| DB | foreign key에는 반드시 인덱스를 생성한다 |
| DB | 연관 데이터 조회는 `include`/`joinedload`로 한다 (N+1 방지) |
| DB | 쿼리는 ORM 쿼리 빌더를 사용한다 |
| DB | 스키마 변경은 반드시 마이그레이션 파일과 함께 한다 |
| API | 목록 API는 반드시 페이지네이션을 적용한다 |
| API | 비동기 함수는 반드시 에러 핸들링을 포함한다 |
| API | breaking change는 API 버전을 올려서 배포한다 |
| Workers | 모든 Celery 태스크에 timeout을 설정한다 (기본 300초) |
| Workers | 외부 API 호출은 exponential backoff retry를 적용한다 |
| Workers | 태스크 결과는 DB에 저장한다 (Redis가 아닌) |
| 테스트 | 모든 PR은 관련 테스트를 포함한 상태에서 머지한다 |
| 테스트 | 테스트는 실제 DB(테스트 컨테이너)로 실행한다 — mock은 외부 의존성에만 사용 |
| 테스트 | behavior 기반 테스트를 작성한다 (snapshot 테스트 최소화) |

### STANDARD — 프론트엔드 컨벤션

| 영역 | 규칙 |
|------|------|
| 타입 | 구체적 타입을 정의한다 (`any` 사용 금지) |
| 데이터 | 서버 데이터는 React Query로 관리한다 (`useEffect` fetch 금지) |
| 상태 | props 전달이 3단계 이상이면 Context 또는 zustand로 전환한다 |
| 스타일 | Tailwind 클래스를 사용한다 (인라인 스타일 금지) |
| 디버깅 | `console.log`는 커밋 전에 제거한다 |
| 마크업 | 시맨틱 HTML 태그를 사용한다 (`div` 남용 금지) |
| 구조 | 컴포넌트는 300줄 이내로 유지하고, 초과 시 분리한다 |

---

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
