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

    def test_company_without_domain_dict_inherits_default(self, pack_dir):
        """Company pack with sections only should inherit _default domain_dict, not get empty."""
        company = pack_dir / "comp_no_dd"
        company.mkdir()
        (company / "pack.json").write_text(json.dumps({
            "pack_id": "comp_no_dd_exec_research",
            "company_id": "comp_no_dd",
            "version": 1,
            "status": "active",
            "base_pack_ref": None,
        }, ensure_ascii=False))

        research = company / "execution_plan" / "research"
        research.mkdir(parents=True)
        # Only sections.json — no domain_dict.json, no boilerplate.json
        (research / "sections.json").write_text(json.dumps({
            "document_type": "execution_plan",
            "domain_type": "research",
            "sections": [
                {"id": "s01", "name": "커스텀 사업 이해", "level": 1, "weight": 0.5, "max_score": 15},
            ],
        }, ensure_ascii=False))

        pm = PackManager(pack_dir)
        resolved = pm.resolve("comp_no_dd", "execution_plan", "research")

        # domain_dict should be inherited from _default, not empty
        assert len(resolved.domain_dict.roles) > 0, "domain_dict.roles should not be empty"
        assert resolved.domain_dict.roles[0].id == "pi"

        # boilerplate should also be inherited from _default
        assert len(resolved.boilerplate.boilerplates) > 0, "boilerplate should not be empty"


class TestPackManagerSecurity:
    def test_path_traversal_company_id(self, pack_dir):
        pm = PackManager(pack_dir)
        with pytest.raises(ValueError, match="Invalid pack company_id"):
            pm.load_sections("../../etc", "execution_plan", "research")

    def test_path_traversal_doc_type(self, pack_dir):
        pm = PackManager(pack_dir)
        with pytest.raises(ValueError, match="Invalid pack doc_type"):
            pm.load_sections("_default", "../secret", "research")

    def test_path_traversal_domain_type(self, pack_dir):
        pm = PackManager(pack_dir)
        with pytest.raises(ValueError, match="Invalid pack domain_type"):
            pm.load_sections("_default", "execution_plan", "../../etc/passwd")

    def test_slash_in_company_id(self, pack_dir):
        pm = PackManager(pack_dir)
        with pytest.raises(ValueError):
            pm.load_pack_config("company/evil")

    def test_valid_ids_pass(self, pack_dir):
        pm = PackManager(pack_dir)
        # Should not raise — these are valid pack IDs
        pm.load_sections("_default", "execution_plan", "research")
