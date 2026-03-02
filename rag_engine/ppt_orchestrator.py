"""PPT Orchestrator — PPT 발표자료 생성 파이프라인.

파이프라인: Layer 1/2 지식 검색 → plan_slides → 콘텐츠 추출 → QnA 생성 → assemble PPTX.
proposal_orchestrator.py 구조 재사용.
"""
from __future__ import annotations

import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional

from knowledge_db import KnowledgeDB
from phase2_models import PptResult, SlideType, build_rfp_context
from ppt_slide_planner import plan_slides, generate_qna_pairs
from ppt_content_extractor import extract_slide_content
from ppt_assembler import assemble_pptx

logger = logging.getLogger(__name__)


def generate_ppt(
    rfx_result: dict[str, Any],
    output_dir: str = "./data/proposals",
    proposal_sections: Optional[list[dict[str, str]]] = None,
    gantt_path: Optional[str] = None,
    duration_min: int = 30,
    target_slide_count: int = 20,
    qna_count: int = 10,
    company_name: str = "",
    api_key: Optional[str] = None,
    max_workers: int = 3,
    knowledge_db_path: str = "./data/knowledge_db",
    company_db_path: str = "./data/company_db",
    company_skills_dir: str = "",
) -> PptResult:
    """PPT 발표자료 생성.

    Steps:
    1. Layer 1 지식 + Layer 2 회사 컨텍스트 검색
    2. plan_slides → 슬라이드 구성 (LLM + Layer 1 + Layer 2)
    3. 병렬 콘텐츠 추출 (proposal_sections 있을 때)
    4. QnA 생성 (Layer 1 + Layer 2)
    5. PPTX 조립
    """
    start = time.time()
    os.makedirs(output_dir, exist_ok=True)

    # 1. Retrieve Layer 1 knowledge for PPT
    knowledge_texts: list[str] = []
    try:
        kb = KnowledgeDB(persist_directory=knowledge_db_path)
        title = rfx_result.get("title", "")
        query = f"기술평가 PT 발표자료 작성 {title}"
        units = kb.search(query, top_k=10)
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

    # Build RFP context string
    rfp_context = build_rfp_context(rfx_result)

    # 2. Plan slides (LLM + Layer 1 + Layer 2 + Profile)
    slides = plan_slides(
        rfx_result=rfx_result,
        proposal_sections=proposal_sections,
        target_slide_count=target_slide_count,
        duration_min=duration_min,
        knowledge_texts=knowledge_texts,
        rfp_context=rfp_context,
        company_context=company_context,
        api_key=api_key,
        profile_md=profile_md,
    )

    # Inject gantt chart path into timeline slides
    if gantt_path and os.path.isfile(gantt_path):
        for slide in slides:
            if slide.slide_type == SlideType.TIMELINE:
                slide.image_path = gantt_path

    # 3. Extract content for content slides (parallel, with Layer 1 knowledge)
    if proposal_sections:
        content_slides = [
            s for s in slides
            if s.slide_type in (SlideType.CONTENT, SlideType.BULLET)
            and not s.body  # Only for slides without pre-filled body
        ]

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {}
            for slide in content_slides:
                matched_text = ""
                for sec in proposal_sections:
                    sec_name = sec.get("name", "")
                    if slide.title in sec_name or sec_name in slide.title:
                        matched_text = sec.get("text", "")
                        break

                if matched_text:
                    future = pool.submit(
                        extract_slide_content,
                        section_name=slide.title,
                        section_text=matched_text,
                        slide_type=slide.slide_type,
                        api_key=api_key,
                        knowledge_texts=knowledge_texts,
                        rfp_context=rfp_context,
                        company_context=company_context,
                    )
                    futures[future] = slide

            for future in as_completed(futures):
                orig_slide = futures[future]
                try:
                    extracted = future.result()
                    orig_slide.body = extracted.body
                    orig_slide.bullets = extracted.bullets
                    orig_slide.speaker_notes = extracted.speaker_notes
                    if extracted.table_data:
                        orig_slide.table_data = extracted.table_data
                except Exception as exc:
                    logger.error("Content extraction failed for %s: %s", orig_slide.title, exc)

    # 4. Generate QnA pairs (with Layer 1 + Layer 2 knowledge)
    qna_pairs = generate_qna_pairs(
        rfx_result=rfx_result,
        proposal_sections=proposal_sections,
        count=qna_count,
        api_key=api_key,
        knowledge_texts=knowledge_texts,
        company_context=company_context,
    )

    # 5. Assemble PPTX
    ts = int(time.time())
    raw_title = rfx_result.get("title", "ppt")[:50]
    safe_title = re.sub(r"[^a-zA-Z0-9가-힣._\-]", "_", raw_title).strip("_")[:100]
    if not safe_title:
        safe_title = "ppt"
    pptx_filename = f"{safe_title}_발표자료_{ts}.pptx"
    pptx_path = os.path.join(output_dir, pptx_filename)

    assemble_pptx(
        title=rfx_result.get("title", ""),
        slides=slides,
        qna_pairs=qna_pairs,
        output_path=pptx_path,
        company_name=company_name,
    )

    # Calculate total duration
    total_duration = sum(s.duration_sec for s in slides) / 60.0

    elapsed = round(time.time() - start, 1)
    return PptResult(
        pptx_path=pptx_path,
        slide_count=len(slides),
        qna_pairs=qna_pairs,
        total_duration_min=round(total_duration, 1),
        generation_time_sec=elapsed,
    )
