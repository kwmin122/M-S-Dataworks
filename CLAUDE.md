# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## 프로젝트 개요

**Kira Bot** — 공공조달 입찰 전 과정 자동화 AI 플랫폼. 공고 발견 → RFP 분석 → GO/NO-GO → 제안서 자동 생성 → 체크리스트 → 수정 학습까지 입찰 라이프사이클 자동화.

현재: 레거시 Chat UI (React + FastAPI) + **멀티테넌트 B2B SaaS** (Phase 1~8 완료) + **A-lite 제안서 생성 파이프라인** (Phase 1 구현 완료).

비전/목표: `docs/우리의_목표.md`

### 현재 진행 중: Bid Studio (입찰 제출 패키지 워크스페이스)
- **설계**: `docs/plans/2026-03-18-bid-studio-master-design.md`
- **구현 계획**: `docs/plans/2026-03-18-bid-studio-master-implementation-plan.md`
- **핵심**: 제안서 작성기가 아니라 **입찰 제출 패키지 Studio** (용역+물품+공사)
- **구현 방식**: 가로 확장 ❌ → **세로 슬라이스** (Slice 1: proposal end-to-end)
- **아키텍처**: package classifier → company/style 연결 → generated docs + evidence checklist → review/relearning
- **제품 경계**: Chat=탐색, Studio=정식 생산 경로, Settings=shared master

확장 설계: `docs/plans/2026-02-27-full-lifecycle-expansion-design.md` (8모듈 + 3계층 학습 모델)
Phase 1 핸드오프: `docs/plans/2026-02-27-phase1-implementation-handoff.md`
현재 상황: `docs/plans/2026-02-27-현재상황-핸드오프.md`
SaaS 설계: `docs/plans/2026-02-20-bid-platform-design.md`
SaaS 구현: `docs/plans/2026-02-21-bid-platform-impl-plan.md` (Phase 1-7), `docs/plans/2026-02-22-phase8-impl-plan.md` (Phase 8)
보안 강화: `docs/plans/2026-02-22-security-hardening-design.md` + `2026-02-22-security-hardening-impl-plan.md`
RFP 요약 리디자인: `docs/plans/2026-02-26-rfp-summary-redesign.md`

---

## 실행 명령어

### Python 백엔드 (FastAPI, 루트)
```bash
pip install -r requirements.txt
python services/web_app/main.py   # 포트 8000 (uvicorn)
```

### React 프론트엔드 (Chat UI)
```bash
cd frontend/kirabot
npm install
npm run dev    # 포트 5173 (Vite) → 백엔드 http://localhost:8000
npm run build  # dist/ 번들 → 백엔드가 서빙
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

### Kira Bot (루트) — 현재 활성 스택

```
frontend/kirabot/              ← React 19 + Vite + TypeScript
  App.tsx                      ← 랜딩페이지 ↔ ChatLayout 전환 (AppView FSM)
  components/chat/ChatLayout.tsx ← Sidebar + ChatArea + ContextPanel (리사이즈 가능)
  context/ChatContext.tsx      ← useReducer 기반 대화 상태 관리
  hooks/useConversationFlow.ts ← 대화 FSM (greeting→검색→분석→채팅) + 모든 액션 핸들러
  services/kiraApiService.ts   ← 백엔드 API 클라이언트 (API_BASE_URL 자동 감지)
        ↓ HTTP (port 8000)
services/web_app/main.py      ← FastAPI: 업로드, 세션, 채팅, 분석, 공고검색, 일괄평가
services/web_app/nara_api.py   ← 나라장터 Open API 클라이언트 (검색, 첨부파일, 다운로드)
        ↓ Python import
  engine.py          ← ChromaDB + BM25 하이브리드 벡터 검색 (BM25 Lock 스레드 안전)
  rfx_analyzer.py    ← LLM 기반 자격요건 추출 (멀티패스 + 병렬 청크 + RFP 요약 생성)
  matcher.py         ← ConstraintEvaluator (결정론 우선) + LLM GO/NO-GO (병렬 매칭)
  llm_utils.py       ← LLM 호출 retry + timeout 헬퍼 (call_with_retry)
  rfp_synonyms.py    ← RFP 동의어 사전 (17개 카테고리, 프롬프트 주입용)
  chat_router.py     ← 인텐트 분류 + 오프토픽 차단
  document_parser.py ← PDF/DOCX/HWP/Excel/PPT 파싱 및 청킹
services/auth_gateway/main.py  ← Supabase JWT → HttpOnly 쿠키 세션

data/vectordb/       ← ChromaDB 영구 저장소
data/web_uploads/    ← 세션별 업로드 파일 (company/ + target/)
data/user_store/     ← 세션 + 사용량 JSON
data/layer1_sources/ ← Layer 1 학습 소스 URL 큐레이션 (youtube/blog/official JSON)
data/knowledge_db/   ← Layer 1 proposal_knowledge ChromaDB (rag_engine)
data/proposals/      ← 생성된 DOCX 제안서 출력 디렉토리
docs/dummy/          ← 테스트용 더미 문서 (PDF/HWP/HWPX)
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
                                     + /api/generate-proposal-v2, /api/checklist, /api/edit-feedback
  proposal_generator.py           ← {{placeholder}} 템플릿 섹션 추출·채움 (기존, v1용)
  hwp_parser.py                   ← HWP magic bytes 감지 + 텍스트 추출

  # A-lite 제안서 파이프라인 (Phase 1, 2026-02-27 추가)
  llm_utils.py                    ← LLM retry+timeout 헬퍼 (call_with_retry, 지수 백오프)
  knowledge_models.py             ← KnowledgeUnit, ProposalSection, ProposalOutline 등 데이터 모델
  knowledge_db.py                 ← ChromaDB proposal_knowledge collection (sha256 복합ID)
  knowledge_harvester.py          ← LLM Pass 1 지식 추출 (7카테고리)
  knowledge_dedup.py              ← LLM Pass 2 충돌 해소 (AGREE/CONDITIONAL/CONFLICT)
  proposal_planner.py             ← RFP → 섹션 아웃라인 (배점 비례 페이지 분배)
  section_writer.py               ← Layer 1+2 지식 주입 LLM 섹션 생성
  quality_checker.py              ← 블라인드 위반(한글 조사 인식 정규식) + 모호 표현 감지
  document_assembler.py           ← mistune 3.x AST + python-docx DOCX 조립
  proposal_orchestrator.py        ← 전체 파이프라인 오케스트레이터 (ThreadPoolExecutor)
  company_db.py                   ← 회사 역량 DB (실적/인력 ChromaDB, hashlib.sha256 ID)
  company_analyzer.py             ← 과거 제안서 문체/구조/강점 분석
  checklist_extractor.py          ← RFP → 제출서류 체크리스트 추출
  diff_tracker.py                 ← AI vs 사용자 수정 diff 추출 + 패턴 키 해싱
  auto_learner.py                 ← 수정 패턴 → Layer 2 자동 학습 (threading.Lock 스레드 안전)

  # Phase 2 모듈 (B/C/F, 2026-02-27 추가)
  phase2_models.py                ← WbsTask, PersonnelAllocation, SlideContent, QnaPair 등 공통 모델
  wbs_planner.py                  ← 방법론 템플릿 + LLM WBS 태스크 생성
  wbs_generator.py                ← openpyxl XLSX + matplotlib 간트차트 + DOCX
  wbs_orchestrator.py             ← WBS 파이프라인 오케스트레이터
  ppt_slide_planner.py            ← 슬라이드 구성 + 예상질문 생성
  ppt_content_extractor.py        ← 제안서→슬라이드 콘텐츠 추출
  ppt_assembler.py                ← python-pptx PPTX 조립
  ppt_orchestrator.py             ← PPT 파이프라인 오케스트레이터
  track_record_writer.py          ← 실적/인력 매칭 + LLM 서술 생성
  track_record_assembler.py       ← 실적기술서 DOCX 조립 (표+서술)
  track_record_orchestrator.py    ← 실적기술서 파이프라인 오케스트레이터

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

### 프론트엔드 Chat UI 구조 (현재)

`Dashboard.tsx` + 워크스페이스 4탭 구조는 **삭제됨**. 대신 대화형 Chat UI로 전환:

```
ChatLayout.tsx ← 전체 레이아웃 (Sidebar + ChatArea + ContextPanel)
  ├── Sidebar.tsx ← 대화 목록 + 새 대화 + 이름 변경/삭제
  ├── ChatArea.tsx ← 메시지 스트림 + 입력창
  │   ├── ChatHeader.tsx ← "다른 문서 분석" / "회사 문서 추가" 버튼
  │   ├── MessageList.tsx → MessageBubble.tsx → 7종 메시지 뷰
  │   └── ChatInput.tsx ← 자유 텍스트 입력
  └── ContextPanel.tsx ← 우측 패널 (문서 미리보기, 공고 상세, 제안서)
      └── DocumentViewer.tsx ← PDF(iframe) + 비PDF(다운로드) 뷰어, 탭 지원
```

대화 FSM (`ConversationPhase`):
```
greeting → bid_search_input → bid_search_results → bid_analyzing → doc_chat
         → doc_upload_company → doc_upload_target → doc_analyzing → doc_chat
         → bid_eval_running → bid_eval_results
```

메시지 타입: `text`, `button_choice`, `bid_card_list`, `analysis_result`, `inline_form`, `file_upload`, `status`

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

### RAG 파이프라인 + 병렬화
- BM25 + 벡터 RRF 하이브리드 (`RAG_HYBRID_ENABLED=1`), BM25 rebuild `threading.Lock` 보호
- `rfx_analyzer.py` 멀티패스 → `RFxAnalysisResult` (requirements) + `generate_rfp_summary()` (3섹션 마크다운)
- `ConstraintEvaluator` 결정론 비교 우선, `FALLBACK_NEEDED` 시 LLM 판단
- **병렬화 패턴**: `ThreadPoolExecutor`로 청크 추출(max 4), 요건 매칭(max 6) 병렬 실행
- **비동기 API**: `asyncio.to_thread()`로 FastAPI 이벤트 루프 차단 방지, `asyncio.gather()`로 분석+요약+매칭 동시 실행
- **일괄 평가**: `asyncio.Semaphore(3)` + `asyncio.gather()`로 동시 3건 제한 병렬 처리
- **LLM 안정성**: `call_with_retry()` — timeout 60초 + 재시도 2회 (429/500/502/503, 지수 백오프)
- **동의어 사전**: `rfp_synonyms.py` — 17개 카테고리 동의어(사업비↔예산↔추정가격 등)를 추출 프롬프트에 주입

### A-lite 제안서 파이프라인 (rag_engine)
- **기존 `/api/proposal/generate` 절대 삭제 금지** — 챗봇 간단 초안 기능의 핵심. v2는 별개 엔드포인트
- **mistune 3.x AST** 기반 마크다운→DOCX 변환 (정규식 파싱 금지)
- **Pydantic 입력 검증**: `RfxResultInput` 스키마 — title 필수, total_pages 10~200
- **한글 단어 경계 정규식**: 블라인드 체크에서 `(?<![가-힣])회사명(?=(?:은|는|이|가|...)?(?![가-힣]))` — 조사 허용, 내용어 결합 차단
- **파일명 sanitization**: `re.sub(r'[^a-zA-Z0-9가-힣._-]', '_', ...)` 화이트리스트 + 100자 제한
- **KnowledgeDB 복합 ID**: `{source_type}_{sha256(source_type:category:rule)[:12]}` — 충돌 방지
- **auto_learner 스레드 안전**: `threading.Lock`으로 전역 dict 보호
- **배포 수준 코딩**: 에러 핸들링, 입력 검증, LLM retry, 스레드 안전성 모두 필수 (MVP 금지)

### Prisma 마이그레이션 (오프라인)
DATABASE_URL 없이 스키마 변경 시 수동 SQL 파일 생성:
```
web_saas/prisma/migrations/YYYYMMDDHHMMSS_<name>/migration.sql
```
`npx prisma migrate dev --create-only`는 DATABASE_URL 필요 → 없으면 파일 직접 생성.
`npx prisma generate`는 DATABASE_URL 없이도 가능.

### 프론트엔드 제약
- 기존 Tailwind 클래스 재사용, 신규 className 최소화
- JSX 다중 형제 조건부 렌더링: `{condition && (<>...</>)}` Fragment 필수
- `useConversationFlow.ts`의 FSM 전환 순서 보존 필수
- `ChatContext.tsx` dispatch 기반 상태 관리 — 직접 state 변경 금지

### 나라장터 API 제약
- `DATA_GO_KR_API_KEY`로 검색(5개 카테고리 엔드포인트) + 첨부파일 조회 정상 동작
- 첨부파일 API(`getBidPblancListInfoEorderAtchFileInfo`)는 **`inqryDiv=2` (공고번호 기준) 필수** — 누락 시 404
- 모든 공고에 e발주 첨부파일이 있는 건 아님 — 없으면 수동 업로드 폴백 UI 제공
- 첨부파일 다운로드 URL은 g2b.go.kr 도메인 (로그인 불필요, 직접 다운로드 가능)
- g2b.go.kr 공고 페이지 링크 클릭 시 나라장터 로그인 필요 (SSO 리다이렉트)

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
| `DATA_GO_KR_API_KEY` | 나라장터 공공데이터포털 API 키 (레거시 공고 검색) |

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
| `test_knowledge_models.py` | `knowledge_models.py` 데이터 모델 |
| `test_knowledge_db.py` | `knowledge_db.py` ChromaDB wrapper |
| `test_knowledge_harvester.py` | `knowledge_harvester.py` Pass 1 |
| `test_knowledge_dedup.py` | `knowledge_dedup.py` Pass 2 |
| `test_proposal_planner.py` | `proposal_planner.py` 아웃라인 |
| `test_section_writer.py` | `section_writer.py` 섹션 생성 |
| `test_quality_checker.py` | `quality_checker.py` 블라인드/모호 |
| `test_document_assembler.py` | `document_assembler.py` DOCX |
| `test_proposal_orchestrator.py` | `proposal_orchestrator.py` 오케스트레이터 |
| `test_proposal_api.py` | `main.py` v2 API 엔드포인트 |
| `test_company_db.py` | `company_db.py` 회사 역량 DB |
| `test_company_analyzer.py` | `company_analyzer.py` 문체 분석 |
| `test_checklist_extractor.py` | `checklist_extractor.py` 체크리스트 |
| `test_diff_tracker.py` | `diff_tracker.py` diff 추출 |
| `test_auto_learner.py` | `auto_learner.py` 자동 학습 |
| `test_track_record_writer.py` | `track_record_writer.py` 실적/인력 매칭 |
| `test_track_record_assembler.py` | `track_record_assembler.py` DOCX 조립 |
| `test_track_record_orchestrator.py` | `track_record_orchestrator.py` 파이프라인 |
| `test_wbs_planner.py` | `wbs_planner.py` WBS 계획 |
| `test_wbs_generator.py` | `wbs_generator.py` XLSX/간트/DOCX |
| `test_wbs_orchestrator.py` | `wbs_orchestrator.py` WBS 파이프라인 |
| `test_ppt_slide_planner.py` | `ppt_slide_planner.py` 슬라이드 구성 |
| `test_ppt_content_extractor.py` | `ppt_content_extractor.py` 콘텐츠 추출 |
| `test_ppt_assembler.py` | `ppt_assembler.py` PPTX 조립 |
| `test_ppt_orchestrator.py` | `ppt_orchestrator.py` PPT 파이프라인 |
| `test_phase2_api.py` | `main.py` Phase 2 API 엔드포인트 |

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

## 기능 구현 현황 (2026-02-27)

### 동작 중 (레거시 백엔드 + Chat UI)
| 기능 | 상태 | 비고 |
|------|------|------|
| 나라장터 공고 검색 | **동작** | 키워드, 업무구분, 기간, 지역, 금액 필터 |
| 문서 업로드 분석 | **동작** | PDF/DOCX/HWP/Excel/PPT (회사문서 없이도 분석 가능), 병렬 처리 |
| 자격요건 추출 (rfx_analyzer) | **동작** | 멀티패스 병렬 청크 추출 + 동의어 사전 프롬프트 주입 |
| RFP 요약 (3섹션 마크다운) | **동작** | 사업개요/핵심요건/평가기준 GFM 마크다운 (react-markdown + remark-gfm) |
| GO/NO-GO 판단 (matcher) | **동작** | 회사문서 등록 시에만 매칭, 요건 병렬 매칭 |
| 분석 결과 2탭 UI | **동작** | "RFP 요약" + "GO/NO-GO 분석" 탭 전환 |
| 문서 기반 Q&A 채팅 | **동작** | RAG 하이브리드 검색 + 참조 페이지 표시 |
| 일괄 공고 평가 | **동작** | 동시 3건 병렬 처리 (asyncio.Semaphore) |
| 검색 결과 CSV 다운로드 | **동작** | 클라이언트 사이드 생성 |
| 컨텍스트 패널 (문서 미리보기) | **동작** | PDF iframe + 탭(분석문서/회사문서) + 하이라이트 |
| 대화 이름 변경/삭제 | **동작** | Sidebar 인라인 편집 |
| 리사이즈 가능 컨텍스트 패널 | **동작** | 드래그로 280~600px 조절 |
| LLM retry + timeout | **동작** | call_with_retry 60초 timeout + 2회 재시도 |
| 공고 첨부파일 자동 다운로드+분석 | **동작** | e발주 첨부파일 자동 다운로드 → 파싱 → GO/NO-GO 분석 |

### A-lite 제안서 파이프라인 (Phase 1 — 2026-02-27 구현, 02-28 E2E 검증 통과)
| 기능 | 상태 | 비고 |
|------|------|------|
| A-lite 제안서 DOCX 생성 | **동작** | Layer 1+2 지식 기반, `/api/generate-proposal-v2`, E2E 검증 통과 |
| Layer 1 지식 파이프라인 | **동작** | harvester(Pass1)+dedup(Pass2)+ChromaDB. 495유닛 탑재 완료 |
| Layer 2 회사 맞춤 학습 | **코드 완성** | company_db + company_analyzer + section_writer 통합 |
| 수정 diff 학습 루프 | **동작** | diff_tracker + auto_learner (1회=기록, 3회+=자동반영) + 영속성(lifespan) |
| 제출 체크리스트 | **동작** | `/api/checklist` + ChecklistView.tsx 프론트엔드 UI 완성 |
| 품질 검증 (quality_checker) | **동작** | 블라인드 위반(한글 조사 인식) + 모호 표현 감지 |
| Pydantic 입력 검증 | **동작** | RfxResultInput 스키마, title 필수, total_pages 10~200 |

### Phase 2: 수행계획서/WBS + PPT + 실적기술서 (2026-02-27 구현, 02-28 E2E 검증 통과)
| 기능 | 상태 | 비고 |
|------|------|------|
| 수행계획서/WBS XLSX+간트차트+DOCX | **동작** | `/api/generate-wbs`, 방법론 LLM감지, Layer1 지식주입, E2E 통과 |
| PPT 발표자료 PPTX+QnA | **동작** | `/api/generate-ppt`, LLM 콘텐츠 생성, 예상질문 10개, E2E 통과 |
| 실적/경력 기술서 DOCX | **동작** | `/api/generate-track-record`, CompanyDB 매칭, Layer1 강화 |
| 프론트엔드 UI 버튼 + 다운로드 | **동작** | AnalysisResultView 5개 버튼 + 채팅 다운로드 링크 |
| 백엔드 프록시 | **동작** | web_app에 3개 프록시 엔드포인트 |
| 다운로드 확장 | **동작** | DOCX/XLSX/PPTX/PNG MIME 타입 지원 |

### 사용자 알림 설정 (2026-02-27 구현 완료)
| 기능 | 상태 | 비고 |
|------|------|------|
| 독립 알림 설정 페이지 | **동작** | /alerts 라우트, 영구 파일 저장 |
| 확장 필터 (물품분류번호, 세부품명) | **동작** | 메타데이터 기반 1차 필터 |
| 제외 지역 필터 | **동작** | excludeRegions 필드 |
| 회사 프로필 자연어 입력 | **UI 완성** | LLM 파싱은 Pro 버전 (미구현) |
| 알림 설정 API | **동작** | GET/POST /api/alerts/config |
| 레거시 마이그레이션 | **스크립트 완성** | scripts/migrate_legacy_alerts.py |

### 미구현 / 제한
| 기능 | 상태 | 비고 |
|------|------|------|
| 회사 DB 온보딩 UI | **미구현** | API 완성, 실적/인력 입력 화면 필요 |
| 회사 스타일 분석 연결 | **미구현** | company_analyzer.analyze_company_style() 구현됨, 파이프라인 미연결 |
| PPT/WBS 회사 맞춤화 | **미구현** | CompanyDB 통합 안 됨 (track_record만 연결) |
| Layer 3 승패 분석 | **미구현** | Phase 3 |
| 관심 공고 자동 알림 | **미구현** | SaaS n8n 워크플로우로만 가능 |
| 엑셀 평가 리포트 다운로드 | **SaaS only** | web_saas의 buildEvaluationExcel, 레거시 미연동 |
| 강점 카드 | **SaaS only** | web_saas의 buildStrengthCard |
| 의견 모드 UI 선택기 | **미구현** | 타입/로직 존재, UI 컴포넌트 미구현 |

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
