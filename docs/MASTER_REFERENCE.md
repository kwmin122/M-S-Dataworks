# Kira Bot - 마스터 레퍼런스 문서

> 📅 최종 업데이트: 2026-03-03
>
> 공공조달 입찰 전 과정 자동화 AI 플랫폼의 모든 기능, 플로우, 변수, 아키텍처를 한 곳에 정리

---

## 📋 목차

1. [프로젝트 개요](#프로젝트-개요)
2. [핵심 비즈니스 플로우](#핵심-비즈니스-플로우)
3. [전체 아키텍처](#전체-아키텍처)
4. [기능 현황](#기능-현황)
5. [사용자 플로우](#사용자-플로우)
6. [환경 변수](#환경-변수)
7. [API 엔드포인트](#api-엔드포인트)
8. [데이터베이스](#데이터베이스)
9. [파이프라인](#파이프라인)
10. [핵심 설계 결정](#핵심-설계-결정)
11. [테스트 커버리지](#테스트-커버리지)
12. [배포 및 운영](#배포-및-운영)

---

## 프로젝트 개요

### 미션
**공공조달 입찰 라이프사이클 완전 자동화**

```
공고 발견 → RFP 분석 → GO/NO-GO 판단 → 제안서 자동 생성
→ 체크리스트 → 사용자 수정 → 학습 → 다음 생성에 반영
```

### 비전
- **Layer 1**: 범용 입찰 지식 (495 유닛, ChromaDB)
- **Layer 2**: 회사 맞춤 학습 (실적, 인력, 문체, 과거 제안서)
- **Layer 3**: 승패 분석 (미구현, Phase 3)

### 현재 상태
- **레거시 Chat UI** (React + FastAPI) - 활성
- **멀티테넌트 B2B SaaS** (Next.js + Prisma + n8n) - Phase 1-8 완료
- **A-lite 제안서 파이프라인** (Phase 1) - 구현 완료, E2E 검증 통과
- **Phase 2 모듈** (WBS, PPT, 실적기술서) - 구현 완료, E2E 검증 통과

---

## 핵심 비즈니스 플로우

### 1️⃣ 공고 검색 및 발견
```
사용자 검색 (키워드/필터)
  ↓
나라장터 API 호출 (5개 카테고리)
  ↓
공고 카드 리스트 렌더링 (bid_card_list)
  ↓
공고 선택 → 자동 첨부파일 다운로드 (e발주)
```

### 2️⃣ RFP 분석
```
RFP 업로드 (PDF/DOCX/HWP/HWPX/Excel/PPT)
  ↓
document_parser.py → 청킹
  ↓
rfx_analyzer.py (멀티패스 병렬 처리)
  ├─ Pass 1: 청크별 자격요건 추출 (ThreadPoolExecutor, max 4)
  ├─ Pass 2: 병합 및 중복 제거
  └─ generate_rfp_summary() → 3섹션 마크다운 (사업개요/핵심요건/평가기준)
  ↓
RFxAnalysisResult 반환 (requirements + rfp_summary)
```

### 3️⃣ GO/NO-GO 판단
```
회사 문서 업로드 (선택, 없어도 분석 가능)
  ↓
matcher.py
  ├─ ConstraintEvaluator: 결정론 비교 우선 (금액, 지역, 면허 등)
  ├─ FALLBACK_NEEDED → LLM 판단 (ThreadPoolExecutor 병렬 매칭, max 6)
  └─ CompanyFactNormalizer: 회사 데이터 정규화
  ↓
MatchResult 반환 (can_participate + reasons)
```

### 4️⃣ 제안서 생성 (A-lite, Phase 1)
```
/api/generate-proposal-v2 호출
  ↓
proposal_orchestrator.py (ThreadPoolExecutor)
  ├─ Pass 1: knowledge_harvester (7카테고리 지식 추출)
  ├─ Pass 2: knowledge_dedup (충돌 해소)
  ├─ Layer 1 검색: knowledge_db.search_knowledge()
  ├─ Layer 2 주입: company_context_builder.build_context()
  ├─ proposal_planner: 섹션 아웃라인 (배점 비례 페이지 분배)
  ├─ section_writer: 섹션별 LLM 생성 (병렬 처리)
  ├─ quality_checker: 블라인드 위반 + 모호 표현 감지
  └─ document_assembler: mistune 3.x AST → DOCX
  ↓
DOCX 파일 반환 + data/proposals/ 저장
```

### 5️⃣ 수정 학습 루프
```
사용자 DOCX 수정
  ↓
/api/edit-feedback 호출 (원본 AI 버전 + 수정 버전)
  ↓
diff_tracker.py: AI vs 사용자 diff 추출 (패턴 해싱)
  ↓
auto_learner.py
  ├─ 1회 발생: learning_patterns에 기록
  ├─ 3회+ 반복: Layer 2 자동 반영 (threading.Lock 보호)
  └─ 영속성: main.py lifespan load/save
  ↓
다음 section_writer 호출 시 학습된 패턴 반영
```

### 6️⃣ Phase 2 문서 생성
```
WBS 생성:
  /api/generate-wbs → wbs_orchestrator
  → wbs_planner (방법론 LLM 감지 + Layer 1)
  → wbs_generator (openpyxl XLSX + matplotlib 간트차트 + DOCX)

PPT 생성:
  /api/generate-ppt → ppt_orchestrator
  → ppt_slide_planner (구성 + 예상질문 10개)
  → ppt_content_extractor (제안서→슬라이드 콘텐츠)
  → ppt_assembler (python-pptx PPTX, KRDS 디자인 토큰)

실적기술서:
  /api/generate-track-record → track_record_orchestrator
  → track_record_writer (CompanyDB 매칭 + Layer 1 강화)
  → track_record_assembler (DOCX, 표+서술)
```

---

## 전체 아키텍처

### 레거시 스택 (현재 활성)
```
frontend/kirabot/                   ← React 19 + Vite + TypeScript
  App.tsx                           ← AppView FSM (landing ↔ chat)
  components/chat/ChatLayout.tsx    ← Sidebar + ChatArea + ContextPanel
  context/ChatContext.tsx           ← useReducer 대화 상태 관리
  hooks/useConversationFlow.ts      ← 대화 FSM + 모든 액션 핸들러
  services/kiraApiService.ts        ← API 클라이언트

        ↓ HTTP (port 8000)

services/web_app/main.py            ← FastAPI (업로드, 세션, 채팅, 분석, 검색, 평가)
  ├─ engine.py                      ← ChromaDB + BM25 하이브리드 (Lock 보호)
  ├─ rfx_analyzer.py                ← 멀티패스 자격요건 추출 + RFP 요약
  ├─ matcher.py                     ← 결정론 + LLM GO/NO-GO (병렬)
  ├─ chat_router.py                 ← 인텐트 분류 + 오프토픽 차단
  ├─ document_parser.py             ← PDF/DOCX/HWP/Excel/PPT 파싱
  ├─ nara_api.py                    ← 나라장터 Open API 클라이언트
  └─ llm_utils.py                   ← call_with_retry (60초 timeout)

        ↓ 프록시 (port 8001)

rag_engine/main.py                  ← FastAPI (A-lite + Phase 2)
  ├─ proposal_orchestrator.py       ← 제안서 파이프라인 (Phase 1)
  ├─ knowledge_db.py                ← ChromaDB proposal_knowledge (495 유닛)
  ├─ company_db.py                  ← 회사 역량 DB (실적/인력 ChromaDB)
  ├─ company_context_builder.py     ← Layer 2 통합 빌더
  ├─ wbs_orchestrator.py            ← WBS 파이프라인 (Phase 2)
  ├─ ppt_orchestrator.py            ← PPT 파이프라인 (Phase 2)
  └─ track_record_orchestrator.py   ← 실적기술서 파이프라인 (Phase 2)

data/
  ├─ vectordb/                      ← ChromaDB 영구 저장소
  ├─ knowledge_db/                  ← Layer 1 proposal_knowledge
  ├─ company_db/                    ← Layer 2 회사 역량 DB
  ├─ web_uploads/                   ← 세션별 업로드 (company/ + target/)
  ├─ proposals/                     ← 생성된 제안서 출력
  └─ user_store/                    ← 세션 + 사용량 JSON
```

### SaaS 스택 (Phase 1-8)
```
web_saas/                           ← Next.js 16 + Prisma 5 + TypeScript
  src/middleware.ts                 ← NextAuth 보호 + CSRF 검증
  src/auth.ts                       ← NextAuth v5 Credentials
  src/lib/
    ├─ env.ts                       ← zod 부팅 검증 (필수 env 누락 시 throw)
    ├─ prisma.ts                    ← PrismaClient 싱글턴
    ├─ hmac.ts                      ← HMAC-SHA256 웹훅 검증
    ├─ internal-auth.ts             ← 내부 API HMAC (nonce 재사용 방지)
    ├─ safe-fetch.ts                ← SSRF 방어 (https, DNS, redirect:manual)
    ├─ csrf.ts                      ← Origin allowlist
    ├─ quota/consumeQuota.ts        ← $transaction 원자 쿼터 차감
    ├─ jobs/createEvaluationJobs.ts ← interestConfig 필터
    ├─ search/buildSearchQuery.ts   ← Prisma where 조건
    ├─ search/ftsSearch.ts          ← PostgreSQL FTS (plainto_tsquery)
    ├─ export/buildEvaluationExcel.ts ← ExcelJS xlsx
    └─ strengthCard/buildStrengthCard.ts ← 강점 카드

  src/app/api/
    ├─ webhooks/n8n/                ← HMAC 웹훅 (리플레이 방지)
    ├─ internal/process-ingestion-job/ ← HMAC + safeFetch + $transaction
    ├─ internal/process-evaluation-job/ ← HMAC + 쿼터차감 + FastAPI + Resend
    ├─ search/bids/                 ← FTS 또는 Prisma 필터
    ├─ evaluate/batch/              ← 다중 공고 EvaluationJob 생성
    ├─ export/evaluations/          ← xlsx 다운로드
    ├─ proposals/                   ← ProposalDraft 생성
    └─ strength-card/[bidNoticeId]/ ← 강점 카드 (params: Promise<>)

        ↓ PostgreSQL (Docker, PGTZ=UTC)

n8n/workflows/                      ← 4종 워크플로우 JSON
  ├─ g2b_bid_crawler.json           ← 나라장터 → BidNotice/IngestionJob
  ├─ ingestion_worker.json          ← process-ingestion-job 호출
  ├─ evaluation_worker.json         ← process-evaluation-job 호출
  └─ stale_lock_reclaim.json        ← 만료 락 해제
```

---

## 기능 현황

### ✅ 동작 중 (레거시 Chat UI)

| 기능 | 모듈 | 비고 |
|------|------|------|
| 나라장터 공고 검색 | `nara_api.py` | 5개 카테고리, 키워드/필터 |
| e발주 첨부파일 자동 다운로드 | `nara_api.py` | `inqryDiv=2` 필수 |
| 문서 업로드 분석 | `document_parser.py` | PDF/DOCX/HWP/HWPX/Excel/PPT |
| 자격요건 추출 | `rfx_analyzer.py` | 멀티패스 병렬 (max 4 청크) |
| RFP 요약 (3섹션 GFM) | `rfx_analyzer.py` | 사업개요/핵심요건/평가기준 |
| GO/NO-GO 판단 | `matcher.py` | 결정론 우선 + LLM 병렬 (max 6) |
| 분석 결과 2탭 UI | `AnalysisResultView.tsx` | RFP 요약 + GO/NO-GO 분석 |
| 문서 기반 Q&A | `chat_router.py` + `engine.py` | RAG 하이브리드 + 참조 페이지 |
| 일괄 공고 평가 | `main.py` `/evaluate/bulk` | `asyncio.Semaphore(3)` 병렬 |
| 검색 결과 CSV 다운로드 | `BidSearchResults.tsx` | 클라이언트 사이드 생성 |
| 컨텍스트 패널 (문서 미리보기) | `DocumentViewer.tsx` | PDF iframe + 탭 + 하이라이트 |
| 대화 이름 변경/삭제 | `Sidebar.tsx` | 인라인 편집 |
| 리사이즈 가능 패널 | `ChatLayout.tsx` | 280~600px 드래그 |

### ✅ A-lite 제안서 (Phase 1, 2026-02-28 E2E 검증)

| 기능 | 모듈 | 비고 |
|------|------|------|
| 제안서 DOCX 생성 | `proposal_orchestrator.py` | Layer 1+2, mistune 3.x AST |
| Layer 1 지식 파이프라인 | `knowledge_harvester.py` + `knowledge_dedup.py` | 495 유닛 탑재 완료 |
| Layer 2 회사 맞춤 학습 | `company_context_builder.py` | 실적/인력/문체 통합 |
| 수정 diff 학습 루프 | `diff_tracker.py` + `auto_learner.py` | 3회+ 자동반영, lifespan 영속성 |
| 제출 체크리스트 | `checklist_extractor.py` | RFP → 서류 목록 |
| 품질 검증 | `quality_checker.py` | 블라인드(한글 조사) + 모호 표현 |
| Pydantic 입력 검증 | `RfxResultInput` | title 필수, total_pages 10~200 |
| 프론트엔드 UI | `AnalysisResultView.tsx` | 5개 버튼 + 채팅 다운로드 링크 |

### ✅ Phase 2 모듈 (2026-02-28 E2E 검증)

| 기능 | 모듈 | 비고 |
|------|------|------|
| WBS XLSX+간트+DOCX | `wbs_orchestrator.py` | 방법론 LLM감지, Layer 1, openpyxl |
| PPT PPTX+QnA | `ppt_orchestrator.py` | KRDS 디자인, 예상질문 10개 |
| 실적기술서 DOCX | `track_record_orchestrator.py` | CompanyDB 매칭, 표+서술 |
| 백엔드 프록시 | `web_app/main.py` | 3개 프록시 엔드포인트 |
| 다운로드 확장 | `kiraApiService.ts` | DOCX/XLSX/PPTX/PNG |

### ✅ 사용자 알림 설정 (2026-02-27)

| 기능 | 모듈 | 비고 |
|------|------|------|
| 독립 알림 설정 페이지 | `/alerts` | 영구 파일 저장 |
| 확장 필터 | `AlertsPage.tsx` | 물품분류번호, 세부품명, 제외지역 |
| 회사 프로필 자연어 | `AlertsPage.tsx` | UI 완성, LLM 파싱 미구현 |
| 알림 설정 API | `/api/alerts/config` | GET/POST |

### 🚧 미구현 / 제한

| 기능 | 상태 | 비고 |
|------|------|------|
| 회사 DB 온보딩 UI | API 완성 | 실적/인력 입력 화면 필요 |
| 회사 스타일 분석 연결 | `company_analyzer.py` 완성 | 파이프라인 미연결 (orphaned) |
| PPT/WBS 회사 맞춤화 | 미구현 | CompanyDB 통합 안 됨 (track_record만 연결) |
| Layer 3 승패 분석 | 미구현 | Phase 3 |
| 관심 공고 자동 알림 | 레거시 미구현 | SaaS n8n만 가능 |
| 엑셀 평가 리포트 | SaaS only | `buildEvaluationExcel` |
| 강점 카드 | SaaS only | `buildStrengthCard` |
| 의견 모드 UI 선택기 | 타입 존재 | UI 컴포넌트 미구현 |

---

## 사용자 플로우

### Chat UI 대화 FSM

```typescript
ConversationPhase:
  greeting                  // 초기 인사
    → bid_search_input      // 공고 검색 입력
    → bid_search_results    // 공고 검색 결과
    → bid_analyzing         // 공고 분석 중
    → doc_chat              // 대화

  greeting
    → doc_upload_company    // 회사 문서 업로드
    → doc_upload_target     // RFP 문서 업로드
    → doc_analyzing         // 문서 분석 중
    → doc_chat              // 대화

  bid_search_results
    → bid_eval_running      // 일괄 평가 실행 중
    → bid_eval_results      // 일괄 평가 결과
```

### 메시지 타입

| 타입 | 용도 | 예시 |
|------|------|------|
| `text` | 일반 텍스트 | AI 답변, 사용자 입력 |
| `button_choice` | 선택 버튼 | "공고 검색" / "문서 분석" |
| `bid_card_list` | 공고 카드 목록 | 검색 결과 리스트 |
| `analysis_result` | 분석 결과 2탭 | RFP 요약 + GO/NO-GO |
| `inline_form` | 인라인 폼 | 검색 조건 입력 |
| `file_upload` | 파일 업로드 UI | 드래그앤드롭 |
| `status` | 상태 메시지 | "분석 중...", "완료!" |

### SaaS 데이터 흐름

```
n8n g2b_bid_crawler (30분 주기)
  ↓
BidNotice UPSERT + IngestionJob INSERT (ON CONFLICT DO NOTHING)
  ↓
n8n ingestion_worker
  ↓
/api/internal/process-ingestion-job
  - HMAC 검증
  - safeFetch 다운로드
  - contentHash 중복 방지
  - $transaction COMPLETED
  ↓
createEvaluationJobsForBidNotice (interestConfig 매칭)
  ↓
n8n evaluation_worker
  ↓
/api/internal/process-evaluation-job
  - HMAC 검증
  - HMAC 락 획득 (UPDATE WHERE locked_at IS NULL)
  - consumeQuotaIfNeeded($tx) 원자 차감
  - FastAPI /api/analyze-bid 호출
  - SCORED 저장
  - Resend 이메일 발송
```

---

## 환경 변수

### 공통 (레거시 + rag_engine)

```bash
# LLM & Embeddings
OPENAI_API_KEY=sk-...
OPENAI_STRICT_JSON_ONLY=1              # Structured Outputs 전용

# RAG
RAG_HYBRID_ENABLED=1                   # BM25 + 벡터 하이브리드

# 나라장터 API
DATA_GO_KR_API_KEY=...                 # 공공데이터포털 API 키
```

### SaaS (web_saas)

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/db?schema=public

# NextAuth
NEXTAUTH_SECRET=...                    # ≥32자, JWT 서명
NEXTAUTH_URL=http://localhost:3000

# CSRF
NEXT_PUBLIC_APP_URL=http://localhost:3000

# HMAC
WEBHOOK_SECRET=...                     # ≥32자, n8n↔Next.js
INTERNAL_API_SECRET=...                # ≥32자, /api/internal/*

# Stripe
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# FastAPI
FASTAPI_URL=http://localhost:8001

# SSRF 방어
ATTACHMENT_ALLOWED_DOMAINS=.go.kr      # safeFetch allowlist

# 이메일
RESEND_API_KEY=re_...
```

### 로컬 개발

```bash
# PostgreSQL (Docker)
PGTZ=UTC                               # 타임존 강제
```

---

## API 엔드포인트

### 레거시 FastAPI (port 8000)

#### 세션 관리
- `POST /api/session` - 세션 생성
- `GET /api/session/{session_id}` - 세션 조회

#### 문서 업로드
- `POST /api/upload-company` - 회사 문서 업로드
- `POST /api/upload-target` - RFP 문서 업로드

#### 분석
- `POST /api/analyze` - RFP 분석 (자격요건 + 요약 + GO/NO-GO)
- `POST /api/chat` - 대화형 Q&A

#### 공고 검색
- `POST /api/search/bids` - 나라장터 공고 검색 (5개 카테고리)
- `POST /api/bid/attachments` - e발주 첨부파일 조회 (`inqryDiv=2`)
- `POST /api/bid/analyze-with-attachments` - 첨부파일 자동 다운로드 + 분석

#### 일괄 평가
- `POST /api/evaluate/bulk` - 다중 공고 평가 (`asyncio.Semaphore(3)`)

#### 제안서 (레거시 v1, 절대 삭제 금지)
- `POST /api/proposal/generate` - 간단 초안 ({{placeholder}} 템플릿)

#### Phase 1 & 2 프록시
- `POST /api/proposal/generate-v2` - A-lite 제안서 (rag_engine 프록시)
- `POST /api/proposal/checklist` - 체크리스트 (rag_engine 프록시)
- `POST /api/proposal/generate-wbs` - WBS (rag_engine 프록시)
- `POST /api/proposal/generate-ppt` - PPT (rag_engine 프록시)
- `POST /api/proposal/generate-track-record` - 실적기술서 (rag_engine 프록시)

#### 알림 설정 (레거시)
- `GET /api/alerts/config` - 알림 설정 조회
- `POST /api/alerts/config` - 알림 설정 저장

### rag_engine FastAPI (port 8001)

#### Phase 1: A-lite 제안서
- `POST /api/generate-proposal-v2` - 제안서 생성 (ThreadPoolExecutor)
- `POST /api/checklist` - 제출 체크리스트 추출
- `POST /api/edit-feedback` - 수정 diff 학습

#### Phase 2: WBS, PPT, 실적
- `POST /api/generate-wbs` - WBS XLSX+간트+DOCX
- `POST /api/generate-ppt` - PPT PPTX + 예상질문 10개
- `POST /api/generate-track-record` - 실적/경력 기술서 DOCX

#### CompanyDB
- `POST /api/company/add-track-record` - 실적 추가
- `POST /api/company/add-personnel` - 인력 추가
- `POST /api/company/add-past-proposal` - 과거 제안서 추가
- `POST /api/company/search-track-records` - 실적 검색
- `POST /api/company/search-personnel` - 인력 검색

#### 유틸리티
- `POST /api/parse-hwp` - HWP 파싱 (magic bytes 감지)
- `POST /api/analyze-bid` - RFP 분석 (SaaS용)

### SaaS Next.js API (port 3000)

#### 인증
- `/api/auth/[...nextauth]` - NextAuth 핸들러

#### 웹훅
- `POST /api/webhooks/n8n` - n8n HMAC 웹훅 (리플레이 방지)
- `POST /api/webhooks/stripe` - Stripe SDK constructEvent

#### 내부 API (HMAC 보호)
- `POST /api/internal/process-ingestion-job` - IngestionJob 처리
- `POST /api/internal/process-evaluation-job` - EvaluationJob 처리
- `GET /api/internal/evaluation-jobs` - org 스코프 목록

#### 검색
- `POST /api/search/bids` - FTS 또는 Prisma 필터

#### 평가
- `POST /api/evaluate/batch` - 다중 공고 EvaluationJob 생성

#### 내보내기
- `GET /api/export/evaluations` - xlsx 다운로드

#### 제안서
- `POST /api/proposals` - ProposalDraft 생성

#### 강점 카드
- `GET /api/strength-card/[bidNoticeId]` - 회사 강점 vs 요건 매칭

#### 사전감지
- `GET /api/pre-bid-signals` - 사전감지 공고 목록

---

## 데이터베이스

### PostgreSQL (SaaS)

#### 주요 테이블

```prisma
model Organization {
  id            String   @id
  name          String
  users         User[]
  quotas        QuotaUsage[]
  evaluations   EvaluationResult[]
  // ...
}

model BidNotice {
  id                  String   @id
  title               String
  agency              String
  budget              Decimal?
  deadline            DateTime?
  category            String?
  content             String?  @db.Text
  rawMetadata         Json?
  ingestionJobs       IngestionJob[]
  evaluationResults   EvaluationResult[]
  // ...
}

model IngestionJob {
  id              String   @id
  bidNoticeId     String
  status          String   // PENDING, FETCHING, PARSING, COMPLETED, FAILED
  locked_at       DateTime?
  locked_by       String?
  contentHash     String?
  // ...
}

model EvaluationJob {
  id              String   @id
  organizationId  String
  bidNoticeId     String
  status          String   // PENDING, EVALUATING, SCORED, FAILED
  locked_at       DateTime?
  locked_by       String?
  quotaConsumed   Boolean  @default(false)
  // ...
}

model QuotaUsage {
  id              String   @id
  organizationId  String
  period_start    DateTime
  period_end      DateTime
  max_count       Int
  used_count      Int
  // ...
}

model UsedNonce {
  nonce     String   @id
  createdAt DateTime @default(now())
}
```

#### 인덱스 전략
- `BidNotice`: `title`, `agency`, `deadline`, `category` (FTS + 일반)
- `IngestionJob`: `bidNoticeId`, `status`, `locked_at`
- `EvaluationJob`: `organizationId`, `bidNoticeId`, `status`, `locked_at`
- `QuotaUsage`: `organizationId`, `period_start`, `period_end`

### ChromaDB (레거시)

#### `data/vectordb/` (문서 Q&A)
- Collection: `company_docs`, `target_docs`
- 임베딩: OpenAI `text-embedding-3-small`
- 메타데이터: `session_id`, `source`, `page_number`

#### `data/knowledge_db/` (Layer 1)
- Collection: `proposal_knowledge`
- 495 유닛 (블로그 47 + 유튜브 40 + 공식문서 18)
- ID: `{source_type}_{sha256(source_type:category:rule)[:12]}`
- 카테고리: `technical_approach`, `methodology`, `risk_management`, `quality_assurance`, `project_management`, `team_composition`, `past_experience`

#### `data/company_db/` (Layer 2)
- Collection: `track_records`, `personnel`
- 실적: `project_name`, `client`, `budget`, `period`, `role`, `description`
- 인력: `name`, `role`, `years_experience`, `certifications`, `skills`, `education`

---

## 파이프라인

### RFP 분석 파이프라인 (rfx_analyzer.py)

```python
# 입력: PDF/DOCX/HWP 등
# 출력: RFxAnalysisResult (requirements + rfp_summary)

1. document_parser.py
   - PDF/DOCX/HWP/Excel/PPT 파싱
   - 청킹 (페이지 단위 또는 semantic chunking)

2. Pass 1: 청크별 자격요건 추출 (병렬)
   - ThreadPoolExecutor (max_workers=4)
   - 각 청크에서 필수/우대/제외 조건 추출
   - rfp_synonyms.py 동의어 프롬프트 주입

3. Pass 2: 병합 및 중복 제거
   - 동일 조건 merge
   - confidence 점수 기반 우선순위

4. RFP 요약 생성 (병렬)
   - generate_rfp_summary() GFM 마크다운
   - 3섹션: 사업개요 / 핵심요건 / 평가기준
   - asyncio.gather() 동시 실행

5. 반환
   - RFxAnalysisResult(requirements, rfp_summary)
```

### GO/NO-GO 파이프라인 (matcher.py)

```python
# 입력: RFxAnalysisResult + 회사 문서
# 출력: MatchResult (can_participate + reasons)

1. CompanyFactNormalizer
   - 회사 데이터 정규화 (금액, 면허, 지역 등)

2. ConstraintEvaluator (결정론 우선)
   - contract_amount: min/max 범위 체크
   - location: 거리 계산 (geopy Nominatim)
   - business_license: 문자열 매칭
   - consortium: 지분율 계산
   - 결과: PASS / FAIL / FALLBACK_NEEDED

3. LLM 판단 (FALLBACK_NEEDED만)
   - ThreadPoolExecutor (max_workers=6) 병렬 매칭
   - 각 요건별 독립 판단
   - call_with_retry (60초 timeout)

4. 통합 판단
   - 1개라도 FAIL → can_participate=False
   - 모두 PASS → can_participate=True
```

### A-lite 제안서 파이프라인 (proposal_orchestrator.py)

```python
# 입력: RfxResultInput (Pydantic)
# 출력: DOCX 파일

1. Pydantic 입력 검증
   - RfxResultInput: title 필수, total_pages 10~200

2. Pass 1: 지식 추출 (병렬)
   - knowledge_harvester.harvest_from_rfp()
   - 7 카테고리, ThreadPoolExecutor

3. Pass 2: 충돌 해소
   - knowledge_dedup.deduplicate_knowledge_units()
   - LLM AGREE/CONDITIONAL/CONFLICT 판단

4. Layer 1 검색
   - knowledge_db.search_knowledge()
   - 카테고리별 top-k 검색

5. Layer 2 주입
   - company_context_builder.build_context()
   - 실적/인력/문체/과거제안서 통합

6. 아웃라인 생성
   - proposal_planner.plan_proposal_outline()
   - 배점 비례 페이지 분배

7. 섹션별 생성 (병렬)
   - section_writer.write_section()
   - Layer 1+2 지식 주입, ThreadPoolExecutor

8. 품질 검증
   - quality_checker.check_quality()
   - 블라인드 위반 (한글 조사 정규식)
   - 모호 표현 감지

9. DOCX 조립
   - document_assembler.assemble_docx()
   - mistune 3.x AST → python-docx

10. 반환
    - DOCX 파일 + data/proposals/ 저장
```

### 수정 학습 파이프라인 (diff_tracker + auto_learner)

```python
# 입력: 원본 AI DOCX + 수정 사용자 DOCX
# 출력: learning_patterns 업데이트

1. diff_tracker.extract_diffs()
   - python-docx로 양쪽 읽기
   - 단락별 diff 추출
   - 패턴 키 해싱 (context_category + modification_type)

2. auto_learner.process_learning_pattern()
   - threading.Lock 보호 (전역 dict)
   - 1회 발생: learning_patterns에 기록
   - 3회+ 반복: Layer 2 자동 반영

3. 영속성 (main.py lifespan)
   - startup: data/learning_patterns.json 로드
   - shutdown: 저장

4. 다음 section_writer 호출 시
   - auto_learner.get_active_patterns(category)
   - 프롬프트에 주입
```

### Phase 2 파이프라인 (WBS, PPT, 실적)

#### WBS (wbs_orchestrator.py)
```python
1. wbs_planner.plan_wbs()
   - 방법론 LLM 자동 감지 (Agile/Waterfall/PMBOK)
   - Layer 1 방법론 지식 검색
   - WBS 태스크 생성

2. wbs_generator.generate_wbs_excel()
   - openpyxl XLSX 생성
   - matplotlib 간트차트 PNG

3. wbs_generator.generate_wbs_docx()
   - python-docx DOCX 조립
   - 표 + 간트차트 이미지 삽입

4. 반환: XLSX + DOCX
```

#### PPT (ppt_orchestrator.py)
```python
1. ppt_slide_planner.plan_slides()
   - 슬라이드 구성 (제목/목차/콘텐츠/데이터/마무리/간지)
   - 예상질문 10개 생성

2. ppt_content_extractor.extract_content()
   - 제안서 DOCX → 슬라이드 콘텐츠 추출
   - 섹션별 핵심 요약

3. ppt_assembler.assemble_ppt()
   - python-pptx PPTX 생성
   - KRDS 디자인 토큰 적용 (Blue 900, Pretendard, 16:9)

4. 반환: PPTX + QnA JSON
```

#### 실적기술서 (track_record_orchestrator.py)
```python
1. track_record_writer.write_track_record_section()
   - CompanyDB 실적/인력 매칭
   - Layer 1 지식 강화
   - LLM 서술 생성

2. track_record_assembler.assemble_track_record_docx()
   - python-docx DOCX
   - 표 + 서술 혼합 레이아웃

3. 반환: DOCX
```

---

## 핵심 설계 결정

### 보안

#### 1. HMAC 웹훅 / 내부 API
- 서명 문자열: `${ts}.${nonce}.${rawBody}`
- Nonce 중복 방지: `UsedNonce.create()` create-only + P2002 catch
- `request.text()` 먼저 → HMAC 검증 → `JSON.parse()`
- **절대 금지**: `request.json()` 직접 호출 (바디 소비)

#### 2. SSRF 방어 (safe-fetch.ts)
- https only (http 차단)
- DNS 사전 해석 (private IP 차단: 10.x, 172.16.x, 192.168.x, 127.x)
- `redirect: 'manual'` (리다이렉트 수동 처리)
- 10초 타임아웃
- `allowedDomains` 화이트리스트 (예: `.go.kr`)

#### 3. CSRF (csrf.ts)
- POST/PUT/PATCH/DELETE만 검증
- Origin 헤더 allowlist (`NEXT_PUBLIC_APP_URL`)
- GET/HEAD/OPTIONS 허용

#### 4. IDOR 방어
- 모든 사용자 API에서 `organizationId` 입력 제거
- `getServerSession()` → `session.user.organizationId` 주입
- Prisma where 조건에 자동 포함

#### 5. env.ts (zod 검증)
- 필수 환경 변수 누락 시 부팅 차단
- `process.env.*` 직접 접근 금지
- `getEnv()` 함수로 통합 접근

### 동시성 및 트랜잭션

#### 1. 락 획득 (SaaS 잡 시스템)
```sql
UPDATE IngestionJob
SET locked_at = NOW(), locked_by = :workerId
WHERE id = :jobId AND locked_at IS NULL
```
- **절대 금지**: `FOR UPDATE SKIP LOCKED` (다른 트랜잭션 차단)
- affected rows 검사로 락 획득 확인

#### 2. 쿼터 차감 (consumeQuota.ts)
```typescript
await prisma.$transaction(async (tx) => {
  const result = await tx.quotaUsage.updateMany({
    where: {
      organizationId,
      period_start: { lte: now },
      period_end: { gte: now },
      used_count: { lt: tx.quotaUsage.fields.max_count }
    },
    data: { used_count: { increment: 1 } }
  });
  if (result.count === 0) throw new QuotaExceededError();
});
```
- `$transaction` 내 원자 실행
- `quotaConsumed=true`로 재시도 중복 차감 방지

#### 3. BM25 Lock (engine.py)
```python
bm25_lock = threading.Lock()

with bm25_lock:
    bm25.fit(corpus)
```
- 전역 `threading.Lock()`으로 BM25 rebuild 보호
- 벡터 검색은 스레드 안전 (ChromaDB)

#### 4. auto_learner Lock (auto_learner.py)
```python
learning_lock = threading.Lock()

with learning_lock:
    learning_patterns[pattern_key] = ...
```
- 전역 dict 보호
- lifespan load/save로 영속성

### ID 생성 및 타임존

#### 1. ID 생성
- **앱 레벨**: `createId()` (cuid2) - 충돌 방지, 정렬 가능
- **절대 금지**: `gen_random_uuid()` (DB 레벨) - 앱 로직 의존성 증가

#### 2. 타임존
- **PostgreSQL**: `PGTZ=UTC` 강제
- **JavaScript**: `Date.UTC()` 사용
- **절대 금지**: `new Date(year, month, 1)` (로컬 타임존)

### LLM 안정성

#### call_with_retry (llm_utils.py)
```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((
        openai.RateLimitError,
        openai.APIError,
        openai.APIConnectionError
    ))
)
def call_with_retry(func, *args, timeout=60, **kwargs):
    with timeout_context(timeout):
        return func(*args, **kwargs)
```
- 60초 timeout (기본)
- 2회 재시도 (429/500/502/503)
- 지수 백오프 (2초 → 4초 → 8초)

### RAG 파이프라인

#### 1. 하이브리드 검색 (engine.py)
```python
if RAG_HYBRID_ENABLED:
    vector_results = chroma_collection.query(...)
    bm25_results = bm25.get_top_n(query, corpus, n=top_k)
    results = rrf_fusion(vector_results, bm25_results)
else:
    results = chroma_collection.query(...)
```
- RRF (Reciprocal Rank Fusion) 점수 결합
- BM25 rebuild는 Lock 보호

#### 2. 동의어 사전 (rfp_synonyms.py)
```python
SYNONYM_CATEGORIES = {
    "budget": ["사업비", "예산", "추정가격", "총사업비", "계약금액"],
    "period": ["사업기간", "계약기간", "수행기간", "착수일", "완료일"],
    # ... 17개 카테고리
}
```
- 자격요건 추출 프롬프트에 주입
- LLM이 다양한 표현 인식

### 병렬화 전략

#### 1. ThreadPoolExecutor (동기 작업)
```python
# rfx_analyzer.py: 청크별 추출 (max 4)
with ThreadPoolExecutor(max_workers=4) as executor:
    futures = [executor.submit(extract_chunk, chunk) for chunk in chunks]
    results = [f.result() for f in futures]

# matcher.py: 요건별 매칭 (max 6)
with ThreadPoolExecutor(max_workers=6) as executor:
    futures = [executor.submit(match_req, req) for req in requirements]
    results = [f.result() for f in futures]
```

#### 2. asyncio (FastAPI)
```python
# main.py: 분석+요약+매칭 동시 실행
analysis_task = asyncio.to_thread(analyze_rfp, ...)
summary_task = asyncio.to_thread(generate_summary, ...)
matching_task = asyncio.to_thread(match_company, ...)

analysis, summary, matching = await asyncio.gather(
    analysis_task, summary_task, matching_task
)

# main.py: 일괄 평가 (동시 3건 제한)
semaphore = asyncio.Semaphore(3)
async def evaluate_with_semaphore(bid):
    async with semaphore:
        return await evaluate_bid(bid)

results = await asyncio.gather(*[evaluate_with_semaphore(b) for b in bids])
```

### 프론트엔드 패턴

#### 1. 대화 상태 관리 (ChatContext.tsx)
```typescript
// useReducer 기반, 직접 state 변경 금지
const [state, dispatch] = useReducer(chatReducer, initialState);

dispatch({
  type: 'ADD_MESSAGE',
  payload: { role: 'assistant', content: '...' }
});
```

#### 2. FSM 전환 (useConversationFlow.ts)
```typescript
// 순서 보존 필수
const transitionTo = (phase: ConversationPhase) => {
  dispatch({ type: 'SET_PHASE', payload: phase });
};

// greeting → bid_search_input → bid_search_results → ...
```

#### 3. 조건부 렌더링 (Fragment 필수)
```tsx
{condition && (
  <>
    <ComponentA />
    <ComponentB />
  </>
)}
```

---

## 테스트 커버리지

### 레거시 Python (tests/)

| 모듈 | 테스트 파일 | 커버리지 |
|------|-------------|----------|
| `matcher.py` | `test_constraint_evaluator.py` | ConstraintEvaluator 전체 |
| `matcher.py` | `test_company_fact_normalizer.py` | CompanyFactNormalizer |
| `matcher.py` | `test_matcher_detail_rules.py` | 규칙형 판단 엣지케이스 |
| `matcher.py` | `test_matcher_consortium_rule.py` | 컨소시엄 지분율 |
| `rfx_analyzer.py` | `test_rfx_analyzer_constraints.py` | constraints 추출 |
| `rfx_analyzer.py` | `test_rfx_analyzer_multipass.py` | 멀티패스 merge |
| `engine.py` | `test_hybrid_search.py` | BM25+벡터 RRF |
| `chat_router.py` | `test_chat_router.py` | 인텐트 분류 |
| `web_app/main.py` | `test_web_runtime_api.py` | API 엔드포인트 |

**총 테스트**: 68개 (pytest)

### rag_engine Python (rag_engine/tests/)

| 모듈 | 테스트 파일 | 커버리지 |
|------|-------------|----------|
| Phase 1 | `test_knowledge_models.py` ~ `test_proposal_api.py` | 14개 파일 |
| Phase 2 | `test_track_record_writer.py` ~ `test_phase2_api.py` | 8개 파일 |
| CompanyDB | `test_company_db.py`, `test_company_analyzer.py` | 2개 파일 |
| 학습 | `test_diff_tracker.py`, `test_auto_learner.py` | 2개 파일 |

**총 테스트**: 78개 (pytest)

### web_saas Jest (src/lib/*/\__tests__/)

| 모듈 | 테스트 파일 | 커버리지 |
|------|-------------|----------|
| HMAC | `lib/__tests__/hmac.test.ts` | verifyWebhookSignature |
| env | `lib/__tests__/env.test.ts` | zod 검증 |
| SSRF | `lib/__tests__/safeFetch.test.ts` | DNS 차단 |
| 내부 API | `lib/__tests__/internalAuth.test.ts` | nonce 재사용 |
| CSRF | `lib/__tests__/csrf.test.ts` | Origin allowlist |
| 쿼터 | `lib/quota/__tests__/consumeQuota.test.ts` | $transaction 원자 |
| 검색 | `lib/search/__tests__/buildSearchQuery.test.ts` | Prisma where |
| FTS | `lib/search/__tests__/ftsSearch.test.ts` | plainto_tsquery |
| 엑셀 | `lib/export/__tests__/buildEvaluationExcel.test.ts` | ExcelJS |

**총 테스트**: 36개 (Jest)

---

## 배포 및 운영

### 로컬 개발

#### 1. 레거시 백엔드 (FastAPI)
```bash
# 의존성 설치
pip install -r requirements.txt

# 서버 실행 (port 8000)
python services/web_app/main.py
```

#### 2. rag_engine (FastAPI)
```bash
cd rag_engine

# 서버 실행 (port 8001)
uvicorn main:app --reload --port 8001
```

#### 3. React 프론트엔드 (Vite)
```bash
cd frontend/kirabot

# 의존성 설치
npm install

# 개발 서버 (port 5173)
npm run dev

# 프로덕션 빌드
npm run build  # → dist/ 번들, 백엔드가 서빙
```

#### 4. SaaS (Next.js)
```bash
cd web_saas

# 의존성 설치
npm install

# Prisma 마이그레이션 (DATABASE_URL 필요)
npx prisma migrate dev --name <name>
npx prisma generate

# 개발 서버 (port 3000)
npm run dev
```

#### 5. PostgreSQL (Docker)
```bash
docker run -d \
  --name kirabot-postgres \
  -e POSTGRES_USER=kirabot \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=kirabot_saas \
  -e PGTZ=UTC \
  -p 5432:5432 \
  postgres:15
```

### 테스트 실행

#### Python (pytest)
```bash
# 레거시 전체
pytest -q

# 특정 파일
pytest tests/test_matcher_detail_rules.py -v

# 특정 테스트
pytest tests/test_constraint_evaluator.py::test_contract_amount_pass -v

# rag_engine
cd rag_engine && pytest -q
cd rag_engine && pytest tests/test_hwp_parser.py -v
```

#### JavaScript (Jest)
```bash
cd web_saas

# 전체 테스트
npx jest --no-coverage

# 특정 파일
npx jest src/lib/__tests__/hmac.test.ts --no-coverage

# 특정 패턴
npx jest --testPathPattern="quota" --no-coverage
```

### 배포 전 체크리스트

#### 1. 정확도 평가
```bash
python scripts/run_accuracy_eval.py
```
- RFP 분석 정확도
- GO/NO-GO 정밀도
- 제안서 품질 점수

#### 2. 사전 배포 체크
```bash
python scripts/run_railway_predeploy_checklist.py \
  --base-url https://your-domain.com
```
- 환경 변수 검증
- API 엔드포인트 health check
- 데이터베이스 연결
- ChromaDB 컬렉션 존재 여부

### 프로덕션 설정

#### 1. Prisma (web_saas)
```typescript
// src/lib/prisma.ts
const prisma = new PrismaClient({
  log: process.env.NODE_ENV === 'production' ? ['error'] : ['query', 'info', 'warn', 'error'],
});
```

#### 2. Next.js 미들웨어 (web_saas)
```typescript
// src/middleware.ts
export const config = {
  matcher: ['/api/((?!webhooks|internal|auth).*)'],
};
```

#### 3. n8n 워크플로우
- `g2b_bid_crawler.json`: 30분 주기 실행
- `ingestion_worker.json`: 1분 주기 폴링
- `evaluation_worker.json`: 1분 주기 폴링
- `stale_lock_reclaim.json`: 10분 주기, 30분 이상 락 해제

---

## 변경 이력

### 2026-03-03
- 초기 마스터 문서 생성
- Phase 1 + Phase 2 통합 (E2E 검증 완료)
- CompanyDB + company_context_builder 통합
- PPT KRDS 디자인 토큰 적용

### 2026-02-28
- A-lite 제안서 E2E 검증 통과 (146 테스트)
- Phase 2 모듈 E2E 검증 통과 (154 테스트)
- auto_learner 영속성 연결 (lifespan)

### 2026-02-27
- Phase 1 구현 완료
- Phase 2 구현 완료
- 사용자 알림 설정 추가

### 2026-02-22
- Phase 8 구현 완료 (보안 강화)
- RFP 요약 리디자인 (3섹션 GFM)

### 2026-02-21
- Phase 1-7 구현 완료 (SaaS)

---

## 참고 문서

### 설계 문서
- `docs/우리의_목표.md` - 비전 및 미션
- `docs/plans/2026-02-27-full-lifecycle-expansion-design.md` - 8모듈 확장 설계
- `docs/plans/2026-02-20-bid-platform-design.md` - SaaS 설계
- `docs/plans/2026-02-27-phase1-implementation-handoff.md` - Phase 1 핸드오프

### 구현 문서
- `docs/plans/2026-02-21-bid-platform-impl-plan.md` - SaaS Phase 1-7
- `docs/plans/2026-02-22-phase8-impl-plan.md` - SaaS Phase 8
- `docs/plans/2026-02-27-phase1-alite-impl-plan.md` - A-lite 구현
- `docs/plans/2026-03-01-document-workspace-impl-plan.md` - 문서 워크스페이스

### 보안 문서
- `docs/plans/2026-02-22-security-hardening-design.md` - 보안 설계
- `docs/plans/2026-02-22-security-hardening-impl-plan.md` - 보안 구현

### 기타
- `CLAUDE.md` - Claude Code 작업 가이드
- `docs/agent-memory/context.md` - 팀 에이전트 컨텍스트
- `docs/plans/ppt-template-guide.md` - KRDS PPT 디자인 가이드
- `docs/plans/RFP_동의어_사전.md` - RFP 동의어 사전

---

**📌 이 문서는 프로젝트의 단일 진실 공급원(Single Source of Truth)입니다.**
**모든 팀원은 이 문서를 기준으로 작업하며, 변경사항은 즉시 반영합니다.**
