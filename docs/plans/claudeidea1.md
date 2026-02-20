# Claude Idea 1 — 최종 수정판 (Go Gate 충족 기준)

작성일: 2026-02-19 (최초) → 수정: 2026-02-19 (코덱스claude 2차 검증 반영)

검토 이력:
- codexidea1~3 분석 → claudeidea1 초안
- 코덱스claude 1차: 5개 오류 지적 → 수정판 1
- 코덱스claude 2차: 4개 Blocking 지적 → **이 문서 (최종 수정판)**

---

## 0) Go Gate — 실행 가능 판정 기준 (코덱스claude 2차 요구사항)

아래 4개가 모두 충족되어야 실행 가능:

| # | 조건 | 확인 방법 |
|---|------|---------|
| G1 | 라우터 가정 정정 완료 | 이 문서에서 단독어 → 복합어 전략으로 교체 ✅ |
| G2 | 평가 스크립트 생성 후 베이스라인 실행 가능 | Priority 0에서 `run_accuracy_eval.py` 생성 |
| G3 | 오탐 테스트가 실제 assert 기반 동작 | Priority 1에서 실패 가능 테스트 작성 |
| G4 | 평가 데이터 준비 상태 명시 | 아래 "데이터 준비 상태" 섹션 참조 |

---

## 1) 데이터 준비 상태 (G4)

### 현재 존재하는 파일

```
testdata/
  adversarial/     ← adversarial PDF 테스트셋 (기존)
    company_adversarial.pdf
    rfx_adversarial.pdf
    answer_key_adversarial_eval.json

scripts/
  phase0_baseline.py               ← PDF 파이프라인 품질 측정
  evaluate_adversarial_accuracy.py ← JSON answer key 기반 매처 정확도
  run_accuracy_eval.py             ← ❌ 없음 (Priority 0에서 생성 필요)
```

### 사전 준비 필수 (없으면 Priority 0 실행 불가)

```bash
# eval_default.xlsx: 수동 복사 필요
cp "/Users/min-kyungwook/Downloads/Kira_평가지_회사정보더미_제안요청서더미.xlsx" \
   testdata/eval_default.xlsx
```

**주의**: "현재 보유"가 아님. 실행 전 위 명령어 수행 필수.

---

## 2) 라우터 가정 정정 (G1) — Blocking 해결

### 왜 이전 가정이 틀렸는가

```python
# chat_router.py:282-284
def route_user_query(message, api_key, ...):
    prefiltered = _build_prefilter_decision(message, ...)
    if prefiltered:
        return prefiltered  # ← 즉시 반환. LLM 미호출
    # LLM은 prefiltered가 None일 때만 호출됨
```

→ 단독어 "기간"이 `DOMAIN_KEYWORDS`에 있으면 "기간이 얼마나 걸려?"도 즉시 ALLOW.
→ 이전 플랜의 "프리필터 통과해도 LLM이 걸러줌" 가정은 완전히 틀림.

### 수정된 키워드 확장 전략: 단독어 금지, 복합어만

**원칙**: 일상 대화에서 단독으로 쓰일 수 있는 단어는 추가하지 않는다.

```python
# ❌ 금지 — 단독어 오탐 위험
"기간"    # "기간이 얼마나 걸려?" → ALLOW 오탐
"금액"    # "금액을 알고 싶어요" → ALLOW 오탐
"인원"    # "인원이 몇 명이야?" → ALLOW 오탐
"사업"    # 너무 일반적

# ✅ 허용 — 복합어·도메인 특화 용어
DOMAIN_KEYWORDS에 추가:
  "사업기간", "수행기간", "계약기간",
  "사업예산", "사업비",
  "신용등급",       # "신용등급 어때?" 는 비업무적이나 입찰 맥락에서만 쓰임
  "마감일시", "제출마감",
  "공고번호", "사업번호",

COMPANY_DOC_KEYWORDS에 추가:
  "설립연도",       # 일상에서 "설립연도가 어떻게 돼?" 는 거의 회사 맥락
  "신고확인서",     # 매우 특화된 업무 용어
  "직접생산확인",
  "기술인원", "투입인력",
  "신용등급",       # 양쪽 모두 추가
  "연매출",         # "우리 연매출이 얼마야?"는 회사 정보 맥락
```

**남은 문제 (F-03, F-04)**: "사업 기간이 어떻게 돼?", "사업 예산이 얼마야?"
→ "사업기간"은 붙여쓰기로만 매칭됨. "사업 기간"(띄어쓰기)은 `_normalize_text`가 공백 정규화하므로 `"사업 기간"` → `"사업 기간"`으로 정규화 → `in` 연산자가 "사업기간" 붙여쓰기를 찾지 못함.
→ **추가 대응**: "사업 기간", "사업 예산" 형태도 DOMAIN_KEYWORDS에 포함해야 함.

```python
# 최종 추가 목록 (띄어쓰기 포함)
"사업기간", "사업 기간",
"수행기간", "수행 기간",
"사업예산", "사업 예산",
"사업비",
"공고번호", "공고 번호",
"신용등급", "신용 등급",
"설립연도", "설립 연도",
"신고확인서",
"직접생산확인",
"기술인원", "투입인력",
"연매출",
```

---

## 3) 오탐 방지 테스트 — 실제 assert 기반 (G3)

### 기존 문제

```python
# ❌ 이전 claudeidea1.md 테스트 (완전히 무효)
def test_keyword_expansion_no_false_positive(message, ...):
    pass   # assert 없음 → 항상 PASS → 회귀 방지 불가
```

### 수정된 테스트 (실패 가능, 회귀 방지 실효)

`tests/test_chat_router.py`에 추가:

```python
def test_dangerous_single_words_not_in_domain_keywords():
    """
    단독 일상어가 DOMAIN_KEYWORDS에 포함되지 않아야 함.
    이 테스트가 실패하면 누군가 단독어를 추가한 것 → 오탐 위험 신호.
    """
    from chat_router import DOMAIN_KEYWORDS
    dangerous = ["기간", "금액", "인원", "매출", "사업"]
    for word in dangerous:
        assert word not in DOMAIN_KEYWORDS, (
            f"'{word}'이 DOMAIN_KEYWORDS에 있음. "
            f"단독어 추가는 오탐 위험 — '사업기간', '사업예산' 등 복합어 사용."
        )


def test_prefilter_returns_none_for_context_free_phrases():
    """
    일상 문장이 프리필터에서 즉시 ALLOW되지 않아야 함.
    _build_prefilter_decision이 None을 반환해야 LLM에 넘겨짐.
    이 테스트가 FAIL이면 키워드 과잉 추가가 오탐을 일으키는 것.
    """
    from chat_router import _build_prefilter_decision
    context_free = [
        "기간이 얼마나 걸려?",
        "금액을 알고 싶어요",
        "인원이 몇 명이야?",
        "매출 이야기 하자",
    ]
    for phrase in context_free:
        result = _build_prefilter_decision(phrase, offtopic_strict=True)
        assert result is None, (
            f"'{phrase}'가 프리필터에서 즉시 처리됨 "
            f"(policy={result.policy.value}). 단독어 오탐 발생."
        )


def test_business_compound_keywords_are_allowed():
    """
    추가한 복합어는 프리필터에서 ALLOW되어야 함 (정상 동작 확인).
    """
    from chat_router import _build_prefilter_decision, ChatPolicy
    business_phrases = [
        "이번 사업기간이 언제야?",
        "사업예산이 얼마야?",
        "공고번호 알려줘",
        "우리 신용등급이 어떻게 돼?",
        "설립연도가 언제야?",
    ]
    for phrase in business_phrases:
        result = _build_prefilter_decision(phrase, offtopic_strict=True)
        assert result is not None and result.policy == ChatPolicy.ALLOW, (
            f"'{phrase}'가 프리필터에서 ALLOW 안 됨 "
            f"(result={result}). 복합어 키워드 미등록 가능성."
        )
```

---

## 4) Priority 0 — `run_accuracy_eval.py` 생성 (G2)

**이 단계가 없으면 이후 모든 Priority의 "완료 기준" 측정 불가.**

### 기존 스크립트와의 차이

| 스크립트 | 입력 | 평가 방식 |
|---------|------|---------|
| `phase0_baseline.py` | company.pdf + rfx.pdf | 파이프라인 성공률 측정 |
| `evaluate_adversarial_accuracy.py` | PDFs + JSON answer key | 매처 상태 정확도 |
| **`run_accuracy_eval.py` (신규)** | **Excel 평가지 (.xlsx)** | **Q&A 키워드 PASS/FAIL** |

### 구현 스펙

```python
"""
scripts/run_accuracy_eval.py

Excel 평가지(J열 판정 기준) → 정확도 측정.
다양한 회사+RFx 평가 파일을 받는 범용 구조.

사용법:
  python scripts/run_accuracy_eval.py \
    --xlsx testdata/eval_default.xlsx \
    --threshold 0.90 \
    --out reports/accuracy_$(date +%Y%m%d).json
"""

구조:
  _load_eval_sheet(xlsx_path) -> list[EvalCase]
    - 시트: 이름에 "질문" 또는 "eval" 포함하는 첫 시트
    - A열: ID, B열: 구분, C열: 질문, D열: 예상답변
    - E열: 정답 키워드 (|로 구분), J열: 판정(PASS/FAIL)

  _calc_accuracy(cases) -> AccuracyReport
    - total / passes / fails
    - accuracy = passes / total

  AccuracyReport.save(out_path)
    - JSON: {date, file, total, passes, fails, accuracy, threshold, passed}
    - 리포트: reports/accuracy_YYYYMMDD_HHMM.json

main():
  --xlsx   평가 파일 경로
  --threshold  합격 기준 (기본 0.90)
  --batch  디렉터리 내 모든 .xlsx 일괄 처리
  --out    리포트 출력 경로
  exit(1) if accuracy < threshold
"""
```

### 실행 시퀀스 (베이스라인 측정)

```bash
# Step 1: 평가 파일 준비 (필수 선행)
cp ".../Kira_평가지_회사정보더미_제안요청서더미.xlsx" testdata/eval_default.xlsx

# Step 2: 스크립트 생성 (Priority 0 구현)
# ... 코드 작성 후 ...

# Step 3: 베이스라인 측정
python scripts/run_accuracy_eval.py \
  --xlsx testdata/eval_default.xlsx \
  --threshold 0.90 \
  --out reports/accuracy_baseline.json

# 예상 결과: 63.6% (21/33 PASS) → FAIL 상태로 기록
```

---

## 5) 수정된 전체 실행 플랜

### Priority 0 — 평가 인프라 (선행 필수, G2+G4)

**완료 기준**: `python scripts/run_accuracy_eval.py --xlsx testdata/eval_default.xlsx` 실행되어 베이스라인 수치 출력

```
1. testdata/eval_default.xlsx 수동 복사 (사전 준비)
2. scripts/run_accuracy_eval.py 구현
3. 베이스라인 측정 → reports/accuracy_baseline.json 저장
   (예상: 63.6%)
```

---

### Priority 1 — chat_router.py 복합어 키워드 확장 + 오탐 테스트 (G1+G3)

**완료 기준**:
- `pytest tests/test_chat_router.py` — 모두 PASS
- `test_dangerous_single_words_not_in_domain_keywords` PASS (단독어 없음)
- `test_prefilter_returns_none_for_context_free_phrases` PASS (오탐 없음)
- `test_business_compound_keywords_are_allowed` PASS (복합어 ALLOW)
- `run_accuracy_eval.py` → ≥75% (F-03,F-04,C-02,C-03,C-07,C-09 해결)

**구현**:
```python
# chat_router.py DOMAIN_KEYWORDS에 추가 (복합어만):
"사업기간", "사업 기간", "수행기간", "수행 기간", "계약기간",
"사업예산", "사업 예산", "사업비",
"공고번호", "공고 번호",
"신용등급", "신용 등급",
"마감일시", "제출마감",

# chat_router.py COMPANY_DOC_KEYWORDS에 추가:
"설립연도", "설립 연도",
"신고확인서",
"직접생산확인",
"기술인원", "투입인력",
"신용등급",
"연매출",
```

---

### Priority 2 — rfx_analyzer.py: constraints 배열 추출 (Stage C 핵심)

**완료 기준**:
- `python -m py_compile rfx_analyzer.py` → OK
- `RFxRequirement`에 `constraints: list[RFxConstraint]` 필드 존재
- LLM 추출 테스트: "건당 20억 이상, 최근 3년, 완료된 실적" → constraints에 amount/period/completed 추출

**구현**:
```python
# rfx_analyzer.py 추가

@dataclass
class RFxConstraint:
    field: str   # amount|count|period|grade|deadline|completed|other
    op: str      # >=|<=|=|in|not_in
    value: str   # "2000000000"|"3"|"true"|"기사이상"
    unit: str    # KRW|건|year|month|""

# RFxRequirement에 추가:
constraints: list[RFxConstraint] = field(default_factory=list)
```

```
rfx_analyzer.py JSON 스키마 추가 (자격요건 항목 내):
"constraints": [
  {"field": "amount", "op": ">=", "value": "2000000000", "unit": "KRW"},
  {"field": "count",  "op": ">=", "value": "2",          "unit": "건"},
  {"field": "period", "op": "<=", "value": "3",          "unit": "year"},
  {"field": "completed","op":"=","value":"true",         "unit": ""}
]

프롬프트 지침:
  금액 → field=amount, op=>=, value=원화 정수(원 단위), unit=KRW
  건수 → field=count,  op=>=, value=정수, unit=건
  기간 → field=period, op=<=, value=정수, unit=year/month
  완료 → field=completed, op==, value=true
  조건 없으면 빈 배열 []
```

---

### Priority 3 — matcher.py: CompanyFactNormalizer + DeterministicRuleEvaluator (Stage D)

**완료 기준**:
- `CompanyFactNormalizer("KEPCO 19.8억, 2023년 완료").extract(...)` → `{"amount": 1980000000, "completed": True}`
- `pytest tests/test_matcher_detail_rules.py` PASS
- X-03 KEPCO 19.8억 → NOT_MET 또는 PARTIALLY_MET

**구현 흐름**:
```
RAG context (자유 문자열)
  "KEPCO 스마트그리드 사업, 계약금액 19.8억원, 2023년 완료"
         ↓
  CompanyFactNormalizer.extract(context, req.constraints)
  → {"amount": 1980000000, "completed": True}
         ↓
  DeterministicRuleEvaluator.evaluate(req.constraints, company_facts)
  → constraint: amount >= 2000000000, actual: 1980000000
  → FAIL → NOT_MET (LLM 미호출)
```

**CompanyFactNormalizer 구현 전략 (Hybrid)**:
```
1단계: 규칙형 파서
  한국어 금액: r'(\d+(?:\.\d+)?)\s*억\s*원?' → ×1억
  기간: r'최근\s*(\d+)\s*년' → 정수
  완료: ["완료", "납품완료", "종료", "준공"] 포함 여부
  진행중: ["진행 중", "수행 중", "~현재", "예정"] 포함 여부

2단계: 파서 실패한 field만 LLM structured output으로 보완
  → LLM 추가 호출 최소화
```

---

### Priority 4 — engine.py: BM25 + 하이브리드 검색 (Stage B)

**완료 기준**:
- `python -c "from rank_bm25 import BM25Okapi; print('OK')"` → OK
- BM25 점수 + 벡터 점수 RRF 결합 동작
- "신고확인서 번호" 쿼리 → 정확한 번호 포함 chunk가 상위 결과

---

### Priority 5 — services/web_app/main.py: citation 강화 + GAP 가드 (Stage E)

**완료 기준**:
- R-05 "필수요건 근거 페이지 같이 알려줘" → references에 page 포함
- R-01/R-02 "필수요건 중 미충족 항목" → 필수만 필터링

**구현**:
```
_generate_chat_answer() 시스템 프롬프트 추가:
  "[RFx 출처: xxx, 페이지 N]" 형식이 컨텍스트에 있으면
  반드시 N을 references에 {"page": N, "text": "..."} 으로 포함.
  수치가 답변에 나오면 해당 페이지 근거 필수.

GAP_QUERY_KEYWORDS 추가:
  "필수요건 중", "필수 요건 중", "미충족 항목"

_build_gap_answer_from_latest_matching():
  "필수" 질문 감지 시 is_mandatory=True 필터링 분기 추가
```

---

### Priority 6 — 범용 자동 평가 + 다회사 테스트

**완료 기준**:
- `pytest tests/test_evaluation_accuracy.py` → 90%+
- `run_accuracy_eval.py --batch testdata/` 로 여러 파일 일괄 측정 가능

---

## 6) 정확도 목표 (검증 조건 기반)

| Phase | 완료 조건 | 측정 명령 | 목표 |
|-------|---------|---------|------|
| Priority 0 | `run_accuracy_eval.py` 실행 가능 | 직접 실행 | 베이스라인 측정 |
| Priority 1 | F-03,04,C-02,03,07,09 → PASS | `run_accuracy_eval.py --xlsx testdata/eval_default.xlsx` | ≥75% |
| Priority 2+3 | X-03,04,05 → PASS | 동일 | ≥90% |
| Priority 4+5 | R-05 → PASS | 동일 | ≥93% |
| Priority 6 | 신규 회사 파일 2종 | `--batch testdata/eval_files/` | 범용 ≥90% |

**※ 모든 수치는 예상치. 실제 측정 전 확정 불가.**

---

## 7) 현황 갭 분석 (최종 정정판)

### Stage A — 문서 전처리

| 요구 | 실제 코드 | 갭 |
|------|---------|-----|
| 페이지 보존 | PDF: 실제 페이지 ✅<br>DOCX/TXT: `pages=[전체텍스트]` → page_number=1 고정 ⚠️ | DOCX는 "page 1"만 있어 의미 없음. 단기 대응 불필요 |
| doc_type | RFx: `"rfx_text"` ✅ (`main.py:938`)<br>회사: `"text"` ⚠️ | 회사 문서에 `"company_text"` 미지정. 검색 필터링 시 문제 |
| section | 없음 ❌ | 장기 개선 대상 |

### Stage B — 검색

| 요구 | 실제 코드 | 갭 |
|------|---------|-----|
| BM25 hybrid | 순수 벡터 (`engine.py:225-272`) | Priority 4 |
| cross-encoder rerank | 없음 | optional (`KIRA_RERANK_ENABLED=0` 기본 off) |

### Stage C — 구조화 추출

| 요구 | 실제 코드 | 갭 |
|------|---------|-----|
| constraints 배열 | `detail: str` 자유 문자열 (`rfx_analyzer.py:31`) | Priority 2 (핵심) |

### Stage D — 비교·판정

| 요구 | 실제 코드 | 갭 |
|------|---------|-----|
| CompanyFactNormalizer | 없음 (`matcher.py:620`: raw string) | Priority 3 (필수) |
| DeterministicRuleEvaluator | 컨소시엄 규칙만 (`matcher.py:497`) | Priority 3 |

### Stage E — 응답 가드

| 요구 | 실제 코드 | 갭 |
|------|---------|-----|
| citation 강화 | `_is_grounded_in_rfx()` 단순 포함 체크 | Priority 5 |
| R-05 근거 페이지 | 시스템 프롬프트 지침 약함 | Priority 5 |

---

## 8) codexidea 시리즈 + 코덱스 검증 통합

| 문서 | 기여 | 반영 |
|------|------|------|
| codexidea1 | P0~P7 프롬프트 체인 | Stage C constraints 스키마 |
| codexidea2 | 2026 RAG 연구 조사 | BM25·grounding 근거 |
| codexidea3 | 5단계 아키텍처 | 전체 설계 기준 |
| 코덱스claude 1차 | 페이지/doc_type/CompanyFact/정확도 수치 | 1차 수정판 반영 |
| 코덱스claude 2차 | 라우터 즉시반환/스크립트 없음/pass 테스트/데이터 미보유 | **이 문서 전면 반영** |
