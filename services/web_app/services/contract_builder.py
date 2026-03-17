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
