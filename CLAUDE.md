# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## 프로젝트 개요

**Kira Bot** — 공공조달 입찰 자격 분석 플랫폼. 기업이 RFx(RFP/RFQ/입찰공고) 문서를 올리면 자격요건을 추출하고, 회사 문서와 매칭하여 GO/NO-GO + 준비 가이드를 제공한다.

현재 전환 중: 기존 단일 사용자 Streamlit MVP → **멀티테넌트 B2B SaaS** (나라장터 공고 자동 수집·분석).

설계 문서: `docs/plans/2026-02-20-bid-platform-design.md`
구현 계획: `docs/plans/2026-02-21-bid-platform-impl-plan.md`

---

## 실행 명령어

### Python 백엔드 (FastAPI)
```bash
# 의존성 설치
pip install -r requirements.txt

# 웹 API 서버 (포트 8010)
python services/web_app/main.py

# Streamlit 앱 (레거시, 포트 8501)
streamlit run app.py
```

### React 프론트엔드
```bash
cd frontend/kirabot
npm install
npm run dev       # 포트 3000
npm run build     # 프로덕션 번들 → dist/
```

### 테스트
```bash
# 전체 테스트
pytest -q

# 단일 테스트 파일
pytest tests/test_matcher_detail_rules.py -v

# 단일 테스트 케이스
pytest tests/test_constraint_evaluator.py::test_contract_amount_pass -v

# 문법 검증
python -m py_compile app.py matcher.py chat_router.py rfx_analyzer.py document_parser.py

# 정확도 평가
python scripts/run_accuracy_eval.py

# 프리디플로이 체크리스트
python scripts/run_railway_predeploy_checklist.py --base-url https://your-domain.com
```

### SaaS 스택 (Phase 1+ 진행 중)
```bash
# Prisma 스키마 변경 후 마이그레이션
cd web_saas
npx prisma migrate dev --name <migration_name>
npx prisma generate

# rag_engine FastAPI (포트 8001)
cd rag_engine
uvicorn main:app --reload --port 8001
```

---

## 아키텍처

### 현재 스택 (기존 Kira Bot)

```
frontend/kirabot/    ← React 19 + Vite + TypeScript (랜딩 + 대시보드)
        ↓ HTTP (port 8010)
services/web_app/main.py   ← FastAPI: 업로드, 세션, 채팅, 분석, 관리자 API
        ↓ Python import
[RAG Core — 루트 레벨]
  engine.py          ← ChromaDB + BM25 하이브리드 벡터 검색
  rfx_analyzer.py    ← LLM 기반 자격요건 구조화 추출 (멀티패스 + Structured Outputs)
  matcher.py         ← 결정론적 constraints 평가기 + LLM GO/NO-GO 판단
  chat_router.py     ← 쿼리 인텐트 분류 + 오프토픽 차단 + 정책 적용
  document_parser.py ← PDF/DOCX/HWP 파싱 및 청킹
  user_store.py      ← 세션, 쿼터, RBAC, 관리자 KPI
services/auth_gateway/main.py  ← JWT 검증 + HttpOnly 쿠키 세션 발급

data/vectordb/       ← ChromaDB 영구 저장소 (회사 문서 임베딩)
data/user_store/     ← 세션 + 사용량 JSON 파일 저장소
```

### 신규 SaaS 스택 (Phase 1-7, 구현 중)

```
web_saas/            ← Next.js + Prisma (멀티테넌트 SaaS 웹)
  prisma/schema.prisma
  src/lib/           ← prisma.ts, hmac.ts, ids.ts, errors.ts
  src/app/api/       ← webhooks/n8n, webhooks/stripe, internal/*

rag_engine/          ← FastAPI 0.115 (POST /api/analyze-bid)
  main.py            ← RFxAnalyzer + QualificationMatcher 래퍼
  engine.py          ← 기존 엔진 복사 (add_document_v2 추가 예정)

n8n/workflows/       ← 4종 JSON: g2b_bid_crawler, ingestion_worker,
                       evaluation_worker, stale_lock_reclaim

PostgreSQL (Docker)  ← Prisma ORM, PGTZ=UTC 강제
```

### 핵심 데이터 흐름 (SaaS)

```
n8n g2b_bid_crawler
  → BidNotice UPSERT (ON CONFLICT DO UPDATE RETURNING id)
  → IngestionJob INSERT (ON CONFLICT DO NOTHING)
  → process-ingestion-job API: 다운로드 → contentHash → COMPLETED
  → createEvaluationJobsForBidNotice (interestConfig 매칭 후)
  → process-evaluation-job API:
      consumeQuotaIfNeeded → FastAPI analyze-bid → SCORED → Resend 이메일
```

---

## 핵심 설계 결정

### RAG 파이프라인 (기존 엔진)
- **검색**: `engine.py` BM25 + 벡터 RRF 하이브리드 (`RAG_HYBRID_ENABLED=1` 활성화)
- **추출**: `rfx_analyzer.py`가 공고문을 멀티패스로 처리 → `RFxAnalysisResult` (constraints 포함)
- **매칭**: `matcher.py`의 `ConstraintEvaluator`가 결정론 비교 우선, FALLBACK_NEEDED 시 LLM 판단
- **확장 계획**: `add_document_v2(contextual=True)` — summary를 ChromaDB `documents`에 저장, 원문은 `metadata.raw_text`에 보존 → SearchResult.text = raw_text 반환 (Summary-for-retrieval + Raw-for-reading)

### SaaS 잡 시스템 (설계 문서 §2-4 참조)
- **중간 상태 (FETCHING, PARSING, EVALUATING, NOTIFYING)는 DB 저장 금지** — 인메모리만, 크래시 시 직전 안정 상태로 복구
- **락 획득**: `SELECT 후보 → UPDATE WHERE id=? AND locked_at IS NULL` + affected rows 검사. `FOR UPDATE SKIP LOCKED` 금지
- **ID 생성**: `createId()` (cuid2, 앱 레벨) — `gen_random_uuid()` 금지
- **UTC 강제**: `PGTZ=UTC`, `DATABASE_URL?timezone=UTC`, `Date.UTC()` 사용 (`new Date(year, month, 1)` 금지)

### HMAC Webhook (§3)
- 서명 문자열: `${timestamp}.${nonce}.${rawBody}` — nonce 포함 필수 (nonce 교체 공격 방지)
- Next.js에서 `request.text()`로 raw body 읽기 (`request.json()` 금지)
- Nonce 중복 방지: `prisma.usedNonce.create()` create-only + P2002 catch (2단계 findUnique+create 금지)

### 쿼터 관리 (§5)
- `consumeQuotaIfNeeded()`: 같은 트랜잭션에서 `Subscription.plan` 조회 → PRO=-1, FREE=10 결정 후 행 upsert
- `quotaConsumed=true` 필드로 재시도 중복 차감 방지
- FastAPI 호출 실패해도 쿼터 차감됨 (요청 기반)

### 프론트엔드 제약
- `frontend/kirabot/` 하위 CSS·레이아웃 **전면 변경 금지**
- 기능 추가 시 기존 Tailwind 클래스 재사용, 신규 className 추가 최소화
- `Dashboard.tsx`: `AppMode = 'manual' | 'auto'` 탭 구조로 기존 채팅 흐름 보존

---

## 환경 변수 핵심 목록

`.env.example` 참조. 자주 쓰는 것:

| 변수 | 기본값 | 용도 |
|---|---|---|
| `OPENAI_API_KEY` | — | 임베딩 + LLM 모델 |
| `OPENAI_STRICT_JSON_ONLY` | `1` | Structured Outputs 전용 모드 |
| `RAG_HYBRID_ENABLED` | `0` | BM25+벡터 하이브리드 활성화 |
| `KIRA_OPINION_ENABLED` | `1` | 의견 생성 on/off |
| `KIRA_OPINION_BALANCED_VARIANT` | `a` | 균형형 A/B 실험 |
| `AUTH_MODE` | `social_only` | 소셜 로그인 전용 |
| `QUOTA_ANALYZE_MONTHLY_LIMIT` | `30` | 월 분석 한도 |
| `WEBHOOK_SECRET` | — | n8n↔Next.js HMAC 서명 |
| `DATABASE_URL` | — | PostgreSQL (SaaS 스택) |

---

## 테스트 파일 매핑

| 파일 | 대상 모듈 |
|---|---|
| `test_constraint_evaluator.py` | `matcher.py` ConstraintEvaluator |
| `test_company_fact_normalizer.py` | `matcher.py` CompanyFactNormalizer |
| `test_matcher_detail_rules.py` | `matcher.py` 규칙형 판단 |
| `test_matcher_consortium_rule.py` | `matcher.py` 컨소시엄 지분 규칙 |
| `test_rfx_analyzer_constraints.py` | `rfx_analyzer.py` constraints 파싱 |
| `test_rfx_analyzer_multipass.py` | `rfx_analyzer.py` 멀티패스 merge |
| `test_hybrid_search.py` | `engine.py` BM25+벡터 RRF |
| `test_chat_router.py` | `chat_router.py` 인텐트 분류 |
| `test_chat_policy_integration.py` | `chat_router.py` 정책 적용 |
| `test_web_runtime_api.py` | `services/web_app/main.py` |

---

## 보고서 및 텔레메트리

- `reports/router_telemetry.jsonl` — 채팅 라우터 판단 로그
- `reports/opinion_experiment.jsonl` — balanced A/B 실험 결과
- `reports/railway_predeploy_checklist.md` — 배포 전 체크리스트 결과

---

## 팀 에이전트 표준

팀 협업 표준 전문: `agent.md` (루트)

**작업 시작 전 필독**: `docs/agent-memory/context.md`

공용 메모리 파일:
- `docs/agent-memory/context.md` — 프로젝트 핵심 컨텍스트
- `docs/agent-memory/decision-log.md` — 주요 의사결정 기록
- `docs/agent-memory/patterns.md` — 재사용 가능한 패턴
- `docs/agent-memory/failures.md` — 실패/회고/재발방지

에이전트 자산 (`.claude/`):
- `.claude/agents/code-review-veteran.md` — 코드 리뷰 서브에이전트
- `.claude/agents/knowledge-curator.md` — 팀 메모리 관리 서브에이전트
- `.claude/skills/maintainability-guardian/SKILL.md` — 유지보수성 루브릭 스킬
- `.claude/skills/agent-memory-sync/SKILL.md` — 핸드오프 전 메모리 동기화 스킬
- `.claude/commands/think.md` — `/think` 슬래시 커맨드 (단계별 사고)
