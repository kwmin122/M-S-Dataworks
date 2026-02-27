"""Proposal Generation Orchestrator.

Top-level orchestrator: RFxAnalysisResult + optional company context
→ builds outline → writes each section → quality checks → assembles DOCX.
"""
from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Optional

from knowledge_db import KnowledgeDB
from knowledge_models import ProposalOutline
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
    total_pages: int = 50,
    api_key: Optional[str] = None,
    max_workers: int = 3,
) -> ProposalResult:
    """Generate a complete proposal DOCX from RFP analysis result.

    A-lite mode: Layer 1 knowledge only, no company DB required.
    """
    start = time.time()
    os.makedirs(output_dir, exist_ok=True)

    # 1. Build outline
    outline = build_proposal_outline(rfx_result, total_pages)

    # 2. Initialize knowledge DB (Layer 1)
    kb = KnowledgeDB(persist_directory=knowledge_db_path)

    # 3. Build RFP context string
    rfp_context_parts = [
        f"사업명: {rfx_result.get('title', '')}",
        f"발주기관: {rfx_result.get('issuing_org', '')}",
        f"사업비: {rfx_result.get('budget', '')}",
        f"사업기간: {rfx_result.get('project_period', '')}",
    ]
    if rfx_result.get("rfp_text_summary"):
        rfp_context_parts.append(f"RFP 요약: {rfx_result['rfp_text_summary']}")
    rfp_context = "\n".join(rfp_context_parts)

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
    safe_title = rfx_result.get("title", "proposal")[:30].replace("/", "_").replace(" ", "_")
    docx_filename = f"{safe_title}_{ts}.docx"
    docx_path = os.path.join(output_dir, docx_filename)
    assemble_docx(
        title=rfx_result.get("title", "기술제안서"),
        sections=sections,
        output_path=docx_path,
    )

    elapsed = round(time.time() - start, 1)

    return ProposalResult(
        docx_path=docx_path,
        sections=sections,
        outline=outline,
        quality_issues=quality_issues,
        generation_time_sec=elapsed,
    )
