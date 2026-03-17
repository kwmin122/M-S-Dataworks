"""Canonical serializer for RFxAnalysisResult → AnalysisSnapshot.analysis_json.

This shape MUST be compatible with Task 8 generate endpoint's rfx_result field
(RfxResultInput schema in rag_engine/main.py).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rfx_analyzer import RFxAnalysisResult


def serialize_analysis_for_db(analysis: RFxAnalysisResult) -> dict:
    """Convert RFxAnalysisResult to RfxResultInput-compatible JSON.

    Maps RFxAnalysisResult shape to rag_engine's RfxResultInput schema:
    - evaluation_criteria: RFxEvaluationCriteria(item, score, detail)
                        → EvaluationCriterionInput(max_score, description)
    - requirements: RFxRequirement(category, description, is_mandatory, ...)
                 → RequirementInput(category, description)

    Returns:
        Dict matching RfxResultInput schema (Task 8 generate endpoint contract)
    """
    return {
        "title": analysis.title,
        "issuing_org": analysis.issuing_org,
        "budget": analysis.budget,
        "project_period": analysis.project_period,
        "evaluation_criteria": [
            {
                "category": ec.category,
                "max_score": ec.score,
                "description": f"{ec.item}. {ec.detail}".strip(". "),
            }
            for ec in analysis.evaluation_criteria
        ],
        "requirements": [
            {
                "category": req.category,
                "description": req.description,
            }
            for req in analysis.requirements
        ],
        "rfp_text_summary": "",  # Summary is stored separately in AnalysisSnapshot.summary_md
    }
