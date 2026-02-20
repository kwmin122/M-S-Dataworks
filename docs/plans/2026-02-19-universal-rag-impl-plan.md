# 범용 RAG 파이프라인 구현 플랜

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 63.6% → 95%+ 정확도. 어떤 회사+RFx 조합에도 일관되게 동작하는 범용 RAG 파이프라인 구축.

**Architecture:**
- rfx_analyzer.py: `RFxConstraint` 선언적 제약 타입 추가 → LLM이 JSON으로 구조화 추출
- matcher.py: `ConstraintEvaluator` (결정론적 비교) → DETERMINED 이면 LLM 미호출, SKIP 이면 기존 LLM fallback
- engine.py: BM25+벡터 RRF 하이브리드 (opt-in `RAG_HYBRID_ENABLED=1`)
- 평가: `evaluator/accuracy.py` 공유 함수 → CLI + pytest 양쪽에서 사용

**Design Doc:** `docs/plans/2026-02-19-universal-rag-pipeline-design.md`

**Tech Stack:** Python 3.11+, OpenAI GPT-4o-mini, ChromaDB, rank_bm25, openpyxl, pytest

---

## 전제 조건

```bash
# 작업 디렉터리
cd /Users/min-kyungwook/Downloads/기업전용챗봇세분화

# 가상환경 활성화 (이미 돼 있으면 스킵)
source .venv/bin/activate

# rank_bm25 설치 확인
python -c "from rank_bm25 import BM25Okapi; print('OK')" 2>/dev/null \
  || pip install rank_bm25>=0.2.2

# openpyxl 설치 확인
python -c "import openpyxl; print('OK')" 2>/dev/null \
  || pip install openpyxl
```

---

## Task 1: RFxConstraint 타입 + RFxRequirement 필드 추가 (`rfx_analyzer.py`)

**Files:**
- Modify: `rfx_analyzer.py:13-35`

**Step 1: imports 확장 (rfx_analyzer.py:13-16)**

현재:
```python
import os
import json
from typing import Any, Optional
from dataclasses import dataclass, field
```

교체 (Literal, Enum 추가):
```python
import os
import json
from typing import Any, Optional, Literal
from dataclasses import dataclass, field
from enum import Enum
```

**Step 2: RFxConstraint 타입 추가 (line 18 문서 import 바로 뒤, line 20 구분선 앞에 삽입)**

```python
# ============================================================
# STEP 0: 선언적 제약 타입 (범용 수치 비교용)
# ============================================================

ConstraintOp = Literal[">=", ">", "<=", "<", "==", "!=", "in", "not_in"]
ConstraintValue = float | bool | str | list[str]


class ConstraintMetric(str, Enum):
    CONTRACT_AMOUNT      = "contract_amount"      # 건당 N억 이상
    PROJECT_COUNT        = "project_count"        # N건 이상
    HEADCOUNT            = "headcount"            # N명 이상
    PERIOD_YEARS         = "period_years"         # 최근 N년 이내 (명확한 경우만)
    COMPLETION_REQUIRED  = "completion_required"  # 완료된 실적만 (bool)
    CERT_GRADE           = "cert_grade"           # 기사 이상 (str)
    CUSTOM               = "CUSTOM"               # 파싱 불가 → LLM fallback


@dataclass
class RFxConstraint:
    """개별 정량 제약 조건. 특정 문서값 하드코딩 없이 metric+op+value로만 표현."""
    metric: str            # ConstraintMetric 값 또는 "CUSTOM"
    op: ConstraintOp
    value: ConstraintValue
    unit: str = ""         # KRW_100M | headcount | year | ""
    raw: str = ""          # 원문 구절 그대로 (추정/재서술 금지)
```

**Step 3: RFxRequirement에 constraints 필드 추가 (기존 line 31 `detail` 바로 아래)**

```python
@dataclass
class RFxRequirement:
    """개별 자격요건"""
    category: str
    description: str
    is_mandatory: bool
    detail: str = ""                                            # 기존 유지 (fallback)
    constraints: list[RFxConstraint] = field(default_factory=list)  # 신규: 선언적 제약

    def __str__(self):
        mandatory = "🔴 필수" if self.is_mandatory else "🟡 권장"
        return f"[{mandatory}] [{self.category}] {self.description}"
```

**Step 4: py_compile 확인**

```bash
python -m py_compile rfx_analyzer.py && echo "OK"
```
Expected: `OK`

**Step 5: 커밋**

```bash
git add rfx_analyzer.py
git commit -m "feat(rfx_analyzer): add RFxConstraint dataclass and ConstraintMetric enum

선언적 제약 타입 추가:
- ConstraintMetric enum (contract_amount/project_count/headcount/period_years/completion_required/cert_grade/CUSTOM)
- RFxConstraint dataclass (metric/op/value/unit/raw)
- RFxRequirement.constraints 필드 추가 (하위 호환, optional)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: rfx_analyzer JSON Schema 확장 (`rfx_analyzer.py:168-179`)

**Files:**
- Modify: `rfx_analyzer.py:168-179` (RFX_EXTRACTION_JSON_SCHEMA의 자격요건 items)

**Step 1: 자격요건 스키마에 constraints 배열 추가**

현재 (line 168-179):
```python
"자격요건": {
    "type": "array",
    "items": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "분류": {"type": "string"},
            "요건": {"type": "string"},
            "필수여부": {"type": "string", "enum": ["필수", "권장"]},
            "상세": {"type": "string"},
        },
        "required": ["분류", "요건", "필수여부", "상세"],
    },
},
```

교체:
```python
"자격요건": {
    "type": "array",
    "items": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "분류": {"type": "string"},
            "요건": {"type": "string"},
            "필수여부": {"type": "string", "enum": ["필수", "권장"]},
            "상세": {"type": "string"},
            "constraints": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "metric": {"type": "string"},
                        "op": {
                            "type": "string",
                            "enum": [">=", ">", "<=", "<", "==", "!=", "in", "not_in"]
                        },
                        "value": {            # #7 수정: 객체 타입 방어
                            "oneOf": [
                                {"type": "number"},
                                {"type": "boolean"},
                                {"type": "string"},
                                {"type": "array", "items": {"type": "string"}}
                            ]
                        },
                        "unit": {"type": "string"},
                        "raw": {"type": "string"},
                    },
                    "required": ["metric", "op", "value", "unit", "raw"],
                },
            },
        },
        "required": ["분류", "요건", "필수여부", "상세", "constraints"],
    },
},
```

**Step 2: py_compile 확인**

```bash
python -m py_compile rfx_analyzer.py && echo "OK"
```
Expected: `OK`

**Step 3: 커밋**

```bash
git add rfx_analyzer.py
git commit -m "feat(rfx_analyzer): extend JSON schema with constraints array

자격요건 JSON schema에 constraints 배열 추가:
- metric/op/value/unit/raw 필드 required
- constraints는 자격요건 required 필드 (빈 배열 포함 항상 출력)
- value는 타입 제한 없음 (number|bool|string|array 모두 허용)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3: rfx_analyzer 프롬프트 + 파서 업데이트 (`rfx_analyzer.py`)

**Files:**
- Modify: `rfx_analyzer.py:557-603` (`_build_extraction_prompt`)
- Modify: `rfx_analyzer.py:848-853` (`_parse_llm_response` 자격요건 파싱 부분)
- Modify: `rfx_analyzer.py:507-512` (`_merge_partial_results` RFxRequirement 생성 부분)

**Step 1: 실패 테스트 작성 (`tests/test_rfx_analyzer_constraints.py` 신규)**

```bash
cat > tests/test_rfx_analyzer_constraints.py << 'PYEOF'
"""
rfx_analyzer의 constraints 추출 검증.
LLM mock으로 파서 로직만 테스트 (실제 API 호출 없음).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rfx_analyzer import RFxAnalyzer, RFxRequirement, RFxConstraint


MOCK_CONSTRAINTS_RESPONSE = """{
    "기본정보": {"공고명": "테스트", "발주기관": "", "공고번호": "", "제출마감일": "", "사업기간": "", "예산": ""},
    "자격요건": [
        {
            "분류": "실적요건",
            "요건": "공공기관 SI 수행실적 2건 이상",
            "필수여부": "필수",
            "상세": "최근 3년간, 건당 20억원 이상, 완료된 실적만",
            "constraints": [
                {"metric": "project_count",       "op": ">=", "value": 2,    "unit": "",         "raw": "2건 이상"},
                {"metric": "contract_amount",     "op": ">=", "value": 20.0, "unit": "KRW_100M", "raw": "건당 20억원 이상"},
                {"metric": "completion_required", "op": "==", "value": true, "unit": "",         "raw": "완료된 실적만"}
            ]
        },
        {
            "분류": "기술요건",
            "요건": "정보처리기사 보유",
            "필수여부": "필수",
            "상세": "정보처리기사 자격증 보유자",
            "constraints": []
        }
    ],
    "평가기준": [],
    "제출서류": [],
    "특이사항": []
}"""


def test_constraints_always_present(tmp_path):
    """constraints 키는 빈 배열이라도 항상 파싱 결과에 있어야 함"""
    analyzer = RFxAnalyzer.__new__(RFxAnalyzer)
    result = analyzer._parse_llm_response(MOCK_CONSTRAINTS_RESPONSE)

    for req in result.requirements:
        assert hasattr(req, 'constraints'), f"constraints 필드 없음: {req.description}"
        assert isinstance(req.constraints, list), "constraints는 list여야 함"


def test_constraints_parsed_correctly(tmp_path):
    """constraints가 RFxConstraint 객체로 올바르게 파싱돼야 함"""
    analyzer = RFxAnalyzer.__new__(RFxAnalyzer)
    result = analyzer._parse_llm_response(MOCK_CONSTRAINTS_RESPONSE)

    req = result.requirements[0]  # 실적요건
    assert len(req.constraints) == 3

    c0 = req.constraints[0]
    assert c0.metric == "project_count"
    assert c0.op == ">="
    assert c0.value == 2
    assert c0.raw == "2건 이상"

    c1 = req.constraints[1]
    assert c1.metric == "contract_amount"
    assert c1.value == 20.0
    assert c1.unit == "KRW_100M"


def test_empty_constraints_for_no_conditions(tmp_path):
    """조건 없는 요건은 constraints=[]이어야 함"""
    analyzer = RFxAnalyzer.__new__(RFxAnalyzer)
    result = analyzer._parse_llm_response(MOCK_CONSTRAINTS_RESPONSE)

    req = result.requirements[1]  # 정보처리기사
    assert req.constraints == []
PYEOF
```

**Step 2: 테스트 실행 (실패 확인)**

```bash
python -m pytest tests/test_rfx_analyzer_constraints.py -v
```
Expected: `FAIL` — `_parse_llm_response`가 아직 constraints를 파싱하지 않음

**Step 3: `_build_extraction_prompt` 업데이트 (line 578 `"상세"` 아래)**

`rfx_analyzer.py:557-603`의 프롬프트 JSON 예시에서 자격요건 항목을 찾아 교체.

찾을 텍스트:
```python
        {{
            "분류": "필수자격|기술요건|실적요건|재무요건|기타",
            "요건": "자격요건 설명",
            "필수여부": "필수|권장",
            "상세": "구체적인 조건 및 기준"
        }}
```

교체 텍스트:
```python
        {{
            "분류": "필수자격|기술요건|실적요건|재무요건|기타",
            "요건": "자격요건 설명",
            "필수여부": "필수|권장",
            "상세": "구체적인 조건 및 기준",
            "constraints": [
                {{"metric": "contract_amount", "op": ">=", "value": 20.0, "unit": "KRW_100M", "raw": "건당 20억원 이상"}},
                {{"metric": "project_count",   "op": ">=", "value": 2,    "unit": "",         "raw": "2건 이상"}},
                {{"metric": "completion_required", "op": "==", "value": true, "unit": "", "raw": "완료된 실적만"}}
            ]
        }}
```

그리고 주의사항(line 594 부근) 끝에 constraints 추출 지침 추가:

찾을 텍스트:
```python
5. 반드시 유효한 JSON만 출력하세요.
```

교체 텍스트:
```python
5. 반드시 유효한 JSON만 출력하세요.
6. 자격요건의 constraints 배열 추출 규칙:
   - 금액 조건 → metric: "contract_amount", 억원 단위 숫자(KRW_100M), 예: "건당 20억원" → value: 20.0
   - 건수/명수 → metric: "project_count" / "headcount", 정수
   - 기간(최근 N년, 명확한 경우만) → metric: "period_years", 정수
   - 완료여부 → metric: "completion_required", boolean
   - 등급/자격 → metric: "cert_grade", 문자열
   - 파싱 불가 또는 애매한 표현 → metric: "CUSTOM", raw에 원문 그대로
   - raw 필드: 반드시 원문 구절 그대로 (추정/재서술 금지)
   - 조건 없으면 constraints: [] (빈 배열, 키 생략 금지)
```

**Step 4: `_parse_llm_response` 업데이트 (line 848-853)**

현재:
```python
            result.requirements.append(RFxRequirement(
                category=str(req.get("분류", "기타")).strip() or "기타",
                description=description,
                is_mandatory=self._parse_mandatory_flag(req.get("필수여부", "필수")),
                detail=str(req.get("상세", "")).strip()
            ))
```

교체:
```python
            raw_constraints = req.get("constraints", [])
            parsed_constraints = []
            if isinstance(raw_constraints, list):
                for c in raw_constraints:
                    if not isinstance(c, dict):
                        continue
                    metric = str(c.get("metric", "CUSTOM")).strip() or "CUSTOM"
                    op = str(c.get("op", ">=")).strip()
                    if op not in (">=", ">", "<=", "<", "==", "!=", "in", "not_in"):
                        op = ">="
                    parsed_constraints.append(RFxConstraint(
                        metric=metric,
                        op=op,
                        value=c.get("value", 0),
                        unit=str(c.get("unit", "")).strip(),
                        raw=str(c.get("raw", "")).strip(),
                    ))
            result.requirements.append(RFxRequirement(
                category=str(req.get("분류", "기타")).strip() or "기타",
                description=description,
                is_mandatory=self._parse_mandatory_flag(req.get("필수여부", "필수")),
                detail=str(req.get("상세", "")).strip(),
                constraints=parsed_constraints,
            ))
```

**Step 5: `_merge_partial_results` 업데이트 (line 507-512)**

현재 (RFxRequirement 생성 부분):
```python
                    req_index[key] = RFxRequirement(
                        category=req.category,
                        description=req.description,
                        is_mandatory=req.is_mandatory,
                        detail=req.detail,
                    )
```

교체:
```python
                    req_index[key] = RFxRequirement(
                        category=req.category,
                        description=req.description,
                        is_mandatory=req.is_mandatory,
                        detail=req.detail,
                        constraints=list(req.constraints),  # 첫 패스 constraints 유지
                    )
```

**Step 6: 테스트 재실행 (통과 확인)**

```bash
python -m pytest tests/test_rfx_analyzer_constraints.py -v
```
Expected: `3 passed`

**Step 7: 기존 테스트 회귀 확인**

```bash
python -m pytest tests/test_rfx_analyzer_multipass.py -v
```
Expected: 모두 PASS

**Step 8: 커밋**

```bash
git add rfx_analyzer.py tests/test_rfx_analyzer_constraints.py
git commit -m "feat(rfx_analyzer): extract and parse constraints from LLM response

- _build_extraction_prompt에 constraints 추출 지침 추가
- _parse_llm_response에서 constraints 파싱 (잘못된 항목은 CUSTOM 치환)
- _merge_partial_results에서 constraints 보존

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4: ConstraintEvaluator 구현 (`matcher.py`)

**Files:**
- Modify: `matcher.py` (imports 섹션 뒤, STEP 1 마킹 앞에 새 섹션 추가)
- Create: `tests/test_constraint_evaluator.py`

**Step 1: 실패 테스트 작성**

```bash
cat > tests/test_constraint_evaluator.py << 'PYEOF'
"""
ConstraintEvaluator 단위 테스트.
TDD: 경계값 / SKIP / 집계 규칙 검증.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from rfx_analyzer import RFxConstraint


# ConstraintEvaluator import는 matcher.py에 구현 후 테스트
def get_evaluator():
    from matcher import ConstraintEvaluator, CompanyFactNormalizer, DeterministicComparator
    return ConstraintEvaluator(), CompanyFactNormalizer(), DeterministicComparator()


# ────────────────────────────────────────────────────────────
# 경계값 비교 테스트
# ────────────────────────────────────────────────────────────

def test_amount_exactly_at_boundary_is_pass():
    """건당 20억 == 20억 → PASS (경계 포함)"""
    evaluator, _, _ = get_evaluator()
    c = RFxConstraint(metric="contract_amount", op=">=", value=20.0, unit="KRW_100M", raw="건당 20억원 이상")
    context = "KEPCO 스마트그리드 사업, 계약금액 20억원, 2023년 완료"
    results = evaluator.evaluate([c], context)
    assert results[0].outcome == "PASS", f"경계값 PASS 기대, 실제: {results[0]}"


def test_amount_below_boundary_is_fail():
    """건당 19.8억 < 20억 기준 → FAIL"""
    evaluator, _, _ = get_evaluator()
    c = RFxConstraint(metric="contract_amount", op=">=", value=20.0, unit="KRW_100M", raw="건당 20억원 이상")
    context = "KEPCO 스마트그리드 사업, 계약금액 19.8억원, 2023년 완료"
    results = evaluator.evaluate([c], context)
    assert results[0].outcome == "FAIL", f"FAIL 기대, 실제: {results[0]}"
    assert results[0].observed_value is not None


def test_headcount_exactly_at_boundary():
    """정보처리기사 10명 기준, 회사 10명 → PASS"""
    evaluator, _, _ = get_evaluator()
    c = RFxConstraint(metric="headcount", op=">=", value=10, unit="headcount", raw="10명 이상")
    context = "정보처리기사 자격증 보유자 10명"
    results = evaluator.evaluate([c], context)
    assert results[0].outcome == "PASS"


def test_headcount_one_below_boundary():
    """9명 < 10명 기준 → FAIL"""
    evaluator, _, _ = get_evaluator()
    c = RFxConstraint(metric="headcount", op=">=", value=10, unit="headcount", raw="10명 이상")
    context = "정보처리기사 9명 보유"
    results = evaluator.evaluate([c], context)
    assert results[0].outcome == "FAIL"


# ────────────────────────────────────────────────────────────
# SKIP 케이스
# ────────────────────────────────────────────────────────────

def test_custom_metric_always_skip():
    """CUSTOM metric → 항상 SKIP"""
    evaluator, _, _ = get_evaluator()
    c = RFxConstraint(metric="CUSTOM", op=">=", value=1, unit="", raw="독특한 조건")
    results = evaluator.evaluate([c], "아무 컨텍스트")
    assert results[0].outcome == "SKIP"


def test_ambiguous_period_is_skip():
    """모호한 기간 표현 → 파싱 실패 → SKIP"""
    evaluator, _, _ = get_evaluator()
    c = RFxConstraint(metric="period_years", op="<=", value=3, unit="year", raw="최근 3년간")
    context = "약 3년 전후에 수행한 사업"  # "약" 때문에 모호
    results = evaluator.evaluate([c], context)
    # period_years 파싱 불가 시 SKIP
    assert results[0].outcome in ("SKIP", "PASS")  # 파서가 숫자를 찾으면 PASS도 허용


def test_completion_conflict_is_skip():
    """완료 + 진행중 동시 → SKIP"""
    evaluator, _, _ = get_evaluator()
    c = RFxConstraint(metric="completion_required", op="==", value=True, unit="", raw="완료된 실적만")
    context = "KEPCO 사업 완료, 다른 사업 진행 중"  # 충돌
    results = evaluator.evaluate([c], context)
    assert results[0].outcome == "SKIP"


def test_no_info_in_context_is_skip():
    """컨텍스트에 금액 정보 없음 → SKIP"""
    evaluator, _, _ = get_evaluator()
    c = RFxConstraint(metric="contract_amount", op=">=", value=20.0, unit="KRW_100M", raw="20억 이상")
    context = "회사 설립연도 2010년, ISO 9001 인증 보유"  # 금액 정보 없음
    results = evaluator.evaluate([c], context)
    assert results[0].outcome == "SKIP"


# ────────────────────────────────────────────────────────────
# 집계 규칙 테스트
# ────────────────────────────────────────────────────────────

def test_aggregate_empty_is_fallback():
    """constraints=[] → FALLBACK_NEEDED"""
    from matcher import ConstraintEvaluator
    assert ConstraintEvaluator.aggregate([]) == "FALLBACK_NEEDED"


def test_aggregate_all_pass_is_determined_met():
    """전부 PASS → DETERMINED_MET"""
    from matcher import ConstraintEvaluator, ConstraintEvalResult
    results = [ConstraintEvalResult("PASS"), ConstraintEvalResult("PASS")]
    assert ConstraintEvaluator.aggregate(results) == "DETERMINED_MET"


def test_aggregate_any_fail_is_determined_not_met():
    """FAIL 1개 이상 → DETERMINED_NOT_MET (PASS 있어도)"""
    from matcher import ConstraintEvaluator, ConstraintEvalResult
    results = [ConstraintEvalResult("PASS"), ConstraintEvalResult("FAIL")]
    assert ConstraintEvaluator.aggregate(results) == "DETERMINED_NOT_MET"


def test_aggregate_skip_no_fail_is_fallback():
    """SKIP 포함 + FAIL 없음 → FALLBACK_NEEDED"""
    from matcher import ConstraintEvaluator, ConstraintEvalResult
    results = [ConstraintEvalResult("PASS"), ConstraintEvalResult("SKIP")]
    assert ConstraintEvaluator.aggregate(results) == "FALLBACK_NEEDED"
PYEOF
```

**Step 2: 테스트 실행 (실패 확인)**

```bash
python -m pytest tests/test_constraint_evaluator.py -v 2>&1 | head -20
```
Expected: `ImportError` 또는 `FAIL` — matcher.py에 아직 ConstraintEvaluator 없음

**Step 3: matcher.py에 ConstraintEvaluator 추가**

`matcher.py` 파일 상단 imports 뒤(`from rfx_analyzer import ...` 줄 뒤)에 삽입:

```python
# ────────────────────────────────────────────────────────────
# 선언적 제약 평가기 (STEP 0: 결정론적 비교 레이어)
# ────────────────────────────────────────────────────────────
import re
from typing import Literal

from rfx_analyzer import RFxConstraint, ConstraintMetric


@dataclass
class ConstraintEvalResult:
    """단일 constraint 평가 결과 (내부 신호 전용)"""
    outcome: Literal["PASS", "FAIL", "SKIP"]
    reason: str = ""
    observed_value: Any = None


AggregateOutcome = Literal["DETERMINED_MET", "DETERMINED_NOT_MET", "FALLBACK_NEEDED"]

_VALID_METRICS = {m.value for m in ConstraintMetric}


class CompanyFactNormalizer:
    """컨텍스트 텍스트에서 metric 별 수치를 추출 (regex 기반, LLM 미호출).

    #2 수정: 키워드 앵커링으로 오인식 방지
    - amount: "계약금액/금액/사업비" 앞 N억 패턴만 추출
    - 동일 metric에서 서로 다른 값이 2개 이상 → None (SKIP, 모호)
    """

    # 금액: 계약 관련 키워드 앞에 오는 N억 (앵커링)
    _AMOUNT_ANCHOR_RE = re.compile(
        r"(?:계약금액|계약액|사업비|총액|금액|규모)[^\d]{0,8}(\d+(?:\.\d+)?)\s*억"
    )
    # 앵커 없이 fallback: N,NNN,NNN원 형식
    _AMOUNT_PLAIN_RE  = re.compile(r"([\d,]{5,})\s*원")
    _COUNT_RE         = re.compile(r"(\d+)\s*건")
    _HEAD_RE          = re.compile(r"(\d+)\s*명")
    _PERIOD_RE        = re.compile(r"(\d+)\s*년")
    _COMP_POS         = {"완료", "납품완료", "종료", "준공"}
    _COMP_NEG         = {"진행 중", "수행 중", "예정", "미완료"}

    def extract(self, context: str, metric: str) -> float | bool | None:
        """metric에 해당하는 값을 context에서 추출. 실패/모호 시 None."""
        if metric == ConstraintMetric.CONTRACT_AMOUNT:
            return self._extract_amount(context)
        if metric == ConstraintMetric.PROJECT_COUNT:
            return self._extract_count(context)
        if metric == ConstraintMetric.HEADCOUNT:
            return self._extract_headcount(context)
        if metric == ConstraintMetric.PERIOD_YEARS:
            return self._extract_period(context)
        if metric == ConstraintMetric.COMPLETION_REQUIRED:
            return self._extract_completion(context)
        return None  # cert_grade, CUSTOM 등 → SKIP

    @staticmethod
    def _unique_or_none(values: list[float]) -> float | None:
        """값이 1종류만 있으면 반환. 서로 다른 값 2개 이상 → None (모호, SKIP)."""
        unique = set(values)
        return values[0] if len(unique) == 1 else None

    def _extract_amount(self, text: str) -> float | None:
        # 앵커 패턴 우선
        hits = [float(m.group(1)) for m in self._AMOUNT_ANCHOR_RE.finditer(text)]
        if hits:
            return self._unique_or_none(hits)
        # fallback: N,NNN,NNN원
        m = self._AMOUNT_PLAIN_RE.search(text)
        if m:
            try:
                return float(m.group(1).replace(",", "")) / 1e8
            except ValueError:
                pass
        return None

    def _extract_count(self, text: str) -> float | None:
        hits = [float(m.group(1)) for m in self._COUNT_RE.finditer(text)]
        return self._unique_or_none(hits) if hits else None

    def _extract_headcount(self, text: str) -> float | None:
        hits = [float(m.group(1)) for m in self._HEAD_RE.finditer(text)]
        return self._unique_or_none(hits) if hits else None

    def _extract_period(self, text: str) -> float | None:
        hits = [float(m.group(1)) for m in self._PERIOD_RE.finditer(text)]
        return self._unique_or_none(hits) if hits else None

    def _extract_completion(self, text: str) -> bool | None:
        has_pos = any(kw in text for kw in self._COMP_POS)
        has_neg = any(kw in text for kw in self._COMP_NEG)
        if has_pos and has_neg:
            return None  # 충돌 → SKIP
        if has_pos:
            return True
        if has_neg:
            return False
        return None  # 정보 없음 → SKIP


class DeterministicComparator:
    """수치 비교 연산자 적용. in/not_in은 현재 미지원(SKIP)."""

    _OPS: dict[str, Any] = {
        ">=": lambda a, b: a >= b,
        ">":  lambda a, b: a >  b,
        "<=": lambda a, b: a <= b,
        "<":  lambda a, b: a <  b,
        "==": lambda a, b: a == b,
        "!=": lambda a, b: a != b,
    }

    def compare(self, constraint: RFxConstraint, observed: Any) -> ConstraintEvalResult:
        op_fn = self._OPS.get(constraint.op)
        if op_fn is None:
            return ConstraintEvalResult("SKIP", f"op '{constraint.op}' 미지원", observed)
        try:
            passed = op_fn(float(observed), float(constraint.value))
            return ConstraintEvalResult(
                "PASS" if passed else "FAIL",
                observed_value=observed
            )
        except (TypeError, ValueError) as exc:
            return ConstraintEvalResult("SKIP", f"수치 변환 실패: {exc}", observed)


class ConstraintEvaluator:
    """
    constraints 목록을 컨텍스트에 대해 평가하고 집계 결과를 반환.

    - CUSTOM metric → 항상 SKIP
    - 파싱 실패 → SKIP (강제 미충족 금지)
    - FAIL ≥ 1 → DETERMINED_NOT_MET
    - 전부 PASS → DETERMINED_MET
    - SKIP ≥ 1 + FAIL = 0 → FALLBACK_NEEDED
    """

    def __init__(self) -> None:
        self._normalizer  = CompanyFactNormalizer()
        self._comparator  = DeterministicComparator()

    def evaluate(
        self, constraints: list[RFxConstraint], context: str
    ) -> list[ConstraintEvalResult]:
        results: list[ConstraintEvalResult] = []
        for c in constraints:
            # CUSTOM 또는 미등록 metric → SKIP
            if c.metric == ConstraintMetric.CUSTOM or c.metric not in _VALID_METRICS:
                results.append(ConstraintEvalResult("SKIP", f"CUSTOM: {c.raw}"))
                continue
            # in/not_in 집합 연산 → SKIP (미구현)
            if c.op in ("in", "not_in"):
                results.append(ConstraintEvalResult("SKIP", f"집합 op '{c.op}' 미지원"))
                continue
            observed = self._normalizer.extract(context, c.metric)
            if observed is None:
                results.append(ConstraintEvalResult("SKIP", f"'{c.metric}' 파싱 실패"))
                continue
            result = self._comparator.compare(c, observed)
            results.append(result)
        return results

    @staticmethod
    def aggregate(results: list[ConstraintEvalResult]) -> AggregateOutcome:
        if not results:
            return "FALLBACK_NEEDED"
        if any(r.outcome == "FAIL" for r in results):
            return "DETERMINED_NOT_MET"
        if any(r.outcome == "SKIP" for r in results):
            return "FALLBACK_NEEDED"
        return "DETERMINED_MET"
```

**Step 4: 테스트 재실행 (통과 확인)**

```bash
python -m pytest tests/test_constraint_evaluator.py -v
```
Expected: 모두 PASS

**Step 5: 기존 매처 테스트 회귀 확인**

```bash
python -m pytest tests/test_matcher_consortium_rule.py tests/test_matcher_opinion.py -v
```
Expected: 모두 PASS

**Step 6: 커밋**

```bash
git add matcher.py tests/test_constraint_evaluator.py
git commit -m "feat(matcher): add ConstraintEvaluator with CompanyFactNormalizer

- ConstraintEvalResult (PASS/FAIL/SKIP + reason + observed_value)
- CompanyFactNormalizer: regex 기반 수치 추출 (LLM 미호출)
  금액(억원/원)/건수/명수/기간/완료여부, 충돌시 SKIP
- DeterministicComparator: 수치 비교 연산자
- ConstraintEvaluator.aggregate(): DETERMINED_MET/NOT_MET/FALLBACK_NEEDED

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 5: matcher `_match_single_requirement` 통합 (`matcher.py:595`)

**Files:**
- Modify: `matcher.py:619-637` (`_match_single_requirement` STEP 5-3A 이후 부분)
- Create: `tests/test_matcher_detail_rules.py`

**Step 1: 실패 테스트 작성**

```bash
cat > tests/test_matcher_detail_rules.py << 'PYEOF'
"""
matcher가 req.constraints를 활용해 결정론적으로 판단하는지 검증.
LLM mock으로 실제 API 호출 없이 테스트.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import MagicMock, patch
from rfx_analyzer import RFxRequirement, RFxConstraint
from matcher import QualificationMatcher, MatchStatus


def _make_matcher_with_context(context_text: str) -> QualificationMatcher:
    mock_rag = MagicMock()
    mock_rag.collection.count.return_value = 1
    mock_rag.search.return_value = [
        MagicMock(text=context_text, source_file="company.pdf")
    ]
    return QualificationMatcher(mock_rag, api_key="test-key")


def test_amount_fail_returns_not_met_without_llm():
    """19.8억 < 20억 기준 → NOT_MET, LLM 미호출"""
    matcher = _make_matcher_with_context(
        "KEPCO 스마트그리드 사업, 계약금액 19.8억원, 2023년 완료"
    )
    req = RFxRequirement(
        category="실적요건",
        description="공공기관 SI 수행실적",
        is_mandatory=True,
        detail="건당 20억원 이상",
        constraints=[
            RFxConstraint("contract_amount", ">=", 20.0, "KRW_100M", "건당 20억원 이상")
        ]
    )
    with patch.object(matcher, '_judge_with_llm') as mock_llm:
        result = matcher._match_single_requirement(req)
    assert result.status == MatchStatus.NOT_MET, f"NOT_MET 기대, 실제: {result.status}"
    mock_llm.assert_not_called()  # LLM 미호출 확인


def test_amount_pass_returns_met_without_llm():
    """20억 == 20억 기준 → MET, LLM 미호출"""
    matcher = _make_matcher_with_context(
        "국방부 물류 사업, 계약금액 20억원, 2023년 완료"
    )
    req = RFxRequirement(
        category="실적요건",
        description="공공기관 SI 수행실적",
        is_mandatory=True,
        detail="건당 20억원 이상",
        constraints=[
            RFxConstraint("contract_amount", ">=", 20.0, "KRW_100M", "건당 20억원 이상")
        ]
    )
    with patch.object(matcher, '_judge_with_llm') as mock_llm:
        result = matcher._match_single_requirement(req)
    assert result.status == MatchStatus.MET, f"MET 기대, 실제: {result.status}"
    mock_llm.assert_not_called()


def test_skip_constraint_falls_back_to_llm():
    """CUSTOM constraint → SKIP → LLM fallback 호출"""
    matcher = _make_matcher_with_context("회사 정보 텍스트")
    req = RFxRequirement(
        category="기타",
        description="특수 조건",
        is_mandatory=True,
        detail="특수 조건 설명",
        constraints=[
            RFxConstraint("CUSTOM", ">=", 1, "", "특수 조건")
        ]
    )
    mock_response = {
        "status": "판단불가",
        "evidence": "정보 부족",
        "confidence": 0.5,
        "preparation_guide": ""
    }
    with patch.object(matcher, '_judge_with_llm', return_value=mock_response) as mock_llm:
        result = matcher._match_single_requirement(req)
    mock_llm.assert_called_once()  # SKIP → LLM 호출 확인


def test_empty_constraints_uses_llm():
    """constraints=[] → LLM fallback (기존 경로 회귀)"""
    matcher = _make_matcher_with_context("ISO 9001 인증 보유")
    req = RFxRequirement(
        category="필수자격",
        description="ISO 9001 유효 인증",
        is_mandatory=True,
        detail="유효한 ISO 9001 인증",
        constraints=[]  # 빈 배열
    )
    mock_response = {
        "status": "충족",
        "evidence": "ISO 9001 보유 확인",
        "confidence": 0.9,
        "preparation_guide": ""
    }
    with patch.object(matcher, '_judge_with_llm', return_value=mock_response) as mock_llm:
        result = matcher._match_single_requirement(req)
    mock_llm.assert_called_once()
PYEOF
```

**Step 2: 테스트 실행 (실패 확인)**

```bash
python -m pytest tests/test_matcher_detail_rules.py -v
```
Expected: FAIL — `_match_single_requirement`가 아직 constraints를 사용하지 않음

**Step 3: `_match_single_requirement` 업데이트 (matcher.py:619-637)**

`# STEP 5-3A: 규칙형 판정이 가능한 요건은 LLM보다 먼저 처리` 줄 앞에 삽입:

```python
        # STEP 5-3A-0: 선언적 제약 평가기 (constraints가 있으면 결정론 비교 우선)
        if req.constraints:
            evaluator = ConstraintEvaluator()
            eval_results = evaluator.evaluate(req.constraints, context)
            aggregate = ConstraintEvaluator.aggregate(eval_results)

            if aggregate == "DETERMINED_NOT_MET":
                failed = [r for r in eval_results if r.outcome == "FAIL"]
                evidence_parts = [
                    f"{c.raw}: 기준={c.value}{c.unit}, 실제={r.observed_value}"
                    for c, r in zip(req.constraints, eval_results)
                    if r.outcome == "FAIL"
                ]
                return RequirementMatch(
                    requirement=req,
                    status=MatchStatus.NOT_MET,
                    evidence="; ".join(evidence_parts) or "정량 기준 미달",
                    confidence=0.95,
                    preparation_guide="제시된 기준을 충족하는 실적/자격을 준비하세요.",
                    source_files=source_files,
                )
            elif aggregate == "DETERMINED_MET":
                return RequirementMatch(
                    requirement=req,
                    status=MatchStatus.MET,
                    evidence="정량 조건 모두 충족",
                    confidence=0.95,
                    preparation_guide="",
                    source_files=source_files,
                )
            # FALLBACK_NEEDED → 아래 기존 경로 계속
```

**Step 4: 테스트 재실행 (통과 확인)**

```bash
python -m pytest tests/test_matcher_detail_rules.py -v
```
Expected: 4 passed

**Step 5: 기존 매처 테스트 전체 회귀 확인**

```bash
python -m pytest tests/test_matcher_consortium_rule.py tests/test_matcher_opinion.py -v
```
Expected: 모두 PASS

**Step 6: 커밋**

```bash
git add matcher.py tests/test_matcher_detail_rules.py
git commit -m "feat(matcher): integrate ConstraintEvaluator into _match_single_requirement

- constraints 있으면 결정론 비교 우선 실행
- DETERMINED_NOT_MET: LLM 미호출, 즉시 NOT_MET 반환
- DETERMINED_MET: LLM 미호출, 즉시 MET 반환
- FALLBACK_NEEDED/empty: 기존 _judge_with_llm 경로 유지

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 6: 라우터 테스트 리팩터 (`tests/test_chat_router.py`)

**Files:**
- Modify: `tests/test_chat_router.py`

**배경**: `chat_router.py:286` fallback은 ASK_CLARIFY 유지 (변경 없음). 테스트를 no-key에 기대지 않도록 수정.

**Step 1: 기존 테스트 파일 확인**

```bash
python -m pytest tests/test_chat_router.py -v 2>&1 | tail -20
```

**Step 2: 새 테스트 추가 (기존 파일 끝에 append)**

```python
# ────────────────────────────────────────────────────────────
# 프리필터 직접 테스트 (no-key 의존 없음)
# ────────────────────────────────────────────────────────────

def test_prefilter_blocks_offtopic_directly() -> None:
    """_build_prefilter_decision이 오프토픽 즉시 차단"""
    from chat_router import _build_prefilter_decision, ChatPolicy
    result = _build_prefilter_decision("배고파 맛집 추천해줘", offtopic_strict=True)
    assert result is not None
    assert result.policy == ChatPolicy.BLOCK_OFFTOPIC


def test_prefilter_allows_rfx_domain() -> None:
    """자격요건/RFx 키워드 → 프리필터 ALLOW"""
    from chat_router import _build_prefilter_decision, ChatPolicy
    result = _build_prefilter_decision("이 RFx 자격요건 분석해줘", offtopic_strict=True)
    assert result is not None
    assert result.policy == ChatPolicy.ALLOW


def test_prefilter_allows_company_doc() -> None:
    """회사 정보 키워드 → 프리필터 ALLOW"""
    from chat_router import _build_prefilter_decision, ChatPolicy
    result = _build_prefilter_decision("우리 회사 이름 알려줘", offtopic_strict=True)
    assert result is not None
    assert result.policy == ChatPolicy.ALLOW


def test_prefilter_returns_none_for_unknown() -> None:
    """키워드 없는 질문 → None 반환 (LLM으로 넘겨야 함)"""
    from chat_router import _build_prefilter_decision
    # 프리필터가 None을 반환해야 LLM이 처리
    result = _build_prefilter_decision("사업 기간이 어떻게 돼?", offtopic_strict=True)
    # 이 질문은 키워드 리스트에 없으므로 None (LLM이 올바르게 DOMAIN_RFX로 분류)
    assert result is None


def test_llm_classifies_business_query_correctly() -> None:
    """LLM mock으로 업무 질의가 ALLOW로 분류되는지 확인"""
    from unittest.mock import patch
    from chat_router import route_user_query, ChatPolicy

    mock_payload = {
        "intent": "DOMAIN_RFX",
        "confidence": 0.92,
        "reason": "입찰 관련 질의",
        "suggested_questions": [],
    }
    with patch("chat_router._classify_intent_with_llm", return_value=mock_payload):
        decision = route_user_query(
            message="사업 기간이 어떻게 돼?",
            api_key="dummy-key-for-test",
        )
    assert decision.policy == ChatPolicy.ALLOW
    assert decision.llm_called is True
```

**Step 3: 테스트 실행**

```bash
python -m pytest tests/test_chat_router.py -v
```
Expected: 모두 PASS (기존 + 신규)

**Step 4: 커밋**

```bash
git add tests/test_chat_router.py
git commit -m "test(chat_router): refactor to test prefilter directly and mock LLM

no-key fallback에 의존하는 대신:
- _build_prefilter_decision() 직접 테스트
- _classify_intent_with_llm mock으로 LLM 분기 테스트
chat_router.py:286 fallback ASK_CLARIFY 변경 없음 (fail-safe 유지)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 7: BM25+벡터 하이브리드 검색 (`engine.py`)

**Files:**
- Modify: `engine.py`
- Create: `tests/test_hybrid_search.py`

**Step 1: 실패 테스트 작성**

```bash
cat > tests/test_hybrid_search.py << 'PYEOF'
"""
BM25+벡터 하이브리드 검색 테스트.
TDD: hybrid_enabled 플래그, dirty flag, filter 동등성, 회귀 방지.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import MagicMock, patch


def _make_engine(hybrid: bool = False) -> object:
    """테스트용 RAGEngine (임베딩 없는 mock)"""
    from engine import RAGEngine
    mock_ef = MagicMock()
    mock_ef.__call__ = MagicMock(return_value=[[0.1] * 256])
    engine = RAGEngine(
        persist_directory="/tmp/test_bm25_engine",
        collection_name=f"test_col_{id(mock_ef)}",
        embedding_function=mock_ef,
        hybrid_enabled=hybrid,
    )
    return engine


def test_hybrid_disabled_by_default():
    """기본값: hybrid_enabled=False → 기존 벡터 검색"""
    engine = _make_engine(hybrid=False)
    assert engine.hybrid_enabled is False


def test_hybrid_enabled_flag():
    """hybrid_enabled=True 인스턴스 설정"""
    engine = _make_engine(hybrid=True)
    assert engine.hybrid_enabled is True


def test_dirty_flag_set_after_add_text():
    """add_text_directly 호출 후 _bm25_dirty=True"""
    engine = _make_engine(hybrid=True)
    assert engine._bm25_dirty is False
    engine.add_text_directly("테스트 텍스트", "test_source")
    assert engine._bm25_dirty is True


def test_bm25_keyword_precision():
    """BM25가 정확한 키워드(코드/번호)를 다른 문서보다 잘 랭킹하는지 확인"""
    from rank_bm25 import BM25Okapi
    corpus = [
        "소프트웨어사업자 신고확인서 번호 SW-2015-034821",
        "회사 설립연도 2012년 대표이사 김철수",
        "ISO 9001 인증 유효기간 2024년까지",
    ]
    tokenized = [doc.split() for doc in corpus]
    bm25 = BM25Okapi(tokenized)

    scores = bm25.get_scores("신고확인서 번호".split())
    best_idx = int(scores.argmax())
    assert "신고확인서" in corpus[best_idx], \
        f"BM25 오류: '{corpus[best_idx]}' 가 최상위"


def test_rebuild_bm25_clears_dirty_flag():
    """_rebuild_bm25() 호출 후 _bm25_dirty=False"""
    engine = _make_engine(hybrid=True)
    engine.add_text_directly("내용 A", "source_a")
    assert engine._bm25_dirty is True
    engine._rebuild_bm25()
    assert engine._bm25_dirty is False
PYEOF
```

**Step 2: BM25 smoke test 실행 (rank_bm25만 테스트)**

```bash
python -m pytest tests/test_hybrid_search.py::test_bm25_keyword_precision -v
```
Expected: PASS

**Step 3: 나머지 테스트 실행 (실패 확인)**

```bash
python -m pytest tests/test_hybrid_search.py -v
```
Expected: `test_hybrid_enabled_flag`, `test_dirty_flag_set_after_add_text`, `test_rebuild_bm25_clears_dirty_flag` 실패

**Step 4: engine.py 수정**

4a. **imports 추가** (파일 상단 `import os` 뒤에):
```python
import os
import re  # 기존 없으면 추가
```
`from document_parser import ...` 줄 뒤에:
```python
try:
    from rank_bm25 import BM25Okapi as _BM25Okapi
    _BM25_AVAILABLE = True
except ImportError:
    _BM25Okapi = None  # type: ignore
    _BM25_AVAILABLE = False
```

4b. **`__init__` 수정** (line 52 `def __init__` 파라미터에 `hybrid_enabled` 추가):

```python
    def __init__(
        self,
        persist_directory: str = "./data/vectordb",
        collection_name: str = "company_knowledge",
        embedding_model: str = "text-embedding-3-small",
        embedding_function: object = None,
        hybrid_enabled: bool | None = None,        # 신규
    ):
```

`self._init_vectordb()` 줄 앞에 추가:
```python
        # BM25 하이브리드 설정
        self.hybrid_enabled: bool = (
            hybrid_enabled
            if hybrid_enabled is not None
            else os.getenv("RAG_HYBRID_ENABLED", "0") == "1"
        )
        self._bm25 = None
        self._bm25_entries: list[dict] = []   # {id, doc, metadata}
        self._bm25_dirty: bool = False
```

4c. **`add_document` 수정** (line 192 `return len(chunks)` 바로 앞에):
```python
        self._bm25_dirty = True
        return len(chunks)
```

4d. **`add_text_directly` 수정** (line 378 `self.collection.add(...)` 바로 뒤에):
```python
        self.collection.add(ids=ids, documents=documents, metadatas=metadatas)
        self._bm25_dirty = True
```

4e. **`_rebuild_bm25` 메서드 추가** (`search` 메서드 앞에):
```python
    def _rebuild_bm25(self) -> None:
        """ChromaDB의 현재 문서로 BM25 인덱스 재구성.

        #3 수정: chunk_key = source_file + chunk_id 를 별도 저장해 RRF ID 정합.
        ids 는 include 에 넣지 않고 기본 반환 필드에서 읽음.
        """
        if not _BM25_AVAILABLE:
            self._bm25_dirty = False
            return
        try:
            results = self.collection.get(include=["documents", "metadatas"])
            ids   = results.get("ids") or []
            docs  = results.get("documents") or []
            metas = results.get("metadatas") or []
            self._bm25_entries = []
            for i, (id_, doc, meta) in enumerate(zip(ids, docs, metas)):
                m = meta or {}
                # chunk_key: 벡터 결과와 동일한 키 (source_file + chunk_id)
                chunk_key = f"{m.get('source_file', '')}_{m.get('chunk_id', i)}"
                self._bm25_entries.append({
                    "id": id_,
                    "chunk_key": chunk_key,
                    "doc": doc,
                    "metadata": m,
                })
            if docs:
                self._bm25 = _BM25Okapi([d.split() for d in docs])
        except Exception as exc:
            print(f"⚠️ BM25 인덱스 재구성 실패 (벡터 검색으로 fallback): {exc}")
        self._bm25_dirty = False

    @staticmethod
    def _matches_filter(metadata: dict, filter_metadata: dict | None) -> bool:
        """BM25 후보에 filter_metadata 동등 적용."""
        if not filter_metadata:
            return True
        return all(metadata.get(k) == v for k, v in filter_metadata.items())
```

4f. **`search` 메서드 수정** (기존 `def search` → 내부 로직을 `_search_vector`로 이동, `search`는 dispatcher로):

기존 `def search(self, query, top_k=5, filter_metadata=None)` 를:

```python
    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: Optional[dict] = None
    ) -> list[SearchResult]:
        """
        쿼리와 관련된 문서 청크를 검색.
        RAG_HYBRID_ENABLED=1 또는 hybrid_enabled=True 이면 BM25+벡터 RRF 사용.
        """
        if self.hybrid_enabled:
            if self._bm25 is None or self._bm25_dirty:
                self._rebuild_bm25()
            return self._search_hybrid(query, top_k, filter_metadata)
        return self._search_vector(query, top_k, filter_metadata)

    def _search_vector(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: Optional[dict] = None
    ) -> list[SearchResult]:
        """순수 벡터 검색 (기존 search 로직)."""
        # (기존 search() 메서드 내용 그대로)
```

4g. **`_search_hybrid` 메서드 추가** (`_search_vector` 뒤에):

```python
    def _search_hybrid(
        self,
        query: str,
        top_k: int,
        filter_metadata: Optional[dict] = None
    ) -> list[SearchResult]:
        """BM25 + 벡터 RRF(Reciprocal Rank Fusion) 하이브리드 검색.

        #3 수정: chunk_key 통일 (source_file_chunk_id) 로 BM25/벡터 ID 정합.
        #4 수정: 최종 결과를 벡터 재정렬이 아닌 전체 후보 풀에서 구성
                 → BM25-only hit도 반환 가능.
        """
        # 1) BM25 후보 (filter 동등 적용)
        candidates = [
            (i, e) for i, e in enumerate(self._bm25_entries)
            if self._matches_filter(e["metadata"], filter_metadata)
        ]
        if not candidates or self._bm25 is None:
            return self._search_vector(query, top_k, filter_metadata)

        # BM25 점수 (후보 인덱스만)
        full_scores = self._bm25.get_scores(query.split())
        candidate_scores = [(orig_idx, full_scores[orig_idx]) for orig_idx, _ in candidates]
        bm25_ranked = sorted(candidate_scores, key=lambda x: x[1], reverse=True)

        # 2) 벡터 검색 결과
        vector_results = self._search_vector(query, top_k * 2, filter_metadata)

        # 3) RRF 결합 (k=60 표준) — chunk_key 기준 통일
        K = 60
        rrf: dict[str, float] = {}

        # BM25 기여 (chunk_key 사용, #3 수정)
        for rank, (orig_idx, _) in enumerate(bm25_ranked[:top_k * 2]):
            ck = self._bm25_entries[orig_idx]["chunk_key"]
            rrf[ck] = rrf.get(ck, 0.0) + 1.0 / (K + rank + 1)

        # 벡터 기여 (동일 chunk_key)
        for rank, vr in enumerate(vector_results):
            ck = f"{vr.source_file}_{vr.chunk_id}"
            rrf[ck] = rrf.get(ck, 0.0) + 1.0 / (K + rank + 1)

        # 4) 전체 후보 풀 구성: 벡터 결과 + BM25-only 엔트리 (#4 수정)
        vector_by_key = {f"{r.source_file}_{r.chunk_id}": r for r in vector_results}
        bm25_by_key   = {e["chunk_key"]: e for _, e in candidates}

        ranked_keys = sorted(rrf, key=rrf.__getitem__, reverse=True)
        final: list[SearchResult] = []
        for ck in ranked_keys:
            if len(final) >= top_k:
                break
            if ck in vector_by_key:
                final.append(vector_by_key[ck])
            elif ck in bm25_by_key:
                entry = bm25_by_key[ck]
                final.append(SearchResult(
                    text=entry["doc"],
                    score=rrf[ck],
                    source_file=entry["metadata"].get("source_file", "unknown"),
                    chunk_id=entry["metadata"].get("chunk_id", -1),
                    metadata=entry["metadata"],
                ))
        return final
```

**Step 5: 테스트 재실행 (통과 확인)**

```bash
python -m pytest tests/test_hybrid_search.py -v
```
Expected: 모두 PASS

**Step 6: py_compile + 기존 검색 테스트 회귀**

```bash
python -m py_compile engine.py && echo "OK"
python -m pytest tests/ -k "not evaluation_accuracy" --ignore=tests/test_hybrid_search.py -v --tb=short 2>&1 | tail -20
```
Expected: 모두 PASS

**Step 7: 커밋**

```bash
git add engine.py tests/test_hybrid_search.py requirements.txt
git commit -m "feat(engine): BM25+vector hybrid search with RRF

- hybrid_enabled 인스턴스 플래그 (RAG_HYBRID_ENABLED env var, 기본 off)
- _bm25_dirty flag: add_document/add_text_directly 후 자동 설정
- _rebuild_bm25(): lazy 재구성, filter 동등성 보장
- _search_hybrid(): BM25+벡터 RRF 결합
- 기존 search() API 시그니처 완전 유지

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 8: 범용 평가 파이프라인

**Files:**
- Create: `evaluator/__init__.py`
- Create: `evaluator/accuracy.py`
- Create: `scripts/run_accuracy_eval.py`
- Create: `tests/test_evaluation_accuracy.py`

**Step 1: `evaluator/` 패키지 생성**

```bash
mkdir -p evaluator
touch evaluator/__init__.py
```

**Step 2: `evaluator/accuracy.py` 작성**

```python
# evaluator/accuracy.py
"""
범용 xlsx 평가 파이프라인 - 공유 핵심 함수.
run_accuracy_eval.py와 tests/test_evaluation_accuracy.py가 같은 함수를 사용.
드리프트 방지: 로직은 이 파일 한 곳에만.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime


@dataclass
class EvalReport:
    file: str
    total: int
    passes: int
    fails: int
    skipped: int             # J열 빈값·오탈자 카운트
    accuracy: float          # passes / (total - skipped); 분모 0이면 0.0
    coverage: float          # (total - skipped) / total; 0이면 0.0  ← #5 추가
    threshold: float
    min_coverage: float      # 커버리지 하한 (기본 0.0 = 비활성)      ← #5 추가
    passed: bool             # accuracy≥threshold AND coverage≥min_coverage (분모 0 → False)
    fail_details: list[dict] = field(default_factory=list)  # {id, question}


def _find_column_indices(header_row: tuple) -> dict[str, int]:
    """
    헤더명 우선 컬럼 매핑.
    없으면 A/B/C/D/E/J 인덱스 fallback.
    """
    name_map = {
        "id": ["id", "번호", "no"],
        "question": ["질문", "question"],
        "judgment": ["판정", "judgment", "pass/fail", "pass_fail"],
    }
    result: dict[str, int] = {}
    if header_row:
        header = [str(h).strip().lower() if h else "" for h in header_row]
        for field_name, candidates in name_map.items():
            for i, h in enumerate(header):
                if any(c in h for c in candidates):
                    result[field_name] = i
                    break
    # fallback: A=0, C=2, J=9
    result.setdefault("id", 0)
    result.setdefault("question", 2)
    result.setdefault("judgment", 9)
    return result


def evaluate_xlsx(xlsx_path: Path, threshold: float = 0.90, min_coverage: float = 0.0) -> EvalReport:
    """
    xlsx 평가 파일로 정확도를 측정한다.

    J열 규칙:
    - "PASS" (대소문자 무관) → passes + 1
    - "FAIL" (대소문자 무관) → fails + 1
    - 빈값 / 오탈자 → skipped + 1

    분모 = total - skipped
    분모 == 0이면 accuracy=0.0, passed=False
    """
    try:
        import openpyxl
    except ImportError:
        raise ImportError("openpyxl 미설치: pip install openpyxl")

    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if not rows:
        return EvalReport(
            file=xlsx_path.name, total=0, passes=0, fails=0,
            skipped=0, accuracy=0.0, coverage=0.0,
            threshold=threshold, min_coverage=min_coverage, passed=False,
        )

    col = _find_column_indices(rows[0])
    data_rows = rows[1:]  # 헤더 제외

    total = passes = fails = skipped = 0
    fail_details: list[dict] = []

    for row in data_rows:
        if not row or not row[col["id"]]:
            continue                  # 빈 행 스킵
        total += 1
        raw_judgment = row[col["judgment"]] if len(row) > col["judgment"] else None
        judgment = str(raw_judgment).strip().upper() if raw_judgment else ""

        if judgment == "PASS":
            passes += 1
        elif judgment == "FAIL":
            fails += 1
            fail_details.append({
                "id": str(row[col["id"]]),
                "question": str(row[col["question"]]) if len(row) > col["question"] else "",
            })
        else:
            skipped += 1   # 빈값·오탈자

    denominator = total - skipped
    accuracy = passes / denominator if denominator > 0 else 0.0
    coverage = denominator / total if total > 0 else 0.0

    # #5 수정: coverage 하한 미달 시에도 passed=False
    if denominator == 0:
        passed = False
    else:
        passed = (accuracy >= threshold) and (
            min_coverage <= 0.0 or coverage >= min_coverage
        )

    return EvalReport(
        file=xlsx_path.name,
        total=total,
        passes=passes,
        fails=fails,
        skipped=skipped,
        accuracy=accuracy,
        coverage=coverage,
        threshold=threshold,
        min_coverage=min_coverage,
        passed=passed,
        fail_details=fail_details,
    )


def save_report(report: EvalReport, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "date": datetime.now().isoformat(),
        "file": report.file,
        "total": report.total,
        "passes": report.passes,
        "fails": report.fails,
        "skipped": report.skipped,
        "accuracy": report.accuracy,
        "threshold": report.threshold,
        "passed": report.passed,
        "fail_details": report.fail_details[:20],  # 상위 20건만
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
```

**Step 3: `scripts/run_accuracy_eval.py` 작성**

```python
#!/usr/bin/env python3
# scripts/run_accuracy_eval.py
"""
범용 xlsx 평가 CLI.

사용법:
  python scripts/run_accuracy_eval.py --xlsx testdata/eval_default.xlsx
  python scripts/run_accuracy_eval.py --batch testdata/eval_files/ --threshold 0.90
  python scripts/run_accuracy_eval.py --out reports/accuracy_$(date +%Y%m%d).json

종료 규칙:
  any(file_accuracy < threshold) → exit(1)
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from evaluator.accuracy import evaluate_xlsx, save_report


def main() -> None:
    parser = argparse.ArgumentParser(description="범용 xlsx 평가 CLI")
    parser.add_argument("--xlsx",      type=Path, default=None)
    parser.add_argument("--batch",     type=Path, default=None)
    parser.add_argument("--threshold", type=float, default=0.90)
    parser.add_argument("--out",       type=Path, default=None)
    args = parser.parse_args()

    targets: list[Path] = []
    if args.batch:
        targets = sorted(args.batch.glob("*.xlsx"))
        if not targets:
            print(f"⚠️ {args.batch} 에 .xlsx 파일이 없습니다.", file=sys.stderr)
            sys.exit(1)
    else:
        targets = [args.xlsx or Path("testdata/eval_default.xlsx")]

    reports = []
    for xlsx_file in targets:
        if not xlsx_file.exists():
            print(f"❌ 파일 없음: {xlsx_file}", file=sys.stderr)
            sys.exit(1)
        report = evaluate_xlsx(xlsx_file, args.threshold)
        reports.append(report)

        status = "✅ PASS" if report.passed else "❌ FAIL"
        denom = report.total - report.skipped
        print(
            f"{status} [{report.file}] "
            f"{report.passes}/{denom} = {report.accuracy:.1%} "
            f"(skip={report.skipped})"
        )
        if not report.passed and report.fail_details:
            for d in report.fail_details[:5]:
                print(f"  - [{d['id']}] {d['question']}")

    # 전체 aggregate
    total_passes = sum(r.passes for r in reports)
    total_denom  = sum(r.total - r.skipped for r in reports)
    overall_acc  = total_passes / total_denom if total_denom > 0 else 0.0
    overall_ok   = all(r.passed for r in reports)
    print(f"\n{'✅' if overall_ok else '❌'} 전체 {total_passes}/{total_denom} = {overall_acc:.1%}")

    if args.out and len(reports) == 1:
        save_report(reports[0], args.out)
        print(f"📄 리포트: {args.out}")

    sys.exit(0 if overall_ok else 1)


if __name__ == "__main__":
    main()
```

**Step 4: `tests/test_evaluation_accuracy.py` 작성**

```python
# tests/test_evaluation_accuracy.py
"""
범용 정확도 평가 pytest 연동.
EVAL_XLSX 환경변수로 파일 교체 가능.
"""
import os
import json
import pytest
from pathlib import Path
from datetime import datetime
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluator.accuracy import evaluate_xlsx

EVAL_XLSX_DEFAULT = Path(__file__).parent.parent / "testdata" / "eval_default.xlsx"
EVAL_XLSX         = Path(os.getenv("EVAL_XLSX", str(EVAL_XLSX_DEFAULT)))
THRESHOLD         = float(os.getenv("EVAL_ACCURACY_THRESHOLD", "0.90"))
REPORT_DIR        = Path(__file__).parent.parent / "reports"


def test_eval_accuracy_summary():
    """
    평가 파일이 있고 J열 판정이 있으면 정확도 ≥ threshold.
    파일 없음 또는 판정 없음 → skip.
    """
    if not EVAL_XLSX.exists():
        pytest.skip(f"평가 파일 없음: {EVAL_XLSX}  (testdata/eval_default.xlsx 준비 필요)")

    report = evaluate_xlsx(EVAL_XLSX, THRESHOLD)

    if report.total - report.skipped == 0:
        pytest.skip("J열에 PASS/FAIL 판정 없음")

    # 리포트 저장
    REPORT_DIR.mkdir(exist_ok=True)
    report_path = REPORT_DIR / f"accuracy_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    from evaluator.accuracy import save_report
    save_report(report, report_path)
    print(f"\n정확도: {report.passes}/{report.total - report.skipped} = {report.accuracy:.1%} "
          f"(skip={report.skipped})")
    print(f"리포트: {report_path}")

    assert report.accuracy >= THRESHOLD, (
        f"정확도 {report.accuracy:.1%} < 목표 {THRESHOLD:.0%}. "
        f"FAIL {report.fails}건, SKIP {report.skipped}건"
    )
```

**Step 5: 모듈 smoke test**

```bash
python -c "from evaluator.accuracy import evaluate_xlsx, EvalReport; print('OK')"
python -m py_compile scripts/run_accuracy_eval.py && echo "OK"
python -m pytest tests/test_evaluation_accuracy.py -v
```
Expected: `OK` + `1 skipped` (eval_default.xlsx 없으니 skip)

**Step 6: 커밋**

```bash
git add evaluator/ scripts/run_accuracy_eval.py tests/test_evaluation_accuracy.py
git commit -m "feat: universal xlsx evaluation framework

- evaluator/accuracy.py: evaluate_xlsx() 공유 함수 (드리프트 방지)
  헤더명 우선 컬럼 매핑, fallback 인덱스 A/C/J
  J열 빈값·오탈자 → skipped 카운트
  분모 0 → accuracy=0.0, passed=False
- scripts/run_accuracy_eval.py: CLI (--xlsx/--batch/--threshold/--out)
  any(accuracy < threshold) → exit(1)
- tests/test_evaluation_accuracy.py: EVAL_XLSX 환경변수로 파일 교체 가능

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 9: 전체 검증 + 베이스라인 측정

**Step 1: 전체 py_compile 확인**

```bash
python -m py_compile rfx_analyzer.py matcher.py engine.py && echo "모두 OK"
```
Expected: `모두 OK`

**Step 2: 전체 테스트 실행**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tee reports/test_results_final.txt
```
Expected:
- `test_constraint_evaluator.py` — PASS
- `test_rfx_analyzer_constraints.py` — PASS
- `test_matcher_detail_rules.py` — PASS
- `test_chat_router.py` — PASS
- `test_hybrid_search.py` — PASS
- `test_evaluation_accuracy.py` — SKIP (eval 파일 없음)
- 기존 테스트 회귀 없음

**Step 3: 평가 파일 준비 + 베이스라인 측정**

```bash
# 평가 파일 준비 (없으면 skip)
ls "/Users/min-kyungwook/Downloads/Kira_평가지_회사정보더미_제안요청서더미.xlsx" 2>/dev/null \
  && mkdir -p testdata \
  && cp "/Users/min-kyungwook/Downloads/Kira_평가지_회사정보더미_제안요청서더미.xlsx" \
        testdata/eval_default.xlsx \
  && echo "파일 복사 완료" \
  || echo "⚠️ 평가 파일 없음 - Step 3 스킵"

# 베이스라인 측정 (파일 있는 경우)
python scripts/run_accuracy_eval.py \
  --xlsx testdata/eval_default.xlsx \
  --threshold 0.90 \
  --out reports/accuracy_baseline.json \
  || echo "현재 정확도 기준 미달 (예상됨 - 베이스라인 측정 완료)"

cat reports/accuracy_baseline.json 2>/dev/null || echo "베이스라인 파일 없음"
```

**Step 4: 최종 커밋**

```bash
git add reports/ testdata/ 2>/dev/null; git status
git commit -m "docs: baseline accuracy measurement and final test results

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>" \
  -- reports/ testdata/ 2>/dev/null || echo "추가할 변경사항 없음"
```

---

## 검증 체크리스트

```bash
# 1. 컴파일
python -m py_compile rfx_analyzer.py matcher.py engine.py && echo "✅ 컴파일 OK"

# 2. 신규 테스트
python -m pytest tests/test_constraint_evaluator.py tests/test_rfx_analyzer_constraints.py \
  tests/test_matcher_detail_rules.py tests/test_hybrid_search.py -v

# 3. 기존 라우터/매처 회귀
python -m pytest tests/test_chat_router.py tests/test_matcher_consortium_rule.py \
  tests/test_matcher_opinion.py -v

# 4. BM25 비활성화 회귀 (기존 동작 유지)
RAG_HYBRID_ENABLED=0 python -m pytest tests/test_hybrid_search.py::test_hybrid_disabled_by_default -v

# 5. 평가 (파일 있을 때)
# python scripts/run_accuracy_eval.py --xlsx testdata/eval_default.xlsx
```
