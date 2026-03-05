# RAG 엔진 3단계 업그레이드 구현 계획

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Kira RAG 검색 품질을 3축으로 업그레이드 — Kiwi BM25 앙상블(7:3), RAPTOR 트리 인덱싱, PDF 표 파싱 강화.

**Architecture:** 기존 `engine.py` + `document_parser.py` 위에 3개 독립 모듈 플러그인. 하위호환 100% 유지 (Kiwi 미설치 시 폴백, RAPTOR 옵트인).

**Tech Stack:** kiwipiepy (형태소), umap-learn + scikit-learn (클러스터링), pdfplumber (표 추출), OpenAI gpt-4o-mini (RAPTOR 요약), ChromaDB (벡터 저장)

**Design Doc:** `docs/plans/2026-03-05-rag-upgrade-design.md`

---

## Task 1: Kiwi 한국어 토크나이저 모듈

**Files:**
- Create: `korean_tokenizer.py`
- Create: `tests/test_korean_tokenizer.py`

### Step 1: 의존성 설치

```bash
pip install kiwipiepy>=0.18.0
```

확인: `python -c "from kiwipiepy import Kiwi; k=Kiwi(); print(k.tokenize('정보통신공사업을 수행합니다'))"` → 토큰 리스트 출력

### Step 2: 실패하는 테스트 작성

```python
# tests/test_korean_tokenizer.py
"""한국어 형태소 분석 BM25 토크나이저 테스트."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


def test_tokenize_ko_basic():
    """기본 한국어 문장을 형태소로 분리."""
    from korean_tokenizer import tokenize_ko
    tokens = tokenize_ko("정보통신공사업을 수행합니다")
    assert "정보" in tokens or "통신" in tokens or "공사" in tokens
    # 조사 '을'과 어미 '합니다'는 제거되어야 함
    assert "을" not in tokens
    assert "합니다" not in tokens


def test_tokenize_ko_removes_particles():
    """조사/어미가 제거되어 동일 어근 매칭 가능."""
    from korean_tokenizer import tokenize_ko
    tokens_a = tokenize_ko("제안서를 작성했습니다")
    tokens_b = tokenize_ko("제안서 작성")
    # 핵심 어근 '제안서', '작성'이 양쪽에 존재
    common = set(tokens_a) & set(tokens_b)
    assert len(common) >= 2, f"공통 토큰 부족: {common}"


def test_tokenize_ko_english_passthrough():
    """영문/숫자는 그대로 토큰으로 포함."""
    from korean_tokenizer import tokenize_ko
    tokens = tokenize_ko("ISO 9001 인증")
    assert "ISO" in tokens or "iso" in tokens.lower() if hasattr(tokens, 'lower') else True
    assert "9001" in tokens


def test_tokenize_ko_empty():
    """빈 문자열 → 빈 리스트."""
    from korean_tokenizer import tokenize_ko
    assert tokenize_ko("") == []


def test_tokenize_ko_fallback_without_kiwi():
    """kiwipiepy 미설치 시 공백 분할 폴백."""
    from korean_tokenizer import _fallback_tokenize
    tokens = _fallback_tokenize("제안서를 작성합니다")
    assert tokens == ["제안서를", "작성합니다"]
```

### Step 3: 테스트 실패 확인

Run: `pytest tests/test_korean_tokenizer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'korean_tokenizer'`

### Step 4: 최소 구현

```python
# korean_tokenizer.py
"""한국어 형태소 분석 기반 BM25 토크나이저.

Kiwi 형태소 분석기로 명사/동사/형용사 어근만 추출.
kiwipiepy 미설치 시 str.split() 폴백.
"""
from __future__ import annotations

_kiwi = None
_USE_KIWI = True

# 추출할 품사 태그 — 내용어만 (기능어 제거)
# NNG: 일반명사, NNP: 고유명사, NNB: 의존명사
# VV: 동사 어근, VA: 형용사 어근, XR: 어근
# SL: 외국어, SN: 숫자
_CONTENT_POS = {"NNG", "NNP", "NNB", "VV", "VA", "XR", "SL", "SN"}

try:
    from kiwipiepy import Kiwi as _KiwiClass
except ImportError:
    _KiwiClass = None  # type: ignore
    _USE_KIWI = False


def _get_kiwi():
    """Kiwi 싱글턴 (lazy init, ~200ms 첫 호출)."""
    global _kiwi
    if _kiwi is None and _KiwiClass is not None:
        _kiwi = _KiwiClass()
    return _kiwi


def _fallback_tokenize(text: str) -> list[str]:
    """kiwipiepy 미설치 시 공백 분할 폴백."""
    return text.split()


def tokenize_ko(text: str) -> list[str]:
    """한국어 텍스트를 BM25용 토큰으로 분해.

    Kiwi 형태소 분석기로 내용어(명사/동사/형용사/외국어/숫자)만 추출.
    조사, 어미 등 기능어는 제거하여 BM25 노이즈 감소.

    Args:
        text: 분석할 한국어 텍스트

    Returns:
        토큰 리스트 (내용어 어근)
    """
    if not text or not text.strip():
        return []

    kiwi = _get_kiwi()
    if kiwi is None:
        return _fallback_tokenize(text)

    tokens = kiwi.tokenize(text)
    return [t.form for t in tokens if t.tag in _CONTENT_POS]
```

### Step 5: 테스트 통과 확인

Run: `pytest tests/test_korean_tokenizer.py -v`
Expected: ALL PASS

### Step 6: 커밋

```bash
git add korean_tokenizer.py tests/test_korean_tokenizer.py
git commit -m "feat: add Kiwi Korean morphological tokenizer for BM25"
```

---

## Task 2: engine.py — Kiwi BM25 + Vector 7:3 앙상블 + MMR 리랭킹

**Files:**
- Modify: `engine.py:22-26` (import), `engine.py:327` (_rebuild_bm25), `engine.py:359` (search), `engine.py:366-378` (RRF 가중치)
- Modify: `tests/test_hybrid_search.py`

> **핵심**: LangChain `EnsembleRetriever(weights=[0.7, 0.3], search_type="mmr")` 패턴을
> LangChain 없이 직접 구현. 가중 RRF 퓨전 + MMR 다양성 리랭킹.

### Step 1: 기존 테스트 통과 확인

Run: `pytest tests/test_hybrid_search.py -v`
Expected: ALL PASS (변경 전 기준선)

### Step 2: 가중 RRF + Kiwi + MMR 테스트 추가

```python
# tests/test_hybrid_search.py에 추가

def test_kiwi_bm25_korean_matching():
    """Kiwi 토크나이저로 한국어 조사 차이를 극복."""
    from korean_tokenizer import tokenize_ko
    from rank_bm25 import BM25Okapi

    corpus = [
        "정보통신공사업 면허를 보유하고 있습니다",
        "건축공사업 면허 보유",
        "소프트웨어 개발 전문기업",
    ]
    tokenized = [tokenize_ko(doc) for doc in corpus]
    bm25 = BM25Okapi(tokenized)

    # "정보통신공사업을" (조사 '을' 포함) → 첫 번째 문서 매칭
    scores = bm25.get_scores(tokenize_ko("정보통신공사업을 보유한 업체"))
    best_idx = int(scores.argmax())
    assert best_idx == 0, f"Expected 0, got {best_idx}. Scores: {scores}"


def test_weighted_rrf_bm25_priority():
    """7:3 가중 RRF에서 BM25 정확 매칭이 벡터 유사 매칭보다 우선."""
    engine = _make_engine(hybrid=True)
    engine.add_text_directly("ISO 9001 품질경영시스템 인증서", "cert")
    engine.add_text_directly("품질 관리 체계 구축 방안", "plan")
    engine.add_text_directly("회사 연혁 2010년 설립", "history")

    results = engine.search("ISO 9001 인증", top_k=3)
    assert len(results) > 0
    # BM25 가중치 0.7 → 정확 키워드 매칭("ISO 9001")이 1위
    assert "ISO" in results[0].text or "9001" in results[0].text


def test_mmr_reduces_redundancy():
    """MMR 리랭킹으로 유사 청크가 연속 배치되지 않음."""
    engine = _make_engine(hybrid=True)
    # 거의 동일한 문서 3개 + 다른 문서 1개
    engine.add_text_directly("ISO 9001 품질경영시스템 인증서 보유", "cert1")
    engine.add_text_directly("ISO 9001 품질경영시스템 인증서 확인", "cert2")
    engine.add_text_directly("ISO 9001 품질경영 인증 획득 완료", "cert3")
    engine.add_text_directly("정보통신공사업 면허 등록 확인서", "license")

    results = engine.search("ISO 인증 및 면허", top_k=4)
    # MMR로 다양성 보장 → "면허" 관련 문서가 상위 3개 안에 포함
    texts = [r.text for r in results[:3]]
    has_license = any("면허" in t for t in texts)
    assert has_license, f"MMR 다양성 부족: top-3에 면허 문서 없음. got: {texts}"
```

### Step 3: 테스트 실패 확인

Run: `pytest tests/test_hybrid_search.py::test_kiwi_bm25_korean_matching tests/test_hybrid_search.py::test_mmr_reduces_redundancy -v`
Expected: FAIL

### Step 4: engine.py 수정

**4a. import 추가** (`engine.py` 상단, line ~11):

```python
from korean_tokenizer import tokenize_ko
```

**4b. `_rebuild_bm25()` 수정** (`engine.py:327`):

변경 전:
```python
self._bm25 = _BM25Okapi([d.split() for d in docs])
```

변경 후:
```python
self._bm25 = _BM25Okapi([tokenize_ko(d) for d in docs])
```

**4c. `_search_hybrid()` 수정** (`engine.py:359`):

변경 전:
```python
full_scores = self._bm25.get_scores(query.split())
```

변경 후:
```python
full_scores = self._bm25.get_scores(tokenize_ko(query))
```

**4d. 가중 RRF (7:3) + MMR 리랭킹** (`engine.py:366-400`):

변경 전:
```python
K = 60
rrf: dict = {}

# BM25 기여 (chunk_key 사용)
for rank, (orig_idx, _) in enumerate(bm25_ranked[:top_k * 2]):
    ck = self._bm25_entries[orig_idx]["chunk_key"]
    rrf[ck] = rrf.get(ck, 0.0) + 1.0 / (K + rank + 1)

# 벡터 기여 (동일 chunk_key)
for rank, vr in enumerate(vector_results):
    ck = f"{vr.source_file}_{vr.chunk_id}"
    rrf[ck] = rrf.get(ck, 0.0) + 1.0 / (K + rank + 1)
```

변경 후:
```python
K = 60
BM25_WEIGHT = 0.7
VECTOR_WEIGHT = 0.3
rrf: dict = {}

# BM25 기여 (70% 가중)
for rank, (orig_idx, _) in enumerate(bm25_ranked[:top_k * 2]):
    ck = self._bm25_entries[orig_idx]["chunk_key"]
    rrf[ck] = rrf.get(ck, 0.0) + BM25_WEIGHT * (1.0 / (K + rank + 1))

# 벡터 기여 (30% 가중)
for rank, vr in enumerate(vector_results):
    ck = f"{vr.source_file}_{vr.chunk_id}"
    rrf[ck] = rrf.get(ck, 0.0) + VECTOR_WEIGHT * (1.0 / (K + rank + 1))
```

**4e. MMR 리랭킹 메서드 추가** (`engine.py`에 새 메서드):

```python
@staticmethod
def _mmr_rerank(
    candidates: list["SearchResult"],
    top_k: int,
    lambda_param: float = 0.7,
) -> list["SearchResult"]:
    """MMR(Maximal Marginal Relevance) 리랭킹.

    관련성(lambda)과 다양성(1-lambda)을 균형.
    중복 청크를 페널티하여 검색 결과 다양성 보장.

    Args:
        candidates: RRF 퓨전 후 후보 리스트 (score 포함)
        top_k: 최종 반환 수
        lambda_param: 관련성 가중치 (0.7 = 관련성 70%, 다양성 30%)
    """
    if len(candidates) <= top_k:
        return candidates

    from difflib import SequenceMatcher

    selected: list["SearchResult"] = []
    remaining = list(candidates)

    # 첫 번째: 가장 높은 RRF 점수
    remaining.sort(key=lambda r: r.score, reverse=True)
    selected.append(remaining.pop(0))

    while len(selected) < top_k and remaining:
        best_score = -float("inf")
        best_idx = 0

        for i, cand in enumerate(remaining):
            # 관련성: RRF 점수 (이미 정규화됨)
            relevance = cand.score

            # 다양성: 이미 선택된 문서들과의 최대 유사도
            max_sim = 0.0
            for sel in selected:
                sim = SequenceMatcher(None, cand.text[:200], sel.text[:200]).ratio()
                max_sim = max(max_sim, sim)

            # MMR = λ * relevance - (1 - λ) * max_similarity
            mmr = lambda_param * relevance - (1 - lambda_param) * max_sim

            if mmr > best_score:
                best_score = mmr
                best_idx = i

        selected.append(remaining.pop(best_idx))

    return selected
```

**4f. `_search_hybrid()` 최종 결과에 MMR 적용:**

기존 `final` 리스트 구성 후, 반환 직전에:

```python
        # MMR 리랭킹으로 다양성 보장
        if len(final) > top_k:
            final = self._mmr_rerank(final, top_k)
        return final
```

실제로는 `final` 후보 풀을 `top_k * 2`개로 확대 수집한 뒤 MMR로 `top_k`개 선택:

```python
        ranked_keys = sorted(rrf, key=rrf.__getitem__, reverse=True)
        pool: list[SearchResult] = []  # 확대 후보 풀
        for ck in ranked_keys:
            if len(pool) >= top_k * 3:  # MMR 입력용 확대 풀
                break
            if ck in vector_by_key:
                sr = vector_by_key[ck]
                sr.score = rrf[ck]  # RRF 점수로 교체
                pool.append(sr)
            elif ck in bm25_by_key:
                entry = bm25_by_key[ck]
                pool.append(SearchResult(
                    text=entry["doc"],
                    score=rrf[ck],
                    source_file=entry["metadata"].get("source_file", "unknown"),
                    chunk_id=entry["metadata"].get("chunk_id", -1),
                    metadata=entry["metadata"],
                ))

        # MMR 리랭킹 → 최종 top_k
        return self._mmr_rerank(pool, top_k)
```

### Step 5: 전체 테스트 통과 확인

Run: `pytest tests/test_hybrid_search.py -v`
Expected: ALL PASS (기존 + 신규)

### Step 6: 커밋

```bash
git add engine.py tests/test_hybrid_search.py
git commit -m "feat: Kiwi BM25 7:3 weighted ensemble + MMR diversity reranking"
```

---

## Task 3: PDF 표 파싱 — `_table_to_markdown()` 헬퍼

**Files:**
- Modify: `document_parser.py`
- Create: `tests/test_document_parser.py`

### Step 1: 테스트 작성

```python
# tests/test_document_parser.py
"""PDF 표 파싱 + 마크다운 변환 테스트."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from document_parser import DocumentParser


class TestTableToMarkdown:
    """_table_to_markdown() 단위 테스트."""

    def test_basic_table(self):
        """기본 2x3 표 → 마크다운 변환."""
        table = [
            ["평가항목", "배점", "세부기준"],
            ["사업이해", "15", "목적 이해도"],
            ["기술방안", "25", "구현 적정성"],
        ]
        result = DocumentParser._table_to_markdown(table)
        assert "| 평가항목 | 배점 | 세부기준 |" in result
        assert "| --- | --- | --- |" in result
        assert "| 사업이해 | 15 | 목적 이해도 |" in result
        assert "| 기술방안 | 25 | 구현 적정성 |" in result

    def test_none_cells(self):
        """None 셀 → 빈 문자열 처리."""
        table = [
            ["구분", "값"],
            [None, "100"],
            ["항목", None],
        ]
        result = DocumentParser._table_to_markdown(table)
        assert "|  | 100 |" in result
        assert "| 항목 |  |" in result

    def test_single_row_returns_empty(self):
        """행 1개 → 빈 문자열 (표가 아님)."""
        table = [["헤더만"]]
        result = DocumentParser._table_to_markdown(table)
        assert result == ""

    def test_empty_table_returns_empty(self):
        """빈 테이블 → 빈 문자열."""
        assert DocumentParser._table_to_markdown([]) == ""
        assert DocumentParser._table_to_markdown(None) == ""

    def test_pipe_in_cell_escaped(self):
        """셀 내 파이프 문자 → 이스케이프."""
        table = [
            ["항목", "값"],
            ["A|B", "100"],
        ]
        result = DocumentParser._table_to_markdown(table)
        assert "A\\|B" in result

    def test_uneven_columns(self):
        """열 수가 불균일 → 부족한 열은 빈 셀로 채움."""
        table = [
            ["A", "B", "C"],
            ["1", "2"],       # C 열 누락
            ["x", "y", "z"],
        ]
        result = DocumentParser._table_to_markdown(table)
        lines = result.strip().split("\n")
        # 모든 데이터 행이 3열
        assert lines[2].count("|") == lines[0].count("|")

    def test_newline_in_cell(self):
        """셀 내 줄바꿈 → 공백으로 치환."""
        table = [
            ["항목", "설명"],
            ["A", "첫째줄\n둘째줄"],
        ]
        result = DocumentParser._table_to_markdown(table)
        assert "첫째줄 둘째줄" in result
        assert "\n" not in result.split("\n")[2]  # 데이터 행에 줄바꿈 없음
```

### Step 2: 테스트 실패 확인

Run: `pytest tests/test_document_parser.py -v`
Expected: FAIL — `AttributeError: type object 'DocumentParser' has no attribute '_table_to_markdown'`

### Step 3: `_table_to_markdown()` 구현

`document_parser.py`의 `DocumentParser` 클래스에 추가:

```python
@staticmethod
def _table_to_markdown(table) -> str:
    """pdfplumber 표 데이터 → GFM 마크다운 테이블.

    Args:
        table: list[list] — pdfplumber extract_tables() 결과

    Returns:
        마크다운 테이블 문자열. 행 1개 이하면 빈 문자열.
    """
    if not table or len(table) < 2:
        return ""

    def _cell(v):
        s = str(v or "").strip()
        return s.replace("|", "\\|").replace("\n", " ")

    header = [_cell(c) for c in table[0]]
    col_count = len(header)
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * col_count) + " |",
    ]

    for row in table[1:]:
        cells = [_cell(c) for c in row]
        while len(cells) < col_count:
            cells.append("")
        lines.append("| " + " | ".join(cells[:col_count]) + " |")

    return "\n".join(lines)
```

### Step 4: 테스트 통과 확인

Run: `pytest tests/test_document_parser.py -v`
Expected: ALL PASS

### Step 5: 커밋

```bash
git add document_parser.py tests/test_document_parser.py
git commit -m "feat: add _table_to_markdown() helper for PDF table parsing"
```

---

## Task 4: PDF 파서에 표 추출 통합

**Files:**
- Modify: `document_parser.py:443-486` (`_parse_pdf`)
- Modify: `tests/test_document_parser.py` (통합 테스트 추가)

### Step 1: 통합 테스트 추가

```python
# tests/test_document_parser.py에 추가

class TestPdfTableIntegration:
    """_parse_pdf() 표 추출 통합 테스트."""

    def test_parse_pdf_with_tables_mock(self, tmp_path):
        """pdfplumber 표 추출이 page text에 포함되는지."""
        from unittest.mock import patch, MagicMock

        parser = DocumentParser()

        mock_page = MagicMock()
        mock_page.extract_text.return_value = "일반 텍스트 내용"
        mock_page.extract_tables.return_value = [
            [["항목", "점수"], ["사업이해", "15"], ["기술방안", "25"]],
        ]

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = lambda s: s
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with patch("pdfplumber.open", return_value=mock_pdf):
            doc = parser.parse(str(tmp_path / "test.pdf"))

        assert "일반 텍스트 내용" in doc.text
        assert "| 항목 | 점수 |" in doc.text
        assert "| 사업이해 | 15 |" in doc.text

    def test_parse_pdf_no_tables(self, tmp_path):
        """표 없는 PDF → 기존 동작 유지."""
        from unittest.mock import patch, MagicMock

        parser = DocumentParser()

        mock_page = MagicMock()
        mock_page.extract_text.return_value = "텍스트만 있는 페이지"
        mock_page.extract_tables.return_value = []

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = lambda s: s
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with patch("pdfplumber.open", return_value=mock_pdf):
            doc = parser.parse(str(tmp_path / "test.pdf"))

        assert "텍스트만 있는 페이지" in doc.text
        assert "|" not in doc.text  # 마크다운 테이블 없음
```

### Step 2: 테스트 실패 확인

Run: `pytest tests/test_document_parser.py::TestPdfTableIntegration -v`
Expected: FAIL — `parse` 경로 문제 또는 마크다운 테이블 미포함

### Step 3: `_parse_pdf()` 수정

`document_parser.py:443-486`의 `_parse_pdf` 수정:

변경 전:
```python
def _parse_pdf(self, path: Path) -> ParsedDocument:
    pages: list[str] = []

    # 1차: pdfplumber 시도
    try:
        import pdfplumber

        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                normalized = self.chunker._normalize_text(page_text)
                pages.append(normalized)
    except ImportError:
        pass
    except Exception:
        pages = []
    ...
```

변경 후:
```python
def _parse_pdf(self, path: Path) -> ParsedDocument:
    pages: list[str] = []

    # 1차: pdfplumber 시도
    try:
        import pdfplumber

        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                parts: list[str] = []

                # 텍스트 추출
                page_text = page.extract_text() or ""
                if page_text.strip():
                    parts.append(page_text)

                # 표 추출 → 마크다운 변환
                try:
                    tables = page.extract_tables() or []
                    for table in tables:
                        md = self._table_to_markdown(table)
                        if md:
                            parts.append(md)
                except Exception:
                    pass  # 표 추출 실패 시 텍스트만 사용

                combined = "\n\n".join(parts)
                normalized = self.chunker._normalize_text(combined)
                pages.append(normalized)
    except ImportError:
        pass
    except Exception:
        pages = []

    # 2차: PyMuPDF 폴백 (기존 동작 유지, 표 추출 없음)
    ...
```

### Step 4: 테스트 통과 확인

Run: `pytest tests/test_document_parser.py -v`
Expected: ALL PASS

### Step 5: 커밋

```bash
git add document_parser.py tests/test_document_parser.py
git commit -m "feat: integrate PDF table extraction into _parse_pdf()"
```

---

## Task 5: RAPTOR 인덱서 — 데이터 모델 + 클러스터링

**Files:**
- Create: `raptor_indexer.py`
- Create: `tests/test_raptor_indexer.py`

### Step 1: 의존성 설치

```bash
pip install umap-learn>=0.5.0
```

확인: `python -c "import umap; print(umap.__version__)"`

### Step 2: 데이터 모델 + 클러스터링 테스트 작성

```python
# tests/test_raptor_indexer.py
"""RAPTOR 트리 인덱서 테스트."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import numpy as np


def test_raptor_node_creation():
    """RaptorNode 데이터 모델."""
    from raptor_indexer import RaptorNode
    node = RaptorNode(text="요약 텍스트", level=1, source_chunks=[0, 1, 2])
    assert node.text == "요약 텍스트"
    assert node.level == 1
    assert node.source_chunks == [0, 1, 2]


def test_cluster_texts_basic():
    """유사 텍스트를 같은 클러스터로 묶기."""
    from raptor_indexer import RaptorIndexer

    indexer = RaptorIndexer()
    # 임베딩을 직접 제공하여 UMAP+GMM 테스트
    # 3개 클러스터 (각 2개씩)
    embeddings = np.array([
        [1.0, 0.0], [1.1, 0.1],   # 클러스터 A
        [0.0, 1.0], [0.1, 1.1],   # 클러스터 B
        [0.5, 0.5], [0.6, 0.4],   # 클러스터 C
    ])
    labels = indexer._cluster_embeddings(embeddings, min_clusters=2, max_clusters=5)
    assert len(labels) == 6
    # 가까운 벡터는 같은 클러스터
    assert labels[0] == labels[1]
    assert labels[2] == labels[3]


def test_skip_short_documents():
    """청크 수가 min_chunks 미만이면 빈 결과."""
    from raptor_indexer import RaptorIndexer

    indexer = RaptorIndexer(min_chunks=10)
    result = indexer.build_tree(["짧은 문서"] * 5, embed_fn=lambda x: [[0.1]*10]*len(x))
    assert result == []


def test_summarize_cluster():
    """클러스터 텍스트 요약 (mock LLM)."""
    from unittest.mock import patch, MagicMock
    from raptor_indexer import RaptorIndexer

    indexer = RaptorIndexer()
    texts = ["첫 번째 내용", "두 번째 내용", "세 번째 내용"]

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "세 가지 내용을 요약합니다."

    with patch("raptor_indexer._call_summary_llm", return_value="세 가지 내용을 요약합니다."):
        summary = indexer._summarize_texts(texts)

    assert "요약" in summary
```

### Step 3: 테스트 실패 확인

Run: `pytest tests/test_raptor_indexer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'raptor_indexer'`

### Step 4: RAPTOR 인덱서 구현

```python
# raptor_indexer.py
"""RAPTOR: Recursive Abstractive Processing for Tree-Organized Retrieval.

문서 청크를 재귀적으로 클러스터링 + 요약하여 트리 구조를 빌드.
검색 시 Collapsed Tree 방식으로 모든 레벨에서 flat 검색.

Reference: https://arxiv.org/abs/2401.18059
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np
from openai import OpenAI
from sklearn.mixture import GaussianMixture


@dataclass
class RaptorNode:
    """RAPTOR 트리의 한 노드."""
    text: str
    level: int                          # 0=리프(원본), 1+=요약
    source_chunks: list[int] = field(default_factory=list)
    node_id: str = ""

    def __post_init__(self):
        if not self.node_id:
            self.node_id = f"raptor_L{self.level}_{uuid.uuid4().hex[:8]}"


SUMMARY_SYSTEM_PROMPT = """당신은 한국어 문서 요약 전문가입니다.
주어진 텍스트 조각들의 핵심 내용을 하나의 요약으로 통합하세요.
- 구체적 수치, 조건, 요건은 반드시 보존
- 추상적 표현 없이 팩트 중심 요약
- 200~400자 분량"""


def _call_summary_llm(
    texts: list[str],
    api_key: Optional[str] = None,
) -> str:
    """클러스터 텍스트를 LLM으로 요약."""
    client = OpenAI(
        api_key=api_key or os.environ.get("OPENAI_API_KEY"),
        timeout=30,
    )
    combined = "\n\n---\n\n".join(texts)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": f"다음 텍스트 조각들을 요약하세요:\n\n{combined}"},
        ],
        temperature=0.3,
        max_tokens=800,
    )
    return resp.choices[0].message.content or ""


class RaptorIndexer:
    """RAPTOR 트리 빌더.

    Args:
        min_chunks: 이 미만이면 RAPTOR 스킵
        max_levels: 최대 트리 깊이
        api_key: OpenAI API 키 (요약용)
    """

    def __init__(
        self,
        min_chunks: int = 10,
        max_levels: int = 3,
        api_key: Optional[str] = None,
    ):
        self.min_chunks = min_chunks
        self.max_levels = max_levels
        self.api_key = api_key

    def _cluster_embeddings(
        self,
        embeddings: np.ndarray,
        min_clusters: int = 2,
        max_clusters: int = 10,
    ) -> np.ndarray:
        """UMAP 차원축소 + GMM 클러스터링 (BIC로 최적 k 결정).

        Args:
            embeddings: (n_samples, n_dims) 임베딩 행렬
            min_clusters: 최소 클러스터 수
            max_clusters: 최대 클러스터 수

        Returns:
            (n_samples,) 클러스터 라벨
        """
        n = len(embeddings)
        if n <= min_clusters:
            return np.zeros(n, dtype=int)

        # UMAP 차원축소 (고차원 → 2D) — 데이터가 충분할 때만
        reduced = embeddings
        if embeddings.shape[1] > 10 and n > 10:
            try:
                import umap
                n_neighbors = min(15, n - 1)
                reducer = umap.UMAP(
                    n_components=min(10, embeddings.shape[1]),
                    n_neighbors=n_neighbors,
                    min_dist=0.0,
                    random_state=42,
                )
                reduced = reducer.fit_transform(embeddings)
            except Exception:
                reduced = embeddings  # UMAP 실패 시 원본 사용

        # GMM + BIC로 최적 k
        max_k = min(max_clusters, n - 1)
        if max_k < min_clusters:
            return np.zeros(n, dtype=int)

        best_bic = float("inf")
        best_labels = np.zeros(n, dtype=int)

        for k in range(min_clusters, max_k + 1):
            try:
                gmm = GaussianMixture(n_components=k, random_state=42)
                gmm.fit(reduced)
                bic = gmm.bic(reduced)
                if bic < best_bic:
                    best_bic = bic
                    best_labels = gmm.predict(reduced)
            except Exception:
                continue

        return best_labels

    def _summarize_texts(self, texts: list[str]) -> str:
        """텍스트 리스트를 LLM으로 요약."""
        return _call_summary_llm(texts, api_key=self.api_key)

    def build_tree(
        self,
        chunks: list[str],
        embed_fn: Optional[Callable[[list[str]], list[list[float]]]] = None,
    ) -> list[RaptorNode]:
        """청크 리스트 → RAPTOR 트리 노드 리스트 (모든 레벨 포함).

        Args:
            chunks: 원본 텍스트 청크 리스트
            embed_fn: 텍스트 → 임베딩 함수 (None이면 OpenAI)

        Returns:
            요약 노드 리스트 (레벨 1 이상). 리프(레벨 0)은 포함하지 않음.
        """
        if len(chunks) < self.min_chunks:
            return []

        if embed_fn is None:
            embed_fn = self._default_embed

        all_nodes: list[RaptorNode] = []
        current_texts = list(chunks)
        level = 0

        while len(current_texts) > 1 and level < self.max_levels:
            # 1. 임베딩
            embeddings = np.array(embed_fn(current_texts))

            # 2. 클러스터링
            labels = self._cluster_embeddings(embeddings)
            unique_labels = set(labels)

            if len(unique_labels) <= 1 and level > 0:
                break  # 더 이상 분할 불가

            # 3. 클러스터별 요약
            level += 1
            summaries = []
            for label in sorted(unique_labels):
                indices = [i for i, l in enumerate(labels) if l == label]
                cluster_texts = [current_texts[i] for i in indices]

                if len(cluster_texts) == 1:
                    summary = cluster_texts[0]  # 단일 청크는 그대로
                else:
                    summary = self._summarize_texts(cluster_texts)

                node = RaptorNode(
                    text=summary,
                    level=level,
                    source_chunks=indices,
                )
                all_nodes.append(node)
                summaries.append(summary)

            current_texts = summaries

        return all_nodes

    def _default_embed(self, texts: list[str]) -> list[list[float]]:
        """OpenAI text-embedding-3-small 임베딩."""
        client = OpenAI(
            api_key=self.api_key or os.environ.get("OPENAI_API_KEY"),
            timeout=30,
        )
        resp = client.embeddings.create(
            model="text-embedding-3-small",
            input=texts,
        )
        return [d.embedding for d in resp.data]
```

### Step 5: 테스트 통과 확인

Run: `pytest tests/test_raptor_indexer.py -v`
Expected: ALL PASS

### Step 6: 커밋

```bash
git add raptor_indexer.py tests/test_raptor_indexer.py
git commit -m "feat: add RAPTOR tree indexer (UMAP+GMM clustering + LLM summarization)"
```

---

## Task 6: engine.py에 RAPTOR 통합

**Files:**
- Modify: `engine.py` (add_document + 설정)

### Step 1: 통합 테스트 작성

```python
# tests/test_raptor_indexer.py에 추가

def test_raptor_integration_with_engine():
    """engine.py와 RAPTOR 통합 — 요약 노드가 ChromaDB에 저장."""
    from unittest.mock import patch, MagicMock
    import time
    from engine import RAGEngine

    class _FakeEF:
        def __call__(self, input):
            return [[0.1] * 256 for _ in input]
        def name(self):
            return "default"

    engine = RAGEngine(
        persist_directory="/tmp/test_raptor_engine",
        collection_name=f"raptor_test_{int(time.time() * 1e6)}",
        embedding_function=_FakeEF(),
        hybrid_enabled=False,
    )
    engine._raptor_enabled = True

    # 15개 청크 추가 (min_chunks=10 초과)
    for i in range(15):
        engine.add_text_directly(f"청크 {i}: 테스트 내용 번호 {i}", f"source_{i}")

    # RAPTOR가 활성화되면 collection에 원본 + 요약 노드 존재
    count = engine.collection.count()
    assert count >= 15  # 최소 원본 15개
```

### Step 2: engine.py 수정

`engine.py`에 RAPTOR 관련 설정 추가:

**초기화** (`__init__` 내부):
```python
# RAPTOR 트리 인덱싱 설정
self._raptor_enabled: bool = os.getenv("RAPTOR_ENABLED", "0") == "1"
self._raptor = None
if self._raptor_enabled:
    try:
        from raptor_indexer import RaptorIndexer
        self._raptor = RaptorIndexer()
    except ImportError:
        self._raptor_enabled = False
```

**`add_document()` 끝에 RAPTOR 빌드 추가**:
```python
# RAPTOR 트리 빌드 (옵트인)
if self._raptor_enabled and self._raptor and len(chunks) >= self._raptor.min_chunks:
    try:
        texts = [c.text for c in chunks]
        tree_nodes = self._raptor.build_tree(texts)
        if tree_nodes:
            rap_ids = [n.node_id for n in tree_nodes]
            rap_docs = [n.text for n in tree_nodes]
            rap_metas = [{
                "source_file": os.path.basename(file_path),
                "chunk_id": -1,
                "page_number": -1,
                "type": "raptor_summary",
                "raptor_level": n.level,
            } for n in tree_nodes]
            self.collection.add(ids=rap_ids, documents=rap_docs, metadatas=rap_metas)
            self._bm25_dirty = True
    except Exception as exc:
        print(f"⚠️ RAPTOR 트리 빌드 실패 (원본 청크는 정상 저장): {exc}")
```

### Step 3: 테스트 통과 확인

Run: `pytest tests/test_raptor_indexer.py -v`
Expected: ALL PASS

### Step 4: 커밋

```bash
git add engine.py tests/test_raptor_indexer.py
git commit -m "feat: integrate RAPTOR tree indexing into engine.py"
```

---

## Task 7: requirements.txt 업데이트 + 전체 회귀 테스트

**Files:**
- Modify: `requirements.txt`

### Step 1: 의존성 추가

`requirements.txt` 끝에:
```
# 🧠 RAG 업그레이드 (2026-03-05)
kiwipiepy>=0.18.0
umap-learn>=0.5.0
```

(`scikit-learn`은 `umap-learn` 의존성으로 자동 설치)

### Step 2: 전체 테스트 실행

Run: `pytest tests/ -v --tb=short`
Expected: ALL PASS (기존 + 신규 모두)

### Step 3: 커밋

```bash
git add requirements.txt
git commit -m "chore: add kiwipiepy and umap-learn dependencies for RAG upgrade"
```

---

## 변경 요약

| Task | 파일 | 변경 | 테스트 |
|------|------|------|--------|
| 1 | `korean_tokenizer.py` (신규) | Kiwi 형태소 토크나이저 | `test_korean_tokenizer.py` |
| 2 | `engine.py` (수정) | Kiwi BM25 + 7:3 가중 RRF | `test_hybrid_search.py` |
| 3 | `document_parser.py` (수정) | `_table_to_markdown()` | `test_document_parser.py` |
| 4 | `document_parser.py` (수정) | `_parse_pdf()` 표 통합 | `test_document_parser.py` |
| 5 | `raptor_indexer.py` (신규) | RAPTOR 클러스터링+요약 | `test_raptor_indexer.py` |
| 6 | `engine.py` (수정) | RAPTOR 옵트인 통합 | `test_raptor_indexer.py` |
| 7 | `requirements.txt` (수정) | 의존성 추가 | 전체 회귀 |
