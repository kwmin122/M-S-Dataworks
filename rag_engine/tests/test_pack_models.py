"""Tests for Pack data models."""
import pytest
from pack_models import (
    PackSection, PackSubsection, GenerationTarget, RenderValidation,
    DomainDictRole, DomainDictPhase, DomainDict, BoilerplateEntry,
    PackConfig, SectionsConfig,
)


def test_pack_section_minimal():
    s = PackSection(id="s01", name="사업 이해", level=1, weight=0.12, max_score=15)
    assert s.required is True
    assert s.conditions == {"always": True}
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
