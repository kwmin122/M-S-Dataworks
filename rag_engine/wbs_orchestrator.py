"""WBS Orchestrator — 수행계획서/WBS 생성 파이프라인.

파이프라인: plan_wbs → XLSX + 간트차트 + DOCX 생성.
proposal_orchestrator.py 구조 재사용.
"""
from __future__ import annotations

import logging
import os
import re
import time
from typing import Any, Optional

from knowledge_db import KnowledgeDB
from knowledge_models import DocumentType
from phase2_models import MethodologyType, WbsResult
from wbs_planner import plan_wbs
from wbs_generator import generate_wbs_xlsx, generate_gantt_chart, generate_wbs_docx

logger = logging.getLogger(__name__)


def generate_wbs(
    rfx_result: dict[str, Any],
    output_dir: str = "./data/proposals",
    methodology: Optional[MethodologyType] = None,
    api_key: Optional[str] = None,
    knowledge_db_path: str = "./data/knowledge_db",
    company_db_path: str = "./data/company_db",
    company_skills_dir: str = "",
) -> WbsResult:
    """수행계획서/WBS 생성.

    Steps:
    1. Layer 1 지식 + Layer 2 회사 컨텍스트 검색
    2. plan_wbs → WBS 구조 + 인력 배치 (Layer 1+2 주입)
    3. XLSX (3시트) 생성
    4. 간트차트 PNG 생성
    5. 수행계획서 DOCX 생성
    """
    start = time.time()
    os.makedirs(output_dir, exist_ok=True)

    # 1. Retrieve Layer 1 knowledge for WBS
    knowledge_texts: list[str] = []
    try:
        kb = KnowledgeDB(persist_directory=knowledge_db_path)
        title = rfx_result.get("title", "")
        query = f"수행계획서 WBS 작성 {title}"
        units = kb.search(query, top_k=10, document_types=[DocumentType.WBS, DocumentType.COMMON])
        knowledge_texts = [u.rule for u in units if u.rule]
    except Exception as exc:
        logger.warning("KnowledgeDB search failed, proceeding without Layer 1: %s", exc)

    # 1b. Build Layer 2 company context
    company_context = ""
    try:
        from company_context_builder import build_company_context
        company_context = build_company_context(rfx_result, company_db_path=company_db_path)
    except Exception as exc:
        logger.warning("Company context build skipped: %s", exc)

    # 1c. Load profile.md (회사 제안서 DNA)
    profile_md = ""
    if company_skills_dir:
        try:
            from company_profile_builder import load_profile_md
            profile_md = load_profile_md(company_skills_dir)
        except Exception as exc:
            logger.debug("Profile load skipped: %s", exc)

    # 2. Plan WBS (with Layer 1 + Layer 2 + Profile)
    tasks, personnel, total_months, used_methodology = plan_wbs(
        rfx_result=rfx_result,
        methodology=methodology,
        api_key=api_key,
        knowledge_texts=knowledge_texts,
        company_context=company_context,
        profile_md=profile_md,
    )

    # File naming
    ts = int(time.time())
    raw_title = rfx_result.get("title", "wbs")[:50]
    safe_title = re.sub(r"[^a-zA-Z0-9가-힣._\-]", "_", raw_title).strip("_")[:100]
    if not safe_title:
        safe_title = "wbs"

    # 2. Generate XLSX
    xlsx_filename = f"{safe_title}_WBS_{ts}.xlsx"
    xlsx_path = os.path.join(output_dir, xlsx_filename)
    generate_wbs_xlsx(
        tasks=tasks,
        personnel=personnel,
        title=rfx_result.get("title", ""),
        total_months=total_months,
        output_path=xlsx_path,
    )

    # 3. Generate Gantt chart
    gantt_filename = f"{safe_title}_간트차트_{ts}.png"
    gantt_path = os.path.join(output_dir, gantt_filename)
    try:
        generate_gantt_chart(
            tasks=tasks,
            total_months=total_months,
            output_path=gantt_path,
        )
    except Exception as exc:
        logger.error("Gantt chart generation failed: %s", exc)
        gantt_path = ""

    # 4. Generate DOCX
    docx_filename = f"{safe_title}_수행계획서_{ts}.docx"
    docx_path = os.path.join(output_dir, docx_filename)
    generate_wbs_docx(
        tasks=tasks,
        personnel=personnel,
        title=f"{rfx_result.get('title', '')} - 수행계획서",
        total_months=total_months,
        methodology_name=used_methodology.value,
        output_path=docx_path,
        gantt_path=gantt_path if gantt_path else None,
    )

    elapsed = round(time.time() - start, 1)
    return WbsResult(
        xlsx_path=xlsx_path,
        gantt_path=gantt_path,
        docx_path=docx_path,
        tasks=tasks,
        personnel=personnel,
        total_months=total_months,
        generation_time_sec=elapsed,
    )
