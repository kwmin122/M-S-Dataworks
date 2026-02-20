# 범용 RAG 파이프라인 설계 문서

작성일: 2026-02-19
목표: 63.6% → 95%+ 정확도. **특정 문서/어휘 하드코딩 없이** 어떤 회사+RFx 조합에도 일관되게 동작하는 범용 파이프라인.

---

## 설계 원칙

1. **하드코딩 금지**: 특정 금액·기관명·어휘를 코드에 직접 넣지 않는다. 스키마+연산자로 표현한다.
2. **구조적 해결 우선**: 프롬프트 땜질이 아닌 데이터 모델 강화.
3. **Fail-safe**: 파싱 실패·모호한 표현 → SKIP → LLM fallback. 강제 미충족 금지.
4. **하위 호환**: 기존 API 시그니처 유지. 신규 필드는 optional+default.
5. **TDD**: 실패 테스트 먼저 작성 후 구현.

---

## 핵심 진단

| 계층 | 현재 문제 | 해결 방향 |
|------|---------|---------|
| chat_router.py | ALLOW 화이트리스트 키워드 → 특정 어휘 종속 | **변경 없음** (LLM이 프로덕션에서 올바르게 분류). 테스트만 수정. |
| rfx_analyzer.py | `detail: str` 자유 문자열 → 숫자 조건 유실 | `constraints: list[RFxConstraint]` 구조화 필드 추가 |
| matcher.py | generic LLM 판단 → 19.8억 vs 20억 재현 불가 | ConstraintEvaluator 결정론 비교 레이어 추가 |
| engine.py | 순수 벡터 검색 → 숫자/코드 희석 | BM25+벡터 RRF 하이브리드 (opt-in 플래그) |
| 평가 | 수동 더미 의존 → 다회사 검증 불가 | 범용 xlsx 평가 파이프라인 |

---

## 섹션 1: 데이터 모델 (`rfx_analyzer.py`)

### RFxConstraint

```python
from typing import Literal
from dataclasses import dataclass, field
from enum import Enum

ConstraintOp = Literal[">=", ">", "<=", "<", "==", "!=", "in", "not_in"]
ConstraintValue = float | bool | str | list[str]

class ConstraintMetric(str, Enum):
    CONTRACT_AMOUNT     = "contract_amount"      # 건당 20억 이상
    PROJECT_COUNT       = "project_count"        # 2건 이상
    HEADCOUNT           = "headcount"            # 10명 이상
    PERIOD_YEARS        = "period_years"         # 최근 3년 이내 (명확한 경우만)
    COMPLETION_REQUIRED = "completion_required"  # 완료된 실적만 (bool)
    CERT_GRADE          = "cert_grade"           # 기사 이상 (str)
    CUSTOM              = "CUSTOM"               # 파싱 불가 → LLM fallback

@dataclass
class RFxConstraint:
    metric: str           # ConstraintMetric 값 또는 "CUSTOM"
    op: ConstraintOp
    value: ConstraintValue
    unit: str = ""        # KRW_100M | headcount | year | ""
    raw: str = ""         # 원문 구절 그대로 (추정/재서술 금지)
```

### RFxRequirement 변경 (하위 호환)

```python
@dataclass
class RFxRequirement:
    category: str
    description: str
    is_mandatory: bool
    detail: str = ""                                      # 기존 유지
    constraints: list[RFxConstraint] = field(default_factory=list)  # 신규 (optional)
```

**규칙**:
- `constraints`는 JSON schema에서 `required`로 강제. 파싱 불가 시 `[]`.
- `detail`은 항상 병행 유지 → fallback 안전망.
- 잘못된 개별 constraint → 전체 실패 아닌 해당 항목만 `CUSTOM`으로 치환.

---

## 섹션 2: rfx_analyzer 추출 (`rfx_analyzer.py`)

### JSON schema 확장

`_build_extraction_prompt()`의 자격요건 스키마에 `constraints` 배열 추가:

```json
{
  "분류": "실적요건",
  "요건": "공공기관 SI 수행실적 2건 이상",
  "필수여부": "필수",
  "상세": "최근 3년간, 건당 20억원 이상, 완료된 실적만 인정, 진행 중 불가",
  "constraints": [
    {"metric": "project_count",        "op": ">=",  "value": 2,    "unit": "",         "raw": "2건 이상"},
    {"metric": "contract_amount",      "op": ">=",  "value": 20.0, "unit": "KRW_100M", "raw": "건당 20억원 이상"},
    {"metric": "period_years",         "op": "<=",  "value": 3,    "unit": "year",     "raw": "최근 3년간"},
    {"metric": "completion_required",  "op": "==",  "value": true, "unit": "",         "raw": "완료된 실적만 인정"}
  ]
}
```

`value` JSON schema: `number | boolean | string | array[string]` 모두 허용.

### 프롬프트 추출 지침 (도메인 공통, 문서 비종속)

```
constraints 추출 규칙:
- 금액      → contract_amount, 억원 단위(KRW_100M)로 정규화
- 건수/명수  → project_count / headcount, 정수
- 기간      → period_years (최근 N년처럼 명확한 경우만), 애매하면 CUSTOM
- 완료여부   → completion_required, boolean
- 등급/자격  → cert_grade, 문자열
- 파싱불가   → metric: "CUSTOM", raw에 원문 그대로 보존
- raw 필드   → 반드시 원문 구절 그대로 (추정·재서술 금지)
- 조건 없음  → constraints: []  (키는 항상 출력, required)
```

---

## 섹션 3: ConstraintEvaluator (`matcher.py`)

### 내부 신호 타입

```python
from typing import Literal, Any
from dataclasses import dataclass

@dataclass
class ConstraintEvalResult:
    outcome: Literal["PASS", "FAIL", "SKIP"]
    reason: str = ""
    observed_value: Any = None

AggregateOutcome = Literal["DETERMINED_MET", "DETERMINED_NOT_MET", "FALLBACK_NEEDED"]
```

### 집계 규칙 (`_match_single_requirement` 근처)

```
constraints = []         → FALLBACK_NEEDED (기존 _judge_with_llm 경로)
FAIL ≥ 1                → DETERMINED_NOT_MET  (LLM 미호출)
전부 PASS                → DETERMINED_MET     (LLM 미호출)
SKIP ≥ 1 + FAIL = 0     → FALLBACK_NEEDED     (LLM fallback 후 최종 판정)
CUSTOM metric            → 항상 SKIP (강제 미충족 금지, fallback 경로)
```

### CompanyFactNormalizer (regex 기반, LLM 미호출)

```python
# 금액: 20억, 2,000,000,000, 20억원 → 모두 KRW_100M float
AMOUNT_PATTERNS = [
    r"(\d+(?:\.\d+)?)\s*억\s*원?",      # N억원 → N
    r"(\d[\d,]+)\s*원",                  # N,NNN,NNN원 → /1억
]
# 완료여부: 완료 vs 진행중 충돌 → SKIP
COMPLETION_POSITIVE = ["완료", "납품완료", "종료", "준공"]
COMPLETION_NEGATIVE = ["진행 중", "수행 중", "예정", "미완료"]
# 양쪽 모두 존재 → SKIP (충돌 표현)

# 파싱 실패 → None → 해당 constraint SKIP (강제 미충족 아님)
```

### DeterministicComparator

```python
# constraint: {metric: contract_amount, op: >=, value: 20.0, unit: KRW_100M}
# company_fact: 19.8
# → 19.8 >= 20.0 → False → ConstraintEvalResult(outcome="FAIL", observed_value=19.8)

# 경계값 포함: >= 20.0 with company=20.0 → PASS
# 모호한 표현 파싱 실패 → SKIP
```

---

## 섹션 4: BM25+벡터 하이브리드 (`engine.py`)

### 핵심 변경 (보정 반영)

```python
class RAGEngine:
    def __init__(self, ..., hybrid_enabled: bool | None = None):
        # 인스턴스 설정 (테스트 주입 가능)
        self.hybrid_enabled = (
            hybrid_enabled
            if hybrid_enabled is not None
            else os.getenv("RAG_HYBRID_ENABLED", "0") == "1"
        )
        self._bm25: BM25Okapi | None = None
        self._bm25_entries: list[dict] = []  # {id, doc, metadata}
        self._bm25_dirty: bool = False

    def add_document(self, file_path: str) -> int:
        ...  # 기존 로직
        self._bm25_dirty = True  # ← add_document 경로도 반드시

    def add_text_directly(self, ...):
        ...  # 기존 로직
        self._bm25_dirty = True  # ← add_text_directly 경로도 반드시

    def _rebuild_bm25(self) -> None:
        # ids는 include 밖에서 읽음 (include는 documents/metadatas만)
        results = self.collection.get(include=["documents", "metadatas"])
        ids = results.get("ids") or []        # ids는 기본 반환 필드로 읽기
        docs = results.get("documents") or []
        metas = results.get("metadatas") or []
        self._bm25_entries = [
            {"id": id_, "doc": doc, "metadata": meta}
            for id_, doc, meta in zip(ids, docs, metas)
        ]
        if docs:
            self._bm25 = BM25Okapi([d.split() for d in docs])
        self._bm25_dirty = False

    def search(self, query: str, top_k: int = 5,
               filter_metadata: dict | None = None) -> list[SearchResult]:
        # 기존 시그니처 완전 유지 (hybrid 파라미터 제거)
        if self.hybrid_enabled:
            # _bm25 없거나 dirty면 rebuild (최초 하이브리드 빌드 보장)
            if self._bm25 is None or self._bm25_dirty:
                self._rebuild_bm25()
            return self._search_hybrid(query, top_k, filter_metadata)
        return self._search_vector(query, top_k, filter_metadata)
```

### filter_metadata 동등성

```python
def _search_hybrid(self, query, top_k, filter_metadata):
    # BM25 후보도 벡터와 동일한 filter_metadata 적용 (동등성 보장)
    candidates = [
        e for e in self._bm25_entries
        if self._matches_filter(e["metadata"], filter_metadata)
    ]
    # RRF: BM25 순위 + 벡터 순위 → score = Σ 1/(60 + rank_i)
    # ID 기준 병합 (문서 ID 정합성 보장)
```

**기본값**: `RAG_HYBRID_ENABLED=0` (기존 동작 완전 유지). 단계적 opt-in.

---

## 섹션 5: 테스트 전략 (TDD)

### Phase A — ConstraintEvaluator 단위 테스트 (`tests/test_constraint_evaluator.py`)

```python
# 경계값 비교
assert eval(contract_amount >= 20.0, company=20.0).outcome == "PASS"  # 경계 포함
assert eval(contract_amount >= 20.0, company=19.8).outcome == "FAIL"

# SKIP 케이스
assert eval(CUSTOM, ...).outcome == "SKIP"
assert eval(period_years, context="약 3년 전후").outcome == "SKIP"  # 모호

# 집계
assert aggregate([PASS, PASS]) == "DETERMINED_MET"
assert aggregate([PASS, FAIL]) == "DETERMINED_NOT_MET"  # FAIL 우선
assert aggregate([PASS, SKIP]) == "FALLBACK_NEEDED"     # SKIP → fallback
assert aggregate([])           == "FALLBACK_NEEDED"     # 빈 → 기존 경로
```

### Phase B — rfx_analyzer 추출 (`tests/test_rfx_analyzer_constraints.py`)

```python
# LLM mock → JSON schema 검증
# "건당 20억원 이상, 최근 3년간, 완료된 실적만" → constraints 3개 추출
# constraints 키 항상 존재 (빈 배열이라도)
# raw 필드 = 원문 구절 (재서술 없음)
```

### Phase C — 라우터 테스트 수정 (`tests/test_chat_router.py`)

```python
# 기존 no-key 테스트 → _build_prefilter_decision() 직접 테스트로 교체
# LLM 분기 → _classify_intent_with_llm mock + 더미 api_key
# chat_router.py:286 fallback ASK_CLARIFY 변경 없음 (fail-safe 유지)
```

### Phase D — BM25 회귀 테스트 (`tests/test_hybrid_search.py`)

```python
# hybrid_enabled=False → 기존 search() 완전 동일 동작
# hybrid_enabled=True  → target_doc in results[:top_k] 확인
# 순위 검증: baseline_rank >= hybrid_rank (개선 또는 동등, 고정 순위 아님 → flaky 방지)
```

---

## 섹션 6: 범용 평가 프레임워크

### 공유 핵심 함수 (`evaluator/accuracy.py` 신규)

`run_accuracy_eval.py`와 `tests/test_evaluation_accuracy.py`가 **동일 함수 공유** (로직 드리프트 방지):

```python
@dataclass
class EvalReport:
    file: str
    total: int
    passes: int
    fails: int
    skipped: int      # J열 빈값·오탈자 카운트
    accuracy: float   # passes / (total - skipped), 분모 0이면 0.0
    threshold: float
    passed: bool      # 분모 0이면 False

def evaluate_xlsx(xlsx_path: Path, threshold: float = 0.90) -> EvalReport:
    """
    헤더명 우선 컬럼 매핑, 없으면 A/B/C/D/E/J 인덱스 fallback.
    J열: "PASS"/"FAIL" 외 빈값·오탈자 → skip으로 집계.
    분모(total - skipped) == 0 → accuracy=0.0, passed=False.
    """
```

### `scripts/run_accuracy_eval.py`

```
사용법:
  python scripts/run_accuracy_eval.py --xlsx testdata/eval_default.xlsx
  python scripts/run_accuracy_eval.py --batch testdata/eval_files/ --threshold 0.90
  python scripts/run_accuracy_eval.py --out reports/accuracy_$(date +%Y%m%d).json

배치 종료 규칙:
  - 파일별 결과 + 전체 aggregate 출력
  - any(file_accuracy < threshold) → exit(1)
```

### `tests/test_evaluation_accuracy.py`

```python
# EVAL_XLSX 환경변수로 파일 교체 가능 (범용성)
# 파일 없음 → pytest.skip()
# J열 판정 없음 → pytest.skip()
# skipped 카운트 리포트 포함
# accuracy >= threshold → assert
```

---

## 구현 우선순위

| Phase | 내용 | 완료 기준 |
|-------|------|---------|
| **P0** | RFxConstraint dataclass + rfx_analyzer JSON schema 확장 | `py_compile` OK, constraints 키 항상 출력 |
| **P1** | ConstraintEvaluator (CompanyFactNormalizer + DeterministicComparator) | `test_constraint_evaluator.py` 전부 PASS |
| **P2** | matcher `_match_single_requirement` 집계 로직 통합 | `test_matcher_detail_rules.py` PASS, 기존 매처 테스트 회귀 없음 |
| **P3** | 라우터 테스트 수정 (no-key → 직접/mock) | `test_chat_router.py` 전부 PASS |
| **P4** | BM25 하이브리드 engine (opt-in) | `test_hybrid_search.py` PASS, `RAG_HYBRID_ENABLED=0` 회귀 없음 |
| **P5** | 범용 평가 파이프라인 | `run_accuracy_eval.py` 실행, 베이스라인 측정 |
| **P6** | 전체 정확도 검증 | `test_evaluation_accuracy.py` ≥ 90% |

---

## 검증 체크리스트

- [ ] `pytest tests/test_constraint_evaluator.py` — 경계값/SKIP/집계 전부 PASS
- [ ] `pytest tests/test_chat_router.py` — 기존 라우터 회귀 없음
- [ ] `pytest tests/test_matcher_consortium_rule.py` — 컨소시엄 규칙 회귀 없음
- [ ] `python scripts/run_accuracy_eval.py --xlsx testdata/eval_default.xlsx` — 베이스라인 측정
- [ ] `RAG_HYBRID_ENABLED=0` 환경에서 기존 search() 동일 동작
- [ ] "배고파" → BLOCK_OFFTOPIC (오프토픽 차단 유지)


  1. BM25 토크나이저 규칙 명시
     split() 대신 코드/숫자(SW-2015-034821, 19.8억) 보존되는 토크나이저 함수 사용 여부를 고
     필터 결과가 0건이면 [] 반환(또는 벡터 fallback)으로 명확히 써두세요.
  3. 평가 리포트에 evaluated_count 추가
     evaluated_count = total - skipped를 명시하면 CI 해석이 더 명확해집니다.
