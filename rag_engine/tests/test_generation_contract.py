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
