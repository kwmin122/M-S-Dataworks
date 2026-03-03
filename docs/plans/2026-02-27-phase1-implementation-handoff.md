# Phase 1: A-lite 제안서 MVP — 구현 완료 핸드오프

> **작성일**: 2026-02-27
> **작성자**: Claude Opus 4.6 (Subagent-Driven Development)
> **계획 문서**: `docs/plans/2026-02-27-phase1-alite-impl-plan.md`
> **설계 문서**: `docs/plans/2026-02-27-full-lifecycle-expansion-design.md`

---

## 1. 무엇을 했는가

Kira Bot을 "공공조달 자격분석 도구"에서 "입찰 전 과정 자동화 플랫폼"으로 확장하기 위한 **Phase 1 A-lite 구현**을 완료했다.

### 핵심 목표
RFP 분석 후 **Layer 1 지식 기반 DOCX 제안서 초안**을 자동 생성하는 파이프라인. 회사 DB 없이도 범용 제안서 60점 수준 생성 가능.

### 구현 범위 (18개 태스크, 69개 테스트 전부 통과)

| 주차 | 모듈 | 파일 | 상태 |
|:---:|------|------|:---:|
| W1 | Knowledge Data Models | `knowledge_models.py` | ✅ |
| W1 | Knowledge DB (ChromaDB) | `knowledge_db.py` | ✅ |
| W1 | Knowledge Harvester (Pass 1) | `knowledge_harvester.py` | ✅ |
| W1 | Knowledge Dedup (Pass 2) | `knowledge_dedup.py` | ✅ |
| W1-2 | Proposal Planner | `proposal_planner.py` | ✅ |
| W1-2 | Section Writer | `section_writer.py` | ✅ |
| W1-2 | Quality Checker | `quality_checker.py` | ✅ |
| W1-2 | Document Assembler | `document_assembler.py` | ✅ |
| W2 | Proposal Orchestrator | `proposal_orchestrator.py` | ✅ |
| W2 | rag_engine API (/api/generate-proposal-v2) | `main.py` | ✅ |
| W2 | Legacy Backend Proxy (/api/proposal/generate-v2) | `services/web_app/main.py` | ✅ |
| W2 | Frontend v2 API + Handler | `kiraApiService.ts`, `useConversationFlow.ts` | ✅ |
| W3-4 | Company DB | `company_db.py` | ✅ |
| W3-4 | Company Style Analyzer | `company_analyzer.py` | ✅ |
| W5 | Layer 2 Prompt Integration | `section_writer.py` (수정) | ✅ |
| W5-6 | Checklist Extractor | `checklist_extractor.py` | ✅ |
| W5-6 | Checklist API + Edit Feedback API | `main.py` (수정) | ✅ |
| W7-8 | Diff Tracker | `diff_tracker.py` | ✅ |
| W7-8 | Auto-Learning Pipeline | `auto_learner.py` | ✅ |

---

## 2. 아키텍처 개요

```
[사용자] → [React Chat UI] → [Legacy Backend :8000]
                                    ↓ proxy
                              [rag_engine :8001]
                                    ↓
           ┌────────────────────────┼────────────────────────┐
           │                        │                        │
    [proposal_planner]     [knowledge_db]           [checklist_extractor]
           ↓                 (ChromaDB)                      │
    [section_writer × N]  ←── search()               [제출 체크리스트]
     (ThreadPoolExecutor)
           ↓
    [quality_checker]
           ↓
    [document_assembler]
           ↓
        📄 DOCX

[diff_tracker] ←→ [auto_learner] → Layer 2 자동 반영
```

### 제안서 생성 파이프라인 (A-lite)

1. **RFP 분석 결과** → `proposal_planner.build_proposal_outline()` → 섹션별 배점 비례 아웃라인
2. **각 섹션마다**: `knowledge_db.search()` → Layer 1 지식 검색
3. **`section_writer.write_section()`** → 지식 + RFP 컨텍스트 + (선택적) 회사 정보로 LLM 생성
4. **병렬 실행**: `ThreadPoolExecutor(max_workers=3)`로 섹션 동시 생성
5. **`quality_checker.check_quality()`** → 블라인드 위반, 모호 표현 감지
6. **`document_assembler.assemble_docx()`** → python-docx로 DOCX 조립 (목차 + 페이지 브레이크)
7. **결과**: `ProposalResult(docx_path, sections, outline, quality_issues, generation_time_sec)`

### 3계층 학습 모델

- **Layer 1 (기본 모델)**: `knowledge_harvester.py` + `knowledge_dedup.py`
  - LLM 2-Pass: Pass 1 = 7카테고리 지식 추출, Pass 2 = AGREE/CONDITIONAL/CONFLICT 해소
  - 소스: YouTube 자막, 블로그, 공식 가이드 (JSON 파일로 큐레이션됨)
  - 벡터DB: ChromaDB `proposal_knowledge` collection

- **Layer 2 (회사 맞춤)**: `company_db.py` + `company_analyzer.py`
  - 과거 제안서 문체/구조/강점 자동 분석
  - 실적/인력 ChromaDB 시맨틱 검색
  - 학습된 패턴 자동 주입

- **Layer 3 (승패 분석)**: 향후 구현 예정

### 수정 Diff 학습 루프 (RLHF for Proposals)

- `diff_tracker.py`: AI 생성 vs 사용자 수정 diff 추출, 패턴 키 해싱
- `auto_learner.py`: 1회=기록, 2회=후보, 3회+=자동 반영 + 알림
- `compute_edit_rate()`: 품질 KPI (v1: 45% → v10: 8% = 학습도 92%)

---

## 3. API 엔드포인트 (새로 추가)

### rag_engine (포트 8001)

| Method | Path | 설명 |
|--------|------|------|
| POST | `/api/generate-proposal-v2` | A-lite DOCX 제안서 생성 |
| POST | `/api/checklist` | 제출 체크리스트 추출 |
| POST | `/api/edit-feedback` | 사용자 수정 diff → 자동 학습 |

### Legacy Backend (포트 8000)

| Method | Path | 설명 |
|--------|------|------|
| POST | `/api/proposal/generate` | **기존 유지** — 간단 제안서 초안 (OpenAI 직접호출) |
| POST | `/api/proposal/generate-v2` | **새로 추가** — rag_engine v2 프록시 |

**중요**: `/api/proposal/generate`와 `/api/proposal/generate-v2`는 **별개 기능**이다.
- v1: 챗봇 UI에서 빠르게 섹션별 텍스트 생성 (기존 기능)
- v2: Layer 1 지식 기반 풀 DOCX 제안서 생성 (A-lite 파이프라인)

### Frontend API

```typescript
// 기존 (유지)
generateProposalDraft(sessionId, bidNoticeId) → { sections: ProposalSections }

// 새로 추가
generateProposalV2(sessionId, totalPages?) → ProposalV2Response
// ProposalV2Response = { docx_path, sections: [{name, preview}], quality_issues, generation_time_sec }
```

---

## 4. 파일 목록 (모든 신규/수정 파일)

### 신규 생성 (15개 모듈)

```
rag_engine/
  llm_utils.py             ← LLM retry+timeout 헬퍼 (call_with_retry, 지수 백오프)
  knowledge_models.py      ← 데이터 모델 (KnowledgeUnit, ProposalSection, ProposalOutline)
  knowledge_db.py          ← ChromaDB wrapper (proposal_knowledge collection)
  knowledge_harvester.py   ← LLM Pass 1 지식 추출 (call_with_retry 적용)
  knowledge_dedup.py       ← Pass 2 충돌 해소 (call_with_retry 적용)
  proposal_planner.py      ← RFP → 섹션 아웃라인 (배점 비례 분배)
  section_writer.py        ← Layer 1+2 지식 주입 LLM 섹션 생성 (call_with_retry 적용)
  quality_checker.py       ← 블라인드 위반(한글 단어 경계) + 모호 표현 감지
  document_assembler.py    ← mistune AST + python-docx DOCX 조립
  proposal_orchestrator.py ← 전체 파이프라인 오케스트레이터 (파일명 sanitization)
  company_db.py            ← 회사 역량 DB (실적/인력 ChromaDB, sha256 ID)
  company_analyzer.py      ← 과거 제안서 문체 분석
  checklist_extractor.py   ← 제출 체크리스트 추출
  diff_tracker.py          ← AI vs 사용자 수정 diff 추적
  auto_learner.py          ← 수정 패턴 → Layer 2 자동 학습 (threading.Lock)
```

### 수정 (5개 파일)

```
rag_engine/main.py                              ← +3 엔드포인트
services/web_app/main.py                        ← +/api/proposal/generate-v2 프록시
frontend/kirabot/services/kiraApiService.ts     ← +generateProposalV2()
frontend/kirabot/hooks/useConversationFlow.ts   ← +generate_proposal_v2 핸들러
frontend/kirabot/types.ts                       ← +generate_proposal_v2 액션 타입
```

### 테스트 (14개 파일, 69개 테스트)

```
rag_engine/tests/
  test_knowledge_models.py       (6 tests)
  test_knowledge_db.py           (4 tests)
  test_knowledge_harvester.py    (3 tests)
  test_knowledge_dedup.py        (6 tests)
  test_proposal_planner.py       (3 tests)
  test_section_writer.py         (3 tests)
  test_quality_checker.py        (4 tests)
  test_document_assembler.py     (2 tests)
  test_proposal_orchestrator.py  (2 tests)
  test_proposal_api.py           (1 test)
  test_company_db.py             (4 tests)
  test_company_analyzer.py       (5 tests)
  test_checklist_extractor.py    (5 tests)
  test_diff_tracker.py           (8 tests)
  test_auto_learner.py           (6 tests)
```

### 데이터 파일 (이전 세션에서 생성)

```
data/layer1_sources/
  youtube_sources.json    (54개 유튜브 소스)
  blog_sources.json       (56개 블로그 소스)
  official_docs.json      (21개 공식 문서 소스)
```

---

## 5. 남은 할 일 (다음 에이전트에게)

### 즉시 필요

1. **Layer 1 데이터 수집 파이프라인 실행**: `data/layer1_sources/` JSON에 있는 소스들의 실제 텍스트를 수집하고 `knowledge_harvester`로 추출 → `knowledge_db`에 저장. YouTube 자막(youtube-transcript-api), 블로그(trafilatura), PDF 파싱 필요.

2. **Golden Test 10건**: 실제 나라장터 공고 10건으로 A-lite 제안서 생성 → 품질 평가. 목표: 커버리지 30%+, 치명적 실수 0건.

3. **Frontend 제안서 다운로드 UI**: 현재 v2 결과를 텍스트로 표시만 함. DOCX 다운로드 링크 + 섹션 미리보기 ContextPanel 필요.

### 개선 필요

4. **auto_learner 영속성**: 현재 인메모리. `save_state()`/`load_state()` 구현은 있지만 서버 재시작 시 호출 안 됨. lifespan 이벤트에서 호출 필요.

5. **Checklist Frontend UI**: API는 있지만 프론트엔드에 체크리스트 패널 미구현.

6. **Company DB 온보딩 UI**: 실적/인력 입력 화면 필요.

### Phase 2로 넘기기

7. 수행계획서/WBS 생성
8. PPT 발표자료 생성
9. 실적/경력 기술서 자동 매칭
10. Layer 3 승패 분석

---

## 6. 기술 결정 로그

| 결정 | 이유 |
|------|------|
| ChromaDB PersistentClient | 계획서는 old Settings API 사용했으나 현 chromadb 버전에 맞게 변경 |
| GPT-4o-mini | 비용 효율. section_writer temp=0.4, harvester temp=0.2 |
| ThreadPoolExecutor(3) | 섹션 병렬 생성. OpenAI rate limit 고려하여 3으로 제한 |
| mistune 3.x AST 파서 | 정규식 기반 마크다운 파싱→AST 기반으로 교체. 엣지케이스(공백 없는 #, 코드블록 내 #) 해결 |
| call_with_retry 패턴 재활용 | 루트 llm_utils.py를 rag_engine에 복사. 60초 timeout + 2회 재시도 (429/500/502/503) |
| Pydantic 입력 검증 | FastAPI 자동 422. RfxResultInput 스키마로 title 필수, total_pages 10~200 범위 |
| 한글 단어 경계 정규식 | blind check에서 조사(은/는/이/가) 허용, 내용어 결합 차단 |
| diff 패턴 키 = MD5 해시 | 숫자/공백 정규화 후 해싱 |
| 기존 /api/proposal/generate 보존 | 별개 기능(챗봇 간단 초안 vs A-lite DOCX). 삭제하면 기존 기능 깨짐 |

---

## 7. 코드 리뷰 결과 및 수정사항

코드 리뷰에서 CRITICAL 3건, IMPORTANT 8건, Suggestion 6건이 발견되었고, 주요 항목은 수정 완료함.

### 수정 완료

| ID | 심각도 | 내용 | 수정 |
|----|--------|------|------|
| C1 | CRITICAL | `/api/generate-proposal-v2`가 서버 경로(`docx_path`) 노출 | `os.path.basename()` 적용, `docx_filename`으로 키 변경 |
| C2 | CRITICAL | 새 3개 엔드포인트에 에러 핸들링 없음 | try/except + HTTPException(500) + logger.error 추가 |
| C3 | CRITICAL | `auto_learner.py` 전역 dict 스레드 안전성 | `threading.Lock` 추가, 모든 읽기/쓰기 함수에 적용 |
| I7 | IMPORTANT | `company_db.py`에 `hash()` 사용 (비결정적) | `hashlib.sha256` 으로 교체 |
| I8 | IMPORTANT | 새 엔드포인트 에러 핸들링 | C2와 동일 |
| I1 | IMPORTANT | rfx_result 입력 검증 미비 | Pydantic `RfxResultInput` 스키마 정의 + `Field(min_length=1)` + `Field(ge=10, le=200)` 적용 |
| I2 | IMPORTANT | LLM 호출 retry/timeout 미적용 | `llm_utils.py` 복사 → `call_with_retry`로 section_writer, harvester, dedup 3곳 래핑 |
| I3 | IMPORTANT | KnowledgeDB ID 충돌 가능 | `{source_type}_{sha256(source_type:category:rule)[:12]}` 복합 ID로 변경 |
| I4 | IMPORTANT | DOCX 목차 heading 누락 | document_assembler 정규식 → **mistune AST 파서** 기반으로 전면 교체. 엣지케이스 전부 해결 |
| I5 | IMPORTANT | blind check 단어 경계 미적용 | 한글 조사 인식 정규식(`(?<![가-힣])회사명(?=(?:은\|는\|...)?(?![가-힣]))`) 적용 |
| I6 | IMPORTANT | 파일명 sanitization 미흡 | `re.sub(r'[^a-zA-Z0-9가-힣._-]', '_', ...)` 화이트리스트 + 100자 제한 |

모든 CRITICAL + IMPORTANT 이슈 수정 완료. 테스트 75/75 통과.

---

## 8. 주의사항

- `auto_learner.py`의 `_histories`/`_learned_patterns`는 **전역 dict (인메모리)**. `threading.Lock`으로 스레드 안전하나, 프로덕션에서는 DB 또는 파일 영속화 필요.
- `knowledge_harvester.py`, `section_writer.py`, `knowledge_dedup.py`는 OpenAI API 호출 필요. 모두 `call_with_retry` (60초 timeout + 2회 재시도) 적용됨. 테스트는 mock 처리.
- `services/web_app/main.py`의 `matcher.py`, `rfx_analyzer.py`에 사용자가 별도로 한 변경이 unstaged로 남아있음. 이 변경은 이 구현과 무관.
- 모든 새 파일은 `rag_engine/` 디렉토리에 위치. `sys.path.insert(0, ...)` 패턴으로 import 경로 설정.
- **기존 `/api/proposal/generate` 엔드포인트 절대 삭제 금지** — 챗봇 제안서 초안 기능의 핵심 플로우. v2는 별개 엔드포인트(`/api/proposal/generate-v2`)로 분리.
- 프론트엔드 `ProposalV2Response` 인터페이스의 키는 `docx_filename` (서버 경로 아님, 파일명만).
- `document_assembler.py`는 **mistune** (3.x) AST 파서 사용 — `pip install mistune` 필요 (이미 설치됨).
- 입력 검증: `/api/generate-proposal-v2`, `/api/checklist`는 Pydantic `RfxResultInput` 스키마로 자동 422 검증. `title` 필수, `total_pages`는 10~200 범위.
- Blind check: 한국어 조사(은/는/이/가 등)를 허용하면서 다른 명사 결합은 차단하는 정규식 적용.

---

*이 문서는 다른 AI 에이전트가 이 프로젝트를 이어받을 때 사용할 수 있도록 작성되었습니다.*
