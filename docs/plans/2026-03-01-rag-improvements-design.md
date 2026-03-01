# RAG System Improvements Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Kira Bot의 2개 RAG 시스템에 Self-Correction, Planning Agent, Middleware Chain, ReAct 패턴을 적용하여 문서 생성 품질과 채팅 응답 정확도를 향상

**Architecture:** Proposal RAG에 Self-Correction Loop + Planning Agent, Chat RAG에 ReAct Pattern, 공유 LLM Middleware Chain. 구현 순서: Middleware(인프라) → Self-Correction → Planning Agent → ReAct.

**Tech Stack:** Python 3.11, FastAPI, OpenAI GPT-4o-mini, ChromaDB, ThreadPoolExecutor

---

## 배경: Kira Bot의 2개 RAG 시스템

### Chat Q&A RAG (`engine.py` — 루트)
- **목적**: 업로드 문서(RFP/회사문서) 기반 실시간 Q&A
- **벡터DB**: ChromaDB (세션별 임시 — `web_company_{sid}`, `web_rfx_{sid}`)
- **검색 전략**: BM25 + Vector RRF 하이브리드 (`RAG_HYBRID_ENABLED=1`)
- **LLM**: Tool Use 1회 호출 (document_qa, general_response, bid_search, bid_analyze)
- **엔트리**: `/api/chat`
- **학습**: 없음 (세션 종료 시 삭제)

### Proposal Generation RAG (`rag_engine/` — 별도 모듈)
- **목적**: 제안서/WBS/PPT/실적기술서 등 프로덕션 문서 생성
- **벡터DB**: ChromaDB 3개 (Layer1 `proposal_knowledge` + Layer2 `company_capabilities` + auto_learn)
- **검색 전략**: 순수 벡터 검색 (쿼리: 섹션명+평가항목)
- **LLM**: 섹션별 section_writer (병렬 ThreadPoolExecutor, max_workers=3)
- **엔트리**: `/api/generate-proposal-v2`
- **학습**: auto_learner (수정 diff → 3회 이상 → 자동 반영)

---

## 개선 1: Self-Correction Loop (Proposal RAG)

### 현재
```
sections 병렬 생성 → 전체 합침 → quality_checker → 이슈 로깅만 (수정 안 됨)
```

### 개선
```
각 section 생성 → per-section quality_checker → critical 이슈 있으면 →
    이슈+원본을 section_writer에 재전달 → 1회 재생성 →
    재생성 후에도 critical 남으면 → 로깅 + 출력 태깅("⚠️ 잔여 이슈 N건")
```

### 변경
- `proposal_orchestrator.py` — `_write_and_check_section()` 래퍼 함수
- `section_writer.py` — `rewrite_section()` 추가 (이슈 프롬프트 주입)

### 제약
- 재생성은 critical 이슈만, 최대 1회
- quality_checker 피드백은 구체적으로 전달 ("N번째 문단에서 정량 수치 누락" 수준)
- GPT-4o-mini가 제대로 수정하도록 explicit 프롬프트

---

## 개선 2: Planning Agent (Proposal RAG)

### 현재
```
rfx_result → build_proposal_outline() → 배점 비례 페이지 분배만
```

### 개선: `ProposalPlanningAgent`
```
rfx_result + company_context
    ↓
[1회 LLM 콜] 전략 분석 + 섹션별 메모 동시 생성
  - RFP 핵심 요구사항 분석
  - 회사 강점 vs 요구사항 매핑
  - 경쟁 우위/열위 식별
  - 섹션별 강조 포인트 + 차별화 전략 + 위험 요소
    ↓
ProposalStrategy JSON 출력 (few-shot 예시로 구조 확정)
    ↓
각 section_writer에 StrategyMemo 주입
```

### Phase 1+2 합치기 전략
- GPT-4o-mini에서 1회 콜로 ProposalStrategy 전체 JSON 추출 시도
- few-shot 예시를 프롬프트에 포함하여 JSON 구조 확정
- 실패(파싱 에러)시 Phase 1(분석) → Phase 2(메모) 분리 폴백

### 새 파일
- `rag_engine/proposal_agent.py` — ProposalPlanningAgent 클래스

### 변경
- `rag_engine/knowledge_models.py` — StrategyMemo, ProposalStrategy 데이터 모델
- `rag_engine/proposal_orchestrator.py` — agent 호출 통합
- `rag_engine/section_writer.py` — `strategy_memo` 파라미터 추가

---

## 개선 3: Middleware Chain (공유)

### 현재
- 각 모듈이 OpenAI 직접 호출 (call_with_retry 또는 raw client)
- 로깅 없음, 토큰 추적 없음, 에러 형식 불통일

### 개선: `llm_middleware.py`
```python
class LLMMiddleware:
    def __init__(self, enable_logging=True, enable_token_tracking=True, enable_cache=False):
        self._records: list[LLMCallRecord] = []

    def wrap(self, fn, caller_name="unknown"):
        """LLM 호출 함수를 감싸서 로깅+추적+에러표준화"""

    def get_session_stats(self) -> dict:
        """세션 토큰 사용량, 비용 추정, 호출 횟수 (과금 기반)"""
```

### 기능
1. **로깅**: 호출자/모델/토큰/latency 기록 (jsonl)
2. **토큰 추적**: prompt_tokens + completion_tokens 누적 (session_stats → 과금 기반)
3. **에러 표준화**: OpenAI 에러 → 통일 LLMError 형식
4. **캐시 구조**: `enable_cache=False` 기본, 구조만 열어둠 (Chat RAG 동일 질문 캐싱 미래용)

### 적용 범위
- Proposal RAG: section_writer, proposal_agent, quality_checker
- Chat RAG: _generate_chat_answer_with_tools
- 기존 call_with_retry는 유지 (retry는 미들웨어 책임 아님)

---

## 개선 4: ReAct Pattern (Chat RAG)

### 현재
```
message → system_prompt(context) → tool_choice="required" → 1회 → return
```

### 개선: ReAct 루프 (max 3턴, early exit)
```
message → [Turn 1] context 빌드 + Tool Use → observation
    ↓ 충분하면 → early exit (대부분 여기서 끝)
    ↓ 불충분 판단 시
  [Turn 2] LLM이 생성한 suggested_query로 재검색 + Tool Use
    ↓ 충분하면 → return
    ↓ 불충분 판단 시
  [Turn 3] 최종 종합 응답 (강제 응답) → return
```

### 불충분 판단 기준
- LLM이 `need_more_context` 도구 호출 (새 도구)
  - `reason`: 왜 불충분한지
  - `suggested_query`: 재검색 쿼리 (LLM이 직접 생성 — ReAct 핵심 가치)
  - `search_scope`: company/rfx/both

### Early Exit 보장
- Turn 1에서 document_qa/general_response 호출 시 → 즉시 반환
- need_more_context 호출 시에만 → Turn 2 진입
- Turn 3은 강제 응답 (tool_choice 변경으로 need_more_context 제거)

### 변경
- `services/web_app/react_chat.py` (새 파일) — ReAct 루프 로직
- `services/web_app/main.py` — `_generate_chat_answer_with_tools` → `react_chat_loop` 위임
- `chat_tools.py` — `need_more_context` 도구 추가

---

## 구현 순서

```
3(Middleware) → 1(Self-correction) → 2(Planning Agent) → 4(ReAct)
```

이유: Middleware가 다른 3개의 LLM 호출을 추적하는 인프라. 먼저 깔고 그 위에 나머지 올림.

---

## 파일 변경 요약

| 파일 | 개선 | 변경 유형 |
|------|------|----------|
| `rag_engine/llm_middleware.py` | 3 | 새 파일 |
| `rag_engine/proposal_agent.py` | 2 | 새 파일 |
| `services/web_app/react_chat.py` | 4 | 새 파일 |
| `rag_engine/knowledge_models.py` | 2 | 모델 추가 |
| `rag_engine/section_writer.py` | 1, 2, 3 | rewrite_section + strategy_memo + middleware |
| `rag_engine/proposal_orchestrator.py` | 1, 2, 3 | self-correction + agent + middleware |
| `rag_engine/quality_checker.py` | - | 변경 없음 |
| `services/web_app/main.py` | 3, 4 | middleware + ReAct 위임 |
| `chat_tools.py` | 4 | need_more_context 도구 |

---

## LLM 비용 영향 (GPT-4o-mini 기준)

| 개선 | 추가 호출 | 비용 추정 |
|------|----------|----------|
| 1. Self-correction | +1회/critical 섹션 (보통 0-2개) | ~$0.001/섹션 |
| 2. Planning Agent | +1회/제안서 (Phase1+2 합침) | ~$0.003/제안서 |
| 3. Middleware | 0 (로깅만) | $0 |
| 4. ReAct | +0~2회/메시지 (대부분 0) | ~$0.001/메시지 |

GPT-4o-mini 가성비로 ReAct 3턴도 부담 없음.

---

## 테스트 전략

| 개선 | 테스트 파일 | 핵심 케이스 |
|------|-----------|-----------|
| 1 | `tests/test_self_correction.py` | critical 재생성, warning 무시, 잔여 이슈 태깅 |
| 2 | `tests/test_proposal_agent.py` | JSON 파싱 성공/실패 폴백, 전략 메모 주입 |
| 3 | `tests/test_llm_middleware.py` | 로깅, 토큰 추적, 에러 표준화, session_stats |
| 4 | `tests/test_react_chat.py` | early exit, 재검색, max 3턴 강제 종료 |
