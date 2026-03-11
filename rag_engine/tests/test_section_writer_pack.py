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
