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
    with pytest.raises(ValueError, match="Unknown doc_type"):
        generate_from_contract("invalid", contract, {}, {})
