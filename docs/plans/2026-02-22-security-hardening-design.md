# 보안 강화 설계 (Security Hardening Design)

작성일: 2026-02-22
대상: `web_saas/` Next.js SaaS 스택
우선순위 근거: 발견된 취약점 심각도 + 실행 가능성

---

## 1. 현황 감사 결과

| 심각도 | 위치 | 취약점 |
|--------|------|--------|
| 🔴 Critical | 모든 `/api/*` | **IDOR** — `organizationId` request body 입력 → 누구나 타 조직 데이터 접근 |
| 🔴 Critical | `/api/internal/*` | 내부 API 완전 공개 — 누구나 `jobId` 주입으로 evaluation 강제 실행 |
| 🟠 High | `stripe/route.ts:7` | `STRIPE_WEBHOOK_SECRET ?? ''` — 빈 문자열로 조용히 실패 |
| 🟠 High | `search/bids/route.ts:64` | `take: body.limit ?? 50` — 상한 없음, 100만 입력 시 DoS |
| 🟠 High | `process-ingestion-job` | `fetch(job.attachmentUrl!)` — URL 검증 없어 SSRF 가능 |
| 🟡 Medium | `process-evaluation-job` | 여러 DB write 비트랜잭션 — 크래시 시 inconsistent state |
| 🟡 Medium | `prisma.ts:7` | `log: ['query']` — 프로덕션에서 민감 쿼리 전체 출력 |
| 🟡 Medium | `evaluate/batch` | `bidNoticeIds` 배열 크기 무제한 |

---

## 2. 설계 섹션 (실행 순서 기준)

### 섹션 C: 즉각 수정 — DoS / SSRF / 로그 / 환경변수 (P0)

**C-1. 환경변수 중앙 검증 (env.ts + zod)**

- `web_saas/src/lib/env.ts` 신규 생성
- `zod.object({...}).parse(process.env)` 패턴으로 앱 시작 시 검증
- 필수 항목: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `WEBHOOK_SECRET`, `INTERNAL_API_SECRET`, `DATABASE_URL`
- 누락 시 → zod `ZodError` throw → 부팅 차단 (process crash가 아닌 명시적 오류 메시지)
- `prisma.ts`, `stripe/route.ts`, 내부 API 파일에서 `process.env.*` 직접 참조 제거 → `env.*` 사용

**C-2. 입력 크기 제한**

- `POST /api/search/bids` → `take: Math.min(body.limit ?? 50, 100)`
- `POST /api/evaluate/batch` → `bidNoticeIds` 배열 최대 50개, 초과 시 400 반환

**C-3. SSRF 방어 (process-ingestion-job)**

```
검증 순서:
1. URL 파싱 — 실패 시 거부
2. scheme === 'https' 만 허용
3. hostname → DNS 해석 → 해석된 IP가 private 대역 차단
   (127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, ::1 등)
4. hostname이 환경변수 ATTACHMENT_ALLOWED_DOMAINS allowlist 내 도메인으로
   끝나는지 확인 (예: .go.kr, .g2b.go.kr)
5. fetch 시 redirect: 'manual' (리다이렉트 따라가기 금지)
6. fetch 시 signal: AbortSignal.timeout(10_000) (10초 타임아웃)
7. 응답 Content-Length 또는 실제 수신 바이트 ≤ 50MB 제한
8. 실제 수신 IP로 private 대역 재검증 (DNS rebinding 방어)
```

구현 위치: `web_saas/src/lib/safe-fetch.ts` 신규 — `safeFetch(url, allowedDomains)` 함수

**C-4. Prisma 로그 레벨**

- `process.env.NODE_ENV === 'production'` → `log: ['error']`
- 개발: 기존대로 `log: ['query', 'error', 'warn']`

---

### 섹션 B: 내부 API 보호 — HMAC 재전송 방지 (P1)

**B-1. 내부 API HMAC 검증**

기존 `lib/hmac.ts`의 `verifyWebhookSignature` 패턴을 그대로 재사용.

헤더 구조:
```
x-internal-timestamp: <unix seconds>
x-internal-nonce: <uuid or random hex>
x-internal-signature: HMAC-SHA256(ts.nonce.body, INTERNAL_API_SECRET)
```

검증 로직 (`lib/internal-auth.ts` 신규):
1. `x-internal-timestamp` ±5분 범위 검증 (replay window)
2. HMAC 서명 검증 (`timingSafeEqual`)
3. nonce 중복 방지 — `UsedNonce` 테이블 create-only + P2002 catch (기존 n8n webhook과 동일 패턴)

**B-2. 적용 대상**

- `POST /api/internal/process-evaluation-job`
- `POST /api/internal/process-ingestion-job`
- `GET /api/internal/evaluation-jobs`

n8n 워크플로우의 HTTP Request 노드에 HMAC 서명 헤더 추가 필요.

---

### 섹션 A: NextAuth 세션 통합 + IDOR 제거 + CSRF 방어 (P1)

**A-1. NextAuth 도입**

- `next-auth` 패키지 설치
- `web_saas/src/app/api/auth/[...nextauth]/route.ts` 신규
- Provider: Credentials 또는 Supabase OAuth (기존 auth_gateway 연동)
- 세션 payload: `{ userId: string, organizationId: string, role: 'ADMIN' | 'MEMBER' }`

**A-2. middleware.ts — 라우트 보호**

```
/api/webhooks/*    → 통과 (Stripe/n8n 자체 서명 검증)
/api/internal/*    → 통과 (섹션 B HMAC으로 보호)
/api/auth/*        → 통과 (NextAuth 자체 엔드포인트)
/api/*             → NextAuth 세션 필요 → 없으면 401
```

**A-3. IDOR 완전 제거**

모든 사용자 API에서 `organizationId` request body/query parameter 수락 완전 제거.
세션에서 `const { organizationId } = await getServerSession(authOptions)` 주입.
모든 Prisma where에 `organizationId: sessionOrgId` 강제 포함:

```typescript
// BEFORE (취약)
const jobs = await prisma.evaluationJob.findMany({
  where: { organizationId }, // 사용자 입력값
});

// AFTER (안전)
const session = await getServerSession(authOptions);
const orgId = session.user.organizationId; // 세션에서만 주입
const jobs = await prisma.evaluationJob.findMany({
  where: { organizationId: orgId }, // 세션값 강제
});
```

적용 대상:
- `POST /api/evaluate/batch` — body의 `organizationId` 제거
- `GET /api/export/evaluations` — query의 `organizationId` 제거
- `GET /api/internal/evaluation-jobs` — (내부 API지만 HMAC 보호 후 body에서 받음)
- `POST /api/proposals` — body의 `organizationId` 제거
- `GET /api/pre-bid-signals` — 현재는 공개 데이터지만 org 스코프 필터 추가

**A-4. CSRF 방어**

쿠키 세션 + API 조합은 CSRF 필수.

```
검증 대상: POST, PUT, PATCH, DELETE
방법: Origin allowlist 검증 (CSRF 토큰보다 구현 단순)
  - req.headers.get('origin') 가 ALLOWED_ORIGINS 목록 안에 없으면 403
  - ALLOWED_ORIGINS = [process.env.NEXT_PUBLIC_APP_URL] + 개발 localhost
  - 검증 위치: middleware.ts 또는 공통 헬퍼 verifyCsrfOrigin()
GET 요청은 검증 제외 (읽기 전용 + 쿠키 인증 적용 후 멱등)
/api/webhooks/*는 CSRF 검증 제외 (외부 서버 발신, Origin이 없음)
```

---

### 섹션 D: 트랜잭션 강화 (P2)

**D-1. process-evaluation-job 전체 상태 전이를 트랜잭션으로 묶기**

현재: SCORED 저장 + lock 해제가 별도 `update` 호출 → FastAPI 응답 저장 후 lock 해제 실패 시 lock 유지

변경: 성공/실패/재시도/QUOTA_EXCEEDED 모든 상태 전이를 `prisma.$transaction`으로 묶기:

```typescript
await prisma.$transaction([
  prisma.evaluationJob.update({ where: { id: jobId }, data: { status: 'SCORED', ...scoreData, lockedAt: null, lockOwner: null } }),
  // 필요 시 관련 레코드 동시 업데이트
]);
```

**D-2. consumeQuota와 상태 전이 트랜잭션 연계**

`consumeQuotaIfNeeded`는 이미 `prisma.$transaction` 내부에서 실행됨 ✅
단, quota 차감 직후 FastAPI 호출 실패 시 쿼터는 이미 차감된 상태 — 이는 설계상 의도된 동작 (설계 문서 §5: "FastAPI 호출 실패해도 쿼터 차감됨") ✅

---

### 섹션 E: 보안 회귀 테스트 (P2)

`web_saas/src/lib/security/__tests__/security.test.ts` 신규:

| 테스트 케이스 | 기대값 |
|---|---|
| 세션 없이 `POST /api/evaluate/batch` | 401 |
| 세션 있지만 다른 org ID 요청 | 403 또는 세션 org 데이터만 반환 |
| x-internal-secret 없이 `POST /api/internal/process-evaluation-job` | 401 |
| x-internal-nonce 재사용 | 409 |
| `body.limit = 1000000` → search API | take=100 capped |
| `bidNoticeIds` 51개 → batch API | 400 |
| `attachmentUrl = 'http://169.254.169.254'` (AWS metadata) | 400 SSRF 차단 |
| `attachmentUrl = 'https://evil.com'` (allowlist 외) | 400 차단 |
| `NEXT_PUBLIC_APP_URL` 외 Origin → POST /api/evaluate/batch | 403 CSRF |
| zod env 검증 — STRIPE_WEBHOOK_SECRET 미설정 | ZodError throw 확인 |

---

## 3. 변경 파일 목록

### 신규 생성
- `web_saas/src/lib/env.ts` — zod 환경변수 중앙 검증
- `web_saas/src/lib/safe-fetch.ts` — SSRF 방어 fetch 래퍼
- `web_saas/src/lib/internal-auth.ts` — 내부 API HMAC 검증
- `web_saas/src/lib/csrf.ts` — Origin allowlist CSRF 검증
- `web_saas/src/middleware.ts` — NextAuth 세션 보호 + CSRF
- `web_saas/src/app/api/auth/[...nextauth]/route.ts` — NextAuth 핸들러
- `web_saas/src/lib/security/__tests__/security.test.ts` — 회귀 테스트

### 수정
- `web_saas/src/lib/prisma.ts` — 로그 레벨 분기
- `web_saas/src/app/api/webhooks/stripe/route.ts` — env.ts 사용
- `web_saas/src/app/api/evaluate/batch/route.ts` — 세션 주입 + 배열 제한
- `web_saas/src/app/api/export/evaluations/route.ts` — 세션 주입
- `web_saas/src/app/api/internal/evaluation-jobs/route.ts` — HMAC 검증
- `web_saas/src/app/api/internal/process-evaluation-job/route.ts` — HMAC + 트랜잭션
- `web_saas/src/app/api/internal/process-ingestion-job/route.ts` — HMAC + safeFetch
- `web_saas/src/app/api/proposals/route.ts` — 세션 주입
- `web_saas/src/app/api/search/bids/route.ts` — limit 상한
- `web_saas/src/app/api/pre-bid-signals/route.ts` — org 스코프 필터

---

## 4. 실행 순서

```
Wave 1 (C): env.ts + 입력 제한 + SSRF + 로그
Wave 2 (B): internal-auth.ts + 내부 API HMAC
Wave 3 (A): NextAuth + middleware.ts + IDOR 제거 + CSRF
Wave 4 (D): 트랜잭션 강화
Wave 5 (E): 회귀 테스트
```

---

## 5. 비기능 요구사항

- 모든 보안 수정은 TDD — 실패하는 테스트 먼저 작성, 그 다음 구현
- env.ts 검증은 최초 import 시 즉시 실행 (lazy evaluation 금지)
- HMAC 검증은 상수시간 비교 (`timingSafeEqual`) 필수 — timing attack 방지
- SSRF DNS 재검증은 HTTP 응답의 최종 IP로 수행 — DNS rebinding 방어
- 모든 401/403 응답은 본문에 오류 세부 정보 포함 금지 (정보 누출 방지)
