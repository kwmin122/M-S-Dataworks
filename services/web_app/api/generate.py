"""Document generation API router.

POST /api/projects/{project_id}/generate - Unified document generation endpoint
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, UTC, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.web_app.db.engine import get_async_session
from services.web_app.db.models.base import new_cuid
from services.web_app.db.models.project import BidProject, AnalysisSnapshot
from services.web_app.db.models.company import CompanyProfile
from services.web_app.db.models.document import DocumentRun, DocumentRevision, DocumentAsset
from services.web_app.api.deps import CurrentUser, resolve_org_membership, require_project_access
from services.web_app.services import generation_service
from services.web_app.services.contract_builder import build_generation_contract
from services.web_app.storage.s3 import get_s3_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["generate"])


class GenerateDocumentProjectRequest(BaseModel):
    """Request to generate a document for a project.

    Phase 1 scope: proposal only.
    """
    doc_type: str = Field(pattern=r"^(proposal)$")
    analysis_snapshot_id: str | None = None
    params: dict = Field(default_factory=dict)


class OutputFileMetadata(BaseModel):
    """Metadata for a generated output file."""
    asset_id: str
    asset_type: str
    size_bytes: int
    download_url: str


class GenerateDocumentProjectResponse(BaseModel):
    """Response from document generation."""
    run_id: str
    revision_id: str
    doc_type: str
    status: str
    output_files: list[OutputFileMetadata]
    generation_time_sec: float
    quality_report: dict | None = None


async def _call_rag_engine_generate(
    *,
    db: AsyncSession,
    snapshot: AnalysisSnapshot,
    contract: dict,
    doc_type: str,
    params: dict,
    upload_targets: list[dict],
) -> dict:
    """Call rag_engine /api/generate-document endpoint.

    Args:
        db: Database session (unused here but matches pattern)
        snapshot: AnalysisSnapshot with analysis_json
        contract: GenerationContract dict (from build_generation_contract)
        doc_type: Document type (proposal, execution_plan, etc.)
        params: Additional generation parameters
        upload_targets: Pre-created assets with presigned URLs

    Returns:
        Response dict with output_files, content_json, etc.

    Raises:
        asyncio.TimeoutError: If rag_engine times out
        Exception: For other rag_engine errors
    """
    rag_engine_url = os.getenv("FASTAPI_URL", "http://localhost:8001")
    endpoint = f"{rag_engine_url}/api/generate-document"

    payload = {
        "doc_type": doc_type,
        "rfx_result": snapshot.analysis_json,
        "contract": contract,
        "params": params,
        "upload_targets": upload_targets,
    }

    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.post(endpoint, json=payload)
        response.raise_for_status()
        return response.json()


@router.post("/{project_id}/generate", response_model=GenerateDocumentProjectResponse)
async def generate_document(
    project_id: str,
    request: GenerateDocumentProjectRequest,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """Generate a document for a project.

    Phase 1 scope: proposal only.

    Requires "editor" access to the project.

    Flow:
    1. ACL check (require_project_access)
    2. Load contract data (project, snapshot, company profile)
    3. Create DocumentRun (queued)
    4. Pre-create DocumentAssets (presigned_issued)
    5. Start DocumentRun (running)
    6. Call rag_engine /api/generate-document
    7. On success: complete_document_run + return response
    8. On failure: fail_document_run + raise 502/504
    """
    # 1. ACL check - verify project access and org membership
    await require_project_access(project_id, "editor", user, db)

    # 2. Load project (already verified by ACL)
    proj_result = await db.execute(
        select(BidProject).where(BidProject.id == project_id)
    )
    project = proj_result.scalar_one()

    # 3. Determine analysis_snapshot_id
    snapshot_id = request.analysis_snapshot_id or project.active_analysis_snapshot_id
    if not snapshot_id:
        raise HTTPException(
            status_code=400,
            detail="분석 스냅샷이 없습니다. 먼저 공고를 분석해주세요."
        )

    # 4. Load snapshot + verify it belongs to this project (anti-IDOR)
    snap_result = await db.execute(
        select(AnalysisSnapshot).where(
            AnalysisSnapshot.id == snapshot_id,
            AnalysisSnapshot.project_id == project_id,
        )
    )
    snapshot = snap_result.scalar_one_or_none()
    if not snapshot:
        # 404 for anti-enumeration (same as ACL deny)
        raise HTTPException(status_code=404, detail="분석 스냅샷을 찾을 수 없습니다")

    # 5. Load CompanyProfile (optional)
    profile_result = await db.execute(
        select(CompanyProfile).where(CompanyProfile.org_id == user.org_id)
    )
    profile = profile_result.scalar_one_or_none()

    # 6. Build GenerationContract
    company_profile_dict = None
    writing_style = None
    company_name = None
    if profile:
        company_profile_dict = {
            "business_type": profile.business_type,
            "headcount": profile.headcount,
            "capital": profile.capital,
            "licenses": profile.licenses,
            "certifications": profile.certifications,
        }
        writing_style = profile.writing_style
        company_name = profile.company_name

    contract = build_generation_contract(
        org_id=user.org_id,
        company_profile=company_profile_dict,
        writing_style=writing_style,
        company_name=company_name,
        mode="starter",
    )

    # 7. Create DocumentRun (queued)
    run = await generation_service.create_document_run(
        db=db,
        org_id=user.org_id,
        project_id=project_id,
        doc_type=request.doc_type,
        created_by=user.username,
        analysis_snapshot_id=snapshot_id,
        params=request.params,
    )
    await db.commit()

    # Track asset IDs for cleanup on failure
    asset_ids: list[str] = []

    try:
        # 8. Pre-create DocumentAssets with presigned URLs
        # (Phase 1: proposal only, single DOCX output)
        s3_client = get_s3_client()
        asset_id = new_cuid()
        asset_ids.append(asset_id)

        key = f"documents/{user.org_id}/{project_id}/{run.id}/{asset_id}.docx"
        presigned_url = s3_client.generate_presigned_upload_url(
            key=key,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            expires_in=3600,
        )

        asset = DocumentAsset(
            id=asset_id,
            org_id=user.org_id,
            project_id=project_id,
            asset_type="docx",
            storage_uri=s3_client.build_full_uri(key),
            upload_status="presigned_issued",
        )
        db.add(asset)
        await db.flush()
        await db.commit()

        # Build upload_targets for rag_engine (UploadTarget contract)
        upload_targets = [{
            "asset_id": asset_id,
            "asset_type": "docx",
            "presigned_url": presigned_url,
            "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }]

        # 9. Start DocumentRun (running)
        await generation_service.start_document_run(db=db, run=run)
        await db.commit()

        # 10. Call rag_engine
        rag_response = await _call_rag_engine_generate(
            db=db,
            snapshot=snapshot,
            contract=contract,
            doc_type=request.doc_type,
            params=request.params,
            upload_targets=upload_targets,
        )

        # 11. Complete DocumentRun
        revision = await generation_service.complete_document_run(
            db=db,
            run=run,
            content_json=rag_response.get("content_json", {}),
            content_schema=rag_response.get("content_schema", ""),
            quality_report=rag_response.get("quality_report"),
            output_files=rag_response.get("output_files", []),
        )
        await db.commit()

        # 12. Build response
        output_files = []
        for f in rag_response.get("output_files", []):
            asset_id_resp = f.get("asset_id")
            if asset_id_resp:
                # Generate download URL
                download_url = f"/api/assets/{asset_id_resp}/download"
                output_files.append(OutputFileMetadata(
                    asset_id=asset_id_resp,
                    asset_type=f.get("asset_type", "docx"),
                    size_bytes=f.get("size_bytes", 0),
                    download_url=download_url,
                ))

        return GenerateDocumentProjectResponse(
            run_id=run.id,
            revision_id=revision.id,
            doc_type=request.doc_type,
            status="completed",
            output_files=output_files,
            generation_time_sec=rag_response.get("generation_time_sec", 0.0),
            quality_report=rag_response.get("quality_report"),
        )

    except asyncio.TimeoutError as e:
        # rag_engine timeout → 504
        await generation_service.fail_document_run(
            db=db,
            run=run,
            error=f"rag_engine timeout: {str(e)}",
        )
        # Mark orphan assets as failed
        await _cleanup_failed_assets(db, asset_ids)
        await db.commit()
        raise HTTPException(status_code=504, detail="문서 생성 타임아웃")

    except Exception as e:
        # rag_engine error → 502
        logger.exception("rag_engine error during generation")
        await generation_service.fail_document_run(
            db=db,
            run=run,
            error=str(e),
        )
        # Mark orphan assets as failed
        await _cleanup_failed_assets(db, asset_ids)
        await db.commit()
        raise HTTPException(status_code=502, detail=f"문서 생성 실패: {str(e)}")


async def _cleanup_failed_assets(db: AsyncSession, asset_ids: list[str]) -> None:
    """Mark pre-created assets as failed on generation error."""
    for aid in asset_ids:
        asset_result = await db.execute(
            select(DocumentAsset).where(DocumentAsset.id == aid)
        )
        asset_obj = asset_result.scalar_one_or_none()
        if asset_obj:
            asset_obj.upload_status = "failed"
