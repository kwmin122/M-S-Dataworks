# Phase 1: A-lite 제안서 MVP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a proposal generation MVP where users upload an RFP and get a structured DOCX proposal draft in under 10 minutes — using Layer 1 knowledge only (no company DB required).

**Architecture:** Extend the existing `rag_engine/` FastAPI microservice with new modules: knowledge DB (ChromaDB collection for Layer 1 expertise), proposal planner (RFP → section outline), section writer (Layer 1-augmented LLM generation), quality checker (anti-pattern gate), and document assembler (DOCX output). The legacy backend (`services/web_app/main.py`) proxies to this service. The React Chat UI adds a "제안서 생성" flow after GO/NO-GO analysis.

**Tech Stack:** Python 3.11+ / FastAPI / ChromaDB / OpenAI GPT-4o-mini / python-docx / pytest

**Design Doc:** `docs/plans/2026-02-27-full-lifecycle-expansion-design.md`

---

## Week 1-2: Mini Layer 1 + A-lite 제안서 MVP

### Task 1: Knowledge Unit Data Models

**Files:**
- Create: `rag_engine/knowledge_models.py`
- Test: `rag_engine/tests/test_knowledge_models.py`

**Context:** All Layer 1 knowledge is stored as `KnowledgeUnit` objects — structured JSON with category, rule, confidence, freshness. These are the atoms of the knowledge DB. See design doc §2-1 Step 2 for the 7-category system.

**Step 1: Write the failing test**

```python
# rag_engine/tests/test_knowledge_models.py
from __future__ import annotations
import pytest
from knowledge_models import (
    KnowledgeUnit,
    KnowledgeCategory,
    SourceType,
    compute_confidence,
    compute_freshness,
)


def test_knowledge_unit_creation():
    unit = KnowledgeUnit(
        category=KnowledgeCategory.WRITING,
        subcategory="page_layout",
        rule="한 페이지에 핵심 메시지는 1개만 담는다",
        explanation="평가위원은 시간이 없어서 캡션과 강조 문구만 본다.",
        example_good="[핵심] 본 사업은 클라우드 전환을 통해 운영비 30% 절감을 달성합니다.",
        example_bad="본 사업은 클라우드 전환, 보안 강화, 운영 효율화, 데이터 분석을 통해...",
        source_type=SourceType.YOUTUBE,
        source_id="video_abc123",
        raw_confidence=0.75,
    )
    assert unit.category == KnowledgeCategory.WRITING
    assert unit.is_valid()


def test_compute_confidence_cross_validation():
    # 1 source → ×1.0
    assert compute_confidence(base=0.75, source_count=1) == 0.75
    # 2 sources → ×1.2
    assert compute_confidence(base=0.75, source_count=2) == 0.90
    # 3+ sources → ×1.4 (capped at 0.95)
    assert compute_confidence(base=0.75, source_count=3) == 0.95  # 0.75*1.4=1.05 → cap


def test_compute_confidence_source_type_base():
    assert compute_confidence(base=0.85, source_count=1) == 0.85  # official_guide
    assert compute_confidence(base=0.35, source_count=1) == 0.35  # blog


def test_compute_freshness():
    from datetime import date
    today = date(2026, 3, 1)
    assert compute_freshness(date(2026, 1, 1), today) == 1.0   # < 6 months
    assert compute_freshness(date(2025, 6, 1), today) == 0.9   # 6-12 months
    assert compute_freshness(date(2024, 6, 1), today) == 0.7   # 1-2 years
    assert compute_freshness(date(2023, 1, 1), today) == 0.5   # 2+ years


def test_compute_freshness_law_based():
    from datetime import date
    today = date(2026, 3, 1)
    # Law-based knowledge never decays until superseded
    assert compute_freshness(date(2020, 1, 1), today, is_law_based=True) == 1.0


def test_knowledge_unit_effective_score():
    unit = KnowledgeUnit(
        category=KnowledgeCategory.EVALUATION,
        subcategory="scoring",
        rule="기술성 배점 70점 중 구현방안이 30점으로 가장 높다",
        explanation="구현방안에 가장 많은 지면을 할애해야 한다.",
        source_type=SourceType.OFFICIAL_GUIDE,
        raw_confidence=0.85,
        source_count=2,
        source_date="2025-09",
    )
    # effective_score = confidence × freshness
    score = unit.effective_score()
    assert 0.0 < score <= 1.0
```

**Step 2: Run test to verify it fails**

Run: `cd rag_engine && python -m pytest tests/test_knowledge_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'knowledge_models'`

**Step 3: Write minimal implementation**

```python
# rag_engine/knowledge_models.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional


class KnowledgeCategory(str, Enum):
    STRUCTURE = "structure"
    EVALUATION = "evaluation"
    WRITING = "writing"
    VISUAL = "visual"
    STRATEGY = "strategy"
    COMPLIANCE = "compliance"
    PITFALL = "pitfall"


class SourceType(str, Enum):
    YOUTUBE = "youtube"
    OFFICIAL_GUIDE = "official_guide"
    BLOG = "blog"
    TEXTBOOK = "textbook"
    EVALUATOR_YOUTUBE = "evaluator_youtube"
    WINNER_STORY = "winner_story"
    CONSULTANT = "consultant"


# Source-weighted base confidence (design doc §2-1 Step 2-A)
SOURCE_BASE_CONFIDENCE: dict[SourceType, float] = {
    SourceType.OFFICIAL_GUIDE: 0.85,
    SourceType.EVALUATOR_YOUTUBE: 0.75,
    SourceType.WINNER_STORY: 0.70,
    SourceType.CONSULTANT: 0.55,
    SourceType.YOUTUBE: 0.55,
    SourceType.BLOG: 0.35,
    SourceType.TEXTBOOK: 0.80,
}


def compute_confidence(base: float, source_count: int) -> float:
    """Source-Weighted Confidence = base × cross_validation_multiplier (cap 0.95)."""
    if source_count >= 3:
        multiplier = 1.4
    elif source_count == 2:
        multiplier = 1.2
    else:
        multiplier = 1.0
    return min(round(base * multiplier, 2), 0.95)


def compute_freshness(
    source_date: date,
    today: Optional[date] = None,
    is_law_based: bool = False,
) -> float:
    """Temporal versioning: freshness score decays over time (design doc §2-1 Step 2-B)."""
    if is_law_based:
        return 1.0
    if today is None:
        today = date.today()
    months = (today.year - source_date.year) * 12 + (today.month - source_date.month)
    if months < 6:
        return 1.0
    if months < 12:
        return 0.9
    if months < 24:
        return 0.7
    return 0.5


@dataclass
class KnowledgeUnit:
    category: KnowledgeCategory
    subcategory: str
    rule: str
    explanation: str
    source_type: SourceType
    raw_confidence: float = 0.5
    source_count: int = 1
    source_date: str = ""  # "YYYY-MM" format
    source_id: str = ""
    example_good: str = ""
    example_bad: str = ""
    superseded_by: Optional[str] = None
    deprecated_by: Optional[str] = None        # conflict loser → winner link
    is_law_based: bool = False
    condition: str = ""                         # 조건부 분기 규칙의 적용 조건 (Pass 2 CONDITIONAL)
    has_conflict_flag: bool = False             # 진짜 충돌이 있었던 규칙 (승자)
    tags: list[str] = field(default_factory=list)

    def is_valid(self) -> bool:
        return bool(self.rule and self.category and self.explanation)

    def confidence(self) -> float:
        return compute_confidence(self.raw_confidence, self.source_count)

    def freshness(self) -> float:
        if not self.source_date:
            return 0.7  # unknown date → moderate penalty
        parts = self.source_date.split("-")
        src = date(int(parts[0]), int(parts[1]) if len(parts) > 1 else 1, 1)
        return compute_freshness(src, is_law_based=self.is_law_based)

    def effective_score(self) -> float:
        """confidence × freshness — used for ranking knowledge during retrieval."""
        return round(self.confidence() * self.freshness(), 3)

    def to_dict(self) -> dict:
        return {
            "category": self.category.value,
            "subcategory": self.subcategory,
            "rule": self.rule,
            "explanation": self.explanation,
            "example_good": self.example_good,
            "example_bad": self.example_bad,
            "source_type": self.source_type.value,
            "source_id": self.source_id,
            "raw_confidence": self.raw_confidence,
            "source_count": self.source_count,
            "source_date": self.source_date,
            "is_law_based": self.is_law_based,
            "condition": self.condition,
            "has_conflict_flag": self.has_conflict_flag,
            "deprecated_by": self.deprecated_by,
            "tags": self.tags,
        }


@dataclass
class ProposalSection:
    """One section of a proposal outline, mapped to an RFP evaluation criterion."""
    name: str                       # e.g. "사업 이해도"
    evaluation_item: str            # e.g. "사업 이해 및 분석"
    max_score: float                # e.g. 15.0
    weight: float                   # relative weight 0~1
    subsections: list[str] = field(default_factory=list)
    instructions: str = ""          # LLM-generated writing instructions


@dataclass
class ProposalOutline:
    """Complete proposal structure derived from RFP analysis."""
    title: str
    issuing_org: str
    sections: list[ProposalSection]
    total_pages_target: int = 50
    format_rules: dict = field(default_factory=dict)  # page size, font, etc.
```

**Step 4: Run test to verify it passes**

Run: `cd rag_engine && python -m pytest tests/test_knowledge_models.py -v`
Expected: All 6 tests PASS

**Step 5: Commit**

```bash
git add rag_engine/knowledge_models.py rag_engine/tests/test_knowledge_models.py
git commit -m "feat: add KnowledgeUnit data models with confidence scoring and freshness"
```

---

### Task 2: Knowledge DB — ChromaDB Collection for Layer 1

**Files:**
- Create: `rag_engine/knowledge_db.py`
- Test: `rag_engine/tests/test_knowledge_db.py`
- Reference: `rag_engine/engine.py` (existing RAGEngine pattern)

**Context:** Wraps ChromaDB for the `proposal_knowledge` collection. Unlike the existing RAGEngine (which stores document chunks), this stores structured KnowledgeUnit objects with rich metadata. Search returns units ranked by `effective_score = confidence × freshness`.

**Step 1: Write the failing test**

```python
# rag_engine/tests/test_knowledge_db.py
from __future__ import annotations
import pytest
import tempfile
import shutil
from knowledge_models import KnowledgeUnit, KnowledgeCategory, SourceType
from knowledge_db import KnowledgeDB


@pytest.fixture
def tmp_db(tmp_path):
    db = KnowledgeDB(persist_directory=str(tmp_path / "test_kb"))
    yield db


def test_add_and_search(tmp_db):
    unit = KnowledgeUnit(
        category=KnowledgeCategory.WRITING,
        subcategory="page_layout",
        rule="한 페이지에 핵심 메시지는 1개만 담는다",
        explanation="평가위원은 시간이 없어서 캡션과 강조 문구만 본다.",
        source_type=SourceType.YOUTUBE,
        raw_confidence=0.75,
        source_count=1,
        source_date="2025-09",
    )
    tmp_db.add(unit)
    results = tmp_db.search("페이지 레이아웃 핵심 메시지", top_k=3)
    assert len(results) >= 1
    assert results[0].rule == unit.rule


def test_search_by_category(tmp_db):
    tmp_db.add(KnowledgeUnit(
        category=KnowledgeCategory.PITFALL,
        subcategory="blind_eval",
        rule="블라인드 평가에서 회사명 노출은 즉시 탈락",
        explanation="회사명, 로고 등 식별 정보가 제안서에 포함되면 감점 또는 탈락.",
        source_type=SourceType.OFFICIAL_GUIDE,
        raw_confidence=0.85,
    ))
    tmp_db.add(KnowledgeUnit(
        category=KnowledgeCategory.WRITING,
        subcategory="tone",
        rule="격식체 사용",
        explanation="공공 제안서는 격식체가 기본.",
        source_type=SourceType.BLOG,
        raw_confidence=0.35,
    ))
    pitfalls = tmp_db.search("감점 요소", top_k=5, category=KnowledgeCategory.PITFALL)
    assert all(r.category == KnowledgeCategory.PITFALL for r in pitfalls)


def test_count(tmp_db):
    assert tmp_db.count() == 0
    tmp_db.add(KnowledgeUnit(
        category=KnowledgeCategory.STRUCTURE,
        subcategory="outline",
        rule="test rule",
        explanation="test explanation",
        source_type=SourceType.BLOG,
    ))
    assert tmp_db.count() == 1


def test_add_batch(tmp_db):
    units = [
        KnowledgeUnit(
            category=KnowledgeCategory.EVALUATION,
            subcategory=f"item_{i}",
            rule=f"평가 규칙 {i}",
            explanation=f"설명 {i}",
            source_type=SourceType.OFFICIAL_GUIDE,
        )
        for i in range(5)
    ]
    tmp_db.add_batch(units)
    assert tmp_db.count() == 5
```

**Step 2: Run test to verify it fails**

Run: `cd rag_engine && python -m pytest tests/test_knowledge_db.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'knowledge_db'`

**Step 3: Write minimal implementation**

```python
# rag_engine/knowledge_db.py
from __future__ import annotations

import hashlib
from typing import Optional

import chromadb
from chromadb.config import Settings

from knowledge_models import KnowledgeCategory, KnowledgeUnit


class KnowledgeDB:
    """ChromaDB wrapper for the proposal_knowledge collection (Layer 1)."""

    COLLECTION_NAME = "proposal_knowledge"

    def __init__(
        self,
        persist_directory: str = "./data/knowledge_db",
        embedding_model: str = "text-embedding-3-small",
    ):
        self._client = chromadb.Client(Settings(
            chroma_db_impl="duckdb+parquet",
            persist_directory=persist_directory,
            anonymized_telemetry=False,
        ))
        self._embedding_model = embedding_model
        # Use default embedding function (chromadb's built-in or OpenAI)
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def _make_id(self, unit: KnowledgeUnit) -> str:
        h = hashlib.sha256(f"{unit.category.value}:{unit.rule}".encode()).hexdigest()[:16]
        return f"kn_{h}"

    def _make_document(self, unit: KnowledgeUnit) -> str:
        """Concatenate rule + explanation for embedding. Include condition for contextual matching."""
        parts = [unit.rule]
        if unit.condition:
            parts.append(f"[조건: {unit.condition}]")
        parts.append(unit.explanation)
        if unit.example_good:
            parts.append(f"좋은 예시: {unit.example_good}")
        if unit.example_bad:
            parts.append(f"나쁜 예시: {unit.example_bad}")
        return "\n".join(parts)

    def add(self, unit: KnowledgeUnit) -> None:
        doc_id = self._make_id(unit)
        self._collection.upsert(
            ids=[doc_id],
            documents=[self._make_document(unit)],
            metadatas=[{
                "category": unit.category.value,
                "subcategory": unit.subcategory,
                "rule": unit.rule,
                "source_type": unit.source_type.value,
                "raw_confidence": unit.raw_confidence,
                "source_count": unit.source_count,
                "source_date": unit.source_date,
                "is_law_based": unit.is_law_based,
                "condition": unit.condition,
                "has_conflict_flag": unit.has_conflict_flag,
            }],
        )

    def add_batch(self, units: list[KnowledgeUnit]) -> None:
        if not units:
            return
        ids = [self._make_id(u) for u in units]
        docs = [self._make_document(u) for u in units]
        metas = [{
            "category": u.category.value,
            "subcategory": u.subcategory,
            "rule": u.rule,
            "source_type": u.source_type.value,
            "raw_confidence": u.raw_confidence,
            "source_count": u.source_count,
            "source_date": u.source_date,
            "is_law_based": u.is_law_based,
            "condition": u.condition,
            "has_conflict_flag": u.has_conflict_flag,
        } for u in units]
        self._collection.upsert(ids=ids, documents=docs, metadatas=metas)

    def search(
        self,
        query: str,
        top_k: int = 10,
        category: Optional[KnowledgeCategory] = None,
    ) -> list[KnowledgeUnit]:
        where = {"category": category.value} if category else None
        results = self._collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where,
        )
        units = []
        for meta in (results.get("metadatas") or [[]])[0]:
            units.append(KnowledgeUnit(
                category=KnowledgeCategory(meta["category"]),
                subcategory=meta.get("subcategory", ""),
                rule=meta.get("rule", ""),
                explanation="",  # not stored in metadata (in document text)
                source_type=SourceType(meta["source_type"]) if meta.get("source_type") else SourceType.BLOG,
                raw_confidence=meta.get("raw_confidence", 0.5),
                source_count=meta.get("source_count", 1),
                source_date=meta.get("source_date", ""),
                is_law_based=meta.get("is_law_based", False),
            ))
        # Sort by effective_score descending
        units.sort(key=lambda u: u.effective_score(), reverse=True)
        return units

    def count(self) -> int:
        return self._collection.count()
```

Note: Import `SourceType` is needed — add at top:
```python
from knowledge_models import KnowledgeCategory, KnowledgeUnit, SourceType
```

**Step 4: Run test to verify it passes**

Run: `cd rag_engine && python -m pytest tests/test_knowledge_db.py -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add rag_engine/knowledge_db.py rag_engine/tests/test_knowledge_db.py
git commit -m "feat: add KnowledgeDB ChromaDB wrapper for Layer 1 knowledge"
```

---

### Task 3: Knowledge Harvester — LLM 2-Pass Extraction Pipeline

**Files:**
- Create: `rag_engine/knowledge_harvester.py`
- Test: `rag_engine/tests/test_knowledge_harvester.py`

**Context:** Takes raw text (YouTube transcript, blog article, official doc) and extracts structured KnowledgeUnit objects via LLM. Pass 1 = extraction, Pass 2 = dedup + merge. See design doc §2-1 Step 2.

**Step 1: Write the failing test**

```python
# rag_engine/tests/test_knowledge_harvester.py
from __future__ import annotations
import json
import pytest
from unittest.mock import patch, MagicMock
from knowledge_harvester import KnowledgeHarvester, extract_knowledge_units
from knowledge_models import KnowledgeCategory, SourceType


SAMPLE_TRANSCRIPT = """
제안서를 쓸 때 가장 중요한 건 평가위원의 시선입니다.
평가위원은 제안서를 처음부터 끝까지 안 읽어요.
캡션, 강조 문구, 그래픽만 봅니다.
그래서 한 페이지에 핵심 메시지는 딱 하나만 넣어야 합니다.
그리고 블라인드 평가에서 회사명이 노출되면 바로 감점이에요.
꼭 확인하세요.
"""

MOCK_LLM_RESPONSE = json.dumps([
    {
        "category": "writing",
        "subcategory": "page_layout",
        "rule": "한 페이지에 핵심 메시지는 1개만 담는다",
        "explanation": "평가위원은 시간이 없어서 캡션과 강조 문구만 본다.",
        "example_good": "",
        "example_bad": "",
        "confidence": 0.75,
    },
    {
        "category": "pitfall",
        "subcategory": "blind_evaluation",
        "rule": "블라인드 평가에서 회사명 노출 시 감점",
        "explanation": "회사명, 로고 등 식별 가능 정보가 포함되면 감점 또는 탈락 처리.",
        "example_good": "",
        "example_bad": "",
        "confidence": 0.85,
    },
])


def test_extract_knowledge_units_from_text():
    """Mock LLM and verify extraction pipeline."""
    with patch("knowledge_harvester._call_llm_for_extraction") as mock_llm:
        mock_llm.return_value = MOCK_LLM_RESPONSE
        units = extract_knowledge_units(
            text=SAMPLE_TRANSCRIPT,
            source_type=SourceType.YOUTUBE,
            source_id="test_video_001",
            source_date="2025-09",
        )
    assert len(units) == 2
    assert units[0].category == KnowledgeCategory.WRITING
    assert units[1].category == KnowledgeCategory.PITFALL
    assert units[0].source_type == SourceType.YOUTUBE
    assert units[0].source_id == "test_video_001"


def test_extract_handles_empty_response():
    with patch("knowledge_harvester._call_llm_for_extraction") as mock_llm:
        mock_llm.return_value = "[]"
        units = extract_knowledge_units(
            text="짧은 텍스트",
            source_type=SourceType.BLOG,
        )
    assert units == []


def test_extract_handles_invalid_json():
    with patch("knowledge_harvester._call_llm_for_extraction") as mock_llm:
        mock_llm.return_value = "not valid json"
        units = extract_knowledge_units(
            text="어떤 텍스트",
            source_type=SourceType.BLOG,
        )
    assert units == []
```

**Step 2: Run test to verify it fails**

Run: `cd rag_engine && python -m pytest tests/test_knowledge_harvester.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'knowledge_harvester'`

**Step 3: Write minimal implementation**

```python
# rag_engine/knowledge_harvester.py
from __future__ import annotations

import json
import logging
import os
from typing import Optional

from openai import OpenAI

from knowledge_models import (
    KnowledgeCategory,
    KnowledgeUnit,
    SourceType,
    SOURCE_BASE_CONFIDENCE,
)

logger = logging.getLogger(__name__)

EXTRACTION_SYSTEM_PROMPT = """당신은 공공조달 제안서 전문가입니다.
아래 텍스트에서 제안서 작성에 도움이 되는 지식을 추출하세요.

각 지식 단위를 다음 JSON 배열 형식으로 출력하세요:
[
  {
    "category": "structure|evaluation|writing|visual|strategy|compliance|pitfall",
    "subcategory": "세부 분류 (자유 문자열)",
    "rule": "한 문장으로 된 핵심 규칙",
    "explanation": "왜 이 규칙이 중요한지 2-3문장",
    "example_good": "잘 쓴 예시 (있으면, 없으면 빈 문자열)",
    "example_bad": "못 쓴 예시 (있으면, 없으면 빈 문자열)",
    "confidence": 0.0에서 1.0 사이의 확신도
  }
]

카테고리 설명:
- structure: 문서 구조, 목차, 섹션 순서
- evaluation: 평가기준, 배점, 점수 배분
- writing: 작성 기법, 문체, 표현법
- visual: 시각화, 레이아웃, 다이어그램
- strategy: 전략적 판단, 발주처 유형별 접근
- compliance: 규정, 자격요건, 법적 요구사항
- pitfall: 흔한 실수, 감점 요소, 탈락 사유

중요: JSON 배열만 출력하세요. 다른 텍스트 없이."""

VALID_CATEGORIES = {c.value for c in KnowledgeCategory}


def _call_llm_for_extraction(text: str, api_key: Optional[str] = None) -> str:
    """Call LLM to extract knowledge from raw text. Returns JSON string."""
    client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": f"다음 텍스트에서 지식을 추출하세요:\n\n{text[:12000]}"},
        ],
        temperature=0.2,
        max_tokens=4000,
    )
    return resp.choices[0].message.content or "[]"


def extract_knowledge_units(
    text: str,
    source_type: SourceType,
    source_id: str = "",
    source_date: str = "",
    api_key: Optional[str] = None,
) -> list[KnowledgeUnit]:
    """Pass 1: Extract KnowledgeUnits from raw text via LLM."""
    raw = _call_llm_for_extraction(text, api_key)
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM extraction response as JSON")
        return []

    if not isinstance(items, list):
        return []

    units: list[KnowledgeUnit] = []
    base_conf = SOURCE_BASE_CONFIDENCE.get(source_type, 0.5)
    for item in items:
        cat_str = item.get("category", "")
        if cat_str not in VALID_CATEGORIES:
            continue
        unit = KnowledgeUnit(
            category=KnowledgeCategory(cat_str),
            subcategory=item.get("subcategory", ""),
            rule=item.get("rule", ""),
            explanation=item.get("explanation", ""),
            example_good=item.get("example_good", ""),
            example_bad=item.get("example_bad", ""),
            source_type=source_type,
            source_id=source_id,
            source_date=source_date,
            raw_confidence=base_conf,
            source_count=1,
        )
        if unit.is_valid():
            units.append(unit)
    return units
```

**Step 4: Run test to verify it passes**

Run: `cd rag_engine && python -m pytest tests/test_knowledge_harvester.py -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add rag_engine/knowledge_harvester.py rag_engine/tests/test_knowledge_harvester.py
git commit -m "feat: add knowledge harvester LLM extraction pipeline (Pass 1)"
```

---

### Task 3-B: Knowledge Deduplicator — Pass 2 Conflict Resolution

**Files:**
- Create: `rag_engine/knowledge_dedup.py`
- Test: `rag_engine/tests/test_knowledge_dedup.py`

**Context:** Pass 2 of the knowledge distillation pipeline. Takes Pass 1 extracted units, deduplicates against existing DB, and resolves conflicts via 3-step pipeline: AGREE (merge), CONDITIONAL (split with condition), CONFLICT (weighted vote). See design doc §2-1 Pass 2 "모순 해소 3단계".

**Step 1: Write the failing test**

```python
# rag_engine/tests/test_knowledge_dedup.py
from __future__ import annotations
import json
import pytest
from unittest.mock import patch
from knowledge_dedup import (
    classify_relationship,
    resolve_and_merge,
    ConflictResolution,
)
from knowledge_models import KnowledgeUnit, KnowledgeCategory, SourceType


def _make_unit(rule, category=KnowledgeCategory.WRITING, confidence=0.55, source=SourceType.YOUTUBE):
    return KnowledgeUnit(
        category=category,
        subcategory="test",
        rule=rule,
        explanation=f"설명: {rule}",
        source_type=source,
        raw_confidence=confidence,
        source_count=1,
    )


MOCK_AGREE = json.dumps({
    "verdict": "AGREE",
    "condition_a": "",
    "condition_b": "",
    "winner": "",
    "reasoning": "같은 내용을 다르게 표현",
})

MOCK_CONDITIONAL = json.dumps({
    "verdict": "CONDITIONAL",
    "condition_a": "적격심사 방식 입찰일 때",
    "condition_b": "기술평가 방식 입찰일 때",
    "winner": "",
    "reasoning": "입찰 방식에 따라 적용이 다름",
})

MOCK_CONFLICT = json.dumps({
    "verdict": "CONFLICT",
    "condition_a": "",
    "condition_b": "",
    "winner": "B",
    "reasoning": "공식 가이드가 더 정확함",
})


def test_classify_agree():
    with patch("knowledge_dedup._call_llm_for_classification") as mock_llm:
        mock_llm.return_value = MOCK_AGREE
        result = classify_relationship(
            _make_unit("한 페이지에 핵심 메시지 1개"),
            _make_unit("페이지당 하나의 메시지만"),
        )
    assert result.verdict == "AGREE"


def test_classify_conditional():
    with patch("knowledge_dedup._call_llm_for_classification") as mock_llm:
        mock_llm.return_value = MOCK_CONDITIONAL
        result = classify_relationship(
            _make_unit("실적기술서는 최대한 많이 넣어라"),
            _make_unit("실적기술서는 상위 5건만 선별"),
        )
    assert result.verdict == "CONDITIONAL"
    assert "적격심사" in result.condition_a
    assert "기술평가" in result.condition_b


def test_classify_conflict():
    with patch("knowledge_dedup._call_llm_for_classification") as mock_llm:
        mock_llm.return_value = MOCK_CONFLICT
        result = classify_relationship(
            _make_unit("표지에 사업명만 적는다"),
            _make_unit("표지에 사업명+제안사명+제출일자"),
        )
    assert result.verdict == "CONFLICT"
    assert result.winner == "B"


def test_resolve_agree_merges():
    unit_a = _make_unit("핵심 메시지 1개", confidence=0.55)
    unit_b = _make_unit("페이지당 메시지 1개", confidence=0.35)
    with patch("knowledge_dedup._call_llm_for_classification") as mock_llm:
        mock_llm.return_value = MOCK_AGREE
        merged = resolve_and_merge(unit_a, unit_b)
    assert len(merged) == 1
    assert merged[0].source_count == 2  # sources merged


def test_resolve_conditional_splits():
    unit_a = _make_unit("실적 많이 넣어라", confidence=0.55)
    unit_b = _make_unit("실적 5건만", confidence=0.85, source=SourceType.OFFICIAL_GUIDE)
    with patch("knowledge_dedup._call_llm_for_classification") as mock_llm:
        mock_llm.return_value = MOCK_CONDITIONAL
        result = resolve_and_merge(unit_a, unit_b)
    assert len(result) == 2  # both kept
    assert result[0].condition != ""
    assert result[1].condition != ""


def test_resolve_conflict_marks_winner():
    unit_a = _make_unit("표지에 사업명만", confidence=0.35, source=SourceType.BLOG)
    unit_b = _make_unit("표지에 사업명+제안사명+일자", confidence=0.85, source=SourceType.OFFICIAL_GUIDE)
    with patch("knowledge_dedup._call_llm_for_classification") as mock_llm:
        mock_llm.return_value = MOCK_CONFLICT
        result = resolve_and_merge(unit_a, unit_b)
    winner = [u for u in result if u.has_conflict_flag]
    loser = [u for u in result if u.deprecated_by]
    assert len(winner) == 1  # winner marked
    assert len(loser) == 1   # loser kept but deprecated
    assert loser[0].raw_confidence < 0.35  # confidence penalized
```

**Step 2: Run test to verify it fails**

Run: `cd rag_engine && python -m pytest tests/test_knowledge_dedup.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'knowledge_dedup'`

**Step 3: Write minimal implementation**

```python
# rag_engine/knowledge_dedup.py
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Optional

from openai import OpenAI

from knowledge_models import KnowledgeUnit

logger = logging.getLogger(__name__)

CLASSIFICATION_PROMPT = """두 지식 단위가 모순인지 판별하세요:

Rule A: "{rule_a}" (소스: {source_a})
Rule B: "{rule_b}" (소스: {source_b})

다음 중 하나로 답하세요:
1. AGREE — 같은 내용을 다르게 표현 (→ 병합)
2. CONDITIONAL — 둘 다 맞지만 적용 조건이 다름 (→ 각각의 condition 설명)
3. CONFLICT — 같은 상황에서 다른 결론 (→ 어느 쪽이 더 정확한지 근거 제시)

JSON 형식으로만 답하세요:
{{"verdict": "AGREE|CONDITIONAL|CONFLICT", "condition_a": "", "condition_b": "", "winner": "A|B", "reasoning": ""}}"""


@dataclass
class ConflictResolution:
    rule_a_id: str
    rule_b_id: str
    verdict: str          # AGREE | CONDITIONAL | CONFLICT
    condition_a: str
    condition_b: str
    winner: str
    reasoning: str


def _call_llm_for_classification(rule_a: str, source_a: str, rule_b: str, source_b: str, api_key: Optional[str] = None) -> str:
    client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
    prompt = CLASSIFICATION_PROMPT.format(rule_a=rule_a, source_a=source_a, rule_b=rule_b, source_b=source_b)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=500,
    )
    return resp.choices[0].message.content or "{}"


def classify_relationship(unit_a: KnowledgeUnit, unit_b: KnowledgeUnit) -> ConflictResolution:
    """Classify the relationship between two similar knowledge units."""
    raw = _call_llm_for_classification(
        unit_a.rule, unit_a.source_type.value,
        unit_b.rule, unit_b.source_type.value,
    )
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Failed to parse conflict classification response")
        data = {"verdict": "AGREE", "reasoning": "parse_error_fallback"}

    return ConflictResolution(
        rule_a_id=f"{unit_a.category.value}:{unit_a.rule[:50]}",
        rule_b_id=f"{unit_b.category.value}:{unit_b.rule[:50]}",
        verdict=data.get("verdict", "AGREE"),
        condition_a=data.get("condition_a", ""),
        condition_b=data.get("condition_b", ""),
        winner=data.get("winner", ""),
        reasoning=data.get("reasoning", ""),
    )


def resolve_and_merge(unit_a: KnowledgeUnit, unit_b: KnowledgeUnit) -> list[KnowledgeUnit]:
    """Resolve relationship and return merged/split/marked units."""
    resolution = classify_relationship(unit_a, unit_b)

    if resolution.verdict == "AGREE":
        # Merge: keep unit_a, increment source_count
        unit_a.source_count += 1
        return [unit_a]

    elif resolution.verdict == "CONDITIONAL":
        # Split: both survive with condition field
        unit_a.condition = resolution.condition_a
        unit_b.condition = resolution.condition_b
        return [unit_a, unit_b]

    elif resolution.verdict == "CONFLICT":
        # Weighted vote: winner keeps confidence, loser gets penalty
        if resolution.winner == "B":
            winner, loser = unit_b, unit_a
        else:
            winner, loser = unit_a, unit_b
        winner.has_conflict_flag = True
        loser.deprecated_by = winner.rule[:50]
        loser.raw_confidence = round(loser.raw_confidence * 0.3, 3)
        return [winner, loser]

    # Fallback: treat as agree
    unit_a.source_count += 1
    return [unit_a]
```

**Step 4: Run test to verify it passes**

Run: `cd rag_engine && python -m pytest tests/test_knowledge_dedup.py -v`
Expected: All 6 tests PASS

**Step 5: Commit**

```bash
git add rag_engine/knowledge_dedup.py rag_engine/tests/test_knowledge_dedup.py
git commit -m "feat: add Pass 2 knowledge deduplicator with 3-step conflict resolution"
```

---

### Task 4: Proposal Planner — RFP → Section Outline

**Files:**
- Create: `rag_engine/proposal_planner.py`
- Test: `rag_engine/tests/test_proposal_planner.py`
- Reference: `rag_engine/rfx_analyzer.py` (RFxAnalysisResult structure)

**Context:** Takes RFxAnalysisResult (already extracted by existing analyzer) and generates a ProposalOutline — ordered list of sections mapped to evaluation criteria with page targets. This is the "skeleton" before section writing. See design doc §3 Module A.

**Step 1: Write the failing test**

```python
# rag_engine/tests/test_proposal_planner.py
from __future__ import annotations
import pytest
from unittest.mock import patch
from knowledge_models import ProposalOutline, ProposalSection
from proposal_planner import build_proposal_outline


def _make_rfx_result():
    """Minimal RFxAnalysisResult-like dict for testing."""
    return {
        "title": "XX기관 정보시스템 구축 사업",
        "issuing_org": "XX기관",
        "budget": "5억원",
        "project_period": "12개월",
        "evaluation_criteria": [
            {"category": "사업 이해도", "max_score": 15, "description": "사업 배경 및 목적 이해"},
            {"category": "기술성", "max_score": 40, "description": "시스템 아키텍처, 구현방안"},
            {"category": "수행관리", "max_score": 15, "description": "일정관리, 품질관리, 리스크관리"},
        ],
        "requirements": [
            {"category": "기술요건", "description": "클라우드 기반 웹 시스템 구축"},
        ],
    }


def test_build_outline_from_evaluation_criteria():
    rfx = _make_rfx_result()
    outline = build_proposal_outline(rfx, total_pages=50)
    assert isinstance(outline, ProposalOutline)
    assert outline.title == rfx["title"]
    assert len(outline.sections) >= 3  # at least one per eval criterion
    # Pages proportional to score weights
    tech_section = next(s for s in outline.sections if "기술" in s.name)
    understand_section = next(s for s in outline.sections if "이해" in s.name)
    assert tech_section.weight > understand_section.weight


def test_build_outline_includes_standard_sections():
    """Outline always includes: 표지, 요약, 사업이해, 기술, 관리, 인력, 일정."""
    rfx = _make_rfx_result()
    outline = build_proposal_outline(rfx, total_pages=50)
    section_names = [s.name for s in outline.sections]
    # Should have at minimum these standard structural sections
    assert any("요약" in n or "개요" in n for n in section_names)


def test_build_outline_empty_eval_criteria():
    """When no eval criteria, use standard template."""
    rfx = {"title": "테스트", "issuing_org": "테스트기관", "evaluation_criteria": [], "requirements": []}
    outline = build_proposal_outline(rfx, total_pages=30)
    assert len(outline.sections) >= 3  # standard fallback sections
```

**Step 2: Run test to verify it fails**

Run: `cd rag_engine && python -m pytest tests/test_proposal_planner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'proposal_planner'`

**Step 3: Write minimal implementation**

```python
# rag_engine/proposal_planner.py
from __future__ import annotations

from typing import Any

from knowledge_models import ProposalOutline, ProposalSection

# Standard fallback sections when no evaluation criteria available
DEFAULT_SECTIONS = [
    ("제안 개요", 10),
    ("사업 이해도", 15),
    ("기술적 접근방안", 35),
    ("수행관리 방안", 15),
    ("투입인력 및 조직", 10),
    ("유사 수행실적", 10),
    ("기타 특이사항", 5),
]


def build_proposal_outline(
    rfx_result: dict[str, Any],
    total_pages: int = 50,
) -> ProposalOutline:
    """Build a ProposalOutline from RFxAnalysisResult dict.

    Maps evaluation criteria to sections with proportional page allocation.
    """
    title = rfx_result.get("title", "제안서")
    issuing_org = rfx_result.get("issuing_org", "")
    eval_criteria = rfx_result.get("evaluation_criteria", [])

    sections: list[ProposalSection] = []

    if eval_criteria:
        total_score = sum(ec.get("max_score", 0) for ec in eval_criteria) or 100
        for ec in eval_criteria:
            name = ec.get("category", ec.get("name", "섹션"))
            max_score = ec.get("max_score", 0)
            weight = max_score / total_score if total_score else 0
            sections.append(ProposalSection(
                name=name,
                evaluation_item=ec.get("description", ""),
                max_score=max_score,
                weight=round(weight, 3),
                instructions=f"RFP 평가항목 '{name}'에 맞춰 작성. 배점 {max_score}점.",
            ))
    else:
        total_score = sum(s for _, s in DEFAULT_SECTIONS)
        for name, score in DEFAULT_SECTIONS:
            sections.append(ProposalSection(
                name=name,
                evaluation_item=name,
                max_score=score,
                weight=round(score / total_score, 3),
            ))

    # Always prepend 제안 개요/요약 if not present
    has_overview = any("요약" in s.name or "개요" in s.name for s in sections)
    if not has_overview:
        sections.insert(0, ProposalSection(
            name="제안 개요",
            evaluation_item="Executive Summary",
            max_score=0,
            weight=0.05,
            instructions="전체 제안의 핵심을 1~2페이지로 요약. 평가위원이 가장 먼저 보는 부분.",
        ))

    # Normalize weights
    total_weight = sum(s.weight for s in sections) or 1
    for s in sections:
        s.weight = round(s.weight / total_weight, 3)

    return ProposalOutline(
        title=title,
        issuing_org=issuing_org,
        sections=sections,
        total_pages_target=total_pages,
    )
```

**Step 4: Run test to verify it passes**

Run: `cd rag_engine && python -m pytest tests/test_proposal_planner.py -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add rag_engine/proposal_planner.py rag_engine/tests/test_proposal_planner.py
git commit -m "feat: add proposal planner — RFP eval criteria to section outline"
```

---

### Task 5: Section Writer — Layer 1 Knowledge-Augmented Generation

**Files:**
- Create: `rag_engine/section_writer.py`
- Test: `rag_engine/tests/test_section_writer.py`
- Reference: `rag_engine/knowledge_db.py`, `rag_engine/knowledge_models.py`

**Context:** Generates one proposal section at a time. Retrieves relevant Layer 1 knowledge from KnowledgeDB, assembles a multi-layer prompt, calls LLM. This is the heart of A-lite — Layer 1 only, no company DB. See design doc §2-1 Step 4 for prompt assembly pattern.

**Step 1: Write the failing test**

```python
# rag_engine/tests/test_section_writer.py
from __future__ import annotations
import pytest
from unittest.mock import patch, MagicMock
from knowledge_models import ProposalSection, KnowledgeUnit, KnowledgeCategory, SourceType
from section_writer import write_section, _assemble_prompt


def test_assemble_prompt_includes_layer1_knowledge():
    section = ProposalSection(
        name="기술적 접근방안",
        evaluation_item="시스템 아키텍처 및 구현방안",
        max_score=40,
        weight=0.4,
    )
    knowledge = [
        KnowledgeUnit(
            category=KnowledgeCategory.WRITING,
            subcategory="page_layout",
            rule="한 페이지에 핵심 메시지는 1개만 담는다",
            explanation="평가위원은 시간 부족.",
            source_type=SourceType.YOUTUBE,
            raw_confidence=0.75,
        ),
    ]
    rfp_context = "클라우드 기반 웹 시스템 구축 사업"
    prompt = _assemble_prompt(section, knowledge, rfp_context)
    assert "기술적 접근방안" in prompt
    assert "핵심 메시지는 1개만" in prompt
    assert "클라우드" in prompt


def test_assemble_prompt_works_without_knowledge():
    section = ProposalSection(
        name="제안 개요",
        evaluation_item="Executive Summary",
        max_score=0,
        weight=0.05,
    )
    prompt = _assemble_prompt(section, [], "테스트 RFP")
    assert "제안 개요" in prompt


def test_write_section_returns_text():
    section = ProposalSection(
        name="사업 이해도",
        evaluation_item="사업 배경 및 목적 이해",
        max_score=15,
        weight=0.15,
    )
    with patch("section_writer._call_llm_for_section") as mock_llm:
        mock_llm.return_value = "## 사업 이해도\n\n본 사업은 XX기관의 정보시스템 현대화를 위한..."
        result = write_section(
            section=section,
            rfp_context="XX기관 정보시스템 구축",
            knowledge=[],
        )
    assert "사업 이해도" in result
    assert len(result) > 20
```

**Step 2: Run test to verify it fails**

Run: `cd rag_engine && python -m pytest tests/test_section_writer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'section_writer'`

**Step 3: Write minimal implementation**

```python
# rag_engine/section_writer.py
from __future__ import annotations

import os
from typing import Optional

from openai import OpenAI

from knowledge_models import KnowledgeUnit, ProposalSection

SYSTEM_PROMPT = """당신은 대한민국 공공조달 기술제안서 작성 전문가입니다.
평가위원이 높은 점수를 줄 수 있도록, 구체적이고 전문적인 제안서 섹션을 작성합니다.
모든 주장에는 근거를 제시하고, 추상적 표현을 피합니다.
마크다운 형식으로 작성하되, 제안서 특성에 맞게 표, 목록, 강조를 활용합니다."""


def _assemble_prompt(
    section: ProposalSection,
    knowledge: list[KnowledgeUnit],
    rfp_context: str,
    company_context: str = "",
) -> str:
    """Assemble multi-layer prompt for section writing (design doc §2-1 Step 4)."""
    parts: list[str] = []

    # Layer 1 — retrieved universal knowledge
    if knowledge:
        rules = []
        pitfalls = []
        examples = []
        for k in knowledge:
            if k.category.value == "pitfall":
                pitfalls.append(f"- {k.rule}")
            else:
                rules.append(f"- {k.rule} — {k.explanation}")
            if k.example_good:
                examples.append(f"- 좋은 예시: {k.example_good}")

        if rules:
            parts.append("## 이 유형의 제안서에 적용할 핵심 규칙:\n" + "\n".join(rules))
        if pitfalls:
            parts.append("## 흔한 실수 (반드시 피할 것):\n" + "\n".join(pitfalls))
        if examples:
            parts.append("## 참고할 좋은 예시:\n" + "\n".join(examples))

    # Layer 2 — company context (empty in A-lite)
    if company_context:
        parts.append(f"## 이 회사의 과거 제안서 스타일:\n{company_context}")

    # RFP context
    parts.append(f"## 이번 공고 정보:\n{rfp_context}")

    # Task
    page_target = max(1, int(section.weight * 50))
    parts.append(
        f"## 작성할 섹션: {section.name}\n"
        f"평가항목: {section.evaluation_item}\n"
        f"배점: {section.max_score}점\n"
        f"목표 분량: 약 {page_target}페이지\n"
        f"위 규칙과 컨텍스트를 반영하여 이 섹션을 작성하세요."
    )
    if section.instructions:
        parts.append(f"추가 지침: {section.instructions}")

    return "\n\n".join(parts)


def _call_llm_for_section(prompt: str, api_key: Optional[str] = None) -> str:
    client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
        max_tokens=4000,
    )
    return resp.choices[0].message.content or ""


def write_section(
    section: ProposalSection,
    rfp_context: str,
    knowledge: list[KnowledgeUnit],
    company_context: str = "",
    api_key: Optional[str] = None,
) -> str:
    """Generate one proposal section with Layer 1 knowledge injection."""
    prompt = _assemble_prompt(section, knowledge, rfp_context, company_context)
    return _call_llm_for_section(prompt, api_key)
```

**Step 4: Run test to verify it passes**

Run: `cd rag_engine && python -m pytest tests/test_section_writer.py -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add rag_engine/section_writer.py rag_engine/tests/test_section_writer.py
git commit -m "feat: add section writer with Layer 1 knowledge-augmented prompt assembly"
```

---

### Task 6: Quality Checker — Anti-Pattern Gate

**Files:**
- Create: `rag_engine/quality_checker.py`
- Test: `rag_engine/tests/test_quality_checker.py`

**Context:** Post-generation quality gate. Checks for common pitfalls: blind evaluation violations, vague claims without evidence, missing table explanations. Returns issues list + auto-fixes where possible. See design doc §2-1 Step 4-A.

**Step 1: Write the failing test**

```python
# rag_engine/tests/test_quality_checker.py
from __future__ import annotations
import pytest
from quality_checker import check_quality, QualityIssue


def test_detect_blind_violation():
    text = "당사 키라솔루션즈는 최고의 기술력을 보유하고 있습니다."
    issues = check_quality(text, company_name="키라솔루션즈")
    blind_issues = [i for i in issues if i.category == "blind_violation"]
    assert len(blind_issues) >= 1
    assert "키라솔루션즈" in blind_issues[0].detail


def test_detect_vague_claims():
    text = "최고 수준의 기술력으로 최적화된 시스템을 구축하겠습니다."
    issues = check_quality(text)
    vague = [i for i in issues if i.category == "vague_claim"]
    assert len(vague) >= 1


def test_clean_text_passes():
    text = """## 시스템 아키텍처

본 사업의 시스템은 3-tier 아키텍처(웹서버-WAS-DB)로 구성하며,
가용성 99.9%를 목표로 이중화 구성합니다.

| 구분 | 사양 | 수량 |
|------|------|------|
| 웹서버 | Nginx 1.25 | 2대 |

위 표와 같이 웹서버는 로드밸런서를 통해 이중화합니다."""
    issues = check_quality(text)
    critical = [i for i in issues if i.severity == "critical"]
    assert len(critical) == 0


def test_no_company_name_skip_blind_check():
    text = "당사는 최고의 기술력을 보유하고 있습니다."
    issues = check_quality(text, company_name=None)
    blind_issues = [i for i in issues if i.category == "blind_violation"]
    # "당사" alone is not necessarily a blind violation
    assert len(blind_issues) == 0
```

**Step 2: Run test to verify it fails**

Run: `cd rag_engine && python -m pytest tests/test_quality_checker.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'quality_checker'`

**Step 3: Write minimal implementation**

```python
# rag_engine/quality_checker.py
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class QualityIssue:
    category: str       # blind_violation | vague_claim | missing_explanation | format_error
    severity: str       # critical | warning | info
    detail: str
    location: str = ""  # approximate location in text
    suggestion: str = ""


# Vague claim patterns — phrases that lack evidence
VAGUE_PATTERNS = [
    r"최고\s*수준",
    r"최적화된",
    r"혁신적인",
    r"차별화된\s*기술력",
    r"탁월한\s*역량",
    r"풍부한\s*경험",
    r"우수한\s*인력",
]

VAGUE_RE = re.compile("|".join(VAGUE_PATTERNS), re.IGNORECASE)


def check_quality(
    text: str,
    company_name: Optional[str] = None,
) -> list[QualityIssue]:
    """Run anti-pattern checks on generated proposal text."""
    issues: list[QualityIssue] = []

    # 1. Blind evaluation violation: company name/brand in text
    if company_name and company_name in text:
        issues.append(QualityIssue(
            category="blind_violation",
            severity="critical",
            detail=f"회사명 '{company_name}' 이 제안서 본문에 노출됨",
            suggestion=f"'{company_name}'을 '당사' 또는 '[제안사]'로 교체",
        ))

    # 2. Vague claims without evidence
    for match in VAGUE_RE.finditer(text):
        # Check if there's a number/evidence within 200 chars after the vague claim
        after = text[match.end():match.end() + 200]
        has_evidence = bool(re.search(r"\d+[%건명억만회]", after))
        if not has_evidence:
            issues.append(QualityIssue(
                category="vague_claim",
                severity="warning",
                detail=f"근거 없는 추상 표현: '{match.group()}'",
                location=f"offset {match.start()}",
                suggestion="구체적 수치, 사례, 또는 출처를 추가하세요",
            ))

    return issues
```

**Step 4: Run test to verify it passes**

Run: `cd rag_engine && python -m pytest tests/test_quality_checker.py -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add rag_engine/quality_checker.py rag_engine/tests/test_quality_checker.py
git commit -m "feat: add quality checker anti-pattern gate for proposal text"
```

---

### Task 7: Document Assembler — DOCX Output

**Files:**
- Create: `rag_engine/document_assembler.py`
- Test: `rag_engine/tests/test_document_assembler.py`
- Dependency: `python-docx` (already in requirements.txt)

**Context:** Takes list of section texts (markdown) and assembles a .docx file with proper formatting. Uses python-docx. Output is saved to disk and returned as file path.

**Step 1: Write the failing test**

```python
# rag_engine/tests/test_document_assembler.py
from __future__ import annotations
import os
import pytest
from document_assembler import assemble_docx


def test_assemble_basic_docx(tmp_path):
    sections = [
        ("제안 개요", "## 제안 개요\n\n본 사업은 XX기관의 정보시스템 구축을 위한 제안입니다."),
        ("기술적 접근방안", "## 기술적 접근방안\n\n### 시스템 아키텍처\n\n3-tier 구조로 구성합니다.\n\n- 웹서버: Nginx\n- WAS: Spring Boot\n- DB: PostgreSQL"),
    ]
    out_path = str(tmp_path / "proposal.docx")
    result = assemble_docx(
        title="XX기관 정보시스템 구축 제안서",
        sections=sections,
        output_path=out_path,
    )
    assert os.path.exists(result)
    assert result.endswith(".docx")
    # File should be non-trivial size
    assert os.path.getsize(result) > 1000


def test_assemble_empty_sections(tmp_path):
    out_path = str(tmp_path / "empty.docx")
    result = assemble_docx(
        title="빈 제안서",
        sections=[],
        output_path=out_path,
    )
    assert os.path.exists(result)
```

**Step 2: Run test to verify it fails**

Run: `cd rag_engine && python -m pytest tests/test_document_assembler.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'document_assembler'`

**Step 3: Write minimal implementation**

```python
# rag_engine/document_assembler.py
from __future__ import annotations

import re
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH


def _add_markdown_content(doc: Document, md_text: str) -> None:
    """Parse simplified markdown and add to document."""
    lines = md_text.split("\n")
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("### "):
            p = doc.add_heading(stripped[4:], level=3)
        elif stripped.startswith("## "):
            p = doc.add_heading(stripped[3:], level=2)
        elif stripped.startswith("# "):
            p = doc.add_heading(stripped[2:], level=1)
        elif stripped.startswith("- ") or stripped.startswith("* "):
            doc.add_paragraph(stripped[2:], style="List Bullet")
        elif re.match(r"^\d+\.\s", stripped):
            text = re.sub(r"^\d+\.\s", "", stripped)
            doc.add_paragraph(text, style="List Number")
        else:
            doc.add_paragraph(stripped)


def assemble_docx(
    title: str,
    sections: list[tuple[str, str]],  # [(section_name, markdown_text), ...]
    output_path: str,
    author: str = "Kira Bot",
) -> str:
    """Assemble a DOCX proposal from section texts."""
    doc = Document()

    # Title page
    doc.core_properties.author = author
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(title)
    run.font.size = Pt(24)
    run.bold = True
    doc.add_page_break()

    # Table of contents placeholder
    doc.add_heading("목차", level=1)
    for i, (name, _) in enumerate(sections, 1):
        doc.add_paragraph(f"{i}. {name}", style="List Number")
    doc.add_page_break()

    # Sections
    for name, content in sections:
        _add_markdown_content(doc, content)
        doc.add_page_break()

    doc.save(output_path)
    return output_path
```

**Step 4: Run test to verify it passes**

Run: `cd rag_engine && python -m pytest tests/test_document_assembler.py -v`
Expected: All 2 tests PASS

**Step 5: Commit**

```bash
git add rag_engine/document_assembler.py rag_engine/tests/test_document_assembler.py
git commit -m "feat: add DOCX document assembler for proposal output"
```

---

### Task 8: Proposal Generation Orchestrator

**Files:**
- Create: `rag_engine/proposal_orchestrator.py`
- Test: `rag_engine/tests/test_proposal_orchestrator.py`

**Context:** Top-level orchestrator that ties everything together: takes RFxAnalysisResult + optional company context → builds outline → writes each section (with Layer 1 knowledge) → quality checks → assembles DOCX. This is the "one function to call" API.

**Step 1: Write the failing test**

```python
# rag_engine/tests/test_proposal_orchestrator.py
from __future__ import annotations
import os
import pytest
from unittest.mock import patch, MagicMock
from proposal_orchestrator import generate_proposal, ProposalResult


def _mock_rfx():
    return {
        "title": "테스트 정보시스템 구축",
        "issuing_org": "테스트기관",
        "budget": "3억원",
        "project_period": "8개월",
        "evaluation_criteria": [
            {"category": "사업 이해도", "max_score": 15, "description": "사업 이해"},
            {"category": "기술성", "max_score": 40, "description": "구현방안"},
        ],
        "requirements": [],
        "rfp_text_summary": "클라우드 기반 시스템 구축 사업",
    }


@patch("proposal_orchestrator.write_section")
@patch("proposal_orchestrator.KnowledgeDB")
def test_generate_proposal_returns_result(mock_kb_class, mock_write):
    mock_kb = MagicMock()
    mock_kb.search.return_value = []
    mock_kb_class.return_value = mock_kb
    mock_write.return_value = "## 섹션 내용\n\n테스트 내용입니다."

    result = generate_proposal(
        rfx_result=_mock_rfx(),
        output_dir="/tmp/test_proposals",
    )
    assert isinstance(result, ProposalResult)
    assert result.docx_path.endswith(".docx")
    assert len(result.sections) >= 2
    assert result.quality_issues is not None


@patch("proposal_orchestrator.write_section")
@patch("proposal_orchestrator.KnowledgeDB")
def test_generate_proposal_calls_section_writer_per_section(mock_kb_class, mock_write):
    mock_kb = MagicMock()
    mock_kb.search.return_value = []
    mock_kb_class.return_value = mock_kb
    mock_write.return_value = "내용"

    result = generate_proposal(
        rfx_result=_mock_rfx(),
        output_dir="/tmp/test_proposals",
    )
    # Should call write_section at least once per eval criterion + overview
    assert mock_write.call_count >= 2
```

**Step 2: Run test to verify it fails**

Run: `cd rag_engine && python -m pytest tests/test_proposal_orchestrator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'proposal_orchestrator'`

**Step 3: Write minimal implementation**

```python
# rag_engine/proposal_orchestrator.py
from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Optional

from knowledge_db import KnowledgeDB
from knowledge_models import ProposalOutline
from proposal_planner import build_proposal_outline
from section_writer import write_section
from quality_checker import check_quality, QualityIssue
from document_assembler import assemble_docx


@dataclass
class ProposalResult:
    docx_path: str
    sections: list[tuple[str, str]]  # [(name, text)]
    outline: ProposalOutline
    quality_issues: list[QualityIssue] = field(default_factory=list)
    generation_time_sec: float = 0.0


def generate_proposal(
    rfx_result: dict[str, Any],
    output_dir: str = "./data/proposals",
    knowledge_db_path: str = "./data/knowledge_db",
    company_context: str = "",
    company_name: Optional[str] = None,
    total_pages: int = 50,
    api_key: Optional[str] = None,
    max_workers: int = 3,
) -> ProposalResult:
    """Generate a complete proposal DOCX from RFP analysis result.

    A-lite mode: Layer 1 knowledge only, no company DB required.
    """
    start = time.time()
    os.makedirs(output_dir, exist_ok=True)

    # 1. Build outline
    outline = build_proposal_outline(rfx_result, total_pages)

    # 2. Initialize knowledge DB (Layer 1)
    kb = KnowledgeDB(persist_directory=knowledge_db_path)

    # 3. Build RFP context string
    rfp_context_parts = [
        f"사업명: {rfx_result.get('title', '')}",
        f"발주기관: {rfx_result.get('issuing_org', '')}",
        f"사업비: {rfx_result.get('budget', '')}",
        f"사업기간: {rfx_result.get('project_period', '')}",
    ]
    if rfx_result.get("rfp_text_summary"):
        rfp_context_parts.append(f"RFP 요약: {rfx_result['rfp_text_summary']}")
    rfp_context = "\n".join(rfp_context_parts)

    # 4. Write sections (parallel with ThreadPoolExecutor)
    def _write_one(section):
        knowledge = kb.search(
            f"{section.name} {section.evaluation_item}",
            top_k=10,
            category=None,
        )
        text = write_section(
            section=section,
            rfp_context=rfp_context,
            knowledge=knowledge,
            company_context=company_context,
            api_key=api_key,
        )
        return (section.name, text)

    sections: list[tuple[str, str]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_write_one, s): s for s in outline.sections}
        results_map: dict[str, str] = {}
        for future in as_completed(futures):
            name, text = future.result()
            results_map[name] = text

    # Preserve original section order
    for s in outline.sections:
        sections.append((s.name, results_map.get(s.name, "")))

    # 5. Quality check
    all_text = "\n\n".join(text for _, text in sections)
    quality_issues = check_quality(all_text, company_name=company_name)

    # 6. Assemble DOCX
    ts = int(time.time())
    safe_title = rfx_result.get("title", "proposal")[:30].replace("/", "_").replace(" ", "_")
    docx_filename = f"{safe_title}_{ts}.docx"
    docx_path = os.path.join(output_dir, docx_filename)
    assemble_docx(
        title=rfx_result.get("title", "기술제안서"),
        sections=sections,
        output_path=docx_path,
    )

    elapsed = round(time.time() - start, 1)

    return ProposalResult(
        docx_path=docx_path,
        sections=sections,
        outline=outline,
        quality_issues=quality_issues,
        generation_time_sec=elapsed,
    )
```

**Step 4: Run test to verify it passes**

Run: `cd rag_engine && python -m pytest tests/test_proposal_orchestrator.py -v`
Expected: All 2 tests PASS

**Step 5: Commit**

```bash
git add rag_engine/proposal_orchestrator.py rag_engine/tests/test_proposal_orchestrator.py
git commit -m "feat: add proposal orchestrator — outline+write+check+assemble pipeline"
```

---

### Task 9: Proposal API Endpoint in rag_engine

**Files:**
- Modify: `rag_engine/main.py` (add `/api/generate-proposal-v2` route)
- Test: `rag_engine/tests/test_proposal_api.py`

**Context:** Expose proposal generation as a FastAPI endpoint. The legacy backend will proxy to this. Request includes RFP analysis result dict; response includes DOCX download URL and section previews.

**Step 1: Write the failing test**

```python
# rag_engine/tests/test_proposal_api.py
from __future__ import annotations
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from main import app
    return TestClient(app)


@patch("main.generate_proposal")
def test_generate_proposal_v2_endpoint(mock_gen, client):
    from proposal_orchestrator import ProposalResult
    from knowledge_models import ProposalOutline
    mock_gen.return_value = ProposalResult(
        docx_path="/tmp/test.docx",
        sections=[("제안 개요", "내용")],
        outline=ProposalOutline(title="테스트", issuing_org="기관", sections=[]),
        quality_issues=[],
        generation_time_sec=5.0,
    )
    resp = client.post("/api/generate-proposal-v2", json={
        "rfx_result": {
            "title": "테스트",
            "issuing_org": "기관",
            "evaluation_criteria": [],
            "requirements": [],
        },
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "docx_path" in data
    assert "sections" in data
    assert data["generation_time_sec"] > 0
```

**Step 2: Run test to verify it fails**

Run: `cd rag_engine && python -m pytest tests/test_proposal_api.py -v`
Expected: FAIL (route doesn't exist yet)

**Step 3: Add endpoint to `rag_engine/main.py`**

Add these imports at the top of `main.py`:
```python
from proposal_orchestrator import generate_proposal
```

Add this route after the existing `/api/generate-proposal` endpoint:
```python
class GenerateProposalV2Request(BaseModel):
    rfx_result: dict
    company_context: str = ""
    company_name: str | None = None
    total_pages: int = 50

@app.post("/api/generate-proposal-v2")
async def generate_proposal_v2(req: GenerateProposalV2Request):
    """Generate a full proposal DOCX using Layer 1 knowledge + RFP analysis."""
    result = await asyncio.to_thread(
        generate_proposal,
        rfx_result=req.rfx_result,
        company_context=req.company_context,
        company_name=req.company_name,
        total_pages=req.total_pages,
    )
    return {
        "docx_path": result.docx_path,
        "sections": [{"name": n, "preview": t[:500]} for n, t in result.sections],
        "quality_issues": [
            {"category": qi.category, "severity": qi.severity, "detail": qi.detail}
            for qi in result.quality_issues
        ],
        "generation_time_sec": result.generation_time_sec,
    }
```

**Step 4: Run test to verify it passes**

Run: `cd rag_engine && python -m pytest tests/test_proposal_api.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add rag_engine/main.py rag_engine/tests/test_proposal_api.py
git commit -m "feat: add /api/generate-proposal-v2 endpoint"
```

---

### Task 10: Backend Integration — Legacy Web App Proxy

**Files:**
- Modify: `services/web_app/main.py` (add proposal generation proxy endpoint)
- Test: Manual — `curl` to verify

**Context:** The React frontend calls the legacy backend. Add a route that proxies to `rag_engine/api/generate-proposal-v2`. This reuses the existing session's RFP analysis result.

**Step 1: Add endpoint to `services/web_app/main.py`**

Find the existing `POST /api/bids/analyze` route area and add after it:

```python
@app.post("/api/proposal/generate")
async def generate_proposal_endpoint(request: Request):
    """Generate proposal DOCX from current session's RFP analysis."""
    body = await request.json()
    session_id = body.get("session_id", "")
    total_pages = body.get("total_pages", 50)

    session = SESSIONS.get(session_id)
    if not session or not session.latest_rfx_analysis:
        return JSONResponse({"error": "분석된 RFP가 없습니다. 먼저 공고를 분석해주세요."}, status_code=400)

    rfx = session.latest_rfx_analysis
    rfx_dict = {
        "title": rfx.title,
        "issuing_org": rfx.issuing_org,
        "budget": rfx.budget,
        "project_period": rfx.project_period,
        "evaluation_criteria": [
            {"category": ec.category, "max_score": ec.max_score, "description": ec.description}
            for ec in (rfx.evaluation_criteria or [])
        ],
        "requirements": [
            {"category": r.category, "description": r.description}
            for r in (rfx.requirements or [])
        ],
        "rfp_text_summary": getattr(rfx, "_rfp_summary_text", ""),
    }

    # Proxy to rag_engine
    fastapi_url = os.environ.get("FASTAPI_URL", "http://localhost:8001")
    import httpx
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(
            f"{fastapi_url}/api/generate-proposal-v2",
            json={"rfx_result": rfx_dict, "total_pages": total_pages},
        )
    if resp.status_code != 200:
        return JSONResponse({"error": "제안서 생성 실패"}, status_code=500)

    return resp.json()
```

**Step 2: Verify it compiles**

Run: `cd /Users/min-kyungwook/Desktop/MS_SOLUTIONS && python -c "import services.web_app.main"`
Expected: No import errors

**Step 3: Commit**

```bash
git add services/web_app/main.py
git commit -m "feat: add /api/proposal/generate proxy to rag_engine"
```

---

### Task 11: Frontend — "제안서 생성" Button + Flow

**Files:**
- Modify: `frontend/kirabot/src/hooks/useConversationFlow.ts`
- Modify: `frontend/kirabot/src/services/kiraApiService.ts`
- Modify: `frontend/kirabot/src/components/chat/MessageBubble.tsx` (or relevant message component)

**Context:** After GO analysis, show a "제안서 초안 만들기" button. On click, call `/api/proposal/generate`, show progress, then display section previews + DOCX download link in the context panel.

**Step 1: Add API method to kiraApiService.ts**

```typescript
// Add to kiraApiService.ts
export async function generateProposal(
  sessionId: string,
  totalPages: number = 50,
): Promise<{
  docx_path: string;
  sections: { name: string; preview: string }[];
  quality_issues: { category: string; severity: string; detail: string }[];
  generation_time_sec: number;
}> {
  const res = await fetch(`${API_BASE_URL}/api/proposal/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, total_pages: totalPages }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || '제안서 생성 실패');
  }
  return res.json();
}
```

**Step 2: Add proposal generation handler to useConversationFlow.ts**

Add a new handler `handleGenerateProposal` in the hook:

```typescript
const handleGenerateProposal = async () => {
  if (!activeConv?.sessionId) return;
  dispatch({ type: 'SET_PROCESSING', value: true });
  pushStatus('info', '제안서 초안을 생성 중입니다... (약 3~5분 소요)');
  try {
    const result = await kiraApi.generateProposal(activeConv.sessionId);
    removeLastStatus();
    pushText(
      `제안서 초안이 완성되었습니다! (${result.generation_time_sec}초)\n\n` +
      `**섹션 구성:**\n` +
      result.sections.map((s, i) => `${i + 1}. ${s.name}`).join('\n') +
      (result.quality_issues.length > 0
        ? `\n\n**품질 검토:**\n` +
          result.quality_issues.map(q => `- [${q.severity}] ${q.detail}`).join('\n')
        : '\n\n품질 검토: 이상 없음')
    );
    // Set context panel to show DOCX download
    dispatch({
      type: 'SET_CONTEXT_PANEL',
      content: {
        type: 'proposal_result',
        docxPath: result.docx_path,
        sections: result.sections,
      },
    });
  } catch (err: any) {
    removeLastStatus();
    pushStatus('error', err.message || '제안서 생성 중 오류가 발생했습니다.');
  } finally {
    dispatch({ type: 'SET_PROCESSING', value: false });
  }
};
```

**Step 3: Add "제안서 만들기" button after GO analysis**

In the analysis result rendering (where GO/NO-GO is shown), add a button:

```typescript
// In the analysis result message rendering, after showing GO recommendation
{latestAnalysis?.latest_matching?.recommendation === 'GO' && (
  <button
    onClick={handleGenerateProposal}
    className="mt-2 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
  >
    제안서 초안 만들기
  </button>
)}
```

**Step 4: Verify frontend compiles**

Run: `cd frontend/kirabot && npm run build`
Expected: Build succeeds

**Step 5: Commit**

```bash
git add frontend/kirabot/src/services/kiraApiService.ts \
  frontend/kirabot/src/hooks/useConversationFlow.ts \
  frontend/kirabot/src/components/chat/MessageBubble.tsx
git commit -m "feat: add proposal generation UI — button + progress + download"
```

---

## Week 3-4: Company Knowledge DB (Module D)

### Task 12: Company DB Data Models + Storage

**Files:**
- Create: `rag_engine/company_db.py`
- Test: `rag_engine/tests/test_company_db.py`

**Context:** Structured storage for company capabilities: track records, personnel, certifications, past proposals. Uses ChromaDB for semantic search + JSON for structured data. See design doc §3 Module D.

**Step 1-5:** Follow same TDD pattern as Tasks 1-2. Key structures:

```python
@dataclass
class TrackRecord:
    project_name: str
    client: str
    period: str          # "2024.03 ~ 2024.12"
    amount: float        # 억원
    description: str
    technologies: list[str]
    outcome: str

@dataclass
class Personnel:
    name: str
    role: str            # PM, PL, 개발자, QA
    experience_years: int
    certifications: list[str]
    key_projects: list[str]
    specialties: list[str]

@dataclass
class CompanyProfile:
    name: str
    registration_number: str
    licenses: list[str]
    certifications: list[str]
    capital: float       # 억원
    employee_count: int
    track_records: list[TrackRecord]
    personnel: list[Personnel]
    writing_style: dict  # analyzed from past proposals
```

Core methods: `add_track_record()`, `add_personnel()`, `search_similar_projects(query)`, `find_matching_personnel(requirements)`.

**Commit message:** `feat: add company knowledge DB with track records and personnel`

---

### Task 13: Company Document Analyzer — Past Proposal Style Extraction

**Files:**
- Create: `rag_engine/company_analyzer.py`
- Test: `rag_engine/tests/test_company_analyzer.py`

**Context:** Analyzes uploaded past proposals to extract writing style, structure patterns, strengths emphasis, terminology. This feeds Layer 2. See design doc §2-3.

**Step 1-5:** TDD pattern. Key function:

```python
def analyze_company_style(
    documents: list[str],  # list of parsed text from past proposals
) -> dict:
    """Extract writing style profile from company's past proposals."""
    # Returns: {
    #   "tone": "격식체",
    #   "avg_sentence_length": 28,
    #   "structure_pattern": "사업이해(15%) → 기술접근(40%) → 관리(20%) → 실적(25%)",
    #   "strength_keywords": ["클라우드", "마이그레이션", "보안"],
    #   "terminology": {"당사 시스템": "KiraCloud Platform"},
    # }
```

**Commit message:** `feat: add company style analyzer for Layer 2 profile extraction`

---

## Week 5-6: A-full + Submission Checklist (Module G)

### Task 14: Layer 2 Prompt Integration — Company-Specific Generation

**Files:**
- Modify: `rag_engine/section_writer.py` (add company_context assembly)
- Modify: `rag_engine/proposal_orchestrator.py` (pass company profile)
- Test: Update existing tests

**Context:** When company DB exists, inject Layer 2 knowledge into section writer prompts. The `_assemble_prompt()` function already has the `company_context` slot — now populate it from CompanyProfile.

**Commit message:** `feat: integrate Layer 2 company profile into proposal generation`

---

### Task 15: Submission Checklist Extractor (Module G)

**Files:**
- Create: `rag_engine/checklist_extractor.py`
- Test: `rag_engine/tests/test_checklist_extractor.py`

**Context:** Extract required submission documents from RFP analysis. Uses existing `rfx_analyzer.py`'s `required_documents` field + LLM for additional detection. See design doc §3 Module G.

```python
@dataclass
class ChecklistItem:
    document_name: str       # "사업자등록증 사본"
    is_mandatory: bool
    format_hint: str         # "PDF 또는 스캔본"
    deadline_note: str       # "입찰마감일 2일 전까지"
    status: str = "pending"  # pending | uploaded | verified
```

**Commit message:** `feat: add submission checklist extractor from RFP analysis`

---

### Task 16: Checklist API + Frontend UI

**Files:**
- Modify: `rag_engine/main.py` (add `/api/checklist` endpoint)
- Modify: `services/web_app/main.py` (proxy)
- Modify: `frontend/kirabot/` (checklist panel in ContextPanel)

**Commit message:** `feat: add submission checklist UI with document tracking`

---

## Week 7-8: Edit Diff Learning Loop

### Task 17: Diff Tracker — Edit History Storage

**Files:**
- Create: `rag_engine/diff_tracker.py`
- Test: `rag_engine/tests/test_diff_tracker.py`

**Context:** Tracks AI-generated text vs user-edited text. Computes diff, stores edit history, detects recurring patterns. See design doc §2-3-A.

```python
@dataclass
class EditDiff:
    section_name: str
    original: str          # AI-generated
    edited: str            # user-modified
    diff_type: str         # "replace" | "delete" | "insert"
    pattern_key: str       # normalized pattern for matching
    occurrence_count: int  # how many times this pattern appeared

def extract_diffs(original: str, edited: str) -> list[EditDiff]: ...
def detect_recurring_patterns(diffs: list[EditDiff], threshold: int = 3) -> list[EditDiff]: ...
```

**Commit message:** `feat: add diff tracker for RLHF-style proposal learning`

---

### Task 18: Auto-Learning Pipeline — Pattern → Layer 2 Update

**Files:**
- Create: `rag_engine/auto_learner.py`
- Modify: `rag_engine/company_db.py` (add learned patterns)
- Test: `rag_engine/tests/test_auto_learner.py`

**Context:** When a pattern reaches 3+ occurrences, auto-apply to Layer 2. Notify user. Track edit rate as quality KPI. See design doc §2-3-A.

```python
def process_edit_feedback(
    company_id: str,
    section_name: str,
    original_text: str,
    edited_text: str,
) -> list[str]:  # list of learned pattern descriptions
    """Extract diffs, detect patterns, update Layer 2 if threshold met."""
    # 1회: 기록만
    # 2회: 후보 마킹
    # 3회+: Layer 2 자동 반영 + 사용자 알림 메시지 반환
```

**Commit message:** `feat: add auto-learning pipeline — edit diffs to Layer 2 patterns`

---

## Dependencies & New Packages

Add to `requirements.txt` (if not already present):
```
youtube-transcript-api>=0.6.0
trafilatura>=1.6.0
```

`python-docx` is already in requirements.txt. `chromadb` is already present.

---

## Summary: 19 Tasks, 8 Weeks

| Week | Tasks | Deliverable |
|------|-------|-------------|
| 1 | 1-3, 3-B | Knowledge data models + DB + harvester (Pass 1) + deduplicator (Pass 2) |
| 1-2 | 4-7 | Proposal planner + section writer + quality checker + DOCX assembler |
| 2 | 8-9 | Proposal orchestrator + API endpoint |
| 2 | 10-11 | Backend proxy + frontend UI |
| 3-4 | 12-13 | Company DB + style analyzer |
| 5-6 | 14-16 | Layer 2 integration + submission checklist |
| 7-8 | 17-18 | Edit diff tracking + auto-learning |

**Success criteria (design doc §6):**
- Week 2: "RFP 넣으면 제안서 나온다" 데모 (60점, Layer 1만)
- Week 4: 회사 맞춤 초안 (85점, Layer 1+2)
- Week 6: 고품질 제안서 + 체크리스트 (92점)
- Week 8: 사용자 수정이 학습되는 자가 개선 루프
