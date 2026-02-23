# Codex 인수인계 문서 (Security Hardening)

작성일: 2026-02-22
작성자: Claude Code (MK-claude 세션)
수신자: Codex (또는 다음 에이전트)

---

## TL;DR

1. **Phase 1~8 코드 구현 완료** (main 브랜치). 보안 강화 작업 중 Token 소진으로 인수인계.
2. **보안 강화 11개 Task 중 Task 1만 완료**, Task 2~11 미착수. 현재 main 브랜치에서 직접 작업 중.
3. 모든 작업 기준 문서: `docs/plans/2026-02-22-security-hardening-impl-plan.md` (Task별 정확한 코드·명령어 포함).
4. 현재 테스트: **30/30 PASS** (`cd web_saas && npx jest --no-coverage`).
5. **Task 2부터 순서대로 실행**하면 된다. Wave 순서(C→B→A→D→E)를 반드시 지킨다.

---

## 현재 브랜치/워크트리 상태

```
Branch: main
Working tree: clean (uncommitted: web_saas/package.json, package-lock.json — zod 설치 흔적, 무해)
Untracked: docs/plans/로드맵.md, 키라봇.png, 키라봇내부.png (무시 가능)
```

**최근 커밋 (관련 순서대로):**
```
c4a27a2  fix(security): env.ts prod guard, n8n WEBHOOK_SECRET via getEnv, test isolation
89df795  feat(security): add zod env validation + fix stripe secret fallback (C-1)
66cb0cb  docs(claude): update CLAUDE.md — Phase 8 complete, security layer, jest constraints
f0afa76  docs: add security hardening implementation plan (11 tasks, 5 waves)
ed4bb39  docs: add security hardening design doc
```

---

## 완료 사항

### Task 1: env.ts — zod 부팅 검증 ✅

**증거:**
- 파일: `web_saas/src/lib/env.ts` (신규)
- 파일: `web_saas/src/lib/__tests__/env.test.ts` (신규, 5개 테스트)
- 파일: `web_saas/src/app/api/webhooks/stripe/route.ts` (수정 — `getEnv()` 사용)
- 파일: `web_saas/src/app/api/webhooks/n8n/route.ts` (수정 — `getEnv()` 사용)
- 커밋: `89df795`, `c4a27a2`
- 테스트: `npx jest src/lib/__tests__/env.test.ts --no-coverage` → **5/5 PASS**

**주요 내용:**
- `getEnv()` — zod 스키마 싱글톤, 부팅 시 10개 환경변수 검증
- `_resetEnv()` — 프로덕션 가드 포함 (테스트 전용)
- `STRIPE_SECRET_KEY`: `sk_test_` 또는 `sk_live_` 접두사 regex 검증
- `WEBHOOK_SECRET`, `INTERNAL_API_SECRET`, `NEXTAUTH_SECRET`: min 32자 검증

---

## 미완료 Task (Task 2~11)

실행 파일: `docs/plans/2026-02-22-security-hardening-impl-plan.md`
모든 Task에 정확한 코드, 테스트 명령어, 커밋 메시지가 기술되어 있다. **파일을 열고 해당 Task 섹션을 그대로 따라가면 된다.**

| Task | Wave | 제목 | 다음 액션 |
|------|------|------|-----------|
| **Task 2** | C (즉각) | 입력 크기 제한 + Prisma 로그 레벨 | `search/bids/route.ts` take에 `Math.min(..., 100)` 적용 |
| **Task 3** | C (즉각) | safe-fetch.ts — SSRF 방어 | `web_saas/src/lib/safe-fetch.ts` 신규 생성 후 ingestion-job 적용 |
| **Task 4** | B | internal-auth.ts + /api/internal/* HMAC | `web_saas/src/lib/internal-auth.ts` 신규 생성 |
| **Task 5** | A | User 모델 추가 (schema + 수동 마이그레이션 SQL) | `prisma/schema.prisma`에 User 모델 추가 |
| **Task 6** | A | NextAuth v5 설치 + auth.ts + route handler | `npm install next-auth@5 bcryptjs @types/bcryptjs` |
| **Task 7** | A | csrf.ts + 테스트 | `web_saas/src/lib/csrf.ts` 신규 생성 |
| **Task 8** | A | middleware.ts — NextAuth + CSRF | `web_saas/src/middleware.ts` 신규 생성 |
| **Task 9** | A | IDOR 제거 — 세션에서 organizationId 주입 | 5개 route 파일 수정 |
| **Task 10** | D | process-evaluation-job 트랜잭션 강화 | `handleScoreError`, `handleNotifyError` → `prisma.$transaction` |
| **Task 11** | E | 보안 회귀 테스트 모음 | `security-regression.test.ts` 신규 생성 |

**실행 순서 엄수:** Task 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11
(Task 8 middleware는 Task 6 NextAuth 완료 후에만 가능. Task 9 IDOR는 Task 6 후에만 가능.)

---

## 처음 30분에 읽어야 할 파일 Top 10 (순서 중요)

1. **`docs/plans/2026-02-22-security-hardening-impl-plan.md`** — 실행 설계도. 모든 코드/명령어 포함. 이것만 있으면 작업 가능.
2. **`docs/plans/2026-02-22-security-hardening-design.md`** — 설계 이유/배경. "왜 이렇게 하는지" 이해용.
3. **`web_saas/src/lib/env.ts`** — Task 1 완성본. 이 패턴을 후속 Task에서 재사용.
4. **`web_saas/src/lib/__tests__/env.test.ts`** — TDD 패턴 레퍼런스. 이 구조로 후속 테스트 작성.
5. **`web_saas/src/lib/hmac.ts`** — Task 4 internal-auth.ts 작성 시 이 패턴 재사용 (`verifyWebhookSignature`).
6. **`web_saas/src/__mocks__/prisma.ts`** — Jest 테스트에서 prisma 모킹 현황. Task 4에서 `usedNonce` mock 추가 필요.
7. **`web_saas/src/app/api/internal/process-evaluation-job/route.ts`** — Task 4, 10의 수정 대상.
8. **`web_saas/src/app/api/evaluate/batch/route.ts`** — Task 2, 9의 수정 대상.
9. **`web_saas/jest.config.js`** — Jest 설정. `testMatch: ['**/__tests__/**/*.test.ts']`, moduleNameMapper 확인 필수.
10. **`CLAUDE.md`** — 프로젝트 전체 아키텍처, 실행 명령어, 설계 결정 요약.

---

## 리스크 / 블로커 / 의사결정 필요사항

### 리스크 1 (High): Task 6 NextAuth v5 — DB 없이 빌드 가능 여부
- `next-auth@5` 설치 후 `npx prisma generate`가 DB 없어도 동작함 (타입 생성만)
- 하지만 실제 로그인 흐름 E2E 테스트는 PostgreSQL 필요. **지금은 유닛 테스트만 작성하고 넘어가도 됨.**
- `npx tsc --noEmit` 타입 체크로 빌드 오류 여부 확인.

### 리스크 2 (High): Task 4 UsedNonce 테이블 — prisma mock에 누락
- 현재 `src/__mocks__/prisma.ts`에 `usedNonce` 없음.
- **Task 4 시작 전** 반드시 mock에 `usedNonce: { create: jest.fn() }` 추가해야 internalAuth 테스트 통과.
- 추가 위치: `web_saas/src/__mocks__/prisma.ts`

### 리스크 3 (Medium): middleware.ts — Next.js App Router와 next-auth@5 API 충돌 가능성
- `next-auth@5`는 `auth()` wrapper 방식으로 middleware 작성 (설계 문서 Task 8 참조).
- 타입 오류 시 `import { auth } from '@/auth'` 경로가 맞는지 확인.

### 리스크 4 (Medium): Task 9 IDOR 제거 — organizationId를 body에서 받는 기존 API
- Task 9는 5개 route 파일에서 `organizationId`를 body/query에서 완전히 제거.
- Task 8 middleware 완료 후에만 실행. (middleware 없이 IDOR 제거하면 401 응답 불가)
- Task 9 이후 기존 클라이언트 코드가 `organizationId`를 body에 보내도 무시됨 — 프론트엔드 수정 필요 (지금은 무시, 배포 시 처리).

### 의사결정 필요 없음
- 설계 문서에 모든 선택 이유가 기술됨. Codex는 플랜대로 실행하면 됨.
- NextAuth provider는 Credentials만 사용 (Supabase OAuth 배제 결정됨).
- CSRF는 CSRF 토큰 아닌 Origin allowlist 방식 결정됨 (구현 단순).

---

## 즉시 실행 가능한 첫 배치 작업 (최대 3개)

아래 3개는 서로 독립적이고 가장 간단하므로 순서대로 즉시 실행:

### Batch 1: Task 2 — 입력 크기 제한 + Prisma 로그 (5분)

```bash
# 검증
cd /path/to/repo/web_saas && npx jest --no-coverage  # 30/30 확인

# 1. search/bids/route.ts — take 상한
# 파일 66번 라인: take: body.limit ?? 50,
# → take: Math.min(Number(body.limit ?? 50), 100),

# 2. evaluate/batch/route.ts — bidNoticeIds 길이 제한
# 11번 라인: if (!bidNoticeIds?.length || !organizationId) {
# → if (!bidNoticeIds?.length || bidNoticeIds.length > 50 || !organizationId) {
#   return NextResponse.json({ error: 'bidNoticeIds: 1–50 items required' }, { status: 400 });

# 3. prisma.ts — 로그 레벨
# log: ['query', 'error', 'warn']
# → log: process.env.NODE_ENV === 'production' ? ['error'] : ['query', 'error', 'warn'],

# 검증
npx jest --no-coverage

# 커밋
git add web_saas/src/app/api/search/bids/route.ts web_saas/src/app/api/evaluate/batch/route.ts web_saas/src/lib/prisma.ts
git commit -m "feat(security): cap input limits, fix prisma log level in production (C-2, C-4)"
```

### Batch 2: Task 3 — safe-fetch.ts SSRF 방어 (20분)

`docs/plans/2026-02-22-security-hardening-impl-plan.md`의 **Task 3 섹션** 그대로 따라가면 됨.
신규 파일: `web_saas/src/lib/safe-fetch.ts` + `web_saas/src/lib/__tests__/safeFetch.test.ts`
수정: `process-ingestion-job/route.ts` (safeFetch 적용)

### Batch 3: Task 4 — internal-auth.ts HMAC (20분)

`docs/plans/2026-02-22-security-hardening-impl-plan.md`의 **Task 4 섹션** 그대로 따라가면 됨.
**주의:** 먼저 `src/__mocks__/prisma.ts`에 `usedNonce: { create: jest.fn() }` 추가 후 시작.

---

## 에이전트/도구 활용 방법 (Claude Code 전용)

이 저장소는 Claude Code의 **Subagent-Driven Development** 방식으로 작업 중이었다.
Codex가 Claude Code를 사용한다면 동일 방식을 따를 것. 아닌 경우 아래를 참고.

### 작업 방식 (Claude Code 사용 시)

각 Task마다 다음 3단계를 반복:

1. **Implementer 서브에이전트** 디스패치
   - 플랜 파일의 해당 Task 전체 코드를 프롬프트에 포함해서 전달
   - 서브에이전트가 TDD (실패 테스트 작성 → 구현 → PASS 확인 → 커밋) 수행

2. **Spec Reviewer 서브에이전트** 디스패치
   - 설계 문서 요구사항과 구현 코드 비교
   - 누락/과잉 구현 체크. ✅ 통과 or ❌ 수정 지시

3. **Code Quality Reviewer 서브에이전트** 디스패치
   - `.claude/agents/code-review-veteran.md` 정의된 에이전트 활용
   - 보안 결함, 테스트 누락, 엣지케이스 체크. ✅ 통과해야 Task 완료

### 프로젝트 커스텀 에이전트 (`.claude/agents/` 내 정의됨)

| 에이전트 | 파일 | 용도 |
|----------|------|------|
| `code-review-veteran` | `.claude/agents/code-review-veteran.md` | 구현 후 코드 품질 리뷰 (Critical→High→Medium 순 지적) |
| `knowledge-curator` | `.claude/agents/knowledge-curator.md` | `docs/agent-memory/` 업데이트 (핸드오프 전 호출) |

### 프로젝트 커스텀 스킬 (`.claude/skills/` 내 정의됨)

| 스킬 | 경로 | 용도 |
|------|------|------|
| `maintainability-guardian` | `.claude/skills/maintainability-guardian/SKILL.md` | 유지보수성 루브릭 기반 리뷰 |
| `agent-memory-sync` | `.claude/skills/agent-memory-sync/SKILL.md` | 핸드오프 전 메모리 파일 동기화 |

### 팀 공용 메모리 파일

- `docs/agent-memory/context.md` — 프로젝트 핵심 컨텍스트
- `docs/agent-memory/decision-log.md` — 주요 의사결정 기록
- `docs/agent-memory/patterns.md` — 재사용 가능한 패턴
- `docs/agent-memory/failures.md` — 실패/회고/재발방지

**작업 시작 전 위 4개 파일 먼저 읽을 것.**

### Codex 단독으로 작업 시 (Claude Code 미사용)

1. 플랜 파일(`2026-02-22-security-hardening-impl-plan.md`)의 각 Task를 순서대로 실행.
2. 각 Step마다 명시된 bash 명령어를 그대로 실행.
3. 테스트 FAIL 시 → 구현 수정 → 재실행. 절대 억지로 테스트를 통과시키지 말 것.
4. 커밋 후 다음 Task로 진행.

---

## 핵심 설계 결정 요약 (재확인용)

| 항목 | 결정 | 이유 |
|------|------|------|
| env.ts 검증 방식 | zod safeParse + 명시적 오류 메시지 | process crash보다 진단 가능한 오류 |
| HMAC 서명 문자열 | `ts.nonce.rawBody` | nonce 교체 공격 방지 |
| Nonce 중복 방지 | `prisma.usedNonce.create()` + P2002 catch | findUnique+create 2-step race condition 방지 |
| CSRF 방식 | Origin allowlist | CSRF 토큰보다 구현 단순, SPA에 적합 |
| 내부 API 보호 | HMAC (기존 lib/hmac.ts 패턴 재사용) | replay window ±5분, nonce 중복 방지 |
| SSRF 방어 | https only + allowlist + DNS rebinding 방지 + redirect:'manual' | 단계별 심층 방어 |
| IDOR 제거 | body에서 organizationId 완전 제거 + session에서만 주입 | 이중 방어 |
| 트랜잭션 범위 | handleScoreError/handleNotifyError 각각 $transaction | 상태 전이 원자성 보장 |

---

## 테스트 실행 레퍼런스

```bash
# 위치 이동
cd /Users/min-kyungwook/Desktop/기업전용챗봇세분화/web_saas

# 전체 테스트 (현재: 30/30 PASS, 8 suites)
npx jest --no-coverage

# 특정 테스트만
npx jest src/lib/__tests__/env.test.ts --no-coverage

# TypeScript 타입 체크
npx tsc --noEmit 2>&1 | head -30

# Prisma 클라이언트 재생성 (schema 변경 후)
npx prisma generate

# Jest 설정 위치
# web_saas/jest.config.js
# testMatch: ['**/__tests__/**/*.test.ts']  ← 이 패턴 외 경로는 인식 안 됨
# moduleNameMapper: '@/lib/prisma' → src/__mocks__/prisma.ts (자동 목킹)
#                   '@/lib/ids'   → src/__mocks__/ids.ts
```

---

## 인수인계 체크리스트 (Codex 수신 확인용)

- [ ] `docs/plans/2026-02-22-security-hardening-impl-plan.md` 읽음
- [ ] `web_saas/src/lib/env.ts` 내용 파악 (Task 1 완성본)
- [ ] `cd web_saas && npx jest --no-coverage` 실행 → 30/30 확인
- [ ] Task 2부터 순서대로 시작 준비 완료
