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
from section_writer import write_section
from quality_checker import check_quality, QualityIssue
from document_assembler import assemble_docx


@dataclass
class ProposalResult:
    docx_path: str
    sections: list[tuple[str, str]]  # [(name, text)]
    outline: ProposalOutline
    quality_issues: list[QualityIssue] = field(default_factory=list)
    generation_time_sec: float = 0.0


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
) -> ProposalResult:
    """Generate a complete proposal DOCX from RFP analysis result.

    Layer 1 (범용 지식) + Layer 2 (회사 맞춤) 결합.
    company_context가 비어있으면 CompanyDB에서 자동 빌드.
    """
    start = time.time()
    os.makedirs(output_dir, exist_ok=True)

    # 0. Build company context from CompanyDB if not provided
    if not company_context:
        try:
            from company_context_builder import build_company_context
            company_context = build_company_context(rfx_result, company_db_path=company_db_path)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("Company context build skipped: %s", exc)

    # 1. Build outline
    outline = build_proposal_outline(rfx_result, total_pages)

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
            import logging
            logging.getLogger(__name__).debug("Profile load skipped: %s", exc)

    # 4. Write sections (parallel with ThreadPoolExecutor)
    def _write_one(section):
        knowledge = kb.search(
            f"{section.name} {section.evaluation_item}",
            top_k=10,
        )
        text = write_section(
            section=section,
            rfp_context=rfp_context,
            knowledge=knowledge,
            company_context=company_context,
            api_key=api_key,
            profile_md=profile_md,
        )
        return (section.name, text)

    results_map: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_write_one, s): s for s in outline.sections}
        for future in as_completed(futures):
            name, text = future.result()
            results_map[name] = text

    # Preserve original section order
    sections: list[tuple[str, str]] = []
    for s in outline.sections:
        sections.append((s.name, results_map.get(s.name, "")))

    # 5. Quality check
    all_text = "\n\n".join(text for _, text in sections)
    quality_issues = check_quality(all_text, company_name=company_name)

    # 6. Assemble DOCX
    ts = int(time.time())
    raw_title = rfx_result.get("title", "proposal")[:50]
    safe_title = re.sub(r"[^a-zA-Z0-9가-힣._\-]", "_", raw_title).strip("_")[:100]
    if not safe_title:
        safe_title = "proposal"
    docx_filename = f"{safe_title}_{ts}.docx"
    docx_path = os.path.join(output_dir, docx_filename)
    assemble_docx(
        title=rfx_result.get("title", "기술제안서"),
        sections=sections,
        output_path=docx_path,
        company_name=company_name or "",
    )

    elapsed = round(time.time() - start, 1)

    return ProposalResult(
        docx_path=docx_path,
        sections=sections,
        outline=outline,
        quality_issues=quality_issues,
        generation_time_sec=elapsed,
    )
