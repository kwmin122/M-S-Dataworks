"""Proposal Generation Orchestrator.

Top-level orchestrator: RFxAnalysisResult + optional company context
→ builds outline → writes each section → quality checks → assembles DOCX.
"""
from __future__ import annotations

import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Optional

from knowledge_db import KnowledgeDB
from knowledge_models import ProposalOutline
from phase2_models import build_rfp_context
from proposal_planner import build_proposal_outline
from section_writer import write_section, rewrite_section
from quality_checker import check_quality, QualityIssue
from document_assembler import assemble_docx


@dataclass
class ProposalResult:
    docx_path: str = ""
    hwpx_path: str = ""
    sections: list[tuple[str, str]] = field(default_factory=list)
    outline: Optional[ProposalOutline] = None
    quality_issues: list[QualityIssue] = field(default_factory=list)
    residual_issues: list[QualityIssue] = field(default_factory=list)
    generation_time_sec: float = 0.0


def _find_hwpx_template(company_skills_dir: str) -> str:
    """Find HWPX template in company skills dir or _default fallback.

    Search order:
    1. {company_skills_dir}/templates/*.hwpx
    2. {data_dir}/company_skills/_default/templates/*.hwpx

    Returns path to first found template, or empty string.
    """
    import glob as _glob

    if company_skills_dir:
        templates_dir = os.path.join(company_skills_dir, "templates")
        templates = sorted(_glob.glob(os.path.join(templates_dir, "*.hwpx")))
        if templates:
            return templates[0]

    # Fallback to _default
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    default_templates = os.path.join(data_dir, "company_skills", "_default", "templates")
    templates = sorted(_glob.glob(os.path.join(default_templates, "*.hwpx")))
    if templates:
        return templates[0]

    return ""


def _try_hwpx_output(
    sections: list[tuple[str, str]],
    output_dir: str,
    company_skills_dir: str,
    safe_title: str,
    ts: int,
) -> str:
    """Try to produce HWPX output. Returns path on success, empty string on failure."""
    import logging
    logger = logging.getLogger(__name__)

    template_path = _find_hwpx_template(company_skills_dir)
    if not template_path:
        logger.info("No HWPX template found, falling back to DOCX")
        return ""

    try:
        from hwpx_injector import inject_content

        # Convert sections list to dict for injector
        sections_dict = {name: text for name, text in sections}

        hwpx_filename = f"{safe_title}_{ts}.hwpx"
        output_path = os.path.join(output_dir, hwpx_filename)

        inject_content(
            template_path=template_path,
            sections=sections_dict,
            output_path=output_path,
        )

        logger.info("HWPX output generated: %s", output_path)
        return output_path

    except Exception as exc:
        logger.warning("HWPX output failed, falling back to DOCX: %s", exc)
        return ""


def _write_and_check_section(
    *,
    section,
    rfp_context: str,
    knowledge: list,
    company_context: str,
    api_key,
    profile_md: str,
    company_name: str | None,
    strategy_memo=None,
    middleware=None,
) -> tuple[str, str, list[QualityIssue]]:
    """Write section, quality check, rewrite if critical issues found.

    Returns (section_name, final_text, residual_critical_issues).
    Residuals are critical issues that remain after 1 rewrite attempt.
    """
    text = write_section(
        section=section,
        rfp_context=rfp_context,
        knowledge=knowledge,
        company_context=company_context,
        api_key=api_key,
        profile_md=profile_md,
        strategy_memo=strategy_memo,
        middleware=middleware,
    )

    issues = check_quality(text, company_name=company_name)
    critical = [i for i in issues if i.severity == "critical"]

    if not critical:
        return section.name, text, []

    # One rewrite attempt for critical issues
    text = rewrite_section(
        section=section,
        rfp_context=rfp_context,
        knowledge=knowledge,
        company_context=company_context,
        api_key=api_key,
        profile_md=profile_md,
        original_text=text,
        issues=critical,
        strategy_memo=strategy_memo,
        middleware=middleware,
    )

    # Check again — residuals are logged but don't block
    remaining = check_quality(text, company_name=company_name)
    residuals = [i for i in remaining if i.severity == "critical"]

    return section.name, text, residuals


def generate_proposal(
    rfx_result: dict[str, Any],
    output_dir: str = "./data/proposals",
    knowledge_db_path: str = "./data/knowledge_db",
    company_context: str = "",
    company_name: Optional[str] = None,
    company_db_path: str = "./data/company_db",
    company_skills_dir: str = "",
    total_pages: int = 50,
    api_key: Optional[str] = None,
    max_workers: int = 3,
    output_format: str = "docx",
) -> ProposalResult:
    """Generate a complete proposal DOCX from RFP analysis result.

    Layer 1 (범용 지식) + Layer 2 (회사 맞춤) 결합.
    company_context가 비어있으면 CompanyDB에서 자동 빌드.
    """
    import logging as _log
    _logger = _log.getLogger(__name__)
    start = time.time()
    os.makedirs(output_dir, exist_ok=True)

    # 0.5. Initialize LLM middleware for observability
    from llm_middleware import LLMMiddleware
    middleware = LLMMiddleware()

    # 0. Build company context from CompanyDB if not provided
    if not company_context:
        try:
            from company_context_builder import build_company_context
            company_context = build_company_context(rfx_result, company_db_path=company_db_path)
        except Exception as exc:
            _logger.warning("Company context build skipped: %s", exc)

    # 1. Build outline
    outline = build_proposal_outline(rfx_result, total_pages)

    # 1.5. Planning Agent — generate strategy
    from knowledge_models import ProposalStrategy
    strategy = ProposalStrategy()
    try:
        from proposal_agent import ProposalPlanningAgent
        agent = ProposalPlanningAgent(api_key=api_key, middleware=middleware)
        strategy = agent.generate_strategy(
            rfx_result=rfx_result,
            outline=outline,
            company_context=company_context,
        )
        if strategy.overall_approach:
            _logger.info("Strategy: %s", strategy.overall_approach)
    except Exception as exc:
        _logger.warning("Planning agent skipped: %s", exc)

    # 2. Initialize knowledge DB (Layer 1)
    kb = KnowledgeDB(persist_directory=knowledge_db_path)

    # 3. Build RFP context string
    rfp_context = build_rfp_context(rfx_result)

    # 3.5. Load profile.md if available
    profile_md = ""
    if company_skills_dir:
        try:
            from company_profile_builder import load_profile_md
            profile_md = load_profile_md(company_skills_dir)
        except Exception as exc:
            _logger.debug("Profile load skipped: %s", exc)

    # 4. Write sections with self-correction (parallel with ThreadPoolExecutor)
    def _write_one(section):
        memo = strategy.get_memo_for(section.name)
        search_query = f"{section.name} {section.evaluation_item}"
        if memo and memo.knowledge_hints:
            search_query += " " + " ".join(memo.knowledge_hints)
        knowledge = kb.search(search_query, top_k=10)
        name, text, residuals = _write_and_check_section(
            section=section,
            rfp_context=rfp_context,
            knowledge=knowledge,
            company_context=company_context,
            api_key=api_key,
            profile_md=profile_md,
            company_name=company_name,
            strategy_memo=memo,
            middleware=middleware,
        )
        return name, text, residuals

    results_map: dict[str, str] = {}
    all_residuals: list[QualityIssue] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_write_one, s): s for s in outline.sections}
        for future in as_completed(futures):
            name, text, residuals = future.result()
            results_map[name] = text
            all_residuals.extend(residuals)

    # Preserve original section order
    sections: list[tuple[str, str]] = []
    for s in outline.sections:
        sections.append((s.name, results_map.get(s.name, "")))

    # 5. Quality check
    all_text = "\n\n".join(text for _, text in sections)
    quality_issues = check_quality(all_text, company_name=company_name)

    # 6. Assemble output
    ts = int(time.time())
    raw_title = rfx_result.get("title", "proposal")[:50]
    safe_title = re.sub(r"[^a-zA-Z0-9가-힣._\-]", "_", raw_title).strip("_")[:100]
    if not safe_title:
        safe_title = "proposal"

    hwpx_path = ""
    docx_path = ""

    if output_format == "hwpx":
        hwpx_path = _try_hwpx_output(
            sections=sections,
            output_dir=output_dir,
            company_skills_dir=company_skills_dir,
            safe_title=safe_title,
            ts=ts,
        )

    if not hwpx_path:
        # DOCX output (default or fallback)
        docx_filename = f"{safe_title}_{ts}.docx"
        docx_path = os.path.join(output_dir, docx_filename)
        assemble_docx(
            title=rfx_result.get("title", "기술제안서"),
            sections=sections,
            output_path=docx_path,
            company_name=company_name or "",
        )

    elapsed = round(time.time() - start, 1)

    # Log LLM middleware session stats
    stats = middleware.get_session_stats()
    _logger.info(
        "LLM stats: %d calls, %d tokens, $%.4f, %.0fms avg",
        stats["total_calls"],
        stats["total_tokens"],
        stats["total_cost_usd"],
        stats["avg_latency_ms"],
    )

    return ProposalResult(
        docx_path=docx_path,
        hwpx_path=hwpx_path,
        sections=sections,
        outline=outline,
        quality_issues=quality_issues,
        residual_issues=all_residuals,
        generation_time_sec=elapsed,
    )
