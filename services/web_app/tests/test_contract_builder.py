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
