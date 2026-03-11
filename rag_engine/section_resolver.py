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
