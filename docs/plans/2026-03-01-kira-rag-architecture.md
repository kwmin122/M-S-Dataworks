# Kira Bot RAG Architecture — 이중 RAG 시스템 아키텍처 문서

> 논문/발표 참고용. 두 RAG 시스템의 설계 철학, 데이터 흐름, 개선 방향 정리.

---

## 1. 시스템 개요

Kira Bot은 공공조달 입찰 자동화 AI 플랫폼으로, **목적이 다른 2개의 독립 RAG 시스템**을 운용한다.

| | Chat Q&A RAG | Proposal Generation RAG |
|---|---|---|
| **핵심 질문** | "이 문서에 뭐라고 써있지?" | "이 입찰에 어떤 제안서를 써야 하지?" |
| **본질** | 정보 검색 (Information Retrieval) | 지식 생성 (Knowledge Generation) |
| **시간축** | 세션 단위 (임시) | 영구 (누적 학습) |
| **입력** | 사용자 자연어 질문 | RFP 분석 결과 + 회사 맥락 |
| **출력** | 채팅 답변 + 참조 페이지 | DOCX/PPTX/XLSX 문서 |

**분리 이유**: 검색 목적의 RAG과 생성 목적의 RAG은 검색 전략, 프롬프트 설계, 품질 기준이 근본적으로 다르다. 하나의 파이프라인으로 통합하면 양쪽 모두 최적화할 수 없다.

---

## 2. Chat Q&A RAG — 실시간 문서 기반 대화

### 2.1 아키텍처

```
사용자 메시지
    ↓
[Pre-check] UNSAFE 키워드 사전 차단 (LLM 비용 절감)
    ↓
[Deterministic] 최신 매칭 결과에서 직접 응답 가능한지 확인
    ↓
[RAG Context] BM25+Vector RRF 하이브리드 검색
  ├── Company ChromaDB (web_company_{session}) → top_k=12
  └── RFx ChromaDB (web_rfx_{session}) → top_k=12
    ↓
[Tool Use] GPT-4o-mini (단일 호출, tool_choice="required")
  ├── document_qa → 답변 + 참조 페이지
  ├── general_response → 일반 응답
  ├── bid_search → 공고 검색 트리거
  └── bid_analyze → 문서 분석 트리거
    ↓
[Post-processing] 참조 검증 (RFx 원문에 존재하는지)
    ↓
답변 반환
```

### 2.2 벡터 데이터베이스

- **엔진**: ChromaDB PersistentClient
- **임베딩**: OpenAI `text-embedding-3-small`
- **컬렉션**: 세션당 2개 (company, rfx)
- **수명**: 세션 TTL (12시간) 후 삭제
- **청킹**: 512토큰 단위, 50토큰 오버랩

### 2.3 하이브리드 검색 (BM25 + Vector RRF)

```
Query: "이 사업의 자격요건은?"
    ↓
  ┌── BM25 (keyword) → rank_bm25 라이브러리
  │   Score: keyword 빈도 + IDF 가중치
  │
  └── Vector (semantic) → ChromaDB cosine similarity
      Score: 임베딩 유사도
    ↓
RRF (Reciprocal Rank Fusion, K=60)
  score_rrf = Σ 1/(K + rank_bm25) + 1/(K + rank_vector)
    ↓
chunk_key (source_file + chunk_id)로 통합
  → BM25 전용 히트도 포함 (벡터 점수 낮은 키워드 매칭)
    ↓
상위 12개 결과 반환
```

**BM25의 가치**: "인증서", "ISO 27001" 같은 고유명사는 의미 임베딩보다 키워드 매칭이 정확하다. 하이브리드는 의미적 이해와 키워드 정확성을 동시에 확보한다.

### 2.4 Tool Use 라우팅

전통적 intent classifier 대신 **OpenAI Function Calling**을 라우팅 메커니즘으로 활용:

- LLM이 컨텍스트(문서 내용)와 사용자 메시지를 보고 적절한 도구 선택
- 4개 도구 정의가 곧 4개 인텐트
- 별도 분류기 학습/유지 불필요
- 단점: 1-shot이라 복합 질문에서 단일 도구만 선택됨

### 2.5 현재 한계와 개선 방향

| 한계 | 원인 | 개선 (ReAct) |
|------|------|------------|
| 복합 질문 처리 불가 | 1회 Tool Use만 | ReAct 루프 (max 3턴) |
| 검색 부족 시 "정보 없음" | 재검색 메커니즘 없음 | LLM이 재검색 쿼리 생성 |
| 멀티홉 추론 불가 | 단일 검색 결과만 | 관찰→재추론→재검색 |

---

## 3. Proposal Generation RAG — 3-Layer 지식 기반 문서 생성

### 3.1 아키텍처

```
RFP 분석 결과 (rfx_result)
    ↓
[Planning Agent] 전략 수립
  - RFP 요구사항 ↔ 회사 강점 매핑
  - 섹션별 전략 메모 (StrategyMemo)
    ↓
[Outline] 배점 비례 섹션 분배
  - 평가항목 → 섹션 1:1 매핑
  - 페이지 = weight × total_pages
    ↓
[Parallel Section Writing] (ThreadPoolExecutor, max_workers=3)
  각 섹션:
  ├── Layer 1 검색: knowledge_db.search(section_name + eval_item, top_k=10)
  ├── Layer 2 주입: company_context (실적, 인력, 문체, 학습 패턴)
  ├── 전략 메모 주입: StrategyMemo (강조 포인트, 차별화)
  └── LLM 생성: GPT-4o-mini (temp=0.4, 4000 tokens)
    ↓
[Self-Correction] per-section quality_checker
  - critical 이슈 → 1회 재생성
  - 잔여 이슈 → 태깅
    ↓
[Assembly] Mistune 3.x AST → python-docx DOCX
    ↓
ProposalResult (docx_path, sections, quality_issues)
```

### 3.2 3-Layer 지식 아키텍처

```
┌─────────────────────────────────────────┐
│  Layer 3: 승패 분석 (미구현)              │
│  - 과거 입찰 결과 분석                    │
│  - 점수대별 전략 최적화                    │
├─────────────────────────────────────────┤
│  Layer 2: 회사 맞춤 지식 (자동 누적)       │
│  ├── CompanyDB: 실적, 인력 (ChromaDB)     │
│  ├── 문체 분석: company_analyzer          │
│  ├── 학습 패턴: auto_learner             │
│  │   └── 수정 diff → 1회=기록             │
│  │               → 2회=후보              │
│  │               → 3회+=자동반영          │
│  └── Profile: profile.json (구조화)       │
├─────────────────────────────────────────┤
│  Layer 1: 범용 지식 (사전 학습)            │
│  ├── 495 KnowledgeUnit (ChromaDB)        │
│  │   ├── 블로그 47개 → 구조/작성법/함정    │
│  │   ├── 유튜브 40개 → 실전 노하우        │
│  │   └── 공식문서 18개 → 법령/규정        │
│  ├── 7개 카테고리: structure, writing,     │
│  │   evaluation, legal, pitfall,          │
│  │   best_practice, methodology           │
│  └── ID: {source}_{sha256[:12]}           │
└─────────────────────────────────────────┘
```

### 3.3 지식 검색 전략

Chat RAG과 달리 **순수 벡터 검색**을 사용:

- **이유**: 쿼리가 자연어가 아닌 합성 쿼리 (section_name + evaluation_item)
  - 예: "기술적 접근방안 시스템 구축 방법론" → 의미 검색이 키워드보다 효과적
- **BM25 불필요**: 합성 쿼리는 키워드 분포가 균일하여 BM25 이점 없음
- **top_k=10**: 섹션당 10개 지식 유닛 검색 → 프롬프트에 rules/pitfalls/examples로 분류 주입

### 3.4 Section Writer 프롬프트 구조 (4-Layer Stack)

```
[System Prompt]
├── Layer 1 Rules (knowledge_db → category별 정리)
│   "structure: 제안서 구조는 평가항목 순서를 따라야 한다"
│   "pitfall: 블라인드 평가에서 회사명 노출은 감점 사유"
│   "writing: 정량적 수치를 제시하되 근거를 병기해야 한다"
│
├── Layer 2 Company Context
│   "과거 제안서 문체: 간결 서술체, 표 활용 빈도 높음"
│   "회사 강점: ITS 교통시스템 10년 경력, ISO 27001 보유"
│   "학습 패턴: 사용자가 3회 이상 '구체적 수치 추가' 수정"
│
├── Strategy Memo (Planning Agent)
│   "이 섹션 강조: 교통신호제어 특허 3건"
│   "차별화: 경쟁사 대비 유지보수 인력 2배"
│   "주의: 예산 초과 인상 금지"
│
└── RFP Context
    "사업명: XX 교통관제시스템 구축"
    "발주기관: 국토교통부"
    "예산: 50억"

[User Prompt]
"섹션 '기술적 접근방안' 작성. 배점 20점, 목표 8페이지."
```

### 3.5 자동 학습 메커니즘 (Auto-Learner)

```
사용자가 AI 생성 제안서 수정
    ↓
diff_tracker: 원본 vs 수정본 비교
  → 변경 유형 분류 (추가/삭제/교체)
  → 패턴 키 해싱: sha256(doc_type:company_id:change_type:context)
    ↓
auto_learner: 패턴 누적
  ├── 1회: 기록 (record)
  ├── 2회: 후보 (candidate)
  └── 3회+: 자동 반영 (promote)
        ├── company_db 프로필 업데이트
        └── 다음 생성 시 section_writer 프롬프트에 주입
    ↓
영속성: FastAPI lifespan (startup: load, shutdown: save)
```

**핵심 인사이트**: "사용자가 같은 수정을 3번 하면, 그건 선호이지 실수가 아니다." 이 임계값 기반 학습은 노이즈를 자동 필터링한다.

---

## 4. 두 RAG 시스템 비교

### 4.1 검색 전략 비교

| 속성 | Chat RAG | Proposal RAG |
|------|----------|-------------|
| 검색 방식 | BM25 + Vector RRF | 순수 Vector |
| 쿼리 타입 | 사용자 자연어 | 합성 (섹션명+평가항목) |
| top_k | 12 | 10 |
| 유사도 메트릭 | cosine (RRF 통합) | cosine |
| BM25 필요성 | 높음 (고유명사) | 없음 (합성 쿼리) |
| 메타데이터 필터 | source_file | category |

### 4.2 LLM 호출 패턴 비교

| 속성 | Chat RAG | Proposal RAG |
|------|----------|-------------|
| 호출 방식 | Tool Use (function calling) | 직접 completion |
| 모델 | gpt-4o-mini | gpt-4o-mini |
| Temperature | 0.3 (보수적) | 0.4 (창의적) |
| Max tokens | 4096 | 4000 |
| 병렬화 | 없음 (순차) | ThreadPoolExecutor (3) |
| Retry | 없음 | call_with_retry (2회) |

### 4.3 데이터 수명 비교

```
Chat RAG:
  세션 시작 ──── 문서 업로드 ──── 질의응답 ──── 세션 만료 (12h) ──── 삭제
                  ↓                 ↓
              ChromaDB 생성    BM25+Vector 검색

Proposal RAG:
  최초 학습 ─── Layer1 탑재 ──── 제안서 생성 ──── 사용자 수정 ──── 자동 학습 ──── 다음 생성 반영
      ↓             ↓                ↓                 ↓                ↓
  495 유닛      ChromaDB 영구    section_writer    diff_tracker    auto_learner
                                                                  (3회→promote)
```

---

## 5. 개선 설계와 적용 매핑

### 5.1 개선 아이디어 → RAG 매핑

```
┌──────────────────┬──────────────┬──────────────┐
│     개선          │  Chat RAG    │ Proposal RAG │
├──────────────────┼──────────────┼──────────────┤
│ 1. Self-Correction│     -        │    ★ 핵심    │
│ 2. Planning Agent │     -        │    ★ 핵심    │
│ 3. Middleware     │   ★ 적용     │    ★ 적용    │
│ 4. ReAct Pattern  │   ★ 핵심     │     -        │
└──────────────────┴──────────────┴──────────────┘
```

### 5.2 Self-Correction (Proposal RAG)

**패턴**: Generate → Check → Fix → Ship

GraphRAG 논문의 Cypher Self-Correction에서 영감:
- Neo4j 쿼리 생성 → 실행 에러 → 에러 메시지를 LLM에 피드백 → 쿼리 재생성
- 우리 적용: 섹션 생성 → 품질 체크 에러 → 에러를 LLM에 피드백 → 섹션 재생성

**차이점**: 우리는 1회 제한 + critical만. "AI가 2번 시도해도 못 고치면 사람이 봐야 할 문제"라는 설계 철학.

### 5.3 Planning Agent (Proposal RAG)

**패턴**: Think → Plan → Execute

LangChain Deep Agents의 계획 수립 에이전트에서 영감:
- 복잡한 작업을 하위 작업으로 분해
- 우리 적용: RFP 분석 → 전략 수립 → 섹션별 전략 메모 → 각 섹션 독립 실행

**핵심 가치**: "어떤 평가항목에서 몇 점을 노릴 것인가"라는 전략적 판단을 섹션 작성과 분리. 전략은 전체를 보는 agent가, 실행은 개별 worker가.

### 5.4 Middleware Chain (공유)

**패턴**: Intercept → Process → Pass

모든 LLM 호출에 대한 관측 가능성(Observability) 확보:
- 로깅, 토큰 추적, 에러 표준화
- 미래 과금 시스템의 데이터 기반 (`session_stats`)

### 5.5 ReAct Pattern (Chat RAG)

**패턴**: Reason → Act → Observe → Repeat

AI Agent의 ReAct (Reasoning + Acting) 패턴:
1. **Reasoning**: "이 질문에 답하려면 자격요건 정보가 필요하다"
2. **Acting**: document_qa 도구로 검색
3. **Observing**: "검색 결과가 불충분하다"
4. **Repeat**: "다른 키워드로 재검색하자" → need_more_context → 재검색

**Early Exit**: 대부분 Turn 1에서 충분 → 즉시 반환. 3턴까지 가는 건 복합 질문만.

---

## 6. 기대 효과

| 메트릭 | 현재 | 개선 후 기대 |
|--------|------|------------|
| 제안서 블라인드 위반율 | 검출만 | 자동 수정 (critical 0건 목표) |
| 제안서 전략 일관성 | 없음 | 섹션 간 전략 정렬 |
| 채팅 복합 질문 응답률 | ~50% | ~85% (ReAct 멀티홉) |
| LLM 비용 추적 | 불가능 | 실시간 session_stats |
| 에러 디버깅 시간 | 길음 | 표준화 로깅으로 단축 |

---

## 7. 구현 결과 (2026-03-01)

### 7.1 구현 파일 및 테스트

| 개선 | 파일 | 테스트 | 테스트 수 |
|------|------|--------|----------|
| Middleware | `rag_engine/llm_middleware.py` | `tests/test_llm_middleware.py` | 11 |
| Self-Correction | `rag_engine/section_writer.py` (rewrite_section) | `tests/test_self_correction.py` | 6 |
| Self-Correction | `rag_engine/proposal_orchestrator.py` (_write_and_check_section) | — | — |
| Planning Agent | `rag_engine/proposal_agent.py` | `tests/test_proposal_agent.py` | 8 |
| Planning Agent | `rag_engine/knowledge_models.py` (StrategyMemo, ProposalStrategy) | — | — |
| ReAct | `services/web_app/react_chat.py` | `tests/test_react_chat.py` | 7 |
| ReAct | `chat_tools.py` (need_more_context) | `tests/test_chat_tools.py` | (기존+1) |
| 통합 | `services/web_app/main.py` (react_chat_loop 위임) | — | — |

**전체 테스트**: rag_engine 273개 통과, 루트 443개 통과 (기존 3건 실패 유지).

### 7.2 코드 리뷰 결과 및 수정

코드 리뷰에서 발견된 이슈와 수정 사항:

| 심각도 | 이슈 | 수정 |
|--------|------|------|
| Critical | `LLMMiddleware.records` 리스트가 ThreadPoolExecutor에서 경합 | `threading.Lock` 추가 (append/read 모두 보호) |
| Important | `react_chat.py`가 매 호출마다 `sys.path.insert` 실행 | 모듈 레벨 import로 이동 |
| Suggestion | `knowledge_hints`가 생성만 되고 사용 안 됨 | knowledge DB 검색 쿼리에 hints 결합 |

### 7.3 LLM 비용 영향 (실측 추정)

| 개선 | 추가 호출 | 비용 (GPT-4o-mini) |
|------|----------|-------------------|
| Middleware | 0 (관측만) | $0 |
| Self-Correction | +0~2회/제안서 | ~$0.002 |
| Planning Agent | +1회/제안서 | ~$0.003 |
| ReAct | +0~2회/메시지 | ~$0.001 |

### 7.4 아키텍처 변경 후 데이터 흐름

```
[Proposal RAG — 개선 후]

RFP 분석 결과
    ↓
★ LLM Middleware 생성 (세션 단위)
    ↓
★ Planning Agent → ProposalStrategy JSON (1회 LLM)
    ↓
Outline (배점 비례 분배)
    ↓
병렬 Section Writing (ThreadPoolExecutor)
  각 섹션:
  ├── knowledge_hints로 강화된 벡터 검색
  ├── Layer 1 + Layer 2 + StrategyMemo 4-layer 프롬프트
  ├── ★ LLM 호출 (middleware 감싸기 → 토큰/비용 추적)
  ├── ★ Self-Correction: quality_checker → critical이면 1회 재생성
  └── 잔여 이슈 태깅
    ↓
DOCX 조립
    ↓
★ Middleware session_stats 로깅 (총 호출/토큰/비용/레이턴시)
    ↓
ProposalResult (docx_path + residual_issues)
```

```
[Chat RAG — 개선 후]

사용자 메시지
    ↓
★ ReAct 루프 진입 (max 3턴)
    ↓
[Turn 1] BM25+Vector 검색 → Tool Use
  ├── document_qa/general_response → ★ 즉시 반환 (early exit)
  └── ★ need_more_context → 재검색 필요 판단
        ├── reason: 불충분 이유
        ├── suggested_query: LLM 생성 재검색 쿼리
        └── scope: company/rfx/both
    ↓
[Turn 2] ★ 재검색 (_rebuild_context) → Tool Use
  └── 대부분 여기서 해결
    ↓
[Turn 3] ★ 강제 응답 (need_more_context 제거)
    ↓
답변 반환
```

---

## 부록 A: 기술 스택

- **언어**: Python 3.11
- **프레임워크**: FastAPI 0.115 (rag_engine), FastAPI (web_app)
- **벡터DB**: ChromaDB (PersistentClient)
- **임베딩**: OpenAI text-embedding-3-small
- **LLM**: GPT-4o-mini (비용 효율)
- **검색**: BM25 (rank_bm25) + Vector (ChromaDB cosine)
- **문서 생성**: python-docx, python-pptx, openpyxl
- **마크다운 파싱**: mistune 3.x AST
- **병렬화**: ThreadPoolExecutor, asyncio.gather
- **프론트엔드**: React 19 + Vite + TypeScript

## 부록 B: 관련 연구

- **RAG (Retrieval-Augmented Generation)**: Lewis et al., 2020
- **ReAct**: Yao et al., 2022 — Synergizing Reasoning and Acting in Language Models
- **GraphRAG**: Microsoft Research, 2024 — From Local to Global
- **LangChain Deep Agents**: LangChain, 2024-2025 — Agentic RAG 프레임워크
- **Self-Correction**: Pan et al., 2023 — Automatically Correcting Large Language Models
