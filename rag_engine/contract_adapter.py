# rag_engine/contract_adapter.py
"""Adapts GenerationContract to each orchestrator's native signature.

Strategy: Thin wrappers that unwrap the contract into existing orchestrator params.
No internal orchestrator refactoring — just bridge the interface gap.

IMPORTANT: execution_plan routes through document_orchestrator.generate_document()
(the pack-aware pipeline), NOT wbs_orchestrator.generate_wbs() (legacy).
The pack pipeline handles: domain detection → pack resolution → schedule planning →
section writing → quality check → DOCX assembly. XLSX/Gantt are generated separately
from the returned DocumentResult.tasks.
"""
from __future__ import annotations

import hashlib
import logging
import time
import tempfile
import os
from typing import Any, Callable

import httpx

from generation_contract import (
    GenerationContract, GenerationResult, OutputFile, UploadTarget,
    normalize_doc_type,
)

logger = logging.getLogger(__name__)


def _unwrap_for_proposal(
    contract: GenerationContract,
    rfx_result: dict,
    params: dict,
) -> dict:
    """Unwrap contract → proposal_orchestrator.generate_proposal kwargs."""
    return {
        "rfx_result": rfx_result,
        "company_context": contract.company_context.profile_summary,
        "company_name": params.get("company_name"),
        "total_pages": params.get("total_pages", 50),
        "output_format": params.get("output_format", "docx"),
        "template_mode": contract.mode == "strict_template",
        "api_key": params.get("api_key"),
        # Knowledge units passed as-is; orchestrator handles search internally
        # when knowledge_db_path is set. Contract pre-fetched units are future optimization.
    }


def _unwrap_for_execution_plan(
    contract: GenerationContract,
    rfx_result: dict,
    params: dict,
) -> dict:
    """Unwrap contract → document_orchestrator.generate_document kwargs.

    Routes through the pack-aware pipeline (NOT legacy wbs_orchestrator).
    document_orchestrator handles: domain detection, pack resolution, schedule planning,
    section writing, quality check, and DOCX assembly.
    """
    return {
        "rfx_result": rfx_result,
        "doc_type": "execution_plan",
        "company_name": params.get("company_name", ""),
        "company_context": contract.company_context.profile_summary,
        "company_id": params.get("company_id", "_default"),
        "api_key": params.get("api_key"),
        "knowledge_db_path": params.get("knowledge_db_path", "./data/knowledge_db"),
        "packs_dir": params.get("packs_dir", ""),
    }


def _unwrap_for_ppt(
    contract: GenerationContract,
    rfx_result: dict,
    params: dict,
) -> dict:
    """Unwrap contract → ppt_orchestrator.generate_ppt kwargs."""
    return {
        "rfx_result": rfx_result,
        "proposal_sections": params.get("proposal_sections"),
        "duration_min": params.get("duration_min", 30),
        "target_slide_count": params.get("target_slide_count", 20),
        "qna_count": params.get("qna_count", 10),
        "company_name": params.get("company_name", ""),
        "api_key": params.get("api_key"),
    }


def _unwrap_for_track_record(
    contract: GenerationContract,
    rfx_result: dict,
    params: dict,
) -> dict:
    """Unwrap contract → track_record_orchestrator.generate_track_record_doc kwargs."""
    return {
        "rfx_result": rfx_result,
        "max_records": params.get("max_records", 10),
        "max_personnel": params.get("max_personnel", 10),
        "company_name": params.get("company_name"),
        "api_key": params.get("api_key"),
    }


def upload_to_presigned_url(url: str, data: bytes, content_type: str = "application/octet-stream") -> dict:
    """Upload data to a presigned PUT URL. Returns {size_bytes, content_hash}."""
    resp = httpx.put(url, content=data, headers={"Content-Type": content_type}, timeout=120)
    resp.raise_for_status()
    return {
        "size_bytes": len(data),
        "content_hash": hashlib.sha256(data).hexdigest(),
    }


def _collect_output_files(output_dir: str, upload_targets: list[UploadTarget]) -> list[OutputFile]:
    """Upload generated files to S3 via presigned URLs, return OutputFile metadata."""
    output_files = []
    for target in upload_targets:
        # Find matching file in output_dir by asset_type extension
        ext = target.asset_type
        candidates = [f for f in os.listdir(output_dir) if f.endswith(f".{ext}")]
        if not candidates:
            logger.warning("No .%s file found in %s for asset %s", ext, output_dir, target.asset_id)
            continue
        filepath = os.path.join(output_dir, candidates[0])
        with open(filepath, "rb") as f:
            data = f.read()
        meta = upload_to_presigned_url(target.presigned_url, data, target.content_type)
        output_files.append(OutputFile(
            asset_id=target.asset_id,
            asset_type=target.asset_type,
            size_bytes=meta["size_bytes"],
            content_hash=meta["content_hash"],
        ))
    return output_files


def generate_from_contract(
    doc_type: str,
    contract: GenerationContract,
    rfx_result: dict,
    params: dict,
    upload_targets: list[UploadTarget] | None = None,
    output_dir: str | None = None,
) -> GenerationResult:
    """Unified entry point: dispatch to the correct orchestrator via contract.

    1. Normalize doc_type
    2. Unwrap contract → orchestrator kwargs
    3. Call orchestrator
    4. Run quality check
    5. Upload to presigned URLs (if provided)
    6. Return GenerationResult
    """
    doc_type = normalize_doc_type(doc_type)
    if doc_type not in DISPATCHER:
        raise ValueError(f"Unsupported doc_type: {doc_type}")

    unwrap_fn, orchestrate_fn_getter, result_mapper = DISPATCHER[doc_type]

    # Unwrap contract → kwargs
    kwargs = unwrap_fn(contract, rfx_result, params)

    # Use temp dir if no output_dir specified
    work_dir = output_dir or tempfile.mkdtemp(prefix=f"kira_{doc_type}_")
    kwargs["output_dir"] = work_dir

    # Call orchestrator — getter returns the actual function (lazy import)
    orchestrate_fn = orchestrate_fn_getter()
    start = time.time()
    raw_result = orchestrate_fn(**kwargs)
    elapsed = time.time() - start

    # Map orchestrator result → GenerationResult
    gen_result = result_mapper(raw_result, doc_type, elapsed)

    # --- Secondary outputs for execution_plan ---
    # document_orchestrator returns DOCX + tasks/personnel data.
    # XLSX (WBS table) and PNG (Gantt chart) must be generated separately
    # from the structured tasks/personnel, using wbs_generator functions.
    # This adapter is the integration layer — it bridges document_orchestrator
    # output to the full output set the spec promises.
    if doc_type == "execution_plan" and hasattr(raw_result, "tasks") and raw_result.tasks:
        from wbs_generator import generate_wbs_xlsx, generate_gantt_chart

        _title = rfx_result.get("title", "수행계획서")
        _total_months = getattr(raw_result, "total_months", 12)

        # XLSX — WBS table + personnel allocation + deliverables
        _xlsx_path = os.path.join(work_dir, f"wbs_{_title[:30]}.xlsx")
        try:
            generate_wbs_xlsx(
                raw_result.tasks, raw_result.personnel,
                _title, _total_months, _xlsx_path,
            )
        except Exception:
            logger.warning("XLSX generation failed for execution_plan", exc_info=True)

        # PNG — Gantt chart (matplotlib optional, graceful degradation)
        _gantt_path = os.path.join(work_dir, f"gantt_{_title[:30]}.png")
        try:
            generate_gantt_chart(raw_result.tasks, _total_months, _gantt_path)
        except Exception:
            logger.warning("Gantt chart generation failed (matplotlib may be unavailable)", exc_info=True)

    # Quality check
    from quality_checker import check_quality_for_doc_type
    text_for_check = _extract_text_for_quality(gen_result)
    if text_for_check:
        quality_issues = check_quality_for_doc_type(
            text_for_check,
            doc_type,
            company_name=params.get("company_name"),
            custom_forbidden=contract.quality_rules.custom_forbidden or None,
        )
        gen_result.quality_report = {
            "issues": [{"category": i.category, "severity": i.severity, "detail": i.detail} for i in quality_issues],
            "total_issues": len(quality_issues),
        }
        gen_result.quality_schema = "quality_report_v1"

    # Upload to presigned URLs
    if upload_targets:
        gen_result.output_files = _collect_output_files(work_dir, upload_targets)

    return gen_result


def _extract_text_for_quality(result: GenerationResult) -> str:
    """Extract text from content_json for quality checking."""
    cj = result.content_json
    parts = []
    for section in cj.get("sections", []):
        parts.append(section.get("text", ""))
    for task in cj.get("tasks", []):
        parts.append(task.get("name", ""))
    for slide in cj.get("slides", []):
        parts.append(slide.get("body", ""))
    for rec in cj.get("records", []):
        parts.append(rec.get("description", ""))
    return "\n".join(parts)


# --- Result mappers (orchestrator result → GenerationResult) ---

def _map_proposal_result(raw, doc_type, elapsed):
    return GenerationResult(
        doc_type=doc_type,
        content_json={"sections": [{"name": n, "text": t} for n, t in raw.sections]},
        content_schema="proposal_sections_v1",
        metadata={"docx_path": raw.docx_path},
        generation_time_sec=elapsed,
    )


def _map_execution_plan_result(raw, doc_type, elapsed):
    """Map DocumentResult (from document_orchestrator) → GenerationResult.

    DocumentResult has: docx_path, tasks (list[WbsTask]), personnel (list[PersonnelAllocation]),
    total_months, domain_type, quality_issues, sections (list[tuple[str, str]]).
    XLSX + Gantt PNG are generated earlier in generate_from_contract() from
    tasks/personnel and placed in work_dir alongside the DOCX.
    """
    return GenerationResult(
        doc_type=doc_type,
        content_json={
            "tasks": [{"id": f"T{i}", "name": t.task_name, "phase": t.phase,
                        "start_month": t.start_month,
                        "duration_months": t.duration_months,
                        "responsible_role": t.responsible_role,
                        "man_months": t.man_months,
                        "deliverables": t.deliverables}
                       for i, t in enumerate(raw.tasks, 1)],
            "personnel": [{"role": p.role, "name": p.name or "", "man_months": p.man_months}
                          for p in raw.personnel],
            "methodology": getattr(raw, "methodology", "waterfall"),
            "total_months": raw.total_months,
            "domain_type": raw.domain_type,
            "sections": [{"name": n, "text": t} for n, t in raw.sections],
        },
        content_schema="execution_plan_tasks_v1",
        metadata={"docx_path": raw.docx_path},
        generation_time_sec=elapsed,
    )


def _map_ppt_result(raw, doc_type, elapsed):
    """Map PptResult → GenerationResult with spec-compliant presentation_slides_v1.

    PptResult has: pptx_path, slide_count, qna_pairs, total_duration_min, slides_metadata.
    slides_metadata is populated by generate_ppt (see Task 4 Step 3b prerequisite).
    Spec: slides[{slide_number, type, title, body, speaker_notes}], qna_pairs, total_duration_min.
    """
    slides = []
    for i, s in enumerate(getattr(raw, "slides_metadata", []), 1):
        slides.append({
            "slide_number": i,
            "type": s.get("type", "content"),
            "title": s.get("title", ""),
            "body": s.get("body", ""),
            "speaker_notes": s.get("speaker_notes", ""),
        })
    # Fallback: if no slides_metadata, generate placeholder from count
    if not slides:
        slides = [{"slide_number": i + 1, "type": "content", "title": "", "body": "", "speaker_notes": ""}
                  for i in range(raw.slide_count)]

    return GenerationResult(
        doc_type=doc_type,
        content_json={
            "slides": slides,
            "qna_pairs": [{"question": q.question, "answer": q.answer, "category": q.category}
                          for q in raw.qna_pairs],
            "total_duration_min": raw.total_duration_min,
        },
        content_schema="presentation_slides_v1",
        metadata={"pptx_path": raw.pptx_path},
        generation_time_sec=elapsed,
    )


def _map_track_record_result(raw, doc_type, elapsed):
    """Map TrackRecordDocResult → GenerationResult with spec-compliant track_record_v1.

    TrackRecordDocResult has: docx_path, track_record_count, personnel_count,
    records_data, personnel_data (populated by generate_track_record_doc, see Task 4 Step 3b).
    Spec: records[{project_name, description, relevance_score}], personnel[{name, role, match_reason}].
    """
    records = [
        {"project_name": r.get("project_name", ""), "description": r.get("description", ""),
         "relevance_score": r.get("relevance_score", 0.0)}
        for r in getattr(raw, "records_data", [])
    ]
    personnel = [
        {"name": p.get("name", ""), "role": p.get("role", ""), "match_reason": p.get("match_reason", "")}
        for p in getattr(raw, "personnel_data", [])
    ]

    return GenerationResult(
        doc_type=doc_type,
        content_json={
            "records": records,
            "personnel": personnel,
        },
        content_schema="track_record_v1",
        metadata={"docx_path": getattr(raw, "docx_path", "")},
        generation_time_sec=elapsed,
    )


# --- Dispatcher registry ---

def _lazy_import_proposal():
    from proposal_orchestrator import generate_proposal
    return generate_proposal

def _lazy_import_execution_plan():
    from document_orchestrator import generate_document
    return generate_document

def _lazy_import_ppt():
    from ppt_orchestrator import generate_ppt
    return generate_ppt

def _lazy_import_track_record():
    from track_record_orchestrator import generate_track_record_doc
    return generate_track_record_doc


# Each entry: (unwrap_fn, orchestrate_fn_getter, result_mapper)
# Using lazy imports to avoid circular dependencies at module load time
DISPATCHER: dict[str, tuple] = {
    "proposal": (_unwrap_for_proposal, _lazy_import_proposal, _map_proposal_result),
    "execution_plan": (_unwrap_for_execution_plan, _lazy_import_execution_plan, _map_execution_plan_result),
    "presentation": (_unwrap_for_ppt, _lazy_import_ppt, _map_ppt_result),
    "track_record": (_unwrap_for_track_record, _lazy_import_track_record, _map_track_record_result),
}
