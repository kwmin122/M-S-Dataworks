# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## 프로젝트 개요

**Kira Bot** — 공공조달 입찰 자격 분석 플랫폼. 기업이 RFx(RFP/RFQ/입찰공고) 문서를 올리면 자격요건을 추출하고, 회사 문서와 매칭하여 GO/NO-GO + 준비 가이드를 제공한다.

현재: 기존 단일 사용자 Streamlit MVP + **멀티테넌트 B2B SaaS** (Phase 1~8 완료, 환경 구성·배포 단계).

설계 문서: `docs/plans/2026-02-20-bid-platform-design.md`
구현 계획: `docs/plans/2026-02-21-bid-platform-impl-plan.md` (Phase 1-7), `docs/plans/2026-02-22-phase8-impl-plan.md` (Phase 8)
보안 강화: `docs/plans/2026-02-22-security-hardening-design.md` + `2026-02-22-security-hardening-impl-plan.md`
다음 할 일: `docs/plans/다음-할-일.md`

---

## 실행 명령어

### Python 레거시 백엔드 (FastAPI, 루트)
```bash
pip install -r requirements.txt
python services/web_app/main.py   # 포트 8010
streamlit run app.py              # 레거시 UI, 포트 8501
```

### React 프론트엔드 (레거시 대시보드)
```bash
cd frontend/kirabot
npm install
npm run dev    # 포트 5173 (Vite)
npm run build  # dist/ 번들
```

### SaaS 스택
```bash
# Next.js (web_saas, 포트 3000)
cd web_saas && npm run dev

# RAG Engine FastAPI (rag_engine, 포트 8001)
cd rag_engine && uvicorn main:app --reload --port 8001

# Prisma — DATABASE_URL이 있을 때만
cd web_saas && npx prisma migrate dev --name <name>
cd web_saas && npx prisma generate

# npm 캐시 권한 오류 시
npm install <pkg> --cache /tmp/npm-cache
```

### 테스트
```bash
# 레거시 Python (루트)
pytest -q
pytest tests/test_matcher_detail_rules.py -v
pytest tests/test_constraint_evaluator.py::test_contract_amount_pass -v

# rag_engine Python
cd rag_engine && pytest -q
cd rag_engine && pytest tests/test_hwp_parser.py -v

# web_saas Jest
cd web_saas && npx jest --no-coverage
cd web_saas && npx jest src/lib/__tests__/hmac.test.ts --no-coverage
cd web_saas && npx jest --testPathPattern="quota" --no-coverage

# 정확도 평가 / 배포 전 체크
python scripts/run_accuracy_eval.py
python scripts/run_railway_predeploy_checklist.py --base-url https://your-domain.com
```

---

## 아키텍처

### 레거시 Kira Bot (루트)

```
frontend/kirabot/    ← React 19 + Vite + TypeScript
        ↓ HTTP (port 8010)
services/web_app/main.py   ← FastAPI: 업로드, 세션, 채팅, 분석
        ↓ Python import
  engine.py          ← ChromaDB + BM25 하이브리드 벡터 검색
  rfx_analyzer.py    ← LLM 기반 자격요건 추출 (멀티패스 + Structured Outputs)
  matcher.py         ← ConstraintEvaluator (결정론 우선) + LLM GO/NO-GO
  chat_router.py     ← 인텐트 분류 + 오프토픽 차단
  document_parser.py ← PDF/DOCX/HWP 파싱 및 청킹
services/auth_gateway/main.py  ← Supabase JWT → HttpOnly 쿠키 세션 (레거시 전용)

data/vectordb/  ← ChromaDB 영구 저장소
data/user_store/ ← 세션 + 사용량 JSON
```

### SaaS 스택 (Phase 1-8 완료)

```
web_saas/                        ← Next.js 16 + Prisma 5 + TypeScript
  src/middleware.ts               ← NextAuth 세션 보호 + CSRF origin check
  src/auth.ts                     ← NextAuth v5 Credentials provider (세션에 organizationId 포함)
  src/lib/
    env.ts                        ← zod 부팅 검증 (필수 env 누락 시 즉시 throw)
    prisma.ts                     ← PrismaClient 싱글턴 (prod: log:['error']만)
    hmac.ts                       ← HMAC-SHA256 verifyWebhookSignature (timingSafeEqual)
    internal-auth.ts              ← 내부 API HMAC 검증 (ts/nonce/sig, UsedNonce 재사용)
    safe-fetch.ts                 ← SSRF 방어 fetch (https only, DNS pre-check, redirect:manual)
    csrf.ts                       ← Origin allowlist CSRF 방어 (POST/PUT/PATCH/DELETE)
    ids.ts, errors.ts             ← createId(cuid2), isUniqueConstraintError(P2002)
    quota/consumeQuota.ts         ← $transaction 내 원자 쿼터 차감
    jobs/createEvaluationJobs.ts  ← interestConfig 필터 → EvaluationJob 생성
    search/buildSearchQuery.ts    ← Prisma where 조건 빌더
    search/ftsSearch.ts           ← PostgreSQL FTS 쿼리 빌더 (plainto_tsquery)
    export/buildEvaluationExcel.ts ← ExcelJS 기반 평가결과 xlsx 생성
    strengthCard/buildStrengthCard.ts ← 회사 강점 vs 공고 요건 매칭
  src/app/api/
    auth/[...nextauth]/           ← NextAuth 핸들러
    webhooks/n8n/                 ← n8n → Next.js HMAC 웹훅 (리플레이 방지)
    webhooks/stripe/              ← Stripe SDK constructEvent 검증
    internal/process-ingestion-job/ ← HMAC 보호, safeFetch, $transaction
    internal/process-evaluation-job/ ← HMAC 보호, 쿼터차감, FastAPI 호출, Resend
    internal/evaluation-jobs/    ← HMAC 보호, org 스코프 목록
    search/bids/                  ← 공고 검색 (FTS 또는 Prisma 필터)
    evaluate/batch/               ← 다중 공고 EvaluationJob 생성 (세션 org 주입)
    export/evaluations/           ← xlsx 다운로드 (세션 org 주입)
    proposals/                    ← ProposalDraft 생성 (FastAPI generate-proposal 호출)
    strength-card/[bidNoticeId]/  ← 강점 카드 (Next.js 15+ params: Promise<> 패턴)
    pre-bid-signals/              ← 사전감지 공고 목록

rag_engine/                       ← FastAPI 0.115 (포트 8001)
  main.py                         ← /api/analyze-bid, /api/generate-proposal, /api/parse-hwp
  proposal_generator.py           ← {{placeholder}} 템플릿 섹션 추출·채움
  hwp_parser.py                   ← HWP magic bytes 감지 + 텍스트 추출

n8n/workflows/                    ← 4종 워크플로우 JSON
  g2b_bid_crawler.json            ← 나라장터 공고 수집 → BidNotice/IngestionJob
  ingestion_worker.json           ← process-ingestion-job 호출
  evaluation_worker.json          ← process-evaluation-job 호출
  stale_lock_reclaim.json         ← 만료 락 해제

PostgreSQL (Docker) ← PGTZ=UTC 강제, Prisma ORM
```

### 핵심 데이터 흐름 (SaaS)

```
n8n g2b_bid_crawler
  → BidNotice UPSERT → IngestionJob INSERT (ON CONFLICT DO NOTHING)
  → process-ingestion-job: safeFetch 다운로드 → contentHash → $transaction COMPLETED
  → createEvaluationJobsForBidNotice (interestConfig 매칭 후)
  → process-evaluation-job:
      HMAC 락 획득 → consumeQuotaIfNeeded($tx) → FastAPI analyze-bid → SCORED → Resend 이메일
```

### 프론트엔드 워크스페이스 구조

`frontend/kirabot/components/Dashboard.tsx`:
- `WorkspaceMode = 'rfx' | 'search' | 'multi' | 'proposal'` — 4탭 구조
- `rfx`: 기존 RFx 분석 채팅 흐름 (보존 필수)
- `search`: `SearchPanel.tsx` — 폼/인터뷰 모드 공고 검색
- `multi`: `MultiAnalysisPanel.tsx` — 다중 평가 + xlsx 다운로드
- `proposal`: `ProposalPanel.tsx` — 제안서 초안 생성

---

## 핵심 설계 결정

### SaaS 잡 시스템
- **중간 상태 DB 저장 금지**: FETCHING/PARSING/EVALUATING 등은 인메모리만 — 크래시 시 직전 안정 상태로 복구
- **락 획득**: `UPDATE WHERE locked_at IS NULL` + affected rows 검사 — `FOR UPDATE SKIP LOCKED` 금지
- **ID 생성**: `createId()` (cuid2, 앱 레벨) — `gen_random_uuid()` 금지
- **UTC**: `PGTZ=UTC`, `Date.UTC()` 사용 — `new Date(year, month, 1)` 금지

### HMAC 웹훅 / 내부 API
- 서명 문자열: `${ts}.${nonce}.${rawBody}` — nonce 필수 (교체 공격 방지)
- `request.text()` 먼저 읽고 → HMAC 검증 → `JSON.parse()` — `request.json()` 직접 호출 금지
- Nonce 중복: `UsedNonce.create()` create-only + P2002 catch — 2단계 findUnique+create 금지
- 내부 API(`/api/internal/*`)도 동일 패턴: `verifyInternalAuth(req, rawBody)`

### 보안 레이어
- **env.ts**: `getEnv()` zod 검증 — 누락 시 부팅 차단. 환경변수 직접 `process.env.*` 접근 금지
- **SSRF**: `safeFetch(url, allowedDomains)` — https only, DNS 사전 해석, private IP 차단, redirect:'manual', 10초 타임아웃
- **CSRF**: `verifyCsrfOrigin(req)` — POST/PUT/PATCH/DELETE에 Origin allowlist 검증
- **IDOR**: 모든 사용자 API에서 `organizationId` 입력 제거, `getServerSession()` → `session.user.organizationId` 주입
- **미들웨어 매처**: `/api/((?!webhooks|internal|auth).*)` — webhooks/internal/auth 제외 후 NextAuth 보호

### 쿼터 관리
- `consumeQuotaIfNeeded()`: `$transaction` 내 원자 실행 — `UPDATE WHERE used_count < max_count` 조건부 증가
- `quotaConsumed=true`로 재시도 중복 차감 방지
- FastAPI 호출 실패해도 쿼터 차감됨 (요청 기반 — 의도된 설계)

### RAG 파이프라인 (레거시)
- BM25 + 벡터 RRF 하이브리드 (`RAG_HYBRID_ENABLED=1`)
- `rfx_analyzer.py` 멀티패스 → `RFxAnalysisResult` (constraints)
- `ConstraintEvaluator` 결정론 비교 우선, `FALLBACK_NEEDED` 시 LLM 판단

### Prisma 마이그레이션 (오프라인)
DATABASE_URL 없이 스키마 변경 시 수동 SQL 파일 생성:
```
web_saas/prisma/migrations/YYYYMMDDHHMMSS_<name>/migration.sql
```
`npx prisma migrate dev --create-only`는 DATABASE_URL 필요 → 없으면 파일 직접 생성.
`npx prisma generate`는 DATABASE_URL 없이도 가능.

### 프론트엔드 제약
- `frontend/kirabot/` CSS·레이아웃 **전면 변경 금지**
- 기존 Tailwind 클래스 재사용, 신규 className 최소화
- `WorkspaceMode = 'rfx'` 탭의 기존 채팅 흐름 보존 필수
- JSX 다중 형제 조건부 렌더링: `{condition && (<>...</>)}` Fragment 필수

---

## web_saas Jest 제약

```
testMatch: ['**/__tests__/**/*.test.ts']   ← __tests__/ 하위 디렉터리에만 위치
moduleNameMapper:
  @/lib/prisma → src/__mocks__/prisma.ts   ← 모든 테스트에서 자동 모킹
  @/lib/ids   → src/__mocks__/ids.ts
```

테스트 파일은 반드시 `src/lib/<module>/__tests__/<name>.test.ts` 패턴.
`src/__mocks__/prisma.ts`에 테스트에서 사용하는 prisma 메서드를 추가해야 함.

---

## 환경 변수

| 변수 | 용도 |
|---|---|
| `OPENAI_API_KEY` | 임베딩 + LLM |
| `DATABASE_URL` | PostgreSQL (SaaS) |
| `WEBHOOK_SECRET` | n8n↔Next.js HMAC (≥32자) |
| `INTERNAL_API_SECRET` | `/api/internal/*` HMAC (≥32자) |
| `STRIPE_SECRET_KEY` | Stripe 결제 |
| `STRIPE_WEBHOOK_SECRET` | Stripe 웹훅 서명 |
| `NEXTAUTH_SECRET` | NextAuth JWT 서명 (≥32자) |
| `NEXTAUTH_URL` | NextAuth 기본 URL |
| `NEXT_PUBLIC_APP_URL` | CSRF allowlist 기준 URL |
| `ATTACHMENT_ALLOWED_DOMAINS` | safeFetch allowlist (예: `.go.kr`) |
| `FASTAPI_URL` | RAG Engine URL (기본: `http://localhost:8001`) |
| `RESEND_API_KEY` | 이메일 알림 |
| `OPENAI_STRICT_JSON_ONLY` | `1` = Structured Outputs 전용 |
| `RAG_HYBRID_ENABLED` | `1` = BM25+벡터 하이브리드 |

---

## 테스트 파일 매핑

### 레거시 Python (tests/)
| 파일 | 대상 |
|---|---|
| `test_constraint_evaluator.py` | `matcher.py` ConstraintEvaluator |
| `test_company_fact_normalizer.py` | `matcher.py` CompanyFactNormalizer |
| `test_matcher_detail_rules.py` | `matcher.py` 규칙형 판단 |
| `test_matcher_consortium_rule.py` | `matcher.py` 컨소시엄 지분 |
| `test_rfx_analyzer_constraints.py` | `rfx_analyzer.py` constraints |
| `test_rfx_analyzer_multipass.py` | `rfx_analyzer.py` 멀티패스 merge |
| `test_hybrid_search.py` | `engine.py` BM25+벡터 RRF |
| `test_chat_router.py` | `chat_router.py` 인텐트 분류 |
| `test_web_runtime_api.py` | `services/web_app/main.py` |

### rag_engine Python (rag_engine/tests/)
| 파일 | 대상 |
|---|---|
| `test_hwp_parser.py` | `hwp_parser.py` |
| `test_proposal_generator.py` | `proposal_generator.py` |

### web_saas Jest (src/lib/*/\__tests__/)
| 파일 | 대상 |
|---|---|
| `lib/__tests__/hmac.test.ts` | `lib/hmac.ts` |
| `lib/__tests__/env.test.ts` | `lib/env.ts` |
| `lib/__tests__/safeFetch.test.ts` | `lib/safe-fetch.ts` |
| `lib/__tests__/internalAuth.test.ts` | `lib/internal-auth.ts` |
| `lib/__tests__/csrf.test.ts` | `lib/csrf.ts` |
| `lib/quota/__tests__/consumeQuota.test.ts` | `lib/quota/consumeQuota.ts` |
| `lib/search/__tests__/buildSearchQuery.test.ts` | `lib/search/buildSearchQuery.ts` |
| `lib/search/__tests__/ftsSearch.test.ts` | `lib/search/ftsSearch.ts` |
| `lib/export/__tests__/buildEvaluationExcel.test.ts` | `lib/export/buildEvaluationExcel.ts` |

---

## 팀 에이전트 표준

**작업 시작 전 필독**: `docs/agent-memory/context.md`

공용 메모리:
- `docs/agent-memory/context.md` — 프로젝트 핵심 컨텍스트
- `docs/agent-memory/decision-log.md` — 주요 의사결정
- `docs/agent-memory/patterns.md` — 재사용 패턴
- `docs/agent-memory/failures.md` — 실패/회고/재발방지

에이전트 자산 (`.claude/`):
- `.claude/agents/code-review-veteran.md` — 코드 리뷰 서브에이전트
- `.claude/agents/knowledge-curator.md` — 팀 메모리 관리 서브에이전트
- `.claude/skills/maintainability-guardian/SKILL.md` — 유지보수성 루브릭
- `.claude/skills/agent-memory-sync/SKILL.md` — 핸드오프 전 메모리 동기화
- `.claude/commands/think.md` — `/think` 슬래시 커맨드
