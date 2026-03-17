# Bid Workspace v1.0 — Phase 2: Contract + Pipeline

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify all 4 document generation pipelines under a single GenerationContract interface, record all generation runs/revisions/assets in PostgreSQL, and migrate doc_type naming to canonical values.

**Architecture:** GenerationContract dataclass defines a uniform interface for company context, knowledge, quality rules, and mode selection. Each orchestrator gets a thin adapter wrapper (no internal refactoring). A unified `/api/generate-document` endpoint in rag_engine dispatches by doc_type. web_app creates DocumentRun → calls rag_engine → records DocumentRevision + DocumentAsset in DB. Legacy endpoints remain untouched for backward compatibility.

**Tech Stack:** Python 3.11+, SQLAlchemy 2.0 (async), Pydantic v2, httpx (presigned URL uploads), pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-03-14-bid-workspace-v1-design.md` (Sections 8-10)

**Prerequisite:** Phase 1 Foundation merged to main (14 ORM models, S3 client, ACL, session adapter).

---

## Scope & Phasing

This is **Phase 2 of 4**:

| Phase | Status | Deliverables |
|-------|--------|-------------|
| 1 | **DONE** | 14 ORM models, S3 storage, ACL, session adapter, 45 tests |
| **2 (this)** | **NOW** | GenerationContract, orchestrator wrappers, quality expansion, DB recording, analysis persistence, doc_type migration |
| 3 | Planned | Workspace UI, review/approval, permissions UI |
| 4 | Planned | Legacy removal, load testing |

---

## Current State (What Exists)

### Orchestrators (rag_engine) — 4 independent silos

| Aspect | proposal | wbs | ppt | track_record |
|--------|----------|-----|-----|--------------|
| Company context | Direct string param | Auto-build from path | Auto-build from path | CompanyDB instance |
| Knowledge retrieval | Per-section custom query → KnowledgeUnit list | Single query → string list | Single query → string list | Single query → string list |
| Quality checker | YES (check_quality) | NO | NO | NO |
| Output format | DOCX + HWPX | XLSX + PNG + DOCX | PPTX | DOCX |
| Return has content_json | sections list | tasks list | slides + qna | records + personnel |

### API Endpoints — Legacy (remain untouched)

| rag_engine | web_app proxy |
|-----------|---------------|
| POST /api/generate-proposal-v2 | POST /api/proposal/generate-v2 |
| POST /api/generate-wbs | POST /api/proposal/generate-wbs |
| POST /api/generate-ppt | POST /api/proposal/generate-ppt |
| POST /api/generate-track-record | POST /api/proposal/generate-track-record |

### doc_type Values — Current vs Target

| Current | Target (canonical) | Used by |
|---------|-------------------|---------|
| `proposal` | `proposal` (no change) | All |
| `wbs` | `execution_plan` | auto_learner, validators, frontend tabs |
| `ppt` | `presentation` | auto_learner, validators, frontend tabs |
| `track_record` | `track_record` (no change) | All |

**Already using new names:** document_orchestrator.py, pack tests, DB CHECK constraints.

---

## File Map

### New Files (rag_engine)

```
rag_engine/
├── generation_contract.py        ← GenerationContract + CompanyContext + QualityRules + GenerationResult dataclasses
├── contract_adapter.py           ← Per-orchestrator unwrap + dispatch + presigned upload
└── tests/
    ├── test_generation_contract.py   ← Contract dataclass validation
    └── test_contract_adapter.py      ← Adapter dispatch + unwrap tests
```

### New Files (web_app)

```
services/web_app/
├── services/
│   ├── __init__.py
│   ├── contract_builder.py       ← Build GenerationContract from DB data
│   └── generation_service.py     ← DocumentRun lifecycle (create → call rag_engine → record revision)
├── api/
│   └── generate.py               ← POST /api/projects/{id}/generate endpoint
└── tests/
    ├── test_contract_builder.py
    ├── test_generation_service.py
    └── test_generate_api.py
```

### Modified Files

```
rag_engine/
├── main.py                       ← Add /api/generate-document endpoint + update doc_type validators
├── auto_learner.py               ← Update VALID_DOC_TYPES + doc_type_label mapping
├── quality_checker.py            ← Add doc_type-aware check_quality_for_doc_type()
├── phase2_models.py              ← Add slides_metadata, records_data, personnel_data to result types
├── ppt_orchestrator.py           ← Populate slides_metadata in PptResult
├── track_record_orchestrator.py  ← Populate records_data, personnel_data in TrackRecordDocResult
└── tests/
    └── test_auto_learner.py      ← Update doc_type test values

services/web_app/
├── main.py                       ← Wire generate router + analysis persistence (all 3 entry points)
├── db/engine.py                  ← Add create_session() helper
└── api/
    └── adapter.py                ← Wire save_analysis into existing proxy flow

frontend/kirabot/
├── components/settings/documents/DocumentTabNav.tsx      ← DocumentTab type + tab ids
├── components/settings/documents/DocumentWorkspace.tsx   ← VALID_TABS + conditional render
├── types.ts                                              ← Action type names
├── hooks/useConversationFlow.ts                          ← Case labels + push keys
├── components/chat/messages/AnalysisResultView.tsx       ← Action dispatches
└── components/settings/documents/__tests__/              ← Test assertions
```

### Import Convention (rag_engine)

**rag_engine is a flat module directory, NOT a Python package.** There is no `__init__.py`.
All imports within rag_engine use bare module names:

```python
# CORRECT — matches existing codebase (proposal_orchestrator.py, document_orchestrator.py, etc.)
from generation_contract import GenerationContract
from contract_adapter import generate_from_contract
from quality_checker import check_quality

# WRONG — would fail at runtime (no rag_engine package)
from rag_engine.generation_contract import GenerationContract
```

Tests run from inside `rag_engine/`: `cd rag_engine && python -m pytest ...`

---

## Chunk 1: Contract Definition + doc_type Migration

### Task 1: GenerationContract Dataclasses

**Files:**
- Create: `rag_engine/generation_contract.py`
- Test: `rag_engine/tests/test_generation_contract.py`

- [ ] **Step 1: Write the test**

```python
# rag_engine/tests/test_generation_contract.py
"""GenerationContract dataclass tests."""
from __future__ import annotations

import pytest
from generation_contract import (
    GenerationContract, CompanyContext, QualityRules,
    GenerationResult, UploadTarget, OutputFile,
    DOC_TYPE_CANONICAL, normalize_doc_type,
)


def test_company_context_defaults():
    ctx = CompanyContext(profile_summary="테스트 회사")
    assert ctx.similar_projects == []
    assert ctx.matching_personnel == []
    assert ctx.licenses == []
    assert ctx.certifications == []


def test_quality_rules_defaults():
    rules = QualityRules()
    assert rules.blind_words == []
    assert rules.min_section_length == 0
    assert rules.max_ambiguity_score == 1.0


def test_generation_contract_minimal():
    contract = GenerationContract(
        company_context=CompanyContext(profile_summary="MS솔루션"),
        quality_rules=QualityRules(),
    )
    assert contract.mode == "starter"
    assert contract.knowledge_units == []
    assert contract.learned_patterns == []
    assert contract.pack_config is None
    assert contract.pass_threshold == 0.0


def test_generation_result_structure():
    result = GenerationResult(
        doc_type="proposal",
        output_files=[OutputFile(asset_id="a1", asset_type="docx", size_bytes=100, content_hash="abc")],
        content_json={"sections": []},
        content_schema="proposal_sections_v1",
    )
    assert result.quality_report is None
    assert result.generation_time_sec == 0.0


def test_upload_target():
    target = UploadTarget(asset_id="a1", presigned_url="https://r2.example.com/put", asset_type="docx")
    assert target.content_type == "application/octet-stream"


def test_normalize_doc_type_canonical():
    assert normalize_doc_type("proposal") == "proposal"
    assert normalize_doc_type("execution_plan") == "execution_plan"
    assert normalize_doc_type("track_record") == "track_record"


def test_normalize_doc_type_aliases():
    assert normalize_doc_type("wbs") == "execution_plan"
    assert normalize_doc_type("ppt") == "presentation"


def test_normalize_doc_type_invalid():
    with pytest.raises(ValueError, match="Unknown doc_type"):
        normalize_doc_type("invalid_type")


def test_doc_type_canonical_values():
    assert set(DOC_TYPE_CANONICAL) == {"proposal", "execution_plan", "presentation", "track_record", "checklist"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd rag_engine && python -m pytest tests/test_generation_contract.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'generation_contract'`

- [ ] **Step 3: Implement the module**

```python
# rag_engine/generation_contract.py
"""GenerationContract — unified interface for all document generation pipelines.

Spec: docs/superpowers/specs/2026-03-14-bid-workspace-v1-design.md Section 8.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


# --- doc_type canonical values (single source of truth for rag_engine) ---

DOC_TYPE_CANONICAL = ["proposal", "execution_plan", "presentation", "track_record", "checklist"]

_DOC_TYPE_ALIASES: dict[str, str] = {
    "wbs": "execution_plan",
    "ppt": "presentation",
}


def normalize_doc_type(doc_type: str) -> str:
    """Convert doc_type to canonical name. Accepts legacy aliases.

    Raises ValueError for unknown doc_type.
    """
    if doc_type in DOC_TYPE_CANONICAL:
        return doc_type
    canonical = _DOC_TYPE_ALIASES.get(doc_type)
    if canonical is not None:
        return canonical
    raise ValueError(f"Unknown doc_type: {doc_type!r}. Valid: {DOC_TYPE_CANONICAL}")


# --- Contract dataclasses ---

@dataclass
class CompanyContext:
    """Company information injected into all generation pipelines."""
    profile_summary: str = ""
    similar_projects: list[dict] = field(default_factory=list)
    matching_personnel: list[dict] = field(default_factory=list)
    licenses: list[str] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)


@dataclass
class QualityRules:
    """Quality gate configuration."""
    blind_words: list[str] = field(default_factory=list)
    custom_forbidden: list[str] = field(default_factory=list)
    min_section_length: int = 0
    max_ambiguity_score: float = 1.0


@dataclass
class GenerationContract:
    """Unified interface consumed by all 4 document generation pipelines.

    web_app builds this from DB data, serializes to JSON, sends to rag_engine.
    rag_engine dispatches to the appropriate orchestrator based on doc_type.
    """
    # 1. Company Context
    company_context: CompanyContext = field(default_factory=CompanyContext)
    company_profile_md: str | None = None
    writing_style: dict | None = None

    # 2. Skill Retrieval
    knowledge_units: list[dict] = field(default_factory=list)
    learned_patterns: list[dict] = field(default_factory=list)
    pack_config: dict | None = None

    # 3. Mode Selection
    mode: Literal["strict_template", "starter", "upgrade"] = "starter"
    template_source: str | None = None

    # 4. Quality Contract
    quality_rules: QualityRules = field(default_factory=QualityRules)
    required_checks: list[str] = field(default_factory=list)
    pass_threshold: float = 0.0


@dataclass
class UploadTarget:
    """Presigned URL target for rag_engine to upload generated files."""
    asset_id: str
    presigned_url: str
    asset_type: str  # docx, xlsx, pptx, pdf, png, json
    content_type: str = "application/octet-stream"


@dataclass
class OutputFile:
    """Metadata for a generated file uploaded to S3."""
    asset_id: str
    asset_type: str
    size_bytes: int = 0
    content_hash: str = ""


@dataclass
class GenerationResult:
    """Unified return type from all generation pipelines."""
    doc_type: str
    output_files: list[OutputFile] = field(default_factory=list)
    content_json: dict = field(default_factory=dict)
    content_schema: str = ""
    quality_report: dict | None = None
    quality_schema: str | None = None
    upgrade_report: dict | None = None
    metadata: dict = field(default_factory=dict)
    generation_time_sec: float = 0.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd rag_engine && python -m pytest tests/test_generation_contract.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add rag_engine/generation_contract.py rag_engine/tests/test_generation_contract.py
git commit -m "feat(contract): add GenerationContract dataclasses + doc_type normalization"
```

---

### Task 2: doc_type Migration in rag_engine

**Files:**
- Modify: `rag_engine/auto_learner.py` (lines 62, 86, 119)
- Modify: `rag_engine/main.py` (doc_type pattern validators)
- Test: `rag_engine/tests/test_auto_learner.py` (update test values)

- [ ] **Step 1: Update VALID_DOC_TYPES in auto_learner.py**

Change line 62:
```python
# Before:
VALID_DOC_TYPES = {"proposal", "wbs", "ppt", "track_record"}

# After:
from generation_contract import DOC_TYPE_CANONICAL, normalize_doc_type

VALID_DOC_TYPES = set(DOC_TYPE_CANONICAL) - {"checklist"}
```

Change line 86-87:
```python
# Before:
if doc_type not in VALID_DOC_TYPES:
    doc_type = "proposal"

# After:
try:
    doc_type = normalize_doc_type(doc_type)
except ValueError:
    doc_type = "proposal"
if doc_type not in VALID_DOC_TYPES:
    doc_type = "proposal"
```

Change line 119:
```python
# Before:
doc_type_label = {"proposal": "제안서", "wbs": "WBS", "ppt": "PPT", "track_record": "실적기술서"}.get(doc_type, doc_type)

# After:
doc_type_label = {
    "proposal": "제안서",
    "execution_plan": "수행계획서",
    "presentation": "발표자료",
    "track_record": "실적기술서",
}.get(doc_type, doc_type)
```

- [ ] **Step 2: Update doc_type validators in rag_engine/main.py**

Find all `pattern=r"^(proposal|wbs|ppt|track_record)$"` and replace with:
```python
pattern=r"^(proposal|execution_plan|presentation|track_record|wbs|ppt)$"
```

This accepts BOTH old and new names. The endpoint handler normalizes:
```python
# Add at top of each endpoint that receives doc_type:
from generation_contract import normalize_doc_type
# In handler:
doc_type = normalize_doc_type(req.doc_type)
```

- [ ] **Step 3: Update test_auto_learner.py doc_type values**

Replace `doc_type="wbs"` → `doc_type="execution_plan"` and `doc_type="ppt"` → `doc_type="presentation"` in test calls.

- [ ] **Step 4: Run tests**

Run: `cd rag_engine && python -m pytest tests/test_auto_learner.py tests/test_generation_contract.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add rag_engine/auto_learner.py rag_engine/main.py rag_engine/tests/test_auto_learner.py
git commit -m "feat(doc-type): migrate wbs→execution_plan, ppt→presentation with alias compat"
```

---

### Task 3: Quality Checker Expansion

**Files:**
- Modify: `rag_engine/quality_checker.py`
- Test: `rag_engine/tests/test_quality_checker.py`

- [ ] **Step 1: Write the test for doc_type-aware quality check**

```python
# Append to rag_engine/tests/test_quality_checker.py

def test_check_quality_for_doc_type_proposal():
    """Proposal: full blind + ambiguity check."""
    from quality_checker import check_quality_for_doc_type
    issues = check_quality_for_doc_type("좋은 제안서 내용입니다.", "proposal", company_name="테스트회사")
    assert isinstance(issues, list)


def test_check_quality_for_doc_type_execution_plan():
    """execution_plan: ambiguity check only (no blind words)."""
    from quality_checker import check_quality_for_doc_type
    # "최고 수준" is a VAGUE_PATTERNS match → vague_claim category
    issues = check_quality_for_doc_type("최고 수준의 기술력", "execution_plan")
    assert any(i.category == "vague_claim" for i in issues)


def test_check_quality_for_doc_type_presentation():
    """presentation: minimal checks."""
    from quality_checker import check_quality_for_doc_type
    issues = check_quality_for_doc_type("발표 내용", "presentation")
    assert isinstance(issues, list)


def test_check_quality_for_doc_type_track_record():
    """track_record: blind check active."""
    from quality_checker import check_quality_for_doc_type
    issues = check_quality_for_doc_type("테스트회사가 수행한 사업", "track_record", company_name="테스트회사")
    assert any(i.category == "blind_violation" for i in issues)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd rag_engine && python -m pytest tests/test_quality_checker.py::test_check_quality_for_doc_type_proposal -v`
Expected: FAIL with `cannot import name 'check_quality_for_doc_type'`

- [ ] **Step 3: Implement check_quality_for_doc_type**

Add to `rag_engine/quality_checker.py`:

```python
# Doc-type-aware quality rules
_DOC_TYPE_CHECKS: dict[str, dict] = {
    "proposal": {"blind": True, "ambiguity": True},
    "execution_plan": {"blind": False, "ambiguity": True},
    "presentation": {"blind": False, "ambiguity": False},
    "track_record": {"blind": True, "ambiguity": True},
    "checklist": {"blind": False, "ambiguity": False},
}


def check_quality_for_doc_type(
    text: str,
    doc_type: str,
    company_name: str | None = None,
    custom_forbidden: list[str] | None = None,
) -> list[QualityIssue]:
    """Run quality checks appropriate for the given doc_type.

    Composes with existing check_quality() rather than duplicating logic.
    proposal/track_record: blind + ambiguity checks.
    execution_plan: ambiguity only.
    presentation/checklist: minimal (custom_forbidden only).
    """
    checks = _DOC_TYPE_CHECKS.get(doc_type, {"blind": True, "ambiguity": True})
    issues: list[QualityIssue] = []

    # Compose with existing check_quality() — pass company_name only when blind check enabled
    if checks.get("blind") or checks.get("ambiguity"):
        base_issues = check_quality(
            text,
            company_name=company_name if checks.get("blind") else None,
        )
        # Filter out vague_claim if ambiguity check is disabled
        if not checks.get("ambiguity"):
            base_issues = [i for i in base_issues if i.category != "vague_claim"]
        # Filter out blind_violation if blind check is disabled
        if not checks.get("blind"):
            base_issues = [i for i in base_issues if i.category != "blind_violation"]
        issues.extend(base_issues)

    if custom_forbidden:
        for pattern in custom_forbidden:
            if pattern in text:
                issues.append(QualityIssue(
                    category="custom_forbidden",
                    severity="warning",
                    detail=f"금지 표현 발견: {pattern}",
                    location="",
                ))

    return issues
```

Note: This composes with the existing `check_quality()` function (which already implements blind violation and vague claim checks inline). No extraction of private functions needed.

- [ ] **Step 4: Run tests**

Run: `cd rag_engine && python -m pytest tests/test_quality_checker.py -v`
Expected: All pass (existing + 4 new)

- [ ] **Step 5: Commit**

```bash
git add rag_engine/quality_checker.py rag_engine/tests/test_quality_checker.py
git commit -m "feat(quality): expand quality_checker to all doc_types via check_quality_for_doc_type"
```

---

## Chunk 2: Orchestrator Wrappers + Unified Endpoint

### Task 4: Contract Adapter — Orchestrator Dispatch

**Prerequisite: Extend orchestrator result types for content_json compliance**

The spec's `presentation_slides_v1` requires `slides[{title, body, speaker_notes}]` and `track_record_v1` requires `records[{project_name, description, relevance_score}]` + `personnel[{name, role, match_reason}]`. Current result types only carry counts. We must add metadata fields to preserve structured data through the result.

Add to `PptResult` in `rag_engine/phase2_models.py`:
```python
slides_metadata: list[dict] = field(default_factory=list)  # [{type, title, body, speaker_notes}]
```

Add to `TrackRecordDocResult` in `rag_engine/phase2_models.py`:
```python
records_data: list[dict] = field(default_factory=list)  # [{project_name, description, relevance_score}]
personnel_data: list[dict] = field(default_factory=list)  # [{name, role, match_reason}]
```

Then in `ppt_orchestrator.py`, after `plan_slides()` returns the slide plan, populate `result.slides_metadata` with title/body/notes from the plan. In `track_record_orchestrator.py`, after writer returns matched records + personnel, populate `result.records_data` and `result.personnel_data`.

These are additive-only changes (new optional fields with defaults) — no behavioral change to existing callers.

**Files:**
- Modify: `rag_engine/phase2_models.py` (add result metadata fields)
- Modify: `rag_engine/ppt_orchestrator.py` (populate slides_metadata)
- Modify: `rag_engine/track_record_orchestrator.py` (populate records_data, personnel_data)
- Create: `rag_engine/contract_adapter.py`
- Test: `rag_engine/tests/test_contract_adapter.py`

- [ ] **Step 1: Write the test**

```python
# rag_engine/tests/test_contract_adapter.py
"""Contract adapter tests — dispatch + unwrap, no LLM calls."""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from generation_contract import (
    GenerationContract, CompanyContext, QualityRules,
    GenerationResult, UploadTarget,
)
from contract_adapter import (
    generate_from_contract,
    _unwrap_for_proposal,
    _unwrap_for_execution_plan,
    _unwrap_for_ppt,
    _unwrap_for_track_record,
    DISPATCHER,
)


def test_dispatcher_has_all_doc_types():
    assert "proposal" in DISPATCHER
    assert "execution_plan" in DISPATCHER
    assert "presentation" in DISPATCHER
    assert "track_record" in DISPATCHER


def test_unwrap_for_proposal_extracts_company_context():
    contract = GenerationContract(
        company_context=CompanyContext(profile_summary="MS솔루션 SI 전문"),
        company_profile_md="# MS솔루션",
    )
    kwargs = _unwrap_for_proposal(contract, {"title": "테스트"}, {"total_pages": 30})
    assert kwargs["company_context"] == "MS솔루션 SI 전문"
    assert kwargs["total_pages"] == 30


def test_unwrap_for_execution_plan_routes_to_document_orchestrator():
    contract = GenerationContract(
        company_context=CompanyContext(profile_summary="MS솔루션"),
    )
    kwargs = _unwrap_for_execution_plan(contract, {"title": "테스트"}, {"company_id": "cid1"})
    assert kwargs["doc_type"] == "execution_plan"
    assert kwargs["company_context"] == "MS솔루션"
    assert kwargs["company_id"] == "cid1"


def test_unwrap_for_ppt_extracts_params():
    contract = GenerationContract()
    kwargs = _unwrap_for_ppt(contract, {"title": "테스트"}, {"duration_min": 20, "qna_count": 5})
    assert kwargs["duration_min"] == 20
    assert kwargs["qna_count"] == 5


def test_unwrap_for_track_record():
    contract = GenerationContract(
        company_context=CompanyContext(
            similar_projects=[{"name": "A"}],
            matching_personnel=[{"name": "B"}],
        ),
    )
    kwargs = _unwrap_for_track_record(contract, {"title": "테스트"}, {})
    assert "max_records" in kwargs or "rfx_result" in kwargs


def test_generate_from_contract_invalid_doc_type():
    contract = GenerationContract()
    with pytest.raises(ValueError, match="Unsupported doc_type"):
        generate_from_contract("invalid", contract, {}, {})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd rag_engine && python -m pytest tests/test_contract_adapter.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement contract_adapter.py**

```python
# rag_engine/contract_adapter.py
"""Adapts GenerationContract to each orchestrator's native signature.

Strategy: Thin wrappers that unwrap the contract into existing orchestrator params.
No internal orchestrator refactoring — just bridge the interface gap.

IMPORTANT: execution_plan routes through document_orchestrator.generate_document()
(the pack-aware pipeline), NOT wbs_orchestrator.generate_wbs() (legacy).
The pack pipeline handles: domain detection → pack resolution → schedule planning →
section writing → quality check → DOCX assembly. XLSX/Gantt are generated separately
from the returned DocumentResult.tasks.
"""
from __future__ import annotations

import hashlib
import logging
import time
import tempfile
import os
from typing import Any, Callable

import httpx

from generation_contract import (
    GenerationContract, GenerationResult, OutputFile, UploadTarget,
    normalize_doc_type,
)

logger = logging.getLogger(__name__)


def _unwrap_for_proposal(
    contract: GenerationContract,
    rfx_result: dict,
    params: dict,
) -> dict:
    """Unwrap contract → proposal_orchestrator.generate_proposal kwargs."""
    return {
        "rfx_result": rfx_result,
        "company_context": contract.company_context.profile_summary,
        "company_name": params.get("company_name"),
        "total_pages": params.get("total_pages", 50),
        "output_format": params.get("output_format", "docx"),
        "template_mode": contract.mode == "strict_template",
        "api_key": params.get("api_key"),
        # Knowledge units passed as-is; orchestrator handles search internally
        # when knowledge_db_path is set. Contract pre-fetched units are future optimization.
    }


def _unwrap_for_execution_plan(
    contract: GenerationContract,
    rfx_result: dict,
    params: dict,
) -> dict:
    """Unwrap contract → document_orchestrator.generate_document kwargs.

    Routes through the pack-aware pipeline (NOT legacy wbs_orchestrator).
    document_orchestrator handles: domain detection, pack resolution, schedule planning,
    section writing, quality check, and DOCX assembly.
    """
    return {
        "rfx_result": rfx_result,
        "doc_type": "execution_plan",
        "company_name": params.get("company_name", ""),
        "company_context": contract.company_context.profile_summary,
        "company_id": params.get("company_id", "_default"),
        "api_key": params.get("api_key"),
        "knowledge_db_path": params.get("knowledge_db_path", "./data/knowledge_db"),
        "packs_dir": params.get("packs_dir", ""),
    }


def _unwrap_for_ppt(
    contract: GenerationContract,
    rfx_result: dict,
    params: dict,
) -> dict:
    """Unwrap contract → ppt_orchestrator.generate_ppt kwargs."""
    return {
        "rfx_result": rfx_result,
        "proposal_sections": params.get("proposal_sections"),
        "duration_min": params.get("duration_min", 30),
        "target_slide_count": params.get("target_slide_count", 20),
        "qna_count": params.get("qna_count", 10),
        "company_name": params.get("company_name", ""),
        "api_key": params.get("api_key"),
    }


def _unwrap_for_track_record(
    contract: GenerationContract,
    rfx_result: dict,
    params: dict,
) -> dict:
    """Unwrap contract → track_record_orchestrator.generate_track_record_doc kwargs."""
    return {
        "rfx_result": rfx_result,
        "max_records": params.get("max_records", 10),
        "max_personnel": params.get("max_personnel", 10),
        "company_name": params.get("company_name"),
        "api_key": params.get("api_key"),
    }


def upload_to_presigned_url(url: str, data: bytes, content_type: str = "application/octet-stream") -> dict:
    """Upload data to a presigned PUT URL. Returns {size_bytes, content_hash}."""
    resp = httpx.put(url, content=data, headers={"Content-Type": content_type}, timeout=120)
    resp.raise_for_status()
    return {
        "size_bytes": len(data),
        "content_hash": hashlib.sha256(data).hexdigest(),
    }


def _collect_output_files(output_dir: str, upload_targets: list[UploadTarget]) -> list[OutputFile]:
    """Upload generated files to S3 via presigned URLs, return OutputFile metadata."""
    output_files = []
    for target in upload_targets:
        # Find matching file in output_dir by asset_type extension
        ext = target.asset_type
        candidates = [f for f in os.listdir(output_dir) if f.endswith(f".{ext}")]
        if not candidates:
            logger.warning("No .%s file found in %s for asset %s", ext, output_dir, target.asset_id)
            continue
        filepath = os.path.join(output_dir, candidates[0])
        with open(filepath, "rb") as f:
            data = f.read()
        meta = upload_to_presigned_url(target.presigned_url, data, target.content_type)
        output_files.append(OutputFile(
            asset_id=target.asset_id,
            asset_type=target.asset_type,
            size_bytes=meta["size_bytes"],
            content_hash=meta["content_hash"],
        ))
    return output_files


def generate_from_contract(
    doc_type: str,
    contract: GenerationContract,
    rfx_result: dict,
    params: dict,
    upload_targets: list[UploadTarget] | None = None,
    output_dir: str | None = None,
) -> GenerationResult:
    """Unified entry point: dispatch to the correct orchestrator via contract.

    1. Normalize doc_type
    2. Unwrap contract → orchestrator kwargs
    3. Call orchestrator
    4. Run quality check
    5. Upload to presigned URLs (if provided)
    6. Return GenerationResult
    """
    doc_type = normalize_doc_type(doc_type)
    if doc_type not in DISPATCHER:
        raise ValueError(f"Unsupported doc_type: {doc_type}")

    unwrap_fn, orchestrate_fn_getter, result_mapper = DISPATCHER[doc_type]

    # Unwrap contract → kwargs
    kwargs = unwrap_fn(contract, rfx_result, params)

    # Use temp dir if no output_dir specified
    work_dir = output_dir or tempfile.mkdtemp(prefix=f"kira_{doc_type}_")
    kwargs["output_dir"] = work_dir

    # Call orchestrator — getter returns the actual function (lazy import)
    orchestrate_fn = orchestrate_fn_getter()
    start = time.time()
    raw_result = orchestrate_fn(**kwargs)
    elapsed = time.time() - start

    # Map orchestrator result → GenerationResult
    gen_result = result_mapper(raw_result, doc_type, elapsed)

    # --- Secondary outputs for execution_plan ---
    # document_orchestrator returns DOCX + tasks/personnel data.
    # XLSX (WBS table) and PNG (Gantt chart) must be generated separately
    # from the structured tasks/personnel, using wbs_generator functions.
    # This adapter is the integration layer — it bridges document_orchestrator
    # output to the full output set the spec promises.
    if doc_type == "execution_plan" and hasattr(raw_result, "tasks") and raw_result.tasks:
        from wbs_generator import generate_wbs_xlsx, generate_gantt_chart

        _title = rfx_result.get("title", "수행계획서")
        _total_months = getattr(raw_result, "total_months", 12)

        # XLSX — WBS table + personnel allocation + deliverables
        _xlsx_path = os.path.join(work_dir, f"wbs_{_title[:30]}.xlsx")
        try:
            generate_wbs_xlsx(
                raw_result.tasks, raw_result.personnel,
                _title, _total_months, _xlsx_path,
            )
        except Exception:
            logger.warning("XLSX generation failed for execution_plan", exc_info=True)

        # PNG — Gantt chart (matplotlib optional, graceful degradation)
        _gantt_path = os.path.join(work_dir, f"gantt_{_title[:30]}.png")
        try:
            generate_gantt_chart(raw_result.tasks, _total_months, _gantt_path)
        except Exception:
            logger.warning("Gantt chart generation failed (matplotlib may be unavailable)", exc_info=True)

    # Quality check
    from quality_checker import check_quality_for_doc_type
    text_for_check = _extract_text_for_quality(gen_result)
    if text_for_check:
        quality_issues = check_quality_for_doc_type(
            text_for_check,
            doc_type,
            company_name=params.get("company_name"),
            custom_forbidden=contract.quality_rules.custom_forbidden or None,
        )
        gen_result.quality_report = {
            "issues": [{"category": i.category, "severity": i.severity, "detail": i.detail} for i in quality_issues],
            "total_issues": len(quality_issues),
        }
        gen_result.quality_schema = "quality_report_v1"

    # Upload to presigned URLs
    if upload_targets:
        gen_result.output_files = _collect_output_files(work_dir, upload_targets)

    return gen_result


def _extract_text_for_quality(result: GenerationResult) -> str:
    """Extract text from content_json for quality checking."""
    cj = result.content_json
    parts = []
    for section in cj.get("sections", []):
        parts.append(section.get("text", ""))
    for task in cj.get("tasks", []):
        parts.append(task.get("name", ""))
    for slide in cj.get("slides", []):
        parts.append(slide.get("body", ""))
    for rec in cj.get("records", []):
        parts.append(rec.get("description", ""))
    return "\n".join(parts)


# --- Result mappers (orchestrator result → GenerationResult) ---

def _map_proposal_result(raw, doc_type, elapsed):
    return GenerationResult(
        doc_type=doc_type,
        content_json={"sections": [{"name": n, "text": t} for n, t in raw.sections]},
        content_schema="proposal_sections_v1",
        metadata={"docx_path": raw.docx_path},
        generation_time_sec=elapsed,
    )


def _map_execution_plan_result(raw, doc_type, elapsed):
    """Map DocumentResult (from document_orchestrator) → GenerationResult.

    DocumentResult has: docx_path, tasks (list[WbsTask]), personnel (list[PersonnelAllocation]),
    total_months, domain_type, quality_issues, sections (list[tuple[str, str]]).
    XLSX + Gantt PNG are generated earlier in generate_from_contract() from
    tasks/personnel and placed in work_dir alongside the DOCX.
    """
    return GenerationResult(
        doc_type=doc_type,
        content_json={
            "tasks": [{"id": f"T{i}", "name": t.task_name, "phase": t.phase,
                        "start_month": t.start_month,
                        "duration_months": t.duration_months,
                        "responsible_role": t.responsible_role,
                        "man_months": t.man_months,
                        "deliverables": t.deliverables}
                       for i, t in enumerate(raw.tasks, 1)],
            "personnel": [{"role": p.role, "name": p.name or "", "man_months": p.man_months}
                          for p in raw.personnel],
            "methodology": getattr(raw, "methodology", "waterfall"),
            "total_months": raw.total_months,
            "domain_type": raw.domain_type,
            "sections": [{"name": n, "text": t} for n, t in raw.sections],
        },
        content_schema="execution_plan_tasks_v1",
        metadata={"docx_path": raw.docx_path},
        generation_time_sec=elapsed,
    )


def _map_ppt_result(raw, doc_type, elapsed):
    """Map PptResult → GenerationResult with spec-compliant presentation_slides_v1.

    PptResult has: pptx_path, slide_count, qna_pairs, total_duration_min, slides_metadata.
    slides_metadata is populated by generate_ppt (see Task 4 Step 3b prerequisite).
    Spec: slides[{slide_number, type, title, body, speaker_notes}], qna_pairs, total_duration_min.
    """
    slides = []
    for i, s in enumerate(getattr(raw, "slides_metadata", []), 1):
        slides.append({
            "slide_number": i,
            "type": s.get("type", "content"),
            "title": s.get("title", ""),
            "body": s.get("body", ""),
            "speaker_notes": s.get("speaker_notes", ""),
        })
    # Fallback: if no slides_metadata, generate placeholder from count
    if not slides:
        slides = [{"slide_number": i + 1, "type": "content", "title": "", "body": "", "speaker_notes": ""}
                  for i in range(raw.slide_count)]

    return GenerationResult(
        doc_type=doc_type,
        content_json={
            "slides": slides,
            "qna_pairs": [{"question": q.question, "answer": q.answer, "category": q.category}
                          for q in raw.qna_pairs],
            "total_duration_min": raw.total_duration_min,
        },
        content_schema="presentation_slides_v1",
        metadata={"pptx_path": raw.pptx_path},
        generation_time_sec=elapsed,
    )


def _map_track_record_result(raw, doc_type, elapsed):
    """Map TrackRecordDocResult → GenerationResult with spec-compliant track_record_v1.

    TrackRecordDocResult has: docx_path, track_record_count, personnel_count,
    records_data, personnel_data (populated by generate_track_record_doc, see Task 4 Step 3b).
    Spec: records[{project_name, description, relevance_score}], personnel[{name, role, match_reason}].
    """
    records = [
        {"project_name": r.get("project_name", ""), "description": r.get("description", ""),
         "relevance_score": r.get("relevance_score", 0.0)}
        for r in getattr(raw, "records_data", [])
    ]
    personnel = [
        {"name": p.get("name", ""), "role": p.get("role", ""), "match_reason": p.get("match_reason", "")}
        for p in getattr(raw, "personnel_data", [])
    ]

    return GenerationResult(
        doc_type=doc_type,
        content_json={
            "records": records,
            "personnel": personnel,
        },
        content_schema="track_record_v1",
        metadata={"docx_path": getattr(raw, "docx_path", "")},
        generation_time_sec=elapsed,
    )


# --- Dispatcher registry ---

def _lazy_import_proposal():
    from proposal_orchestrator import generate_proposal
    return generate_proposal

def _lazy_import_execution_plan():
    from document_orchestrator import generate_document
    return generate_document

def _lazy_import_ppt():
    from ppt_orchestrator import generate_ppt
    return generate_ppt

def _lazy_import_track_record():
    from track_record_orchestrator import generate_track_record_doc
    return generate_track_record_doc


# Each entry: (unwrap_fn, orchestrate_fn_getter, result_mapper)
# Using lazy imports to avoid circular dependencies at module load time
DISPATCHER: dict[str, tuple] = {
    "proposal": (_unwrap_for_proposal, _lazy_import_proposal, _map_proposal_result),
    "execution_plan": (_unwrap_for_execution_plan, _lazy_import_execution_plan, _map_execution_plan_result),
    "presentation": (_unwrap_for_ppt, _lazy_import_ppt, _map_ppt_result),
    "track_record": (_unwrap_for_track_record, _lazy_import_track_record, _map_track_record_result),
}
```

**Note:** The DISPATCHER uses lazy import functions instead of direct function references to avoid importing heavy orchestrator modules at module load time. The `generate_from_contract()` function calls the getter to get the actual function at dispatch time.

- [ ] **Step 4: Run tests**

Run: `cd rag_engine && python -m pytest tests/test_contract_adapter.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add rag_engine/contract_adapter.py rag_engine/tests/test_contract_adapter.py
git commit -m "feat(contract): add contract_adapter with orchestrator dispatch + presigned upload"
```

---

### Task 5: Unified /api/generate-document Endpoint in rag_engine

**Files:**
- Modify: `rag_engine/main.py`
- Test: `rag_engine/tests/test_unified_api.py` (new)

- [ ] **Step 1: Write the test**

```python
# rag_engine/tests/test_unified_api.py
"""Unified /api/generate-document endpoint structural test."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_generate_document_endpoint_exists():
    from main import app
    client = TestClient(app)
    # Should return 422 (validation error) not 404 (not found)
    resp = client.post("/api/generate-document", json={})
    assert resp.status_code == 422


def test_generate_document_rejects_invalid_doc_type():
    from main import app
    client = TestClient(app)
    resp = client.post("/api/generate-document", json={
        "doc_type": "invalid_type",
        "rfx_result": {"title": "test"},
        "contract": {},
        "params": {},
    })
    assert resp.status_code == 422 or resp.status_code == 400


def test_generate_document_accepts_alias_doc_type():
    """wbs and ppt should be accepted (alias resolution)."""
    from main import app
    from generation_contract import normalize_doc_type
    # Just verify alias resolution works at API level
    assert normalize_doc_type("wbs") == "execution_plan"
    assert normalize_doc_type("ppt") == "presentation"
```

- [ ] **Step 2: Add the endpoint to rag_engine/main.py**

```python
# Add Pydantic model near other request models:
class GenerateDocumentRequest(BaseModel):
    doc_type: str = Field(pattern=r"^(proposal|execution_plan|presentation|track_record|wbs|ppt)$")
    rfx_result: RfxResultInput
    contract: dict = Field(default_factory=dict)
    params: dict = Field(default_factory=dict)
    upload_targets: list[dict] = Field(default_factory=list)

# Add endpoint:
@app.post("/api/generate-document")
async def generate_document_unified(req: GenerateDocumentRequest):
    """Unified document generation endpoint. Dispatches by doc_type via GenerationContract."""
    from generation_contract import (
        GenerationContract, CompanyContext, QualityRules,
        UploadTarget, normalize_doc_type,
    )
    from contract_adapter import generate_from_contract

    doc_type = normalize_doc_type(req.doc_type)

    # Rebuild contract from dict — explicit field mapping
    cc = req.contract.get("company_context", {})
    qr = req.contract.get("quality_rules", {})
    contract = GenerationContract(
        company_context=CompanyContext(
            profile_summary=cc.get("profile_summary", ""),
            similar_projects=cc.get("similar_projects", []),
            matching_personnel=cc.get("matching_personnel", []),
            licenses=cc.get("licenses", []),
            certifications=cc.get("certifications", []),
        ),
        company_profile_md=req.contract.get("company_profile_md"),
        writing_style=req.contract.get("writing_style"),
        knowledge_units=req.contract.get("knowledge_units", []),
        learned_patterns=req.contract.get("learned_patterns", []),
        pack_config=req.contract.get("pack_config"),
        mode=req.contract.get("mode", "starter"),
        template_source=req.contract.get("template_source"),
        quality_rules=QualityRules(
            blind_words=qr.get("blind_words", []),
            custom_forbidden=qr.get("custom_forbidden", []),
            min_section_length=qr.get("min_section_length", 0),
            max_ambiguity_score=qr.get("max_ambiguity_score", 1.0),
        ),
        required_checks=req.contract.get("required_checks", []),
        pass_threshold=req.contract.get("pass_threshold", 0.0),
    )

    upload_targets = [UploadTarget(**t) for t in req.upload_targets]

    result = await asyncio.to_thread(
        generate_from_contract,
        doc_type=doc_type,
        contract=contract,
        rfx_result=req.rfx_result.model_dump(),
        params=req.params,
        upload_targets=upload_targets,
    )

    return {
        "doc_type": result.doc_type,
        "content_json": result.content_json,
        "content_schema": result.content_schema,
        "quality_report": result.quality_report,
        "quality_schema": result.quality_schema,
        "output_files": [
            {"asset_id": f.asset_id, "asset_type": f.asset_type,
             "size_bytes": f.size_bytes, "content_hash": f.content_hash}
            for f in result.output_files
        ],
        "generation_time_sec": result.generation_time_sec,
    }
```

- [ ] **Step 3: Run test**

Run: `cd rag_engine && python -m pytest tests/test_unified_api.py -v`
Expected: 3 passed

- [ ] **Step 4: Commit**

```bash
git add rag_engine/main.py rag_engine/tests/test_unified_api.py
git commit -m "feat(api): add unified /api/generate-document endpoint with contract dispatch"
```

---

## Chunk 3: DB Recording + web_app Integration

### Task 6: Contract Builder Service (web_app)

**Files:**
- Create: `services/web_app/services/__init__.py`
- Create: `services/web_app/services/contract_builder.py`
- Test: `services/web_app/tests/test_contract_builder.py`

- [ ] **Step 1: Write the test**

```python
# services/web_app/tests/test_contract_builder.py
"""Contract builder tests — builds GenerationContract dict from DB data."""
from __future__ import annotations

import pytest
from services.web_app.services.contract_builder import build_generation_contract


def test_build_contract_minimal():
    """Builds contract with minimal inputs (no company profile, no knowledge)."""
    contract = build_generation_contract(
        org_id="org1",
        company_profile=None,
        writing_style=None,
        company_name=None,
    )
    assert "company_context" in contract
    assert "quality_rules" in contract
    assert contract["mode"] == "starter"


def test_build_contract_with_company():
    """Builds contract with company profile."""
    contract = build_generation_contract(
        org_id="org1",
        company_profile={"licenses": {"SW사업자": True}},
        writing_style={"tone": "formal"},
        company_name="MS솔루션",
    )
    assert contract["company_context"]["profile_summary"] != ""
    assert contract["quality_rules"]["blind_words"] == ["MS솔루션"]
    assert contract["writing_style"] == {"tone": "formal"}


def test_build_contract_mode_override():
    """Mode can be overridden."""
    contract = build_generation_contract(
        org_id="org1",
        company_profile=None,
        mode="strict_template",
    )
    assert contract["mode"] == "strict_template"
```

- [ ] **Step 2: Implement**

```python
# services/web_app/services/__init__.py
# (empty)

# services/web_app/services/contract_builder.py
"""Builds GenerationContract dict from web_app DB data.

The contract is serialized to JSON and sent to rag_engine's /api/generate-document.
"""
from __future__ import annotations

from typing import Any


def build_generation_contract(
    org_id: str,
    company_profile: dict | None = None,
    writing_style: dict | None = None,
    company_name: str | None = None,
    knowledge_units: list[dict] | None = None,
    learned_patterns: list[dict] | None = None,
    pack_config: dict | None = None,
    mode: str = "starter",
    template_source: str | None = None,
    custom_forbidden: list[str] | None = None,
) -> dict[str, Any]:
    """Build a GenerationContract dict from DB data.

    Returns a plain dict (JSON-serializable) matching GenerationContract schema.
    web_app sends this to rag_engine via HTTP.
    """
    # Company context
    profile_summary = ""
    licenses = []
    certifications = []
    if company_profile:
        profile_summary = _build_profile_summary(company_profile, company_name)
        licenses = list((company_profile.get("licenses") or {}).keys())
        certifications = list((company_profile.get("certifications") or {}).keys())

    # Quality rules — always include company_name in blind_words
    blind_words = [company_name] if company_name else []

    return {
        "company_context": {
            "profile_summary": profile_summary,
            "similar_projects": [],
            "matching_personnel": [],
            "licenses": licenses,
            "certifications": certifications,
        },
        "company_profile_md": None,
        "writing_style": writing_style,
        "knowledge_units": knowledge_units or [],
        "learned_patterns": learned_patterns or [],
        "pack_config": pack_config,
        "mode": mode,
        "template_source": template_source,
        "quality_rules": {
            "blind_words": blind_words,
            "custom_forbidden": custom_forbidden or [],
            "min_section_length": 0,
            "max_ambiguity_score": 1.0,
        },
        "required_checks": ["blind", "ambiguity"],
        "pass_threshold": 0.0,
    }


def _build_profile_summary(profile: dict, company_name: str | None) -> str:
    """Build a one-paragraph company summary from profile data."""
    parts = []
    if company_name:
        parts.append(company_name)
    btype = profile.get("business_type")
    if btype:
        parts.append(f"({btype})")
    hc = profile.get("headcount")
    if hc:
        parts.append(f"인원 {hc}명")
    cap = profile.get("capital")
    if cap:
        parts.append(f"자본금 {cap}")
    return " ".join(parts) if parts else ""
```

- [ ] **Step 3: Run test**

Run: `python -m pytest services/web_app/tests/test_contract_builder.py -v`
Expected: 3 passed

- [ ] **Step 4: Commit**

```bash
git add services/web_app/services/ services/web_app/tests/test_contract_builder.py
git commit -m "feat(web_app): add contract_builder service for GenerationContract assembly"
```

---

### Task 7: Generation Service — DocumentRun Lifecycle

**Files:**
- Create: `services/web_app/services/generation_service.py`
- Test: `services/web_app/tests/test_generation_service.py`

**Note:** Tests use the `db_session` fixture from `services/web_app/tests/conftest.py` (created in Phase 1). This fixture provides an async SQLAlchemy session connected to the test PostgreSQL database and rolls back after each test.

- [ ] **Step 1: Write the test**

```python
# services/web_app/tests/test_generation_service.py
"""Generation service tests — DocumentRun lifecycle. Requires PostgreSQL."""
from __future__ import annotations

import pytest
from services.web_app.db.models.org import Organization
from services.web_app.db.models.project import BidProject
from services.web_app.db.models.document import DocumentRun


@pytest.mark.asyncio
async def test_create_document_run(db_session):
    """Creates a DocumentRun with status=queued."""
    from services.web_app.services.generation_service import create_document_run

    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    project = BidProject(org_id=org.id, created_by="u1", title="테스트 사업")
    db_session.add(project)
    await db_session.flush()

    run = await create_document_run(
        db=db_session,
        org_id=org.id,
        project_id=project.id,
        doc_type="proposal",
        created_by="u1",
        params={"total_pages": 50},
    )
    assert run.status == "queued"
    assert run.doc_type == "proposal"


@pytest.mark.asyncio
async def test_complete_document_run(db_session):
    """Transitions DocumentRun to completed and creates DocumentRevision."""
    from services.web_app.services.generation_service import (
        create_document_run, complete_document_run,
    )

    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    project = BidProject(org_id=org.id, created_by="u1", title="테스트")
    db_session.add(project)
    await db_session.flush()

    run = await create_document_run(
        db=db_session, org_id=org.id, project_id=project.id,
        doc_type="proposal", created_by="u1",
    )

    revision = await complete_document_run(
        db=db_session,
        run=run,
        content_json={"sections": [{"name": "개요", "text": "내용"}]},
        content_schema="proposal_sections_v1",
        quality_report={"issues": [], "total_issues": 0},
        output_files=[],
    )
    assert run.status == "completed"
    assert revision.content_schema == "proposal_sections_v1"
    assert revision.source == "ai_generated"


@pytest.mark.asyncio
async def test_fail_document_run(db_session):
    """Transitions DocumentRun to failed."""
    from services.web_app.services.generation_service import (
        create_document_run, fail_document_run,
    )

    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    project = BidProject(org_id=org.id, created_by="u1", title="테스트")
    db_session.add(project)
    await db_session.flush()

    run = await create_document_run(
        db=db_session, org_id=org.id, project_id=project.id,
        doc_type="execution_plan", created_by="u1",
    )

    await fail_document_run(db=db_session, run=run, error="LLM timeout")
    assert run.status == "failed"
    assert run.error_message == "LLM timeout"
```

- [ ] **Step 2: Implement**

```python
# services/web_app/services/generation_service.py
"""DocumentRun lifecycle management.

create_document_run → (call rag_engine) → complete_document_run/fail_document_run.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.web_app.db.models.document import (
    DocumentRun, DocumentRevision, DocumentAsset, ProjectCurrentDocument,
)


ENGINE_VERSION = "bid-workspace-v1.0-phase2"


async def create_document_run(
    db: AsyncSession,
    org_id: str,
    project_id: str,
    doc_type: str,
    created_by: str,
    analysis_snapshot_id: str | None = None,
    params: dict | None = None,
    mode: str | None = None,
) -> DocumentRun:
    """Create a new DocumentRun with status=queued."""
    run = DocumentRun(
        org_id=org_id,
        project_id=project_id,
        doc_type=doc_type,
        status="queued",
        analysis_snapshot_id=analysis_snapshot_id,
        params_json=params or {},
        mode_used=mode,
        engine_version=ENGINE_VERSION,
        created_by=created_by,
    )
    db.add(run)
    await db.flush()
    return run


async def start_document_run(db: AsyncSession, run: DocumentRun) -> None:
    """Transition to running."""
    run.status = "running"
    run.started_at = datetime.now(timezone.utc)
    await db.flush()


async def complete_document_run(
    db: AsyncSession,
    run: DocumentRun,
    content_json: dict,
    content_schema: str,
    quality_report: dict | None = None,
    quality_schema: str | None = "quality_report_v1",
    output_files: list[dict] | None = None,
) -> DocumentRevision:
    """Complete a DocumentRun: create revision, update current pointer, record assets."""
    run.status = "completed"
    run.completed_at = datetime.now(timezone.utc)

    # Determine revision number
    result = await db.execute(
        select(DocumentRevision.revision_number)
        .where(DocumentRevision.project_id == run.project_id, DocumentRevision.doc_type == run.doc_type)
        .order_by(DocumentRevision.revision_number.desc())
        .limit(1)
    )
    last_rev = result.scalar_one_or_none()
    next_rev = (last_rev or 0) + 1

    # Create revision
    revision = DocumentRevision(
        org_id=run.org_id,
        project_id=run.project_id,
        doc_type=run.doc_type,
        run_id=run.id,
        revision_number=next_rev,
        source="ai_generated",
        status="draft",
        content_json=content_json,
        content_schema=content_schema,
        quality_report_json=quality_report,
        quality_schema=quality_schema if quality_report else None,
        created_by=run.created_by,
    )
    db.add(revision)
    await db.flush()

    # Update or create ProjectCurrentDocument pointer
    result = await db.execute(
        select(ProjectCurrentDocument).where(
            ProjectCurrentDocument.project_id == run.project_id,
            ProjectCurrentDocument.doc_type == run.doc_type,
        )
    )
    current = result.scalar_one_or_none()
    if current:
        current.current_revision_id = revision.id
    else:
        current = ProjectCurrentDocument(
            org_id=run.org_id,
            project_id=run.project_id,
            doc_type=run.doc_type,
            current_revision_id=revision.id,
        )
        db.add(current)

    # Mark previous completed runs as superseded (Spec Section 11)
    result = await db.execute(
        select(DocumentRun).where(
            DocumentRun.project_id == run.project_id,
            DocumentRun.doc_type == run.doc_type,
            DocumentRun.status == "completed",
            DocumentRun.id != run.id,
        )
    )
    for prev_run in result.scalars().all():
        prev_run.status = "superseded"

    # Update pre-created asset records: presigned_issued → uploaded (S3 confirmed)
    # Phase 1 semantics: "verified" requires S3 head + ETag confirmation.
    # rag_engine uploaded the file and returned size_bytes + content_hash (client-side).
    # We set to "uploaded" here; the caller (generate endpoint) then calls
    # confirm_upload_from_generation() to do S3 head + ETag → "verified".
    for f in (output_files or []):
        asset_id = f.get("asset_id")
        if asset_id:
            result = await db.execute(
                select(DocumentAsset).where(DocumentAsset.id == asset_id)
            )
            asset = result.scalar_one_or_none()
            if asset:
                asset.revision_id = revision.id
                asset.upload_status = "uploaded"
                asset.size_bytes = f.get("size_bytes")
                asset.content_hash = f"client:{f.get('content_hash', '')}"

    # NOTE: caller owns the transaction — do NOT commit here
    await db.flush()
    return revision


async def fail_document_run(
    db: AsyncSession,
    run: DocumentRun,
    error: str,
) -> None:
    """Mark DocumentRun as failed."""
    run.status = "failed"
    run.completed_at = datetime.now(timezone.utc)
    run.error_message = error
    # NOTE: caller owns the transaction — do NOT commit here
    await db.flush()
```

- [ ] **Step 3: Run test**

Run: `BID_TEST_DATABASE_URL="postgresql+asyncpg://kira:kira@localhost:5434/kira_bid_test" python -m pytest services/web_app/tests/test_generation_service.py -v`
Expected: 3 passed

- [ ] **Step 4: Commit**

```bash
git add services/web_app/services/generation_service.py services/web_app/tests/test_generation_service.py
git commit -m "feat(web_app): add generation_service with DocumentRun lifecycle"
```

---

### Task 8: /api/projects/{id}/generate Endpoint (web_app)

**Files:**
- Create: `services/web_app/api/generate.py`
- Modify: `services/web_app/main.py` (wire router)
- Test: `services/web_app/tests/test_generate_api.py`

- [ ] **Step 1: Write the test**

```python
# services/web_app/tests/test_generate_api.py
"""Generate API structural test."""
from __future__ import annotations

from services.web_app.api.generate import router


def test_generate_router_has_routes():
    route_paths = [r.path for r in router.routes]
    assert "/api/projects/{project_id}/generate" in route_paths
```

- [ ] **Step 2: Implement generate.py**

```python
# services/web_app/api/generate.py
"""POST /api/projects/{project_id}/generate — trigger document generation."""
from __future__ import annotations

import logging
import os
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from services.web_app.db.engine import get_async_session
from services.web_app.db.models.project import BidProject, AnalysisSnapshot
from services.web_app.db.models.company import CompanyProfile
from services.web_app.db.models.audit import AuditLog
from services.web_app.api.deps import CurrentUser, resolve_org_membership, require_project_access
from services.web_app.services.contract_builder import build_generation_contract
from services.web_app.services.generation_service import (
    create_document_run, start_document_run, complete_document_run, fail_document_run,
)
from services.web_app.storage.s3 import get_s3_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["generate"])

_RAG_ENGINE_URL = os.getenv("FASTAPI_URL", "http://localhost:8001")


class GenerateRequest(BaseModel):
    doc_type: str = Field(pattern=r"^(proposal|execution_plan|presentation|track_record)$")
    params: dict = Field(default_factory=dict)
    mode: str = Field(default="starter", pattern=r"^(strict_template|starter|upgrade)$")


@router.post("/{project_id}/generate")
async def generate_document(
    project_id: str,
    req: GenerateRequest,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """Trigger document generation for a project.

    1. Verify project access (editor+)
    2. Load active analysis snapshot
    3. Build GenerationContract from DB
    4. Create DocumentRun (queued)
    5. Pre-create DocumentAssets with presigned upload URLs
    6. Call rag_engine /api/generate-document
    7. Record DocumentRevision + update assets
    8. Audit log
    """
    # ACL
    await require_project_access(project_id, "editor", user, db)

    # Load project + active analysis
    result = await db.execute(
        select(BidProject).where(BidProject.id == project_id, BidProject.org_id == user.org_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404)

    result = await db.execute(
        select(AnalysisSnapshot).where(
            AnalysisSnapshot.project_id == project_id,
            AnalysisSnapshot.is_active == True,
        )
    )
    snapshot = result.scalar_one_or_none()
    if not snapshot:
        raise HTTPException(status_code=409, detail="분석 결과가 없습니다. 먼저 분석을 실행하세요.")

    # Load company profile
    result = await db.execute(
        select(CompanyProfile).where(CompanyProfile.org_id == user.org_id)
    )
    company = result.scalar_one_or_none()

    # Build contract
    contract = build_generation_contract(
        org_id=user.org_id,
        company_profile={
            "licenses": company.licenses if company else None,
            "certifications": company.certifications if company else None,
            "business_type": company.business_type if company else None,
            "headcount": company.headcount if company else None,
            "capital": company.capital if company else None,
        } if company else None,
        writing_style=company.writing_style if company else None,
        company_name=company.company_name if company else None,
        mode=req.mode,
    )

    # Create DocumentRun
    run = await create_document_run(
        db=db,
        org_id=user.org_id,
        project_id=project_id,
        doc_type=req.doc_type,
        created_by=user.username,
        analysis_snapshot_id=snapshot.id,
        params=req.params,
        mode=req.mode,
    )
    await start_document_run(db, run)

    # Pre-create asset records + presigned upload URLs for ALL expected outputs.
    #
    # Pre-allocate the full output set per doc_type. rag_engine's contract_adapter
    # generates all files in work_dir and _collect_output_files() uploads each one
    # to the matching presigned URL by extension. If an optional file isn't produced
    # (e.g., Gantt PNG when matplotlib is unavailable), the unused asset record is
    # cleaned up after generation completes.
    #
    # Output sets:
    #   proposal: docx OR hwpx (mutually exclusive, based on output_format param)
    #   execution_plan: docx (primary) + xlsx (WBS table) + png (Gantt chart, optional)
    #   presentation: pptx
    #   track_record: docx
    s3 = get_s3_client()
    from services.web_app.db.models.document import DocumentAsset
    from services.web_app.db.models.base import new_cuid

    def _asset_types_for_doc_type(doc_type: str, params: dict) -> list[str]:
        """Return all expected output file extensions for this doc_type."""
        if doc_type == "proposal":
            fmt = params.get("output_format", "docx")
            return ["hwpx"] if fmt == "hwpx" else ["docx"]
        if doc_type == "execution_plan":
            return ["docx", "xlsx", "png"]  # DOCX primary + XLSX WBS + PNG Gantt
        if doc_type == "presentation":
            return ["pptx"]
        return ["docx"]  # track_record

    upload_targets = []
    for atype in _asset_types_for_doc_type(req.doc_type, req.params):
        asset_id = new_cuid()
        key = s3.build_storage_key(user.org_id, project_id, asset_id, f"output.{atype}")
        url = s3.generate_presigned_upload_url(key)
        asset = DocumentAsset(
            id=asset_id,
            org_id=user.org_id,
            project_id=project_id,
            asset_type=atype,
            storage_uri=s3.build_full_uri(key),
            upload_status="presigned_issued",
        )
        db.add(asset)
        upload_targets.append({
            "asset_id": asset_id,
            "presigned_url": url,
            "asset_type": atype,
        })
    await db.flush()

    # Call rag_engine
    try:
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(
                f"{_RAG_ENGINE_URL}/api/generate-document",
                json={
                    "doc_type": req.doc_type,
                    "rfx_result": snapshot.analysis_json,
                    "contract": contract,
                    "params": req.params,
                    "upload_targets": upload_targets,
                },
            )
            resp.raise_for_status()
            rag_result = resp.json()
    except Exception as e:
        await fail_document_run(db, run, str(e))
        # Audit log for failure
        audit = AuditLog(
            org_id=user.org_id, user_id=user.username, project_id=project_id,
            action="generate_document_failed", target_type="document_run", target_id=run.id,
            detail_json={"doc_type": req.doc_type, "error": str(e)[:500]},
        )
        db.add(audit)
        await db.commit()
        raise HTTPException(status_code=502, detail=f"Generation failed: {e}")

    # Record revision (assets set to "uploaded", not yet "verified")
    revision = await complete_document_run(
        db=db,
        run=run,
        content_json=rag_result.get("content_json", {}),
        content_schema=rag_result.get("content_schema", ""),
        quality_report=rag_result.get("quality_report"),
        output_files=rag_result.get("output_files", []),
    )

    # Phase 1 verified semantics: S3 head + ETag confirmation for each asset
    for f in rag_result.get("output_files", []):
        aid = f.get("asset_id")
        if not aid:
            continue
        try:
            result = await db.execute(select(DocumentAsset).where(DocumentAsset.id == aid))
            asset = result.scalar_one_or_none()
            if asset and asset.storage_uri:
                key = s3.parse_storage_uri(asset.storage_uri)
                head = await asyncio.to_thread(s3.head_object, key)
                s3_etag = head.get("ETag", "").strip('"')
                actual_size = head.get("ContentLength", 0)
                asset.size_bytes = actual_size
                if s3_etag:
                    client_hash = f.get("content_hash", "")
                    asset.content_hash = f"etag:{s3_etag},client:{client_hash}"
                    asset.upload_status = "verified"
                else:
                    logger.warning("No ETag from S3 for generated asset %s", aid)
        except Exception:
            logger.warning("S3 head verification failed for asset %s", aid, exc_info=True)

    # Clean up unused pre-allocated assets (e.g., Gantt PNG when matplotlib unavailable).
    # If a pre-allocated asset was never uploaded (still "presigned_issued"),
    # delete the orphaned record — it was an optional output that wasn't produced.
    uploaded_ids = {f.get("asset_id") for f in rag_result.get("output_files", [])}
    for t in upload_targets:
        if t["asset_id"] not in uploaded_ids:
            result = await db.execute(
                select(DocumentAsset).where(DocumentAsset.id == t["asset_id"])
            )
            orphan = result.scalar_one_or_none()
            if orphan and orphan.upload_status == "presigned_issued":
                await db.delete(orphan)
                logger.info("Cleaned up unused asset %s (type=%s)", t["asset_id"], t["asset_type"])
    await db.flush()

    # Audit
    audit = AuditLog(
        org_id=user.org_id,
        user_id=user.username,
        project_id=project_id,
        action="generate_document",
        target_type="document_run",
        target_id=run.id,
        detail_json={"doc_type": req.doc_type, "revision_id": revision.id},
    )
    db.add(audit)
    await db.commit()

    return {
        "run_id": run.id,
        "revision_id": revision.id,
        "doc_type": req.doc_type,
        "content_schema": rag_result.get("content_schema"),
        "quality_report": rag_result.get("quality_report"),
        "output_files": rag_result.get("output_files", []),
        "generation_time_sec": rag_result.get("generation_time_sec", 0),
    }
```

- [ ] **Step 3: Wire router in main.py**

Add to `services/web_app/main.py` inside the `if _BID_DB_ENABLED:` block:
```python
from services.web_app.api.generate import router as generate_router
app.include_router(generate_router)
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest services/web_app/tests/test_generate_api.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add services/web_app/api/generate.py services/web_app/main.py services/web_app/tests/test_generate_api.py
git commit -m "feat(web_app): add /api/projects/{id}/generate with full DocumentRun lifecycle"
```

---

### Task 9: Analysis Persistence Wiring

**Files:**
- Modify: `services/web_app/db/engine.py` (expose session factory helper)
- Modify: `services/web_app/main.py` (analysis endpoint, line ~1908)

**Context:** There are **3 analysis entry points** that store results to session memory.
All 3 must have a DB write-through persistence policy for Phase 2's goal of "all analysis
snapshots in DB" to be honest.

| Entry point | Line | Async? | Stores to session at line |
|---|---|---|---|
| `POST /api/analyze/upload` | 1800 | async | 1908-1910 |
| `POST /api/analyze/text` | 1939 | **sync** (needs async conversion) | 1973-1975 |
| `POST /api/bids/analyze` | 2278 | async | 2385-2387 |

All 3 follow the same pattern: `session.latest_rfx_analysis = analysis` + Redis backup.
All 3 have `request: Request` in scope for identity resolution.

`SessionAdapter.save_analysis()` expects: `analysis_json: dict`, `summary_md: str | None`, `go_nogo_json: dict | None`, `username: str | None`.

**Two critical boundaries this task must respect:**

1. **Identity resolution**: `SessionAdapter.get_or_create_project(session_id, username)` passes
   `username` to `_ensure_org()` (adapter.py:127) which queries `Membership.user_id == username`.
   Using `session_id` as username would create ghost orgs in dev bootstrap or fail membership
   resolution in production. Must use `_resolve_usage_actor(request, session_id)` at line 392
   to get the real authenticated username. Anonymous users (empty username) must be skipped.

2. **Serialization boundary**: `RFxAnalysisResult.evaluation_criteria` stores `{category, item,
   score, detail}` (rfx_analyzer.py:69), but Task 8's generate endpoint sends
   `snapshot.analysis_json` directly as `rfx_result` to rag_engine, where `RfxResultInput`
   (main.py:385) expects `{category, max_score, description}`. Raw `_asdict(analysis)` would
   silently zero-out `max_score` (field name mismatch: `score` vs `max_score`) and lose
   `description` (field name mismatch: `item`+`detail` vs `description`). Need a canonical
   serialization function.

**Important:** `engine.py` keeps `_async_session_factory` private (line 12). We cannot import `AsyncSessionLocal`. We need a helper function.

- [ ] **Step 1: Add `create_session()` helper to engine.py**

Add after `get_async_session()` in `services/web_app/db/engine.py`:
```python
def create_session() -> AsyncSession:
    """Create a standalone AsyncSession (for non-Depends usage).

    Caller is responsible for commit/close. Use with `async with`.
    """
    if _async_session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _async_session_factory()
```

- [ ] **Step 2: Add `_serialize_for_rfx_input()` conversion function**

Add in `services/web_app/main.py` (near other helper functions, e.g. after `_resolve_usage_actor`):

```python
def _serialize_for_rfx_input(analysis) -> dict:
    """Convert RFxAnalysisResult → dict matching RfxResultInput schema.

    RFxAnalysisResult stores evaluation_criteria as {category, item, score, detail}
    but RfxResultInput (rag_engine) expects {category, max_score, description}.
    Raw _asdict() would silently lose/zero-out fields at the Pydantic boundary.
    This function produces a canonical shape that round-trips cleanly through
    AnalysisSnapshot.analysis_json → generate endpoint → RfxResultInput validation.
    """
    from dataclasses import asdict as _asdict

    raw = _asdict(analysis)

    # Map evaluation_criteria: score→max_score, item+detail→description
    canonical_criteria = []
    for ec in raw.get("evaluation_criteria", []):
        desc_parts = [ec.get("item", ""), ec.get("detail", "")]
        canonical_criteria.append({
            "category": ec.get("category", ""),
            "max_score": ec.get("score", 0.0),
            "description": " — ".join(p for p in desc_parts if p),
        })

    # Map requirements: category+description only (Pydantic ignores extras)
    canonical_reqs = []
    for req in raw.get("requirements", []):
        canonical_reqs.append({
            "category": req.get("category", ""),
            "description": req.get("description", ""),
        })

    return {
        "title": raw.get("title", ""),
        "issuing_org": raw.get("issuing_org", ""),
        "budget": raw.get("budget", ""),
        "project_period": raw.get("project_period", ""),
        "evaluation_criteria": canonical_criteria,
        "requirements": canonical_reqs,
        "rfp_text_summary": raw.get("raw_text", "")[:10000],  # truncate for storage
        # Preserve extra metadata for audit (Pydantic ignores unknown fields)
        "announcement_number": raw.get("announcement_number", ""),
        "deadline": raw.get("deadline", ""),
        "required_documents": raw.get("required_documents", []),
        "special_notes": raw.get("special_notes", []),
        "document_type": raw.get("document_type", "unknown"),
        "is_rfx_like": raw.get("is_rfx_like", True),
    }
```

Key mappings:
- `RFxEvaluationCriteria.score` → `EvaluationCriterionInput.max_score`
- `RFxEvaluationCriteria.item` + `.detail` → `EvaluationCriterionInput.description`
- Extra metadata preserved under known keys (Pydantic v2 ignores extras by default)
- `raw_text` truncated to 10KB for `rfp_text_summary` (full text is in session memory)

- [ ] **Step 3: Extract `_persist_analysis_to_db()` async helper**

All 3 analysis entry points must persist to DB. Extract a reusable helper:

```python
async def _persist_analysis_to_db(
    request: Request,
    session_id: str,
    session,  # SessionState
    analysis,  # RFxAnalysisResult
    rfp_summary: str,
    matching,  # MatchingResult | None
) -> None:
    """Write-through: persist analysis snapshot to DB.

    Graceful degradation — never raises, only logs.
    Skipped for anonymous users (no org membership to resolve).
    """
    if not _BID_DB_ENABLED:
        return
    try:
        from dataclasses import asdict as _asdict
        from services.web_app.api.adapter import SessionAdapter
        from services.web_app.db.engine import create_session

        _, _username = _resolve_usage_actor(request, session_id)
        if not _username:  # Anonymous — no org to map to
            return
        async with create_session() as _db:
            _adapter = SessionAdapter(_db)
            _project = await _adapter.get_or_create_project(
                session.session_id, _username,
            )
            await _adapter.save_analysis(
                project_id=_project.id,
                org_id=_project.org_id,
                analysis_json=_serialize_for_rfx_input(analysis),
                summary_md=rfp_summary or None,
                go_nogo_json=_asdict(matching) if matching else None,
                username=_username,
            )
            # save_analysis() commits internally (adapter.py:105)
    except Exception:
        logger.warning("Failed to persist analysis to DB", exc_info=True)
```

- [ ] **Step 4: Wire into entry point 1 — `POST /api/analyze/upload` (line 1800, async)**

After line 1910 (`session.latest_document_name = primary_filename`), add:

```python
    await _persist_analysis_to_db(request, session_id, session, analysis, rfp_summary, matching)
```

- [ ] **Step 5: Wire into entry point 2 — `POST /api/analyze/text` (line 1939)**

This endpoint is currently sync (`def analyze_text`). Convert to `async def` — FastAPI
handles both, and the function does no blocking I/O itself (analyzer.analyze_text is
already fast for inline text). After line 1975 (`session.latest_document_name = ...`), add:

```python
    await _persist_analysis_to_db(request, payload.session_id, session, analysis, "", matching)
```

Note: `rfp_summary` is empty string here because `analyze_text` doesn't generate a
separate summary (the input text IS the document). The second arg is `payload.session_id`
(the Form field name differs from the upload endpoint).

Also change the function signature from `def analyze_text(...)` to `async def analyze_text(...)`.

- [ ] **Step 6: Wire into entry point 3 — `POST /api/bids/analyze` (line 2278, async)**

After line 2387 (`session.latest_document_name = best["fileNm"]`), add:

```python
    await _persist_analysis_to_db(request, payload.session_id, session, analysis, rfp_summary, matching)
```

**Three entry points, one helper** — complete persistence policy:

| Entry point | Line | Async? | session_id source |
|---|---|---|---|
| `POST /api/analyze/upload` | 1800 | yes | `session_id` (Form param) |
| `POST /api/analyze/text` | 1939 | convert to async | `payload.session_id` |
| `POST /api/bids/analyze` | 2278 | yes | `payload.session_id` |

**Identity resolution**:
- `_resolve_usage_actor(request, session_id)` at line 392 resolves the authenticated
  username from the auth cookie, returning `(scope, username)`.
- `username` is the real user identity that `_ensure_org()` can resolve membership for.
- If anonymous (`username == ""`), skip DB persistence entirely — anonymous users
  don't have org membership.
- `session.session_id` (first arg to `get_or_create_project`) is the session key for
  `legacy_session_id` lookup — correct (it's the session identifier, not the user identity).

**Serialization boundary**:
- `_serialize_for_rfx_input(analysis)` produces canonical dict matching `RfxResultInput`.
- Task 8's generate endpoint at line 1762 sends `snapshot.analysis_json` directly as
  `rfx_result` to rag_engine — round-trips cleanly through Pydantic validation.
- `_asdict(matching)` for go_nogo_json is fine — stored separately, consumed by frontend.

- [ ] **Step 7: Run regression tests**

Run: `python -m pytest tests/ -q --timeout=30`
Expected: All existing tests pass (DB code is behind `_BID_DB_ENABLED` flag)

- [ ] **Step 8: Commit**

```bash
git add services/web_app/db/engine.py services/web_app/main.py
git commit -m "feat(persistence): wire analysis write-through to DB for all 3 entry points"
```

---

### Task 10: Frontend doc_type Migration

**Files to update** (all `'wbs'` → `'execution_plan'`, `'ppt'` → `'presentation'` as doc_type identifiers):

| File | Lines | What to change |
|------|-------|----------------|
| `components/settings/documents/DocumentTabNav.tsx` | 4, 15, 16 | `DocumentTab` type union + tab id values |
| `components/settings/documents/DocumentWorkspace.tsx` | 11, 30, 31 | `VALID_TABS` set + conditional render |
| `components/settings/documents/WbsViewer.tsx` | 17 | localStorage key stays `kira_last_wbs` (UI data, not API type) |
| `components/settings/documents/PptViewer.tsx` | 17 | localStorage key stays `kira_last_ppt` (UI data, not API type) |
| `components/settings/documents/__tests__/DocumentWorkspace.test.ts` | 6, 34-39 | VALID_TABS + test assertions |
| `components/settings/documents/__tests__/viewerValidators.test.ts` | 124-143 | localStorage key refs (no change needed — UI keys) |
| `hooks/useConversationFlow.ts` | 1462, 1502, 1514, 1551 | case labels + pushDocHistory keys |
| `types.ts` | 385-386 | `generate_wbs` → `generate_execution_plan`, `generate_ppt` → `generate_presentation` |
| `components/chat/messages/AnalysisResultView.tsx` | 266, 273 | action type dispatches |

**Note:** File extension detection (`'.ppt'`, `'.pptx'` → DocFileType `'ppt'`) in `useConversationFlow.ts:57` and `ChatHeader.tsx:27` are about file format detection, NOT doc_type. These stay as-is.

**Note:** `localStorage` keys (`kira_last_wbs`, `kira_last_ppt`) are UI storage keys, not API doc_type identifiers. These can stay as-is (renaming them would break existing users' cached data).

- [ ] **Step 1: Update DocumentTabNav.tsx type + tab definitions**

```typescript
// Line 4: Update type
export type DocumentTab = 'profile' | 'rfp' | 'proposal' | 'execution_plan' | 'presentation' | 'track_record';

// Lines 15-16: Update tab ids
  { id: 'execution_plan', label: '수행계획서', icon: CalendarDays },
  { id: 'presentation', label: '발표자료', icon: Presentation },
```

- [ ] **Step 2: Update DocumentWorkspace.tsx**

```typescript
// Line 11:
const VALID_TABS: Set<string> = new Set(['profile', 'rfp', 'proposal', 'execution_plan', 'presentation', 'track_record']);

// Lines 30-31:
{activeTab === 'execution_plan' && <WbsViewer />}
{activeTab === 'presentation' && <PptViewer />}
```

- [ ] **Step 3: Update types.ts action types**

```typescript
// Lines 385-386:
  | { type: 'generate_execution_plan' }
  | { type: 'generate_presentation' }
```

- [ ] **Step 4: Update useConversationFlow.ts case labels**

```typescript
// Line 1462: case 'generate_execution_plan':
// Line 1514: case 'generate_presentation':
// pushDocHistory keys stay as kira_last_wbs / kira_last_ppt (localStorage, not API)
```

- [ ] **Step 5: Update AnalysisResultView.tsx action dispatches**

```typescript
// Line 266: onClick={() => onAction?.({ type: 'generate_execution_plan' })}
// Line 273: onClick={() => onAction?.({ type: 'generate_presentation' })}
```

- [ ] **Step 6: Update test files**

DocumentWorkspace.test.ts:
```typescript
const VALID_TABS = new Set(['profile', 'rfp', 'proposal', 'execution_plan', 'presentation', 'track_record']);
// Update test assertions for 'execution_plan' and 'presentation'
```

- [ ] **Step 7: Run frontend type check + build**

Run: `cd frontend/kirabot && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 8: Commit**

```bash
git add frontend/kirabot/
git commit -m "feat(frontend): migrate doc_type identifiers from wbs/ppt to execution_plan/presentation"
```

---

### Task 11: Full Regression Tests

**Files:** (no new files — verification only)

- [ ] **Step 1: Run rag_engine tests**

Run: `cd rag_engine && python -m pytest -q --timeout=30`
Expected: All pass (367+)

- [ ] **Step 2: Run web_app tests (unit)**

Run: `python -m pytest services/web_app/tests/ -v -k "not storage"`
Expected: All pass (45+ existing + new)

- [ ] **Step 3: Run web_app tests (DB)**

Run: `BID_TEST_DATABASE_URL="postgresql+asyncpg://kira:kira@localhost:5434/kira_bid_test" BID_DEV_BOOTSTRAP=1 python -m pytest services/web_app/tests/ -v`
Expected: All pass

- [ ] **Step 4: Run root legacy tests**

Run: `python -m pytest tests/ -q --timeout=30`
Expected: 195+ pass, 0 regressions

- [ ] **Step 5: Run frontend type check**

Run: `cd frontend/kirabot && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 6: Commit (if any test fixes needed)**

```bash
git commit -m "fix: test adjustments for Phase 2 integration"
```

---

## Summary

| Task | Deliverable | Files |
|------|------------|-------|
| 1 | GenerationContract dataclasses | `rag_engine/generation_contract.py` |
| 2 | doc_type migration (wbs→execution_plan, ppt→presentation) | `auto_learner.py`, `main.py` |
| 3 | Quality checker expansion to all doc_types | `quality_checker.py` |
| 4 | Contract adapter + orchestrator dispatch | `rag_engine/contract_adapter.py` + modify `phase2_models.py`, `ppt_orchestrator.py`, `track_record_orchestrator.py` |
| 5 | Unified /api/generate-document endpoint | `rag_engine/main.py` |
| 6 | Contract builder service | `services/web_app/services/contract_builder.py` |
| 7 | Generation service (DocumentRun lifecycle) | `services/web_app/services/generation_service.py` |
| 8 | /api/projects/{id}/generate endpoint | `services/web_app/api/generate.py` (dynamic asset allocation) |
| 9 | Analysis persistence write-through (all 3 entry points) | `services/web_app/db/engine.py`, `services/web_app/main.py` |
| 10 | Frontend doc_type tab migration | 9 files: `DocumentTabNav.tsx`, `DocumentWorkspace.tsx`, `types.ts`, `useConversationFlow.ts`, `AnalysisResultView.tsx`, + test files |
| 11 | Full regression verification | (verify only) |

**New files:** 7 (+ 7 test files)
**Modified files:** 12 (engine.py, main.py×2, quality_checker.py, phase2_models.py, ppt_orchestrator.py, track_record_orchestrator.py, + 5 frontend)
**Total tasks:** 11
**Estimated commits:** 11
