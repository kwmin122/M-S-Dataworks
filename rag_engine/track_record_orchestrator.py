"""Track Record Orchestrator — 실적/경력 기술서 생성 파이프라인.

파이프라인: select → ThreadPoolExecutor 병렬 텍스트 생성 → assemble DOCX.
proposal_orchestrator.py 구조 재사용.
"""
from __future__ import annotations

import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional

from company_db import CompanyDB
from knowledge_db import KnowledgeDB
from phase2_models import TrackRecordDocResult, TrackRecordEntry, PersonnelEntry, build_rfp_context
from track_record_writer import (
    select_track_records,
    select_personnel,
    generate_track_record_text,
    generate_personnel_text,
)
from track_record_assembler import assemble_track_record_docx

logger = logging.getLogger(__name__)


def generate_track_record_doc(
    rfx_result: dict[str, Any],
    output_dir: str = "./data/proposals",
    company_db_path: str = "./data/company_db",
    knowledge_db_path: str = "./data/knowledge_db",
    max_records: int = 10,
    max_personnel: int = 10,
    api_key: Optional[str] = None,
    max_workers: int = 3,
    company_name: Optional[str] = None,
    company_skills_dir: str = "",
) -> TrackRecordDocResult:
    """실적/경력 기술서 DOCX 생성.

    Steps:
    1. Layer 1 지식 검색 (실적기술서 관련)
    2. CompanyDB에서 실적/인력 선정
    3. 병렬 LLM 텍스트 생성 (Layer 1 지식 주입)
    4. DOCX 조립
    """
    start = time.time()
    os.makedirs(output_dir, exist_ok=True)

    # 1. Retrieve Layer 1 knowledge for track record writing
    knowledge_texts: list[str] = []
    try:
        kb = KnowledgeDB(persist_directory=knowledge_db_path)
        title = rfx_result.get("title", "")
        query = f"유사수행실적 기술서 경력기술서 작성 {title}"
        units = kb.search(query, top_k=10)
        knowledge_texts = [u.rule for u in units if u.rule]
    except Exception as exc:
        logger.warning("KnowledgeDB search failed, proceeding without Layer 1: %s", exc)

    # 1b. Load profile.md (회사 제안서 DNA)
    profile_md = ""
    if company_skills_dir:
        try:
            from company_profile_builder import load_profile_md
            profile_md = load_profile_md(company_skills_dir)
        except Exception as exc:
            logger.debug("Profile load skipped: %s", exc)

    # Initialize company DB
    db = CompanyDB(persist_directory=company_db_path)

    rfp_context = build_rfp_context(rfx_result)

    # 2. Select records and personnel
    records = select_track_records(rfx_result, db, max_records=max_records)
    personnel = select_personnel(rfx_result, db, max_personnel=max_personnel)

    if not records and not personnel:
        logger.warning("No track records or personnel found in company DB")
        # Return empty result with no file
        return TrackRecordDocResult(
            track_record_count=0,
            personnel_count=0,
            generation_time_sec=round(time.time() - start, 1),
        )

    # 3. Parallel LLM text generation (with Layer 1 knowledge)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        # Track record texts (with Layer 1 knowledge)
        tr_futures = {}
        for rec in records:
            future = pool.submit(
                generate_track_record_text,
                entry=rec,
                rfp_context=rfp_context,
                api_key=api_key,
                knowledge_texts=knowledge_texts,
                profile_md=profile_md,
            )
            tr_futures[future] = rec

        # Personnel texts (with Layer 1 knowledge)
        ps_futures = {}
        for person in personnel:
            future = pool.submit(
                generate_personnel_text,
                entry=person,
                rfp_context=rfp_context,
                api_key=api_key,
                knowledge_texts=knowledge_texts,
                profile_md=profile_md,
            )
            ps_futures[future] = person

        # Collect results
        for future in as_completed(tr_futures):
            rec = tr_futures[future]
            try:
                rec.generated_text = future.result()
            except Exception as exc:
                logger.error("Track record text generation failed for %s: %s", rec.project_name, exc)
                rec.generated_text = rec.description  # fallback to raw description

        for future in as_completed(ps_futures):
            person = ps_futures[future]
            try:
                person.generated_text = future.result()
            except Exception as exc:
                logger.error("Personnel text generation failed for %s: %s", person.name, exc)
                person.generated_text = ""

    # 4. Assemble DOCX
    ts = int(time.time())
    raw_title = rfx_result.get("title", "track_record")[:50]
    safe_title = re.sub(r"[^a-zA-Z0-9가-힣._\-]", "_", raw_title).strip("_")[:100]
    if not safe_title:
        safe_title = "track_record"
    docx_filename = f"{safe_title}_실적기술서_{ts}.docx"
    docx_path = os.path.join(output_dir, docx_filename)

    assemble_track_record_docx(
        title=f"{rfx_result.get('title', '')} - 유사수행실적 및 투입인력 기술서",
        records=records,
        personnel=personnel,
        output_path=docx_path,
        company_name=company_name or "",
    )

    elapsed = round(time.time() - start, 1)
    return TrackRecordDocResult(
        docx_path=docx_path,
        track_record_count=len(records),
        personnel_count=len(personnel),
        generation_time_sec=elapsed,
    )
