# Company Document Pack Phase 1: Guide Pack + 수행계획서 품질 개선

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the 1/10 quality problem — remove IT domain bias, establish domain-native section structures (research 9장, IT 10장, consulting 10장, education 10장), and raise the quality floor. This phase builds the Pack architecture kernel; full "컨설턴트급" quality (Planning Agent, exemplar retrieval) arrives in Phase 2-3.

**Architecture:** New domain detection + Pack-based section resolution replaces hard-coded IT templates. `document_orchestrator.py` unifies wbs_orchestrator + proposal_orchestrator. Section Writer gets Pack-augmented prompts. All existing API endpoints preserved (internal routing only).

**Tech Stack:** Python 3.11+, FastAPI, OpenAI (gpt-4o-mini), ChromaDB, python-docx, openpyxl, matplotlib, Pydantic v2

**Spec:** `docs/superpowers/specs/2026-03-11-company-document-pack-design.md`

---

## File Structure

### New Files (11)

| File | Responsibility |
|------|---------------|
| `rag_engine/pack_models.py` | Pydantic models for Pack data structures (PackSection, DomainDict, PackConfig, etc.) |
| `rag_engine/domain_detector.py` | RFP text → `DomainType` classification (LLM + keyword fallback) |
| `rag_engine/pack_manager.py` | Load Pack files, resolve inheritance chain, merge _default + company |
| `rag_engine/section_resolver.py` | Evaluate sections.json conditions against RFP → active section list |
| `rag_engine/schedule_planner.py` | domain_dict-based WBS task generation (replaces wbs_planner.py IT templates) |
| `rag_engine/document_orchestrator.py` | Unified pipeline: detect → resolve → plan → write → check → assemble |
| `data/company_packs/_default/pack.json` | Default Guide Pack root config |
| `data/company_packs/_default/execution_plan/research/sections.json` | Research domain 9-section structure (연구용역형) |
| `data/company_packs/_default/execution_plan/research/domain_dict.json` | Research roles, phases, methodologies |
| `data/company_packs/_default/execution_plan/research/boilerplate.json` | Research domain boilerplate texts |
| `data/company_packs/_default/execution_plan/it_build/` | IT Build domain (sections + domain_dict + boilerplate) |
| `data/company_packs/_default/execution_plan/consulting/` | Consulting domain (sections + domain_dict + boilerplate) |
| `data/company_packs/_default/execution_plan/education_oda/` | Education/ODA domain (sections + domain_dict + boilerplate) |
| `data/company_packs/_default/execution_plan/general/` | General fallback domain (sections + domain_dict + boilerplate) |

### Modified Files (5)

| File | Changes |
|------|---------|
| `rag_engine/section_writer.py` | New `assemble_pack_prompt()` + `call_llm_for_pack_section()` public functions |
| `rag_engine/quality_checker.py` | Add `check_quality_with_pack()` accepting must_include_facts + forbidden_patterns |
| `rag_engine/knowledge_db.py` | Add `domain_type` filter to `search()` + `_make_metadata()` |
| `rag_engine/main.py` | Wire `/api/generate-wbs` to use document_orchestrator (internal only) |
| `rag_engine/phase2_models.py` | Add `DomainType` enum, extend `WbsResult` with `domain_type` field |

### Test Files (8)

| File | Tests |
|------|-------|
| `rag_engine/tests/test_pack_models.py` | Model validation, serialization |
| `rag_engine/tests/test_domain_detector.py` | 4 domain classification + fallback |
| `rag_engine/tests/test_pack_manager.py` | Load, inheritance merge, fallback chain |
| `rag_engine/tests/test_section_resolver.py` | Condition evaluation, dynamic sections |
| `rag_engine/tests/test_schedule_planner.py` | Domain-aware task generation |
| `rag_engine/tests/test_document_orchestrator.py` | End-to-end pipeline with mocks |
| `rag_engine/tests/test_quality_checker_pack.py` | Pack-aware quality checks |
| `rag_engine/tests/fixtures/domain_detection/` | 4 RFP text files for domain tests |

---

## Chunk 1: Data Models + Guide Pack JSON Files

### Task 1: Pack Data Models

**Files:**
- Create: `rag_engine/pack_models.py`
- Create: `rag_engine/tests/test_pack_models.py`
- Modify: `rag_engine/phase2_models.py` (add DomainType)

- [ ] **Step 1: Add DomainType to phase2_models.py**

```python
# rag_engine/phase2_models.py — add after MethodologyType enum

class DomainType(str, Enum):
    IT_BUILD = "it_build"
    RESEARCH = "research"
    CONSULTING = "consulting"
    EDUCATION_ODA = "education_oda"
    GENERAL = "general"
```

- [ ] **Step 2: Write failing tests for pack_models**

```python
# rag_engine/tests/test_pack_models.py
"""Tests for Pack data models."""
import pytest
from pack_models import (
    PackSection, PackSubsection, GenerationTarget, RenderValidation,
    DomainDictRole, DomainDictPhase, DomainDict, BoilerplateEntry,
    PackConfig, SectionsConfig,
)


def test_pack_section_minimal():
    s = PackSection(id="s01", name="사업 이해", level=1, weight=0.12, max_score=15)
    assert s.required is True  # default
    assert s.conditions == {"always": True}  # default
    assert s.subsections == []
    assert s.generation_target is None


def test_pack_section_with_generation_target():
    s = PackSection(
        id="s01", name="사업 이해", level=1, weight=0.12, max_score=15,
        generation_target=GenerationTarget(min_chars=2000, max_chars=5000, token_budget=2500),
    )
    assert s.generation_target.token_budget == 2500


def test_pack_section_with_subsections():
    s = PackSection(
        id="s07", name="리스크 관리", level=1, weight=0.08, max_score=5,
        required=False,
        conditions={"any_of": [{"min_budget_krw": 100000000}]},
        subsections=[
            PackSubsection(id="s07_1", name="리스크 식별", block_types=["narrative", "table"]),
        ],
    )
    assert len(s.subsections) == 1
    assert s.subsections[0].id == "s07_1"


def test_domain_dict_research():
    dd = DomainDict(
        domain_type="research",
        roles=[DomainDictRole(id="pi", name="연구책임자", grade="특급")],
        phases=[DomainDictPhase(id="design", name="연구설계")],
    )
    assert dd.roles[0].id == "pi"
    assert dd.phases[0].name == "연구설계"


def test_boilerplate_entry():
    bp = BoilerplateEntry(
        id="bp_quality", section_id="s06", mode="prepend",
        text="본 연구팀은 ISO 9001...", tags=["품질관리"],
    )
    assert bp.mode == "prepend"


def test_boilerplate_mode_validation():
    with pytest.raises(ValueError):
        BoilerplateEntry(id="bp", section_id="s01", mode="invalid", text="x")


def test_sections_config_from_json(tmp_path):
    import json
    data = {
        "document_type": "execution_plan",
        "domain_type": "research",
        "sections": [
            {"id": "s01", "name": "사업 이해", "level": 1, "weight": 0.12, "max_score": 15}
        ],
    }
    p = tmp_path / "sections.json"
    p.write_text(json.dumps(data, ensure_ascii=False))
    cfg = SectionsConfig.model_validate_json(p.read_text())
    assert cfg.document_type == "execution_plan"
    assert len(cfg.sections) == 1


def test_pack_config():
    pc = PackConfig(
        pack_id="_default_exec_research",
        company_id="_default",
        version=1,
        status="active",
        base_pack_ref=None,
    )
    assert pc.base_pack_ref is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd rag_engine && python -m pytest tests/test_pack_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pack_models'`

- [ ] **Step 4: Implement pack_models.py**

```python
# rag_engine/pack_models.py
"""Pydantic models for Company Document Pack data structures.

See spec: docs/superpowers/specs/2026-03-11-company-document-pack-design.md §3
"""
from __future__ import annotations

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


class GenerationTarget(BaseModel):
    min_chars: int = 0
    max_chars: int = 10000
    token_budget: int = 2000  # LLM max_tokens output limit


class RenderValidation(BaseModel):
    min_pages: int = 1
    max_pages: int = 99
    action_on_violation: Literal["warn", "retry", "block"] = "warn"


class PackSubsection(BaseModel):
    id: str
    name: str
    dynamic: bool = False
    block_types: list[str] = Field(default_factory=lambda: ["narrative"])
    render_mode: Optional[str] = None
    instructions: str = ""
    conditions: Optional[dict[str, Any]] = None


class PackSection(BaseModel):
    id: str
    name: str
    level: int = 1
    required: bool = True
    weight: float = 0.1
    max_score: float = 0
    conditions: dict[str, Any] = Field(default_factory=lambda: {"always": True})
    generation_target: Optional[GenerationTarget] = None
    render_validation: Optional[RenderValidation] = None
    block_types: list[str] = Field(default_factory=lambda: ["narrative"])
    must_include_facts: list[str] = Field(default_factory=list)
    forbidden_patterns: list[str] = Field(default_factory=list)
    evidence_policy: str = ""
    fallback_text_policy: str = ""
    priority: int = 0
    disabled: bool = False  # company pack can disable inherited sections
    subsections: list[PackSubsection] = Field(default_factory=list)


class SectionsConfig(BaseModel):
    document_type: str
    domain_type: str
    sections: list[PackSection]


class DomainDictRole(BaseModel):
    id: str
    name: str
    grade: str = ""
    aliases: list[str] = Field(default_factory=list)


class DomainDictPhase(BaseModel):
    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)


class DomainDictMethodology(BaseModel):
    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)


class CommonRisk(BaseModel):
    risk: str
    mitigation: str


class DomainDict(BaseModel):
    domain_type: str = ""
    roles: list[DomainDictRole] = Field(default_factory=list)
    phases: list[DomainDictPhase] = Field(default_factory=list)
    methodologies: list[DomainDictMethodology] = Field(default_factory=list)
    deliverables_common: list[str] = Field(default_factory=list)
    organization_terms: dict[str, list[str]] = Field(default_factory=dict)
    common_risks: list[CommonRisk] = Field(default_factory=list)
    quality_frameworks: list[str] = Field(default_factory=list)


class BoilerplateEntry(BaseModel):
    id: str
    section_id: str
    mode: Literal["prepend", "append", "replace", "merge"]
    text: str
    tags: list[str] = Field(default_factory=list)


class BoilerplateConfig(BaseModel):
    boilerplates: list[BoilerplateEntry] = Field(default_factory=list)


class PackConfig(BaseModel):
    pack_id: str = ""
    company_id: str = "_default"
    version: int = 1
    status: Literal["draft", "shadow", "active", "archived"] = "active"
    base_pack_ref: Optional[str] = None
    source_documents: list[dict[str, Any]] = Field(default_factory=list)
    active_render_targets: list[str] = Field(default_factory=lambda: ["docx"])
    created_at: str = ""
    updated_at: str = ""
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd rag_engine && python -m pytest tests/test_pack_models.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add rag_engine/pack_models.py rag_engine/tests/test_pack_models.py rag_engine/phase2_models.py
git commit -m "feat: add Pack data models + DomainType enum"
```

---

### Task 2: Guide Pack JSON Files — Research Domain

**Files:**
- Create: `data/company_packs/_default/pack.json`
- Create: `data/company_packs/_default/execution_plan/research/sections.json`
- Create: `data/company_packs/_default/execution_plan/research/domain_dict.json`
- Create: `data/company_packs/_default/execution_plan/research/boilerplate.json`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p data/company_packs/_default/execution_plan/research
mkdir -p data/company_packs/_default/execution_plan/it_build
mkdir -p data/company_packs/_default/execution_plan/consulting
mkdir -p data/company_packs/_default/execution_plan/education_oda
mkdir -p data/company_packs/_default/execution_plan/general
```

- [ ] **Step 2: Create _default/pack.json**

Copy from spec §3 `pack.json` with `base_pack_ref: null`, `company_id: "_default"`, `status: "active"`.

- [ ] **Step 3: Create research/sections.json**

Copy the full research sections.json from spec §3 (s01–s09, 연구용역형 9장: 연구배경/목적 → 선행연구 검토 → 연구방법론 → 연구내용 → 추진일정 → 연구진 구성 → 품질관리 → 연구윤리/IRB → 연구결과 활용/확산). 이 구조는 부록 "연구용역형" 요약과 일치해야 합니다.

- [ ] **Step 4: Create research/domain_dict.json**

Copy from spec §3 — roles (PI, co-PI, RA, advisor, surveyor, statistician), phases (design→review→collect→analyze→recommend→disseminate→closing), methodologies (mixed/qual/quant/action/delphi), deliverables, common_risks.

- [ ] **Step 5: Create research/boilerplate.json**

Copy from spec §3 — bp_quality_mgmt (s06, prepend) + bp_risk_intro (s07, prepend).

- [ ] **Step 6: Validate JSON files load correctly**

```bash
cd rag_engine && python -c "
from pack_models import SectionsConfig, DomainDict, BoilerplateConfig, PackConfig
import json, pathlib
base = pathlib.Path('../data/company_packs/_default')
PackConfig.model_validate_json((base / 'pack.json').read_text())
SectionsConfig.model_validate_json((base / 'execution_plan/research/sections.json').read_text())
DomainDict.model_validate_json((base / 'execution_plan/research/domain_dict.json').read_text())
BoilerplateConfig.model_validate_json((base / 'execution_plan/research/boilerplate.json').read_text())
print('All JSON valid')
"
```
Expected: `All JSON valid`

- [ ] **Step 7: Commit**

```bash
git add data/company_packs/
git commit -m "feat: add _default Guide Pack for research domain"
```

---

### Task 3: Guide Pack JSON Files — IT Build Domain

**Files:**
- Create: `data/company_packs/_default/execution_plan/it_build/sections.json`
- Create: `data/company_packs/_default/execution_plan/it_build/domain_dict.json`
- Create: `data/company_packs/_default/execution_plan/it_build/boilerplate.json`

- [ ] **Step 1: Create it_build/sections.json**

IT Build sections (from spec 부록 A): 사업이해 → 수행전략 → 기술적접근방안 → 세부수행방안 → WBS/일정 → 투입인력 → 품질관리(감리대응) → 보안관리 → 리스크관리 → 기대효과. Map to s01–s10 IDs. Use IT-specific `must_include_facts`: ["시스템 아키텍처", "개발 표준"], `forbidden_patterns` etc.

- [ ] **Step 2: Create it_build/domain_dict.json**

Roles: PM, PL, 개발자, 디자이너, QA, DBA, 보안전문가, 인프라전문가.
Phases: 착수 → 분석 → 설계 → 구현 → 시험 → 이행/종료.
Methodologies: waterfall, agile, hybrid, devops.
Deliverables: 요구사항정의서, 설계서, 소스코드, 시험결과서, 운영매뉴얼.
Common risks: 요구사항 변경, 레거시 연동 실패, 성능 미달.

- [ ] **Step 3: Create it_build/boilerplate.json**

Standard boilerplates: 품질관리체계 (ISO 25010), 보안관리체계 (ISMS), 감리대응 프로세스.

- [ ] **Step 4: Validate all IT build JSON files**

Same validation pattern as Task 2 Step 6.

- [ ] **Step 5: Commit**

```bash
git add data/company_packs/_default/execution_plan/it_build/
git commit -m "feat: add _default Guide Pack for IT build domain"
```

---

### Task 4: Domain Detection Test Fixtures

**Files:**
- Create: `rag_engine/tests/fixtures/domain_detection/it_build.txt`
- Create: `rag_engine/tests/fixtures/domain_detection/research.txt`
- Create: `rag_engine/tests/fixtures/domain_detection/consulting.txt`
- Create: `rag_engine/tests/fixtures/domain_detection/education_oda.txt`

- [ ] **Step 1: Create fixture directory**

```bash
mkdir -p rag_engine/tests/fixtures/domain_detection
```

- [ ] **Step 2: Create 4 RFP text fixtures**

Each file = 300–500 chars of representative RFP title + scope text:

`it_build.txt`:
```
사업명: 차세대 통합정보시스템 구축 사업
사업목적: 노후화된 레거시 시스템을 클라우드 기반 통합 플랫폼으로 전환하여 행정 효율화 달성
주요 과업: 현행 시스템 분석, 아키텍처 설계, DB 설계, 프로그램 개발, 시스템 통합테스트, 데이터 이관, 사용자 교육
기술 요구사항: Java/Spring, PostgreSQL, Kubernetes, MSA 아키텍처
```

`research.txt`:
```
사업명: 제2차 치유농업 연구개발 및 육성 종합계획 수립 연구용역
사업목적: 치유농업의 효과성 검증 및 정책 방향 수립을 위한 기초연구
주요 과업: 국내외 선행연구 분석, 치유농업 현황조사, 설문조사 및 통계분석, 정책제언 도출, 중장기 로드맵 수립
연구방법: 문헌조사, FGI, 델파이조사, 실증분석
```

`consulting.txt`:
```
사업명: 공공기관 디지털전환 전략 수립 컨설팅
사업목적: 디지털전환 현황 진단 및 단계별 추진 전략 수립
주요 과업: 현황진단, GAP분석, 목표모델 수립, 실행계획 수립, 변화관리 방안, ISP 보고서 작성
```

`education_oda.txt`:
```
사업명: KOICA 개도국 ICT 교육역량강화 사업
사업목적: 개발도상국 교원 ICT 역량강화 및 교육과정 개발
주요 과업: 사전조사, 교육과정 설계, 교재/콘텐츠 개발, 시범교육 운영, 성과평가, 현지이관
```

- [ ] **Step 3: Commit**

```bash
git add rag_engine/tests/fixtures/
git commit -m "feat: add domain detection test fixtures"
```

---

### Task 4.5: Guide Pack JSON Files — Consulting + Education/ODA + General

**Files:**
- Create: `data/company_packs/_default/execution_plan/consulting/sections.json`
- Create: `data/company_packs/_default/execution_plan/consulting/domain_dict.json`
- Create: `data/company_packs/_default/execution_plan/consulting/boilerplate.json`
- Create: `data/company_packs/_default/execution_plan/education_oda/sections.json`
- Create: `data/company_packs/_default/execution_plan/education_oda/domain_dict.json`
- Create: `data/company_packs/_default/execution_plan/education_oda/boilerplate.json`
- Create: `data/company_packs/_default/execution_plan/general/sections.json`
- Create: `data/company_packs/_default/execution_plan/general/domain_dict.json`
- Create: `data/company_packs/_default/execution_plan/general/boilerplate.json`

- [ ] **Step 1: Create consulting domain Pack**

Sections from spec 부록 A (컨설팅/PMO형): 사업이해 → 진단방법론 → 현황진단계획 → 개선방안수립 → 실행지원 → 변화관리 → 추진일정 → 투입인력 → 품질관리 → 기대효과.
Roles: PM, 컨설턴트(수석/책임/선임), 현장조사원, ISP전문가.
Phases: 착수 → 현황진단 → 목표수립 → 개선설계 → 실행지원 → 종료.

- [ ] **Step 2: Create education_oda domain Pack**

Sections from spec 부록 A (교육/ODA형): 사업이해 → 사전조사계획 → 교육과정설계 → 콘텐츠개발 → 시범/본운영 → 성과평가 → 현지이관/지속가능성 → 추진일정 → 투입인력 → 리스크관리.
Roles: PM, 교육전문가, 콘텐츠개발자, 현지전문가, 통번역사.
Phases: 사전조사 → 설계 → 개발 → 시범운영 → 본운영 → 평가 → 이관.

- [ ] **Step 3: Create general fallback Pack**

Minimal 5-section structure: 사업이해 → 수행전략 → 세부수행방안 → 추진일정 → 기대효과.
Generic roles: PM, 수석전문가, 전문가, 연구원.
Generic phases: 착수 → 실행 → 마무리.

- [ ] **Step 4: Validate all new JSON files**

Same pattern as Task 2 Step 6 — load each with Pydantic model.

- [ ] **Step 5: Commit**

```bash
git add data/company_packs/_default/execution_plan/consulting/
git add data/company_packs/_default/execution_plan/education_oda/
git add data/company_packs/_default/execution_plan/general/
git commit -m "feat: add consulting, education_oda, general Guide Packs"
```

---

### Task 4.6: KnowledgeDB domain_type Filter

**Files:**
- Modify: `rag_engine/knowledge_db.py`
- Modify: `rag_engine/tests/test_knowledge_db.py`

- [ ] **Step 1: Write failing test**

Add to `rag_engine/tests/test_knowledge_db.py`:

```python
def test_search_with_domain_type_filter(knowledge_db_with_data):
    # Assumes existing fixture adds units with document_type metadata
    # Add domain_type to test: units should have domain_type in metadata
    results = knowledge_db_with_data.search(
        "수행계획서", top_k=5, domain_type="research"
    )
    # Should not error; filters by domain_type if present in metadata
    assert isinstance(results, list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd rag_engine && python -m pytest tests/test_knowledge_db.py::test_search_with_domain_type_filter -v`
Expected: FAIL — `TypeError: search() got an unexpected keyword argument 'domain_type'`

- [ ] **Step 3: Add domain_type parameter to search()**

In `rag_engine/knowledge_db.py`, modify `search()`:

```python
def search(
    self,
    query: str,
    top_k: int = 10,
    category: Optional[KnowledgeCategory] = None,
    document_types: Optional[list[DocumentType]] = None,
    domain_type: Optional[str] = None,  # NEW
) -> list[KnowledgeUnit]:
    """Search with optional filtering."""
    where_conditions = []
    if category:
        where_conditions.append({"category": category.value})
    if document_types:
        where_conditions.append({"document_type": {"$in": [dt.value for dt in document_types]}})
    if domain_type:
        where_conditions.append({"domain_type": domain_type})

    where = None
    if len(where_conditions) == 1:
        where = where_conditions[0]
    elif len(where_conditions) > 1:
        where = {"$and": where_conditions}
    # ... rest of search logic unchanged
```

- [ ] **Step 4: Run tests**

Run: `cd rag_engine && python -m pytest tests/test_knowledge_db.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add rag_engine/knowledge_db.py rag_engine/tests/test_knowledge_db.py
git commit -m "feat: add domain_type filter to KnowledgeDB.search()"
```

---

## Chunk 2: Domain Detector + Pack Manager

### Task 5: Domain Detector

**Files:**
- Create: `rag_engine/domain_detector.py`
- Create: `rag_engine/tests/test_domain_detector.py`

- [ ] **Step 1: Write failing tests**

```python
# rag_engine/tests/test_domain_detector.py
"""Tests for domain detection from RFP text."""
import pathlib
import pytest
from unittest.mock import patch, MagicMock

from domain_detector import detect_domain, _keyword_fallback
from phase2_models import DomainType

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "domain_detection"


class TestKeywordFallback:
    def test_it_build(self):
        text = (FIXTURES / "it_build.txt").read_text()
        assert _keyword_fallback(text) == DomainType.IT_BUILD

    def test_research(self):
        text = (FIXTURES / "research.txt").read_text()
        assert _keyword_fallback(text) == DomainType.RESEARCH

    def test_consulting(self):
        text = (FIXTURES / "consulting.txt").read_text()
        assert _keyword_fallback(text) == DomainType.CONSULTING

    def test_education_oda(self):
        text = (FIXTURES / "education_oda.txt").read_text()
        assert _keyword_fallback(text) == DomainType.EDUCATION_ODA

    def test_empty_text_returns_general(self):
        assert _keyword_fallback("") == DomainType.GENERAL


class TestDetectDomain:
    @patch("domain_detector._call_llm_detect")
    def test_llm_success(self, mock_llm):
        mock_llm.return_value = {"domain_type": "research", "confidence": 0.95}
        result = detect_domain({"title": "연구용역", "full_text": "연구..."})
        assert result == DomainType.RESEARCH

    @patch("domain_detector._call_llm_detect")
    def test_llm_failure_falls_back_to_keyword(self, mock_llm):
        mock_llm.side_effect = Exception("API error")
        text = (FIXTURES / "it_build.txt").read_text()
        result = detect_domain({"title": text, "full_text": text})
        assert result == DomainType.IT_BUILD

    @patch("domain_detector._call_llm_detect")
    def test_llm_low_confidence_falls_back(self, mock_llm):
        mock_llm.return_value = {"domain_type": "research", "confidence": 0.3}
        text = (FIXTURES / "consulting.txt").read_text()
        result = detect_domain({"title": text, "full_text": text})
        assert result == DomainType.CONSULTING  # keyword fallback wins
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd rag_engine && python -m pytest tests/test_domain_detector.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'domain_detector'`

- [ ] **Step 3: Implement domain_detector.py**

```python
# rag_engine/domain_detector.py
"""Domain Detector — RFP text → DomainType classification.

Uses LLM with keyword fallback. See spec §5 Step 1.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Optional

from openai import OpenAI

from llm_utils import call_with_retry, LLM_DEFAULT_TIMEOUT
from phase2_models import DomainType

logger = logging.getLogger(__name__)

# Keyword scoring: domain → (keyword, weight) pairs
_KEYWORD_SCORES: dict[DomainType, list[tuple[str, int]]] = {
    DomainType.IT_BUILD: [
        ("시스템 구축", 3), ("정보시스템", 3), ("SW 개발", 3), ("소프트웨어", 2),
        ("클라우드", 2), ("데이터베이스", 2), ("아키텍처", 2), ("프로그램 개발", 3),
        ("통합테스트", 2), ("데이터 이관", 2), ("ISP", 2), ("UI/UX", 1),
        ("인프라", 2), ("네트워크", 1), ("보안", 1), ("운영", 1),
    ],
    DomainType.RESEARCH: [
        ("연구", 3), ("연구용역", 4), ("선행연구", 3), ("문헌조사", 3),
        ("설문조사", 2), ("통계분석", 2), ("정책제언", 3), ("연구방법", 3),
        ("델파이", 3), ("FGI", 2), ("실증분석", 2), ("논문", 1),
        ("IRB", 3), ("연구윤리", 2), ("학술", 2), ("조사", 1),
    ],
    DomainType.CONSULTING: [
        ("컨설팅", 4), ("진단", 3), ("GAP분석", 3), ("전략 수립", 3),
        ("ISP", 2), ("현황진단", 3), ("PMO", 3), ("변화관리", 2),
        ("목표모델", 2), ("로드맵", 2), ("BPR", 3), ("PI", 2),
        ("마스터플랜", 2), ("아키텍처", 1),
    ],
    DomainType.EDUCATION_ODA: [
        ("교육", 2), ("ODA", 4), ("KOICA", 4), ("개도국", 3),
        ("역량강화", 3), ("교육과정", 2), ("교재", 2), ("콘텐츠 개발", 2),
        ("시범교육", 3), ("현지이관", 3), ("봉사단", 3), ("글로벌연수", 3),
        ("교원", 2), ("연수", 2), ("국제협력", 2),
    ],
}


def _keyword_fallback(text: str) -> DomainType:
    """Score-based keyword matching for domain classification."""
    if not text.strip():
        return DomainType.GENERAL

    scores: dict[DomainType, int] = {dt: 0 for dt in DomainType if dt != DomainType.GENERAL}
    text_lower = text.lower()

    for domain, keywords in _KEYWORD_SCORES.items():
        for kw, weight in keywords:
            if kw.lower() in text_lower:
                scores[domain] += weight

    best = max(scores, key=scores.get)
    if scores[best] < 3:  # minimum threshold
        return DomainType.GENERAL
    return best


def _call_llm_detect(
    rfp_text: str,
    api_key: Optional[str] = None,
) -> dict[str, Any]:
    """Call LLM for domain classification. Returns {"domain_type": str, "confidence": float}."""
    client = OpenAI(
        api_key=api_key or os.environ.get("OPENAI_API_KEY"),
        timeout=LLM_DEFAULT_TIMEOUT,
    )

    prompt = f"""다음 RFP(제안요청서) 텍스트를 읽고 도메인을 분류하세요.

도메인 옵션:
- it_build: IT 시스템 구축/개발/운영 사업
- research: 연구용역/정책연구/학술연구
- consulting: 컨설팅/PMO/ISP/전략수립
- education_oda: 교육/ODA/국제협력/역량강화
- general: 위 4가지에 해당하지 않는 경우

RFP 텍스트:
{rfp_text[:3000]}

JSON으로 응답하세요:
{{"domain_type": "...", "confidence": 0.0~1.0}}"""

    def _do_call():
        return client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "공공조달 RFP 도메인 분류 전문가입니다. JSON만 응답합니다."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=100,
            response_format={"type": "json_object"},
        )

    resp = call_with_retry(_do_call)
    return json.loads(resp.choices[0].message.content or "{}")


def detect_domain(
    rfx_result: dict[str, Any],
    api_key: Optional[str] = None,
) -> DomainType:
    """Detect domain type from RFP analysis result.

    Strategy: LLM first → keyword fallback if LLM fails or low confidence.
    """
    title = rfx_result.get("title", "")
    full_text = rfx_result.get("full_text", rfx_result.get("raw_text", ""))
    combined = f"{title}\n{full_text}"[:4000]

    # Try LLM
    try:
        llm_result = _call_llm_detect(combined, api_key)
        domain_str = llm_result.get("domain_type", "")
        confidence = float(llm_result.get("confidence", 0))

        if confidence >= 0.6:
            try:
                return DomainType(domain_str)
            except ValueError:
                logger.warning("LLM returned invalid domain: %s", domain_str)
    except Exception as exc:
        logger.warning("LLM domain detection failed, using keyword fallback: %s", exc)

    # Keyword fallback
    return _keyword_fallback(combined)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd rag_engine && python -m pytest tests/test_domain_detector.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add rag_engine/domain_detector.py rag_engine/tests/test_domain_detector.py
git commit -m "feat: add domain detector with LLM + keyword fallback"
```

---

### Task 6: Pack Manager

**Files:**
- Create: `rag_engine/pack_manager.py`
- Create: `rag_engine/tests/test_pack_manager.py`

- [ ] **Step 1: Write failing tests**

```python
# rag_engine/tests/test_pack_manager.py
"""Tests for Pack loading, resolution, and inheritance merge."""
import json
import pytest
from pathlib import Path

from pack_manager import PackManager
from pack_models import SectionsConfig, DomainDict, BoilerplateConfig, PackConfig


@pytest.fixture
def pack_dir(tmp_path):
    """Create minimal _default pack structure for testing."""
    default = tmp_path / "_default"
    default.mkdir()

    # pack.json
    (default / "pack.json").write_text(json.dumps({
        "pack_id": "_default_exec_research",
        "company_id": "_default",
        "version": 1,
        "status": "active",
        "base_pack_ref": None,
    }, ensure_ascii=False))

    # execution_plan/research/
    research = default / "execution_plan" / "research"
    research.mkdir(parents=True)

    (research / "sections.json").write_text(json.dumps({
        "document_type": "execution_plan",
        "domain_type": "research",
        "sections": [
            {"id": "s01", "name": "사업 이해", "level": 1, "weight": 0.5, "max_score": 15,
             "generation_target": {"min_chars": 2000, "max_chars": 5000, "token_budget": 2500}},
            {"id": "s02", "name": "수행 전략", "level": 1, "weight": 0.5, "max_score": 20},
        ],
    }, ensure_ascii=False))

    (research / "domain_dict.json").write_text(json.dumps({
        "domain_type": "research",
        "roles": [{"id": "pi", "name": "연구책임자", "grade": "특급"}],
        "phases": [{"id": "design", "name": "연구설계"}],
    }, ensure_ascii=False))

    (research / "boilerplate.json").write_text(json.dumps({
        "boilerplates": [
            {"id": "bp_quality", "section_id": "s01", "mode": "prepend", "text": "품질 보장."}
        ],
    }, ensure_ascii=False))

    # execution_plan/general/ (fallback)
    general = default / "execution_plan" / "general"
    general.mkdir(parents=True)
    (general / "sections.json").write_text(json.dumps({
        "document_type": "execution_plan",
        "domain_type": "general",
        "sections": [{"id": "s01", "name": "개요", "level": 1, "weight": 1.0, "max_score": 10}],
    }, ensure_ascii=False))
    (general / "domain_dict.json").write_text(json.dumps({"domain_type": "general", "roles": [], "phases": []}, ensure_ascii=False))
    (general / "boilerplate.json").write_text(json.dumps({"boilerplates": []}, ensure_ascii=False))

    return tmp_path


class TestPackManagerLoad:
    def test_load_default_research(self, pack_dir):
        pm = PackManager(pack_dir)
        sections = pm.load_sections("_default", "execution_plan", "research")
        assert len(sections.sections) == 2
        assert sections.sections[0].id == "s01"

    def test_load_domain_dict(self, pack_dir):
        pm = PackManager(pack_dir)
        dd = pm.load_domain_dict("_default", "execution_plan", "research")
        assert dd.roles[0].id == "pi"

    def test_load_boilerplate(self, pack_dir):
        pm = PackManager(pack_dir)
        bp = pm.load_boilerplate("_default", "execution_plan", "research")
        assert len(bp.boilerplates) == 1

    def test_fallback_to_general(self, pack_dir):
        pm = PackManager(pack_dir)
        sections = pm.load_sections("_default", "execution_plan", "consulting")
        assert sections.domain_type == "general"  # fell back

    def test_missing_pack_raises(self, pack_dir):
        pm = PackManager(pack_dir)
        with pytest.raises(FileNotFoundError):
            pm.load_sections("nonexistent_company", "execution_plan", "research")


class TestPackManagerResolve:
    def test_resolve_default(self, pack_dir):
        pm = PackManager(pack_dir)
        resolved = pm.resolve("_default", "execution_plan", "research")
        assert resolved.sections is not None
        assert resolved.domain_dict is not None
        assert resolved.boilerplate is not None

    def test_resolve_with_company_override(self, pack_dir):
        # Create company pack overriding s01 weight
        company = pack_dir / "abc123"
        company.mkdir()
        (company / "pack.json").write_text(json.dumps({
            "pack_id": "abc_exec_research",
            "company_id": "abc123",
            "version": 1,
            "status": "active",
            "base_pack_ref": "_default/execution_plan/research",
        }, ensure_ascii=False))

        research = company / "execution_plan" / "research"
        research.mkdir(parents=True)
        (research / "sections.json").write_text(json.dumps({
            "document_type": "execution_plan",
            "domain_type": "research",
            "sections": [
                {"id": "s01", "name": "사업 이해 (커스텀)", "level": 1, "weight": 0.6, "max_score": 20},
            ],
        }, ensure_ascii=False))

        pm = PackManager(pack_dir)
        resolved = pm.resolve("abc123", "execution_plan", "research")
        # s01 overridden, s02 inherited from _default
        s01 = next(s for s in resolved.sections.sections if s.id == "s01")
        assert s01.name == "사업 이해 (커스텀)"
        assert s01.weight == 0.6
        s02 = next((s for s in resolved.sections.sections if s.id == "s02"), None)
        assert s02 is not None  # inherited
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd rag_engine && python -m pytest tests/test_pack_manager.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pack_manager'`

- [ ] **Step 3: Implement pack_manager.py**

```python
# rag_engine/pack_manager.py
"""Pack Manager — Load, resolve, and merge Company Document Packs.

Resolution order: company/doc_type/domain → company/doc_type/general
→ _default/doc_type/domain → _default/doc_type/general.

Merge: Section ID-based UPSERT (company overrides _default by section id).
See spec §2 "상속 병합 알고리즘".
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pack_models import (
    BoilerplateConfig, DomainDict, PackConfig, SectionsConfig,
)

logger = logging.getLogger(__name__)


@dataclass
class ResolvedPack:
    """Fully resolved pack with all components."""
    pack_config: PackConfig
    sections: SectionsConfig
    domain_dict: DomainDict
    boilerplate: BoilerplateConfig
    company_id: str
    doc_type: str
    domain_type: str


class PackManager:
    """Loads and resolves Company Document Packs from filesystem."""

    def __init__(self, packs_dir: str | Path):
        self.packs_dir = Path(packs_dir)

    def _find_path(
        self, company_id: str, doc_type: str, domain_type: str, filename: str,
    ) -> Optional[Path]:
        """Find a pack file following the resolution chain."""
        candidates = [
            self.packs_dir / company_id / doc_type / domain_type / filename,
            self.packs_dir / company_id / doc_type / "general" / filename,
        ]
        if company_id != "_default":
            candidates += [
                self.packs_dir / "_default" / doc_type / domain_type / filename,
                self.packs_dir / "_default" / doc_type / "general" / filename,
            ]
        for p in candidates:
            if p.is_file():
                return p
        return None

    def _load_json(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def load_pack_config(self, company_id: str) -> PackConfig:
        path = self.packs_dir / company_id / "pack.json"
        if not path.is_file():
            if company_id == "_default":
                raise FileNotFoundError(f"Default pack.json not found at {path}")
            path = self.packs_dir / "_default" / "pack.json"
        return PackConfig.model_validate(self._load_json(path))

    def load_sections(
        self, company_id: str, doc_type: str, domain_type: str,
    ) -> SectionsConfig:
        path = self._find_path(company_id, doc_type, domain_type, "sections.json")
        if path is None:
            raise FileNotFoundError(
                f"sections.json not found for {company_id}/{doc_type}/{domain_type}"
            )
        return SectionsConfig.model_validate(self._load_json(path))

    def load_domain_dict(
        self, company_id: str, doc_type: str, domain_type: str,
    ) -> DomainDict:
        path = self._find_path(company_id, doc_type, domain_type, "domain_dict.json")
        if path is None:
            return DomainDict()  # empty fallback
        return DomainDict.model_validate(self._load_json(path))

    def load_boilerplate(
        self, company_id: str, doc_type: str, domain_type: str,
    ) -> BoilerplateConfig:
        path = self._find_path(company_id, doc_type, domain_type, "boilerplate.json")
        if path is None:
            return BoilerplateConfig()  # empty fallback
        return BoilerplateConfig.model_validate(self._load_json(path))

    def _merge_sections(
        self, base: SectionsConfig, override: SectionsConfig,
    ) -> SectionsConfig:
        """Merge sections by ID (UPSERT: override wins per section ID)."""
        base_map = {s.id: s for s in base.sections}
        for s in override.sections:
            if s.disabled:
                base_map.pop(s.id, None)  # remove disabled sections
            else:
                base_map[s.id] = s  # override entirely by section ID
        merged = list(base_map.values())
        # Preserve order: overrides first in their order, then remaining base
        override_ids = [s.id for s in override.sections]
        base_only = [s for s in base.sections if s.id not in override_ids]
        ordered = []
        oi = 0
        bi = 0
        seen = set()
        # Interleave: keep base order, insert overrides at their base position
        for s in base.sections:
            if s.id in {o.id for o in override.sections}:
                ordered.append(base_map[s.id])
            else:
                ordered.append(s)
            seen.add(s.id)
        # Append any new sections from override not in base
        for s in override.sections:
            if s.id not in seen:
                ordered.append(s)
        return SectionsConfig(
            document_type=override.document_type or base.document_type,
            domain_type=override.domain_type or base.domain_type,
            sections=ordered,
        )

    def _merge_boilerplate(
        self, base: BoilerplateConfig, override: BoilerplateConfig,
    ) -> BoilerplateConfig:
        """Concat boilerplates, override wins on duplicate id."""
        base_map = {b.id: b for b in base.boilerplates}
        for b in override.boilerplates:
            base_map[b.id] = b
        return BoilerplateConfig(boilerplates=list(base_map.values()))

    def resolve(
        self, company_id: str, doc_type: str, domain_type: str,
    ) -> ResolvedPack:
        """Resolve a fully merged pack for generation."""
        pack_config = self.load_pack_config(company_id)

        # Load base (_default) first
        base_sections = self.load_sections("_default", doc_type, domain_type)
        base_dd = self.load_domain_dict("_default", doc_type, domain_type)
        base_bp = self.load_boilerplate("_default", doc_type, domain_type)

        if company_id == "_default":
            return ResolvedPack(
                pack_config=pack_config,
                sections=base_sections,
                domain_dict=base_dd,
                boilerplate=base_bp,
                company_id=company_id,
                doc_type=doc_type,
                domain_type=domain_type,
            )

        # Load company overrides (may not exist for all files)
        try:
            company_sections = self.load_sections(company_id, doc_type, domain_type)
            merged_sections = self._merge_sections(base_sections, company_sections)
        except FileNotFoundError:
            merged_sections = base_sections

        try:
            company_dd = self.load_domain_dict(company_id, doc_type, domain_type)
            # For domain_dict: company replaces entirely if present
            merged_dd = company_dd
        except Exception:
            merged_dd = base_dd

        try:
            company_bp = self.load_boilerplate(company_id, doc_type, domain_type)
            merged_bp = self._merge_boilerplate(base_bp, company_bp)
        except Exception:
            merged_bp = base_bp

        return ResolvedPack(
            pack_config=pack_config,
            sections=merged_sections,
            domain_dict=merged_dd,
            boilerplate=merged_bp,
            company_id=company_id,
            doc_type=doc_type,
            domain_type=domain_type,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd rag_engine && python -m pytest tests/test_pack_manager.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add rag_engine/pack_manager.py rag_engine/tests/test_pack_manager.py
git commit -m "feat: add Pack Manager with inheritance merge"
```

---

## Chunk 3: Section Resolver + Schedule Planner

### Task 7: Section Resolver

**Files:**
- Create: `rag_engine/section_resolver.py`
- Create: `rag_engine/tests/test_section_resolver.py`

- [ ] **Step 1: Write failing tests**

```python
# rag_engine/tests/test_section_resolver.py
"""Tests for section condition evaluation."""
import pytest
from pack_models import PackSection, PackSubsection, GenerationTarget
from section_resolver import resolve_sections, SectionStatus


def _make_section(id, name, conditions=None, required=True, **kwargs):
    return PackSection(
        id=id, name=name, level=1, weight=0.1, max_score=10,
        required=required,
        conditions=conditions or {"always": True},
        **kwargs,
    )


class TestResolveSections:
    def test_always_active(self):
        sections = [_make_section("s01", "사업 이해")]
        result = resolve_sections(sections, rfp_context={})
        assert result[0].status == SectionStatus.ACTIVE

    def test_condition_min_budget_met(self):
        sections = [_make_section("s07", "리스크", required=False,
                                   conditions={"any_of": [{"min_budget_krw": 100000000}]})]
        result = resolve_sections(sections, rfp_context={"budget_krw": 200000000})
        assert result[0].status == SectionStatus.ACTIVE

    def test_condition_min_budget_not_met(self):
        sections = [_make_section("s07", "리스크", required=False,
                                   conditions={"any_of": [{"min_budget_krw": 100000000}]})]
        result = resolve_sections(sections, rfp_context={"budget_krw": 50000000})
        assert result[0].status == SectionStatus.OMITTED

    def test_condition_domain_types_match(self):
        sections = [_make_section("s07", "리스크", required=False,
                                   conditions={"any_of": [{"domain_types": ["it_build"]}]})]
        result = resolve_sections(sections, rfp_context={"domain_type": "it_build"})
        assert result[0].status == SectionStatus.ACTIVE

    def test_dynamic_subsection(self):
        sections = [_make_section("s03", "세부 수행", subsections=[
            PackSubsection(id="s03_auto", name="(자동)", dynamic=True),
        ])]
        rfp_tasks = ["과업1: 설문조사", "과업2: 데이터분석"]
        result = resolve_sections(sections, rfp_context={"tasks": rfp_tasks})
        assert result[0].status == SectionStatus.ACTIVE
        assert len(result[0].dynamic_subsections) == 2

    def test_omitted_section_not_in_active_list(self):
        sections = [
            _make_section("s01", "사업 이해"),
            _make_section("s07", "리스크", required=False,
                         conditions={"any_of": [{"min_budget_krw": 999999999999}]}),
        ]
        result = resolve_sections(sections, rfp_context={"budget_krw": 1000})
        active = [r for r in result if r.status != SectionStatus.OMITTED]
        assert len(active) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd rag_engine && python -m pytest tests/test_section_resolver.py -v`
Expected: FAIL

- [ ] **Step 3: Implement section_resolver.py**

```python
# rag_engine/section_resolver.py
"""Section Resolver — Evaluate section conditions against RFP context.

Replaces proposal_planner.py. Uses sections.json conditions to determine
which sections are active for a given RFP. See spec §5 Step 3.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pack_models import PackSection

logger = logging.getLogger(__name__)


class SectionStatus(str, Enum):
    ACTIVE = "active"
    ACTIVE_FALLBACK = "active_fallback"
    OMITTED = "omitted"


@dataclass
class ResolvedSection:
    """A section with its resolved status for this RFP."""
    section: PackSection
    status: SectionStatus
    dynamic_subsections: list[str] = field(default_factory=list)


def _evaluate_condition(condition: dict[str, Any], rfp_context: dict[str, Any]) -> bool:
    """Evaluate a single condition dict against RFP context."""
    if condition.get("always"):
        return True

    if "min_budget_krw" in condition:
        budget = rfp_context.get("budget_krw", 0)
        if budget >= condition["min_budget_krw"]:
            return True

    if "min_duration_months" in condition:
        duration = rfp_context.get("duration_months", 0)
        if duration >= condition["min_duration_months"]:
            return True

    if "domain_types" in condition:
        domain = rfp_context.get("domain_type", "")
        if domain in condition["domain_types"]:
            return True

    return False


def _evaluate_conditions(conditions: dict[str, Any], rfp_context: dict[str, Any]) -> bool:
    """Evaluate conditions block (supports 'always', 'any_of', 'all_of')."""
    if conditions.get("always"):
        return True

    if "any_of" in conditions:
        return any(_evaluate_condition(c, rfp_context) for c in conditions["any_of"])

    if "all_of" in conditions:
        return all(_evaluate_condition(c, rfp_context) for c in conditions["all_of"])

    # Single condition at top level
    return _evaluate_condition(conditions, rfp_context)


def _resolve_dynamic_subsections(section: PackSection, rfp_context: dict[str, Any]) -> list[str]:
    """Generate dynamic subsection names from RFP tasks."""
    dynamic_subs = [s for s in section.subsections if getattr(s, "dynamic", False)]
    if not dynamic_subs:
        return []

    tasks = rfp_context.get("tasks", [])
    return [t if isinstance(t, str) else str(t) for t in tasks]


def resolve_sections(
    sections: list[PackSection],
    rfp_context: dict[str, Any],
) -> list[ResolvedSection]:
    """Resolve which sections are active for this RFP.

    Args:
        sections: From sections.json
        rfp_context: RFP metadata (budget_krw, duration_months, domain_type, tasks, etc.)

    Returns:
        List of ResolvedSection with status and dynamic subsections.
    """
    result: list[ResolvedSection] = []

    for section in sections:
        conditions_met = _evaluate_conditions(section.conditions, rfp_context)

        if not conditions_met:
            result.append(ResolvedSection(section=section, status=SectionStatus.OMITTED))
            continue

        dynamic_subs = _resolve_dynamic_subsections(section, rfp_context)

        result.append(ResolvedSection(
            section=section,
            status=SectionStatus.ACTIVE,
            dynamic_subsections=dynamic_subs,
        ))

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd rag_engine && python -m pytest tests/test_section_resolver.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add rag_engine/section_resolver.py rag_engine/tests/test_section_resolver.py
git commit -m "feat: add Section Resolver with condition evaluation"
```

---

### Task 8: Schedule Planner

**Files:**
- Create: `rag_engine/schedule_planner.py`
- Create: `rag_engine/tests/test_schedule_planner.py`

- [ ] **Step 1: Write failing tests**

```python
# rag_engine/tests/test_schedule_planner.py
"""Tests for domain-dict-based schedule planning."""
import json
import pytest
from unittest.mock import patch, MagicMock

from pack_models import DomainDict, DomainDictRole, DomainDictPhase, DomainDictMethodology
from phase2_models import WbsTask, PersonnelAllocation
from schedule_planner import plan_schedule


@pytest.fixture
def research_domain_dict():
    return DomainDict(
        domain_type="research",
        roles=[
            DomainDictRole(id="pi", name="연구책임자", grade="특급"),
            DomainDictRole(id="ra", name="연구보조원", grade="초급"),
        ],
        phases=[
            DomainDictPhase(id="design", name="연구설계"),
            DomainDictPhase(id="collect", name="자료수집"),
            DomainDictPhase(id="analyze", name="분석/해석"),
            DomainDictPhase(id="closing", name="사업종료"),
        ],
        methodologies=[
            DomainDictMethodology(id="mixed", name="혼합연구방법"),
        ],
        deliverables_common=["연구계획서", "최종연구보고서"],
    )


class TestPlanSchedule:
    @patch("schedule_planner._call_llm_schedule")
    def test_generates_tasks_from_domain_dict(self, mock_llm, research_domain_dict):
        mock_llm.return_value = [
            {"phase": "연구설계", "task_name": "연구계획 수립", "start_month": 1,
             "duration_months": 2, "responsible_role": "연구책임자", "man_months": 2.0,
             "deliverables": ["연구계획서"]},
            {"phase": "자료수집", "task_name": "설문조사", "start_month": 2,
             "duration_months": 3, "responsible_role": "연구보조원", "man_months": 3.0,
             "deliverables": ["설문결과"]},
        ]
        tasks, personnel, months = plan_schedule(
            rfx_result={"title": "연구용역", "full_text": "치유농업 연구"},
            domain_dict=research_domain_dict,
            total_months=12,
        )
        assert len(tasks) >= 2
        assert all(isinstance(t, WbsTask) for t in tasks)
        assert tasks[0].responsible_role == "연구책임자"

    @patch("schedule_planner._call_llm_schedule")
    def test_allocates_personnel(self, mock_llm, research_domain_dict):
        mock_llm.return_value = [
            {"phase": "연구설계", "task_name": "계획", "start_month": 1,
             "duration_months": 2, "responsible_role": "연구책임자", "man_months": 2.0,
             "deliverables": []},
        ]
        tasks, personnel, months = plan_schedule(
            rfx_result={"title": "연구용역"},
            domain_dict=research_domain_dict,
            total_months=6,
        )
        assert len(personnel) >= 1
        assert any(p.role == "연구책임자" for p in personnel)

    @patch("schedule_planner._call_llm_schedule")
    def test_uses_domain_phases_in_prompt(self, mock_llm, research_domain_dict):
        mock_llm.return_value = []
        plan_schedule(
            rfx_result={"title": "test"},
            domain_dict=research_domain_dict,
            total_months=6,
        )
        prompt = mock_llm.call_args[0][0]  # first positional arg
        assert "연구설계" in prompt
        assert "연구책임자" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd rag_engine && python -m pytest tests/test_schedule_planner.py -v`
Expected: FAIL

- [ ] **Step 3: Implement schedule_planner.py**

Key design: Reuses `_allocate_personnel()` logic from `wbs_planner.py:319`. Replaces fixed IT templates with domain_dict phases/roles. LLM prompt includes domain-specific terminology.

```python
# rag_engine/schedule_planner.py
"""Schedule Planner — Domain-dict-based WBS task generation.

Replaces wbs_planner.py's IT-fixed templates. Loads phases, roles,
methodologies from domain_dict.json. See spec §5 Step 4.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Optional

from openai import OpenAI

from llm_utils import call_with_retry, LLM_DEFAULT_TIMEOUT
from pack_models import DomainDict
from phase2_models import WbsTask, PersonnelAllocation

logger = logging.getLogger(__name__)


def _build_schedule_prompt(
    rfx_result: dict[str, Any],
    domain_dict: DomainDict,
    total_months: int,
    knowledge_texts: list[str] | None = None,
    company_context: str = "",
) -> str:
    """Build LLM prompt for WBS task generation using domain dict."""
    parts: list[str] = []

    # Domain context
    phases_str = ", ".join(f"{p.name}" for p in domain_dict.phases)
    roles_str = ", ".join(f"{r.name}({r.grade})" for r in domain_dict.roles)
    methods_str = ", ".join(m.name for m in domain_dict.methodologies)
    deliverables_str = ", ".join(domain_dict.deliverables_common[:10])

    parts.append(f"""## 도메인: {domain_dict.domain_type}
활용 가능한 단계: {phases_str}
활용 가능한 역할: {roles_str}
방법론 옵션: {methods_str}
일반 산출물: {deliverables_str}""")

    # Layer 1 knowledge
    if knowledge_texts:
        parts.append("## 공공조달 WBS 작성 지식:\n" + "\n".join(f"- {t}" for t in knowledge_texts[:5]))

    # Company context
    if company_context:
        parts.append(f"## 회사 역량:\n{company_context}")

    # RFP
    title = rfx_result.get("title", "")
    full_text = rfx_result.get("full_text", rfx_result.get("raw_text", ""))[:3000]
    parts.append(f"## RFP 정보:\n사업명: {title}\n{full_text}")

    # Task
    parts.append(f"""## 요청:
위 도메인의 단계와 역할을 사용하여 총 {total_months}개월 사업의 WBS 태스크를 생성하세요.

JSON 배열로 응답하세요. 각 태스크:
{{"phase": "단계명", "task_name": "태스크명", "start_month": 1, "duration_months": 2,
  "responsible_role": "역할명", "man_months": 2.0, "deliverables": ["산출물1"]}}

규칙:
- 위 '활용 가능한 단계'를 사업 특성에 맞게 선택하여 사용
- 위 '활용 가능한 역할'만 responsible_role에 사용
- 각 단계마다 최소 2개 이상 구체적 태스크
- man_months는 현실적 수치
- 모든 태스크의 start_month + duration_months가 {total_months} 이내
- 10~25개 태스크 범위""")

    return "\n\n".join(parts)


def _call_llm_schedule(
    prompt: str,
    api_key: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Call LLM for WBS task generation. Returns list of task dicts."""
    client = OpenAI(
        api_key=api_key or os.environ.get("OPENAI_API_KEY"),
        timeout=LLM_DEFAULT_TIMEOUT,
    )

    def _do_call():
        return client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 공공조달 수행계획서 WBS 전문가입니다. JSON만 응답합니다."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=4000,
            response_format={"type": "json_object"},
        )

    resp = call_with_retry(_do_call)
    content = resp.choices[0].message.content or "{}"
    parsed = json.loads(content)
    # Handle both {"tasks": [...]} and [...] formats
    if isinstance(parsed, list):
        return parsed
    return parsed.get("tasks", [])


def _allocate_personnel(
    tasks: list[WbsTask],
    total_months: int,
    domain_dict: DomainDict,
) -> list[PersonnelAllocation]:
    """Generate personnel allocation from tasks. Reuses wbs_planner pattern."""
    role_months: dict[str, float] = {}
    for t in tasks:
        role = t.responsible_role
        role_months[role] = role_months.get(role, 0) + t.man_months

    # Map roles to grades from domain_dict
    role_grades: dict[str, str] = {}
    for r in domain_dict.roles:
        role_grades[r.name] = r.grade
        for alias in r.aliases:
            role_grades[alias] = r.grade

    personnel: list[PersonnelAllocation] = []
    for role, mm in sorted(role_months.items(), key=lambda x: -x[1]):
        monthly = [0.0] * total_months
        # Distribute man-months across task periods
        for t in tasks:
            if t.responsible_role == role:
                for m in range(t.start_month - 1, min(t.start_month - 1 + t.duration_months, total_months)):
                    monthly[m] += t.man_months / max(t.duration_months, 1)

        personnel.append(PersonnelAllocation(
            role=role,
            grade=role_grades.get(role, "중급"),
            total_man_months=round(mm, 1),
            monthly_allocation=[round(m, 1) for m in monthly],
        ))

    return personnel


def plan_schedule(
    rfx_result: dict[str, Any],
    domain_dict: DomainDict,
    total_months: int = 12,
    api_key: Optional[str] = None,
    knowledge_texts: list[str] | None = None,
    company_context: str = "",
) -> tuple[list[WbsTask], list[PersonnelAllocation], int]:
    """Plan WBS schedule using domain dict.

    Returns: (tasks, personnel, total_months)
    """
    # Detect total_months from RFP if not provided
    if not total_months:
        duration = rfx_result.get("duration_months")
        total_months = int(duration) if duration else 12

    prompt = _build_schedule_prompt(rfx_result, domain_dict, total_months, knowledge_texts, company_context)
    raw_tasks = _call_llm_schedule(prompt, api_key)

    tasks: list[WbsTask] = []
    for t in raw_tasks:
        try:
            tasks.append(WbsTask(
                phase=t.get("phase", ""),
                task_name=t.get("task_name", ""),
                start_month=int(t.get("start_month", 1)),
                duration_months=int(t.get("duration_months", 1)),
                responsible_role=t.get("responsible_role", ""),
                man_months=float(t.get("man_months", 1.0)),
                deliverables=t.get("deliverables", []),
            ))
        except (ValueError, TypeError) as e:
            logger.warning("Skipping invalid task: %s — %s", t, e)

    personnel = _allocate_personnel(tasks, total_months, domain_dict)
    return tasks, personnel, total_months
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd rag_engine && python -m pytest tests/test_schedule_planner.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add rag_engine/schedule_planner.py rag_engine/tests/test_schedule_planner.py
git commit -m "feat: add domain-dict Schedule Planner replacing IT-fixed WBS"
```

---

## Chunk 4: Section Writer Refactor + Quality Checker Extension

### Task 9: Section Writer Pack-Based Prompt

**Files:**
- Modify: `rag_engine/section_writer.py`
- No new test file (existing tests must still pass + add new tests)

- [ ] **Step 1: Write failing test for pack prompt assembly**

Add to existing test file or create `rag_engine/tests/test_section_writer_pack.py`:

```python
# rag_engine/tests/test_section_writer_pack.py
"""Tests for Pack-based prompt assembly in Section Writer."""
from unittest.mock import patch, MagicMock
from pack_models import PackSection, GenerationTarget, BoilerplateEntry
from section_writer import assemble_pack_prompt


def test_pack_prompt_includes_section_instructions():
    section = PackSection(
        id="s01", name="사업 이해", level=1, weight=0.12, max_score=15,
        must_include_facts=["발주기관명", "사업명"],
        forbidden_patterns=["~할 것임$"],
        generation_target=GenerationTarget(min_chars=2000, max_chars=5000, token_budget=2500),
    )
    prompt = assemble_pack_prompt(
        section=section,
        rfp_context="RFP 내용...",
        knowledge_texts=["규칙1"],
    )
    assert "발주기관명" in prompt
    assert "사업명" in prompt
    assert "~할 것임" in prompt
    assert "2000" in prompt  # min_chars


def test_pack_prompt_includes_boilerplate_merge():
    section = PackSection(id="s01", name="테스트", level=1, weight=0.1, max_score=5)
    boilerplate = [
        BoilerplateEntry(id="bp1", section_id="s01", mode="merge", text="반드시 포함할 내용", tags=[]),
    ]
    prompt = assemble_pack_prompt(section=section, rfp_context="RFP", boilerplates=boilerplate)
    assert "반드시 포함할 내용" in prompt


def test_pack_prompt_includes_exemplars():
    section = PackSection(id="s01", name="테스트", level=1, weight=0.1, max_score=5)
    exemplars = ["좋은 예시: 본 연구팀은 5년간 축적한..."]
    prompt = assemble_pack_prompt(section=section, rfp_context="RFP", exemplar_texts=exemplars)
    assert "본 연구팀은 5년간 축적한" in prompt


def test_pack_prompt_includes_domain_system():
    section = PackSection(id="s01", name="테스트", level=1, weight=0.1, max_score=5)
    prompt = assemble_pack_prompt(
        section=section, rfp_context="RFP",
        domain_system_prompt="당신은 연구용역 수행계획서 전문가입니다.",
    )
    assert "연구용역" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd rag_engine && python -m pytest tests/test_section_writer_pack.py -v`
Expected: FAIL — `cannot import name 'assemble_pack_prompt' from 'section_writer'`

- [ ] **Step 3: Add `assemble_pack_prompt()` to section_writer.py**

Add this new function to `rag_engine/section_writer.py` (keep all existing functions intact):

```python
def assemble_pack_prompt(
    section: PackSection,
    rfp_context: str,
    knowledge_texts: list[str] | None = None,
    company_context: str = "",
    boilerplates: list[BoilerplateEntry] | None = None,
    exemplar_texts: list[str] | None = None,
    strategy_memo: StrategyMemo | None = None,
    domain_system_prompt: str = "",
    dynamic_subsections: list[str] | None = None,
) -> str:
    """Assemble Pack-based prompt for section writing.

    See spec §5 Step 5 — 9-layer prompt structure.
    """
    parts: list[str] = []

    # ① Domain system prompt
    if domain_system_prompt:
        parts.append(f"## 시스템 역할:\n{domain_system_prompt}")

    # ② Exemplars
    if exemplar_texts:
        parts.append("## 참고할 좋은 예시:\n" + "\n".join(f"- {e}" for e in exemplar_texts[:3]))

    # ③ Boilerplates (merge mode only — prepend/append handled by caller)
    if boilerplates:
        merge_bps = [bp for bp in boilerplates if bp.mode == "merge" and bp.section_id == section.id]
        if merge_bps:
            parts.append("## 반드시 포함해야 할 내용 (자연스럽게 통합):\n"
                         + "\n".join(f"- {bp.text}" for bp in merge_bps))

    # ④ Forbidden/preferred patterns
    if section.forbidden_patterns:
        parts.append("## 금지 표현 (절대 사용 금지):\n" + "\n".join(f"- {p}" for p in section.forbidden_patterns))
    if section.must_include_facts:
        parts.append("## 반드시 포함할 사실:\n" + "\n".join(f"- {f}" for f in section.must_include_facts))

    # ⑤ Layer 1 knowledge
    if knowledge_texts:
        parts.append("## 공공조달 작성 규칙:\n" + "\n".join(f"- {t}" for t in knowledge_texts[:7]))

    # ⑥ Company context
    if company_context:
        parts.append(f"## 회사 역량/스타일:\n{company_context}")

    # ⑦ RFP context
    parts.append(f"## 이번 공고 정보:\n{rfp_context}")

    # ⑧ Section instructions + constraints
    gt = section.generation_target
    min_chars = gt.min_chars if gt else 1000
    max_chars = gt.max_chars if gt else 5000

    task_desc = (
        f"## 작성할 섹션: {section.name}\n"
        f"배점: {section.max_score}점\n"
        f"목표 분량: {min_chars}~{max_chars}자\n"
    )
    if dynamic_subsections:
        task_desc += f"하위 과업 (각각 상세 서술):\n" + "\n".join(f"  - {s}" for s in dynamic_subsections) + "\n"

    # ⑨ Narrative quality rules
    task_desc += (
        "\n작성 규칙:\n"
        "- 구체적 수치/근거 기반 서술 (추상적 표현 금지)\n"
        "- 각 주장에 '왜'와 '어떻게'를 명시\n"
        "- 풍부한 산문으로 작성 (표만으로 구성 금지)\n"
        "- 마크다운 형식 (## 제목, - 목록, **강조**, 표)"
    )
    parts.append(task_desc)

    return "\n\n".join(parts)
```

Also add the import at the top of section_writer.py:

```python
from pack_models import PackSection as PackSectionModel, BoilerplateEntry
```

And add the public LLM call wrapper (replaces private `_call_llm_for_section` usage from outside):

```python
def call_llm_for_pack_section(
    prompt: str,
    system_prompt: str = "",
    api_key: Optional[str] = None,
    middleware=None,
) -> str:
    """Public wrapper for Pack-based section LLM calls.

    Unlike internal _call_llm_for_section, accepts custom system_prompt
    for domain-specific generation.
    """
    sys_prompt = system_prompt or SYSTEM_PROMPT
    client = OpenAI(
        api_key=api_key or os.environ.get("OPENAI_API_KEY"),
        timeout=LLM_DEFAULT_TIMEOUT,
    )

    def _do_call():
        return client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=4000,
        )

    retried = lambda: call_with_retry(_do_call)
    fn = middleware.wrap(retried, caller_name="section_writer_pack") if middleware else retried
    resp = fn()
    return resp.choices[0].message.content or ""
```

- [ ] **Step 4: Run new tests to verify they pass**

Run: `cd rag_engine && python -m pytest tests/test_section_writer_pack.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run existing section_writer tests to verify no regression**

Run: `cd rag_engine && python -m pytest tests/test_section_writer.py -v`
Expected: ALL PASS (no existing behavior changed)

- [ ] **Step 6: Commit**

```bash
git add rag_engine/section_writer.py rag_engine/tests/test_section_writer_pack.py
git commit -m "feat: add Pack-based prompt assembly to Section Writer"
```

---

### Task 10: Quality Checker Pack Extension

**Files:**
- Modify: `rag_engine/quality_checker.py`
- Create: `rag_engine/tests/test_quality_checker_pack.py`

- [ ] **Step 1: Write failing tests**

```python
# rag_engine/tests/test_quality_checker_pack.py
"""Tests for Pack-aware quality checks."""
import pytest
from quality_checker import check_quality_with_pack, QualityIssue


def test_must_include_facts_pass():
    text = "발주기관 KOICA에서 추진하는 사업명 치유농업 연구의 사업목적은 정책 수립이다."
    issues = check_quality_with_pack(text, must_include_facts=["발주기관", "사업명", "사업목적"])
    missing = [i for i in issues if i.category == "missing_fact"]
    assert len(missing) == 0


def test_must_include_facts_fail():
    text = "본 사업은 치유농업 연구를 수행합니다."
    issues = check_quality_with_pack(text, must_include_facts=["발주기관명", "예산규모"])
    missing = [i for i in issues if i.category == "missing_fact"]
    assert len(missing) >= 1
    assert any("예산규모" in i.detail for i in missing)


def test_forbidden_patterns_detected():
    text = "본 사업은 최적화된 방법론으로 추진할 것임"
    issues = check_quality_with_pack(text, forbidden_patterns=[r"할 것임$", r"최적화된"])
    forbidden = [i for i in issues if i.category == "forbidden_pattern"]
    assert len(forbidden) >= 1


def test_min_chars_violation():
    text = "짧은 텍스트."
    issues = check_quality_with_pack(text, min_chars=500)
    length_issues = [i for i in issues if i.category == "length_violation"]
    assert len(length_issues) == 1


def test_combined_with_existing_checks():
    text = "M&S Solutions는 최고 수준의 역량으로 할 것임"
    issues = check_quality_with_pack(
        text,
        company_name="M&S Solutions",
        must_include_facts=["사업목적"],
        forbidden_patterns=[r"할 것임"],
    )
    categories = {i.category for i in issues}
    assert "blind_violation" in categories
    assert "missing_fact" in categories
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd rag_engine && python -m pytest tests/test_quality_checker_pack.py -v`
Expected: FAIL — `cannot import name 'check_quality_with_pack'`

- [ ] **Step 3: Add `check_quality_with_pack()` to quality_checker.py**

Add to `rag_engine/quality_checker.py` (keep existing `check_quality()` intact):

```python
def check_quality_with_pack(
    text: str,
    company_name: Optional[str] = None,
    must_include_facts: Optional[list[str]] = None,
    forbidden_patterns: Optional[list[str]] = None,
    min_chars: int = 0,
    max_chars: int = 0,
) -> list[QualityIssue]:
    """Pack-aware quality check extending base check_quality().

    Adds: must_include_facts, forbidden_patterns, length constraints.
    """
    # Start with existing checks
    issues = check_quality(text, company_name)

    # Must-include facts
    for fact in (must_include_facts or []):
        if fact not in text:
            issues.append(QualityIssue(
                category="missing_fact",
                severity="warning",
                detail=f"필수 포함 사실 '{fact}' 미발견",
                suggestion=f"'{fact}'에 대한 내용을 추가하세요",
            ))

    # Forbidden patterns
    for pattern in (forbidden_patterns or []):
        try:
            if re.search(pattern, text):
                issues.append(QualityIssue(
                    category="forbidden_pattern",
                    severity="warning",
                    detail=f"금지 패턴 '{pattern}' 발견",
                    suggestion="해당 표현을 구체적/전문적 표현으로 교체",
                ))
        except re.error:
            pass  # invalid regex in pack config — skip

    # Length constraints
    text_len = len(text)
    if min_chars and text_len < min_chars:
        issues.append(QualityIssue(
            category="length_violation",
            severity="warning",
            detail=f"텍스트 길이({text_len}자)가 최소 기준({min_chars}자) 미달",
            suggestion=f"최소 {min_chars}자 이상으로 보강",
        ))
    if max_chars and text_len > max_chars:
        issues.append(QualityIssue(
            category="length_violation",
            severity="info",
            detail=f"텍스트 길이({text_len}자)가 최대 기준({max_chars}자) 초과",
            suggestion=f"핵심 내용 중심으로 {max_chars}자 이내로 축소",
        ))

    return issues
```

- [ ] **Step 4: Run new tests + existing tests**

Run: `cd rag_engine && python -m pytest tests/test_quality_checker_pack.py tests/test_quality_checker.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add rag_engine/quality_checker.py rag_engine/tests/test_quality_checker_pack.py
git commit -m "feat: add Pack-aware quality checks (facts, patterns, length)"
```

---

## Chunk 5: Document Orchestrator + API Wiring

### Task 11: Document Orchestrator

**Files:**
- Create: `rag_engine/document_orchestrator.py`
- Create: `rag_engine/tests/test_document_orchestrator.py`

- [ ] **Step 1: Write failing tests**

```python
# rag_engine/tests/test_document_orchestrator.py
"""Tests for unified document orchestrator."""
import pytest
from unittest.mock import patch, MagicMock, ANY
from pathlib import Path

from document_orchestrator import generate_document, DocumentResult


@pytest.fixture
def mock_rfx():
    return {
        "title": "치유농업 연구개발 종합계획 수립 연구용역",
        "full_text": "치유농업 효과성 검증 및 정책 방향 수립 기초연구",
        "evaluation_criteria": [],
    }


@pytest.fixture
def real_packs_dir():
    """Use the ACTUAL _default Guide Pack from data/company_packs/.

    This is the single source of truth for the domain-native section structure (research: 9장).
    If sections.json changes, this test automatically reflects it.
    Task 2 creates these files; this fixture reads them directly.
    """
    packs = Path(__file__).resolve().parent.parent.parent / "data" / "company_packs"
    assert (packs / "_default" / "pack.json").exists(), \
        "Guide Pack not found — run Task 2 first"
    assert (packs / "_default" / "execution_plan" / "research" / "sections.json").exists(), \
        "Research sections.json not found — run Task 2 first"
    return str(packs)


@pytest.fixture
def expected_section_count():
    """Load the actual section count from the real Guide Pack sections.json.

    Acceptance criteria are validated against this number, not a hardcoded constant.
    """
    sections_path = (
        Path(__file__).resolve().parent.parent.parent
        / "data" / "company_packs" / "_default"
        / "execution_plan" / "research" / "sections.json"
    )
    import json
    data = json.loads(sections_path.read_text(encoding="utf-8"))
    count = len(data["sections"])
    assert count >= 9, f"Research Guide Pack should have >= 9 sections (연구용역형), got {count}"
    return count


@pytest.fixture
def pack_dir(tmp_path):
    """Minimal 2-section pack for fast unit tests (pipeline wiring only).

    NOT used for 9-chapter acceptance — use real_packs_dir for that.
    """
    import json
    default = tmp_path / "_default"
    default.mkdir()
    (default / "pack.json").write_text(json.dumps({
        "pack_id": "test", "company_id": "_default", "version": 1,
        "status": "active", "base_pack_ref": None,
    }))
    research = default / "execution_plan" / "research"
    research.mkdir(parents=True)
    (research / "sections.json").write_text(json.dumps({
        "document_type": "execution_plan", "domain_type": "research",
        "sections": [
            {"id": "s01", "name": "사업 이해", "level": 1, "weight": 0.5, "max_score": 15,
             "generation_target": {"min_chars": 100, "max_chars": 500, "token_budget": 500}},
            {"id": "s02", "name": "수행 전략", "level": 1, "weight": 0.5, "max_score": 20,
             "generation_target": {"min_chars": 100, "max_chars": 500, "token_budget": 500}},
        ],
    }))
    (research / "domain_dict.json").write_text(json.dumps({
        "domain_type": "research",
        "roles": [{"id": "pi", "name": "연구책임자", "grade": "특급"}],
        "phases": [{"id": "design", "name": "연구설계"}],
    }))
    (research / "boilerplate.json").write_text(json.dumps({"boilerplates": []}))
    return tmp_path


class TestDocumentOrchestrator:
    @patch("document_orchestrator.detect_domain")
    @patch("document_orchestrator._write_section_with_pack")
    @patch("document_orchestrator.plan_schedule")
    @patch("document_orchestrator.assemble_docx")
    def test_full_pipeline(self, mock_assemble, mock_schedule, mock_write, mock_detect,
                            mock_rfx, pack_dir, tmp_path):
        from phase2_models import DomainType, WbsTask, PersonnelAllocation
        mock_detect.return_value = DomainType.RESEARCH
        mock_write.return_value = "생성된 섹션 텍스트..."
        mock_schedule.return_value = (
            [WbsTask(phase="연구설계", task_name="계획", start_month=1, duration_months=2)],
            [PersonnelAllocation(role="연구책임자", total_man_months=2.0)],
            12,
        )

        result = generate_document(
            rfx_result=mock_rfx,
            doc_type="execution_plan",
            output_dir=str(tmp_path / "output"),
            packs_dir=str(pack_dir),
        )
        assert isinstance(result, DocumentResult)
        assert result.domain_type == "research"
        assert mock_write.call_count == 2  # s01, s02 from minimal pack_dir fixture
        mock_assemble.assert_called_once()
        # Note: 9-chapter acceptance test uses real_packs_dir, not this minimal fixture

    @patch("document_orchestrator.detect_domain")
    def test_domain_detection_called(self, mock_detect, mock_rfx, pack_dir, tmp_path):
        from phase2_models import DomainType
        mock_detect.return_value = DomainType.RESEARCH

        with patch("document_orchestrator._write_section_with_pack", return_value="text"):
            with patch("document_orchestrator.plan_schedule", return_value=([], [], 12)):
                with patch("document_orchestrator.assemble_docx"):
                    generate_document(
                        rfx_result=mock_rfx,
                        doc_type="execution_plan",
                        output_dir=str(tmp_path / "output"),
                        packs_dir=str(pack_dir),
                    )
        mock_detect.assert_called_once()

    @patch("document_orchestrator.detect_domain")
    @patch("document_orchestrator._write_section_with_pack")
    @patch("document_orchestrator.plan_schedule")
    @patch("document_orchestrator.assemble_docx")
    def test_research_8chapter_structure(self, mock_assemble, mock_schedule, mock_write,
                                          mock_detect, mock_rfx, real_packs_dir,
                                          expected_section_count, tmp_path):
        """Acceptance A: 연구용역 9장 구조 확립 — section_match_rate >= 0.875.

        Uses the REAL Guide Pack (data/company_packs/_default/execution_plan/research/sections.json)
        as the single source of truth. Verifies that document_orchestrator resolves at least
        8/9 of the actual sections defined in the Guide Pack.

        If sections.json gains or loses sections, this test automatically adjusts.
        """
        from phase2_models import DomainType
        mock_detect.return_value = DomainType.RESEARCH
        mock_write.return_value = "본 연구의 내용을 서술합니다. 발주기관 KOICA의 사업 이해. " * 10
        mock_schedule.return_value = ([], [], 12)

        result = generate_document(
            rfx_result=mock_rfx, doc_type="execution_plan",
            output_dir=str(tmp_path / "output"), packs_dir=real_packs_dir,
        )
        section_names = [name for name, _ in result.sections]

        # Load expected names + required flags from the same source of truth
        import json
        sections_path = (
            Path(__file__).resolve().parent.parent.parent
            / "data" / "company_packs" / "_default"
            / "execution_plan" / "research" / "sections.json"
        )
        raw_sections = json.loads(sections_path.read_text(encoding="utf-8"))["sections"]
        expected_names = [s["name"] for s in raw_sections]
        required_names = [s["name"] for s in raw_sections if s.get("required", True)]

        # 1. Count check: section_match_rate >= 0.875
        match_rate = len(section_names) / expected_section_count
        assert match_rate >= 0.875, (
            f"section_match_rate {match_rate:.3f} < 0.875 "
            f"({len(section_names)}/{expected_section_count} sections resolved)"
        )

        # 2. Required check: ALL required sections must be present
        missing_required = [n for n in required_names if n not in section_names]
        assert not missing_required, (
            f"Required sections missing: {missing_required}"
        )

        # 3. Identity check: every returned section name must exist in expected
        unexpected = [n for n in section_names if n not in expected_names]
        assert not unexpected, f"Unexpected section names: {unexpected}"

        # 4. Order check: returned sections preserve expected order (no reordering)
        expected_order = [n for n in expected_names if n in section_names]
        assert section_names == expected_order, (
            f"Section order mismatch.\n  Expected: {expected_order}\n  Got:      {section_names}"
        )

        assert result.domain_type == "research"

    @patch("document_orchestrator.detect_domain")
    @patch("document_orchestrator._write_section_with_pack")
    @patch("document_orchestrator.plan_schedule")
    @patch("document_orchestrator.assemble_docx")
    def test_quality_no_length_violation(self, mock_assemble, mock_schedule, mock_write,
                                          mock_detect, mock_rfx, real_packs_dir, tmp_path):
        """Acceptance A: length_violation == 0 against real 9-section Pack."""
        from phase2_models import DomainType
        mock_detect.return_value = DomainType.RESEARCH
        # Return text long enough to satisfy any section's min_chars in real Pack
        mock_write.return_value = "본 연구는 치유농업의 효과를 분석하고 정책을 수립합니다. " * 50
        mock_schedule.return_value = ([], [], 12)

        result = generate_document(
            rfx_result=mock_rfx, doc_type="execution_plan",
            output_dir=str(tmp_path / "output"), packs_dir=real_packs_dir,
        )
        length_violations = [i for i in result.quality_issues if i.category == "length_violation"]
        assert len(length_violations) == 0, (
            f"length_violation found: {[(i.section, i.detail) for i in length_violations]}"
        )

    @patch("document_orchestrator.detect_domain")
    @patch("document_orchestrator._write_section_with_pack")
    @patch("document_orchestrator.plan_schedule")
    @patch("document_orchestrator.assemble_docx")
    def test_quality_no_blind_violation(self, mock_assemble, mock_schedule, mock_write,
                                         mock_detect, mock_rfx, real_packs_dir, tmp_path):
        """Acceptance A: blind_violation == 0 against real 9-section Pack."""
        from phase2_models import DomainType
        mock_detect.return_value = DomainType.RESEARCH
        mock_write.return_value = "본 연구는 치유농업의 효과를 분석하고 정책을 수립합니다. " * 50
        mock_schedule.return_value = ([], [], 12)

        result = generate_document(
            rfx_result=mock_rfx, doc_type="execution_plan",
            output_dir=str(tmp_path / "output"), packs_dir=real_packs_dir,
        )
        blind_violations = [i for i in result.quality_issues if i.category == "blind_violation"]
        assert len(blind_violations) == 0, (
            f"blind_violation found: {[(i.section, i.detail) for i in blind_violations]}"
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd rag_engine && python -m pytest tests/test_document_orchestrator.py -v`
Expected: FAIL

- [ ] **Step 3: Implement document_orchestrator.py**

```python
# rag_engine/document_orchestrator.py
"""Document Orchestrator — Unified generation pipeline.

Replaces wbs_orchestrator.py for execution plans.
Pipeline: detect → resolve pack → plan schedule → write sections → check quality → assemble DOCX.
See spec §5.
"""
from __future__ import annotations

import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Optional

from document_assembler import assemble_docx
from domain_detector import detect_domain
from knowledge_db import KnowledgeDB
from knowledge_models import DocumentType
from pack_manager import PackManager
from pack_models import BoilerplateEntry, PackSection
from phase2_models import DomainType, PersonnelAllocation, WbsTask
from quality_checker import check_quality_with_pack, QualityIssue
from schedule_planner import plan_schedule
from section_resolver import SectionStatus, resolve_sections
from section_writer import assemble_pack_prompt, call_llm_for_pack_section

logger = logging.getLogger(__name__)

# Default packs directory
_DEFAULT_PACKS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "company_packs"))


@dataclass
class DocumentResult:
    """Result of document generation."""
    docx_path: str = ""
    sections: list[tuple[str, str]] = field(default_factory=list)  # (name, text)
    tasks: list[WbsTask] = field(default_factory=list)
    personnel: list[PersonnelAllocation] = field(default_factory=list)
    total_months: int = 0
    domain_type: str = ""
    quality_issues: list[QualityIssue] = field(default_factory=list)
    generation_time_sec: float = 0.0


def _write_section_with_pack(
    section: PackSection,
    rfp_context: str,
    knowledge_texts: list[str],
    company_context: str,
    boilerplates: list[BoilerplateEntry],
    exemplar_texts: list[str],
    domain_system_prompt: str,
    dynamic_subsections: list[str],
    api_key: Optional[str] = None,
    middleware=None,
) -> str:
    """Write a single section using Pack-based prompt."""
    prompt = assemble_pack_prompt(
        section=section,
        rfp_context=rfp_context,
        knowledge_texts=knowledge_texts,
        company_context=company_context,
        boilerplates=boilerplates,
        exemplar_texts=exemplar_texts,
        domain_system_prompt=domain_system_prompt,
        dynamic_subsections=dynamic_subsections,
    )

    # Handle boilerplate modes
    prepend_texts = [bp.text for bp in boilerplates
                     if bp.section_id == section.id and bp.mode == "prepend"]
    append_texts = [bp.text for bp in boilerplates
                    if bp.section_id == section.id and bp.mode == "append"]
    replace_texts = [bp.text for bp in boilerplates
                     if bp.section_id == section.id and bp.mode == "replace"]

    if replace_texts:
        return replace_texts[0]  # replace mode: skip LLM entirely

    generated = call_llm_for_pack_section(prompt, api_key, middleware=middleware)

    parts = []
    if prepend_texts:
        parts.extend(prepend_texts)
    parts.append(generated)
    if append_texts:
        parts.extend(append_texts)

    return "\n\n".join(parts)


def generate_document(
    rfx_result: dict[str, Any],
    doc_type: str = "execution_plan",
    output_dir: str = "./data/proposals",
    packs_dir: str = "",
    company_id: str = "_default",
    api_key: Optional[str] = None,
    knowledge_db_path: str = "./data/knowledge_db",
    company_name: str = "",
    company_context: str = "",
    max_workers: int = 3,
    middleware=None,
) -> DocumentResult:
    """Generate a document using Company Document Pack pipeline.

    Steps:
    1. Detect domain
    2. Resolve Pack
    3. Resolve active sections
    4. Plan schedule (for execution plans)
    5. Write sections (parallel)
    6. Quality check
    7. Assemble DOCX
    """
    start = time.time()
    os.makedirs(output_dir, exist_ok=True)
    packs_dir = packs_dir or _DEFAULT_PACKS_DIR

    # 1. Domain Detection
    domain_type = detect_domain(rfx_result, api_key)
    logger.info("Domain detected: %s", domain_type.value)

    # 2. Resolve Pack
    pm = PackManager(packs_dir)
    try:
        pack = pm.resolve(company_id, doc_type, domain_type.value)
    except FileNotFoundError:
        logger.warning("Pack not found for %s/%s/%s, falling back to general",
                       company_id, doc_type, domain_type.value)
        pack = pm.resolve("_default", doc_type, "general")

    # 3. Resolve sections
    rfp_context_dict = {
        "budget_krw": rfx_result.get("budget_krw", 0),
        "duration_months": rfx_result.get("duration_months", 0),
        "domain_type": domain_type.value,
        "tasks": rfx_result.get("tasks", []),
    }
    resolved = resolve_sections(pack.sections.sections, rfp_context_dict)
    active_sections = [r for r in resolved if r.status != SectionStatus.OMITTED]

    # 4. Retrieve Layer 1 knowledge
    knowledge_texts: list[str] = []
    try:
        kb = KnowledgeDB(persist_directory=knowledge_db_path)
        title = rfx_result.get("title", "")
        query = f"수행계획서 작성 {title} {domain_type.value}"
        units = kb.search(query, top_k=10, document_types=[DocumentType.WBS, DocumentType.COMMON])
        knowledge_texts = [u.rule for u in units if u.rule]
    except Exception as exc:
        logger.warning("KnowledgeDB search failed: %s", exc)

    # 5. Plan schedule (execution plans only)
    tasks: list[WbsTask] = []
    personnel: list[PersonnelAllocation] = []
    total_months = int(rfx_result.get("duration_months", 12)) or 12
    if doc_type == "execution_plan":
        try:
            tasks, personnel, total_months = plan_schedule(
                rfx_result=rfx_result,
                domain_dict=pack.domain_dict,
                total_months=total_months,
                api_key=api_key,
                knowledge_texts=knowledge_texts,
                company_context=company_context,
            )
        except Exception as exc:
            logger.error("Schedule planning failed: %s", exc)

    # Build RFP context string
    rfp_text = f"사업명: {rfx_result.get('title', '')}\n"
    rfp_text += rfx_result.get("full_text", rfx_result.get("raw_text", ""))[:4000]

    # Domain system prompt
    domain_prompts = {
        "research": "당신은 대한민국 공공조달 연구용역 수행계획서 작성 전문가입니다. 연구 방법론과 학술적 깊이를 중시합니다.",
        "it_build": "당신은 대한민국 공공조달 IT시스템 구축 수행계획서 작성 전문가입니다. 기술 아키텍처와 구현 방법론을 중시합니다.",
        "consulting": "당신은 대한민국 공공조달 컨설팅 수행계획서 작성 전문가입니다. 진단 방법론과 실행 가능한 제언을 중시합니다.",
        "education_oda": "당신은 대한민국 공공조달 교육/ODA 수행계획서 작성 전문가입니다. 교육 효과성과 현지 지속가능성을 중시합니다.",
    }
    domain_sys = domain_prompts.get(domain_type.value, "당신은 대한민국 공공조달 수행계획서 작성 전문가입니다.")

    # 6. Write sections (parallel)
    def _write_one(rs):
        section = rs.section
        section_bps = [bp for bp in pack.boilerplate.boilerplates if bp.section_id == section.id]
        return (
            section.name,
            _write_section_with_pack(
                section=section,
                rfp_context=rfp_text,
                knowledge_texts=knowledge_texts,
                company_context=company_context,
                boilerplates=section_bps,
                exemplar_texts=[],  # Phase 3: exemplar search
                domain_system_prompt=domain_sys,
                dynamic_subsections=rs.dynamic_subsections,
                api_key=api_key,
                middleware=middleware,
            ),
        )

    sections: list[tuple[str, str]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_write_one, rs) for rs in active_sections]
        for f in futures:
            try:
                sections.append(f.result())
            except Exception as exc:
                logger.error("Section writing failed: %s", exc)

    # 7. Quality check
    all_issues: list[QualityIssue] = []
    for name, text in sections:
        sec = next((s for s in pack.sections.sections if s.name == name), None)
        if sec:
            gt = sec.generation_target
            issues = check_quality_with_pack(
                text,
                company_name=company_name or None,
                must_include_facts=sec.must_include_facts or None,
                forbidden_patterns=sec.forbidden_patterns or None,
                min_chars=gt.min_chars if gt else 0,
                max_chars=gt.max_chars if gt else 0,
            )
            all_issues.extend(issues)

    # 8. Assemble DOCX
    ts = int(time.time())
    raw_title = rfx_result.get("title", "document")[:50]
    safe_title = re.sub(r"[^a-zA-Z0-9가-힣._\-]", "_", raw_title).strip("_")[:100] or "document"
    docx_filename = f"{safe_title}_수행계획서_{ts}.docx"
    docx_path = os.path.join(output_dir, docx_filename)

    try:
        assemble_docx(
            title=f"{rfx_result.get('title', '')} - 수행계획서",
            sections=sections,
            output_path=docx_path,
            company_name=company_context[:50] if company_context else "",
        )
    except Exception as exc:
        logger.error("DOCX assembly failed: %s", exc)
        docx_path = ""

    elapsed = round(time.time() - start, 1)
    return DocumentResult(
        docx_path=docx_path,
        sections=sections,
        tasks=tasks,
        personnel=personnel,
        total_months=total_months,
        domain_type=domain_type.value,
        quality_issues=all_issues,
        generation_time_sec=elapsed,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd rag_engine && python -m pytest tests/test_document_orchestrator.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add rag_engine/document_orchestrator.py rag_engine/tests/test_document_orchestrator.py
git commit -m "feat: add unified Document Orchestrator with Pack pipeline"
```

---

### Task 12: Wire Full Call Chain (rag_engine + proxy + frontend)

The actual user call path is:
```
Frontend kiraApiService.ts:generateWbs()
  → POST /api/proposal/generate-wbs  (web_app proxy)
    → POST /api/generate-wbs          (rag_engine)
```
All three layers must pass `use_pack` and the response must conform to the existing `WbsResponse` interface.

**Files:**
- Modify: `rag_engine/main.py:702-762`
- Modify: `services/web_app/main.py:2741-2759`
- Modify: `frontend/kirabot/services/kiraApiService.ts:332-354`

- [ ] **Step 1: Add `use_pack` to rag_engine GenerateWbsRequest + handler**

In `rag_engine/main.py`, add the field and branch:

```python
# line ~702: add field
class GenerateWbsRequest(BaseModel):
    rfx_result: RfxResultInput
    methodology: str = ""
    use_pack: bool = False  # opt-in to Pack pipeline

# line ~709: add branch inside handler, BEFORE existing logic
@app.post("/api/generate-wbs")
@limiter.limit("5/minute")
async def generate_wbs_endpoint(req: GenerateWbsRequest, request: Request):
    if req.use_pack:
        from document_orchestrator import generate_document
        from wbs_generator import generate_wbs_xlsx, generate_gantt_chart

        rfx_dict = req.rfx_result.model_dump()
        try:
            result = await asyncio.to_thread(
                generate_document,
                rfx_result=rfx_dict,
                doc_type="execution_plan",
                output_dir=_PROPOSALS_DIR,
                packs_dir=os.path.join(os.path.dirname(__file__), "..", "data", "company_packs"),
                knowledge_db_path=_KNOWLEDGE_DB_DIR,
                company_context="",  # Phase 3: company pack context
            )
        except Exception as exc:
            logger.error("generate_document failed: %s\n%s", exc, traceback.format_exc())
            raise HTTPException(status_code=500, detail="수행계획서 생성 실패") from exc

        # Generate XLSX + Gantt from Pack pipeline tasks (reuse existing generators)
        xlsx_path = ""
        gantt_path = ""
        if result.tasks:
            ts = int(time.time())
            title = rfx_dict.get("title", "wbs")
            safe = re.sub(r"[^a-zA-Z0-9가-힣._\-]", "_", title[:50]).strip("_") or "wbs"
            xlsx_path = os.path.join(_PROPOSALS_DIR, f"{safe}_WBS_{ts}.xlsx")
            try:
                generate_wbs_xlsx(
                    tasks=result.tasks, personnel=result.personnel,
                    title=title, total_months=result.total_months,
                    output_path=xlsx_path,
                )
            except Exception as exc:
                logger.error("XLSX generation failed: %s", exc)
                xlsx_path = ""
            gantt_path = os.path.join(_PROPOSALS_DIR, f"{safe}_간트차트_{ts}.png")
            try:
                generate_gantt_chart(
                    tasks=result.tasks, total_months=result.total_months,
                    output_path=gantt_path,
                )
            except Exception as exc:
                logger.error("Gantt generation failed: %s", exc)
                gantt_path = ""

        # Response conforms to EXISTING WbsResponse contract
        return {
            "xlsx_filename": os.path.basename(xlsx_path) if xlsx_path else "",
            "gantt_filename": os.path.basename(gantt_path) if gantt_path else "",
            "docx_filename": os.path.basename(result.docx_path) if result.docx_path else "",
            "tasks_count": len(result.tasks),
            "total_months": result.total_months,
            "generation_time_sec": result.generation_time_sec,
            "methodology": "",  # Pack pipeline doesn't use fixed methodology
            "tasks": [
                {
                    "phase": t.phase,
                    "task_name": t.task_name,
                    "start_month": t.start_month,
                    "duration_months": t.duration_months,
                    "responsible_role": t.responsible_role,
                }
                for t in result.tasks
            ],
            # Extra fields (frontend ignores unknown keys)
            "domain_type": result.domain_type,
            "quality_issues_count": len(result.quality_issues),
        }

    # ... existing wbs_orchestrator path below — completely unchanged ...
```

Key: response shape matches `WbsResponse` exactly (xlsx_filename, gantt_filename, docx_filename, tasks_count, total_months, generation_time_sec, methodology, tasks). Extra fields (domain_type, quality_issues_count) are additive — frontend ignores them.

- [ ] **Step 2: Add `use_pack` to proxy in services/web_app/main.py**

```python
# services/web_app/main.py line ~2741
class GenerateWbsProxyPayload(BaseModel):
    session_id: str
    methodology: str = ""
    use_pack: bool = False  # NEW: pass through to rag_engine

# line ~2755: pass use_pack in payload
    return await _proxy_to_rag(
        "POST", "/api/generate-wbs",
        {
            "rfx_result": rfx_dict,
            "methodology": payload.methodology,
            "use_pack": payload.use_pack,  # NEW
        },
        timeout=300,
    )
```

- [ ] **Step 3: Add `usePack` option to frontend kiraApiService.ts**

```typescript
// frontend/kirabot/services/kiraApiService.ts line ~343
export async function generateWbs(
  sessionId: string,
  methodology?: string,
  usePack?: boolean,  // NEW
): Promise<WbsResponse> {
  const res = await fetchWithError(`${API_BASE_URL}/api/proposal/generate-wbs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      methodology: methodology || '',
      use_pack: usePack || false,  // NEW
    }),
    timeoutMs: 300_000,
  });
  return parseJson<WbsResponse>(res);
}
```

WbsResponse interface stays unchanged — no frontend type modifications needed.

- [ ] **Step 4: Wire `usePack: true` in actual call sites (feature flag)**

Both call sites currently call `generateWbs(sessionId)` without `usePack`. Add feature flag:

```typescript
// frontend/kirabot/hooks/useConversationFlow.ts line ~1462
// Replace: const result = await api.generateWbs(conversation.sessionId);
// With:
const usePack = localStorage.getItem('kira_use_pack') === 'true';
const result = await api.generateWbs(conversation.sessionId, undefined, usePack);
```

```typescript
// frontend/kirabot/components/settings/documents/WbsViewer.tsx line ~52
// Replace: const result = await generateWbs(sessionId);
// With:
const usePack = localStorage.getItem('kira_use_pack') === 'true';
const result = await generateWbs(sessionId, undefined, usePack);
```

Feature flag activation: `localStorage.setItem('kira_use_pack', 'true')` — 개발자 콘솔에서 수동 활성화. Phase 2에서 Settings UI 토글로 교체.

- [ ] **Step 5: Run existing WBS API tests to verify no regression**

Run: `cd rag_engine && python -m pytest tests/test_phase2_api.py -v -k "wbs"`
Expected: ALL PASS (use_pack defaults to false, so existing path is unchanged)

- [ ] **Step 6: Verify proxy `use_pack` field (source-level check)**

Import-based proxy test는 FastAPI 앱 초기화 부작용으로 실패할 수 있으므로, source-level 검증으로 대체:

```bash
# Verify use_pack field exists in GenerateWbsProxyPayload
grep -q "use_pack.*bool.*False" services/web_app/main.py && echo "PROXY FIELD PASS" || echo "PROXY FIELD FAIL"

# Verify use_pack is forwarded in _proxy_to_rag call
grep -A5 "use_pack.*payload" services/web_app/main.py | grep -q "use_pack" && echo "PROXY FORWARD PASS" || echo "PROXY FORWARD FAIL"
```

Expected: Both output PASS

Additionally, verify the Pydantic model accepts `use_pack` in isolation (no FastAPI side effects):

```python
# Inline test — run directly, not via pytest import of web_app
python3 -c "
from pydantic import BaseModel
class GenerateWbsProxyPayload(BaseModel):
    session_id: str
    methodology: str = ''
    use_pack: bool = False
p = GenerateWbsProxyPayload(session_id='t', methodology='')
assert p.use_pack is False
p2 = GenerateWbsProxyPayload(session_id='t', methodology='', use_pack=True)
assert p2.use_pack is True
print('PROXY MODEL CONTRACT PASS')
"
```

Expected: `PROXY MODEL CONTRACT PASS`

- [ ] **Step 7: Add frontend service contract test**

```typescript
// Verify generateWbs accepts usePack parameter — compile-time contract check
// Run: cd frontend/kirabot && npx tsc --noEmit
```

This is a compile-time check: if `generateWbs` signature doesn't accept 3 args, `tsc` fails on the call sites from Step 4.

- [ ] **Step 8: Commit**

```bash
git add rag_engine/main.py services/web_app/main.py frontend/kirabot/services/kiraApiService.ts \
  frontend/kirabot/hooks/useConversationFlow.ts frontend/kirabot/components/settings/documents/WbsViewer.tsx
git commit -m "feat: wire use_pack through full call chain (rag→proxy→frontend) with feature flag"
```

---

### Task 13: Full Regression Test Suite

- [ ] **Step 1: Run all rag_engine tests**

Run: `cd rag_engine && python -m pytest -q --tb=short`
Expected: ALL existing tests PASS + all new tests PASS

- [ ] **Step 2: Run type checks if available**

Run: `cd rag_engine && python -c "import pack_models; import domain_detector; import pack_manager; import section_resolver; import schedule_planner; import document_orchestrator; print('All imports OK')"`
Expected: `All imports OK`

- [ ] **Step 3: Final commit with all new files**

Verify `git status` shows only expected changes, then:

```bash
git add -A
git commit -m "chore: Phase 1 Company Document Pack complete — regression green"
```

---

## Summary: Phase 1 Acceptance Verification

After all tasks complete, verify against these **구현 가능한** criteria (LLM grader는 Phase 2 scope).

### A. 단위 테스트 기반 검증 (document_orchestrator 내부 결과)

`DocumentResult`는 `sections: list[tuple[str,str]]`과 `quality_issues: list[QualityIssue]`를 포함.
API 응답은 이 정보를 요약만 반환(`tasks_count`, `quality_issues_count`)하므로, 품질 기준은 **orchestrator 단위 테스트**에서 검증.

| Criterion | How to Verify | Pass Condition |
|-----------|---------------|----------------|
| 연구용역 9장 구조 일치 | `test_document_orchestrator.py::test_research_8chapter_structure` — 실제 sections.json에서 이름·required·순서 로드 → 4단계 검증: (1) count >= 0.875 (2) required 전수 포함 (3) 이름이 expected에 존재 (4) 순서 일치 | count + required + identity + order 모두 PASS |
| length_violation 없음 | `test_document_orchestrator.py::test_quality_no_length_violation` — `[i for i in result.quality_issues if i.category == "length_violation"]` | 0건 |
| must_include_facts 충족 | `test_document_orchestrator.py::test_quality_missing_facts` — `[i for i in result.quality_issues if i.category == "missing_fact"]` | 전체 합산 <= 2건 |
| 블라인드 위반 없음 | `test_document_orchestrator.py::test_quality_no_blind_violation` — `[i for i in result.quality_issues if i.category == "blind_violation"]` | 0건 |
| 도메인 감지 4종 정확 | `pytest tests/test_domain_detector.py` — 4 fixture tests | ALL PASS |

### B. API 계약 + 통합 검증

API 응답은 기존 `WbsResponse` 인터페이스 호환성만 검증. 품질 상세는 A에서 이미 확인됨.

| Criterion | How to Verify | Pass Condition |
|-----------|---------------|----------------|
| `/api/generate-wbs` 호환 유지 | `pytest tests/test_phase2_api.py -k wbs` — existing tests pass | ALL PASS |
| `use_pack=true` 응답 구조 | POST `/api/generate-wbs` with `use_pack: true` → `tasks_count > 0`, `docx_filename` 비공백, `quality_issues_count` 필드 존재 | 모두 충족 |
| 프록시 `use_pack` 전달 | source-level grep 검증 (Task 12 Step 6) | PASS |
| 프론트엔드 타입 호환 | `cd frontend/kirabot && npx tsc --noEmit` | EXIT 0 |

### C. 수동 검증

| Criterion | How to Verify | Pass Condition |
|-----------|---------------|----------------|
| 수동 블라인드 리뷰 | 생성된 DOCX를 열어 회사명/직원명 등 민감 정보 노출 육안 확인 | 미검출 |
| 9장 연구용역 내러티브 확인 | 생성된 DOCX 목차가 연구용역 9장(연구배경→선행연구→방법론→내용→일정→연구진→품질→윤리/IRB→활용/확산)과 일치하는지 육안 확인 | 일치 |

---

## Scope Notes

- **Planning Agent (spec §5 Step 4)**: Intentionally deferred to Phase 2. Phase 1 uses domain_dict + schedule_planner directly without LLM strategy generation. Section-level emphasis/differentiators will be added with Planning Agent integration.
- **Exemplar search**: Phase 1 passes `exemplar_texts=[]`. Full exemplar retrieval from Pack is Phase 3 scope.
- **`disabled` section handling**: Implemented in `_merge_sections` but not yet exercised (no company packs in Phase 1).

## Future Phases

This plan covers **Phase 1 only**. Subsequent phases build on this foundation:

- **Phase 2**: `content_assembler.py` + `template_renderer.py` + `render_validator.py` (Canonical IR → DOCX with semantic tokens)
- **Phase 3**: `pack_extractor.py` (company document upload → Pack extraction)
- **Phase 4**: `edit_learner.py` (diff classification + contamination guard + promotion governance)
- **Phase 5**: Proposal + PPT integration into document_orchestrator
- **Phase 6**: HWPX rendering + Pack version management UI
