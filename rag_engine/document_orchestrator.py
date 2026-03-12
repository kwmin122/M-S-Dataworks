"""Document Orchestrator — Unified generation pipeline.

Replaces wbs_orchestrator.py for execution plans.
Pipeline: detect -> resolve pack -> plan schedule -> write sections -> check quality -> assemble DOCX.
See spec S5.
"""
from __future__ import annotations

import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Optional

from document_assembler import assemble_docx
from domain_detector import detect_domain
from knowledge_db import KnowledgeDB
from knowledge_models import DocumentType
from pack_manager import PackManager
from pack_models import BoilerplateEntry, PackSection
from phase2_models import DomainType, PersonnelAllocation, WbsTask
from quality_checker import check_quality_with_pack, QualityIssue
from schedule_planner import plan_schedule
from section_resolver import SectionStatus, resolve_sections
from section_writer import assemble_pack_prompt, call_llm_for_pack_section

logger = logging.getLogger(__name__)

# Default packs directory
_DEFAULT_PACKS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "company_packs"))


@dataclass
class DocumentResult:
    """Result of document generation."""
    docx_path: str = ""
    sections: list[tuple[str, str]] = field(default_factory=list)  # (name, text)
    tasks: list[WbsTask] = field(default_factory=list)
    personnel: list[PersonnelAllocation] = field(default_factory=list)
    total_months: int = 0
    domain_type: str = ""
    quality_issues: list[QualityIssue] = field(default_factory=list)
    generation_time_sec: float = 0.0


def _write_section_with_pack(
    section: PackSection,
    rfp_context: str,
    knowledge_texts: list[str],
    company_context: str,
    boilerplates: list[BoilerplateEntry],
    exemplar_texts: list[str],
    domain_system_prompt: str,
    dynamic_subsections: list[str],
    api_key: Optional[str] = None,
    middleware=None,
) -> str:
    """Write a single section using Pack-based prompt."""
    # Check replace boilerplate first — skip LLM entirely if present
    replace_texts = [bp.text for bp in boilerplates
                     if bp.section_id == section.id and bp.mode == "replace"]
    if replace_texts:
        return replace_texts[0]

    prompt = assemble_pack_prompt(
        section=section,
        rfp_context=rfp_context,
        knowledge_texts=knowledge_texts,
        company_context=company_context,
        boilerplates=boilerplates,
        exemplar_texts=exemplar_texts,
        domain_system_prompt=domain_system_prompt,
        dynamic_subsections=dynamic_subsections,
    )

    generated = call_llm_for_pack_section(
        prompt, system_prompt=domain_system_prompt, api_key=api_key, middleware=middleware,
    )

    # Handle prepend/append boilerplate modes
    prepend_texts = [bp.text for bp in boilerplates
                     if bp.section_id == section.id and bp.mode == "prepend"]
    append_texts = [bp.text for bp in boilerplates
                    if bp.section_id == section.id and bp.mode == "append"]

    parts = []
    if prepend_texts:
        parts.extend(prepend_texts)
    parts.append(generated)
    if append_texts:
        parts.extend(append_texts)

    return "\n\n".join(parts)


def generate_document(
    rfx_result: dict[str, Any],
    doc_type: str = "execution_plan",
    output_dir: str = "./data/proposals",
    packs_dir: str = "",
    company_id: str = "_default",
    api_key: Optional[str] = None,
    knowledge_db_path: str = "./data/knowledge_db",
    company_name: str = "",
    company_context: str = "",
    max_workers: int = 3,
    middleware=None,
) -> DocumentResult:
    """Generate a document using Company Document Pack pipeline.

    Steps:
    1. Detect domain
    2. Resolve Pack
    3. Resolve active sections
    4. Plan schedule (for execution plans)
    5. Write sections (parallel)
    6. Quality check
    7. Assemble DOCX
    """
    start = time.time()
    os.makedirs(output_dir, exist_ok=True)
    packs_dir = packs_dir or _DEFAULT_PACKS_DIR

    # 1. Domain Detection
    domain_type = detect_domain(rfx_result, api_key)
    logger.info("Domain detected: %s", domain_type.value)

    # 2. Resolve Pack
    pm = PackManager(packs_dir)
    try:
        pack = pm.resolve(company_id, doc_type, domain_type.value)
    except FileNotFoundError:
        logger.warning("Pack not found for %s/%s/%s, falling back to general",
                       company_id, doc_type, domain_type.value)
        pack = pm.resolve("_default", doc_type, "general")

    # 3. Resolve sections
    rfp_context_dict = {
        "budget_krw": rfx_result.get("budget_krw", 0),
        "duration_months": rfx_result.get("duration_months", 0),
        "domain_type": domain_type.value,
        "tasks": rfx_result.get("tasks", []),
        "full_text": rfx_result.get("full_text", rfx_result.get("raw_text", "")),
    }
    resolved = resolve_sections(pack.sections.sections, rfp_context_dict)
    active_sections = [r for r in resolved if r.status != SectionStatus.OMITTED]

    # 4. Retrieve Layer 1 knowledge
    knowledge_texts: list[str] = []
    try:
        kb = KnowledgeDB(persist_directory=knowledge_db_path)
        title = rfx_result.get("title", "")
        query = f"수행계획서 작성 {title} {domain_type.value}"
        units = kb.search(
            query, top_k=10,
            document_types=[DocumentType.WBS, DocumentType.COMMON],
            domain_type=domain_type.value,
        )
        knowledge_texts = [u.rule for u in units if u.rule]
    except Exception as exc:
        logger.warning("KnowledgeDB search failed: %s", exc)

    # 5. Plan schedule (execution plans only)
    tasks: list[WbsTask] = []
    personnel: list[PersonnelAllocation] = []
    try:
        total_months = int(rfx_result.get("duration_months", 12)) or 12
    except (TypeError, ValueError):
        total_months = 12
    if doc_type == "execution_plan":
        try:
            tasks, personnel, total_months = plan_schedule(
                rfx_result=rfx_result,
                domain_dict=pack.domain_dict,
                total_months=total_months,
                api_key=api_key,
                knowledge_texts=knowledge_texts,
                company_context=company_context,
            )
        except Exception as exc:
            logger.error("Schedule planning failed: %s", exc)

    # Build RFP context string
    rfp_text = f"사업명: {rfx_result.get('title', '')}\n"
    rfp_text += rfx_result.get("full_text", rfx_result.get("raw_text", ""))[:4000]

    # Domain system prompt
    domain_prompts = {
        "research": "당신은 대한민국 공공조달 연구용역 수행계획서 작성 전문가입니다. 연구 방법론과 학술적 깊이를 중시합니다.",
        "it_build": "당신은 대한민국 공공조달 IT시스템 구축 수행계획서 작성 전문가입니다. 기술 아키텍처와 구현 방법론을 중시합니다.",
        "consulting": "당신은 대한민국 공공조달 컨설팅 수행계획서 작성 전문가입니다. 진단 방법론과 실행 가능한 제언을 중시합니다.",
        "education_oda": "당신은 대한민국 공공조달 교육/ODA 수행계획서 작성 전문가입니다. 교육 효과성과 현지 지속가능성을 중시합니다.",
    }
    domain_sys = domain_prompts.get(domain_type.value, "당신은 대한민국 공공조달 수행계획서 작성 전문가입니다.")

    # 6. Write sections (parallel)
    def _write_one(rs):
        section = rs.section
        section_bps = [bp for bp in pack.boilerplate.boilerplates if bp.section_id == section.id]
        return (
            section.name,
            _write_section_with_pack(
                section=section,
                rfp_context=rfp_text,
                knowledge_texts=knowledge_texts,
                company_context=company_context,
                boilerplates=section_bps,
                exemplar_texts=[],  # Phase 3: exemplar search
                domain_system_prompt=domain_sys,
                dynamic_subsections=rs.dynamic_subsections,
                api_key=api_key,
                middleware=middleware,
            ),
        )

    sections: list[tuple[str, str]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_write_one, rs) for rs in active_sections]
        for f in futures:
            try:
                sections.append(f.result())
            except Exception as exc:
                logger.error("Section writing failed: %s", exc)

    # 7. Quality check — match by active_sections index (not name) to handle overrides
    all_issues: list[QualityIssue] = []
    for i, (name, text) in enumerate(sections):
        sec = active_sections[i].section if i < len(active_sections) else None
        if sec:
            gt = sec.generation_target
            issues = check_quality_with_pack(
                text,
                company_name=company_name or None,
                must_include_facts=sec.must_include_facts or None,
                forbidden_patterns=sec.forbidden_patterns or None,
                min_chars=gt.min_chars if gt else 0,
                max_chars=gt.max_chars if gt else 0,
            )
            all_issues.extend(issues)

    # 8. Assemble DOCX
    ts = int(time.time())
    raw_title = rfx_result.get("title", "document")[:50]
    safe_title = re.sub(r"[^a-zA-Z0-9가-힣._\-]", "_", raw_title).strip("_")[:100] or "document"
    docx_filename = f"{safe_title}_수행계획서_{ts}.docx"
    docx_path = os.path.join(output_dir, docx_filename)

    try:
        assemble_docx(
            title=f"{rfx_result.get('title', '')} - 수행계획서",
            sections=sections,
            output_path=docx_path,
            company_name=company_context[:50] if company_context else "",
        )
    except Exception as exc:
        logger.error("DOCX assembly failed: %s", exc)
        docx_path = ""

    elapsed = round(time.time() - start, 1)
    return DocumentResult(
        docx_path=docx_path,
        sections=sections,
        tasks=tasks,
        personnel=personnel,
        total_months=total_months,
        domain_type=domain_type.value,
        quality_issues=all_issues,
        generation_time_sec=elapsed,
    )
