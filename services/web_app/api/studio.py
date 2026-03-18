"""Studio project control plane — CRUD + snapshot clone + analyze + classify."""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.web_app.db.engine import get_async_session
from services.web_app.db.models.base import new_cuid
from services.web_app.db.models.project import BidProject, ProjectAccess, AnalysisSnapshot
from services.web_app.db.models.studio import ProjectPackageItem
from services.web_app.db.models.audit import AuditLog
from services.web_app.api.deps import CurrentUser, resolve_org_membership, require_project_access
from services.web_app.services.package_classifier import classify_and_build

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/studio", tags=["studio"])


# --- Request / Response schemas ---

class CreateStudioProjectRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    from_analysis_snapshot_id: str | None = None
    rfp_source_type: Literal['upload', 'nara_search', 'manual'] | None = None
    rfp_source_ref: str | None = None


class StudioProjectResponse(BaseModel):
    id: str
    title: str
    status: str
    project_type: str
    studio_stage: str | None
    pinned_style_skill_id: str | None
    active_analysis_snapshot_id: str | None
    rfp_source_type: str | None
    rfp_source_ref: str | None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class UpdateStudioStageRequest(BaseModel):
    studio_stage: str = Field(pattern="^(rfp|package|company|style|generate|review|relearn)$")


class AnalyzeRfpTextRequest(BaseModel):
    document_text: str = Field(min_length=50, max_length=200_000)


class PackageItemResponse(BaseModel):
    id: str
    package_category: str
    document_code: str
    document_label: str
    required: bool
    status: str
    generation_target: str | None
    sort_order: int

    class Config:
        from_attributes = True


class ClassifyResponse(BaseModel):
    procurement_domain: str
    contract_method: str
    confidence: float
    detection_method: str
    package_items: list[PackageItemResponse]


# --- Endpoints ---

@router.post("/projects", response_model=StudioProjectResponse, status_code=201)
async def create_studio_project(
    req: CreateStudioProjectRequest,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """Create a new Studio project. Optionally clone an existing analysis snapshot."""
    project = BidProject(
        org_id=user.org_id,
        created_by=user.username,
        title=req.title,
        status="draft",
        project_type="studio",
        studio_stage="rfp",
        rfp_source_type=req.rfp_source_type,
        rfp_source_ref=req.rfp_source_ref,
    )
    db.add(project)
    await db.flush()

    # Creator gets owner access (matches projects.py pattern)
    db.add(ProjectAccess(
        project_id=project.id,
        user_id=user.username,
        access_level="owner",
    ))

    # Audit log
    db.add(AuditLog(
        org_id=user.org_id,
        user_id=user.username,
        project_id=project.id,
        action="studio_project_created",
        target_type="bid_project",
        target_id=project.id,
    ))

    # Clone analysis snapshot if provided
    if req.from_analysis_snapshot_id:
        source_snap = await _get_snapshot_for_clone(
            db, req.from_analysis_snapshot_id, user.org_id
        )
        cloned = AnalysisSnapshot(
            id=new_cuid(),
            org_id=user.org_id,
            project_id=project.id,
            version=1,
            analysis_json=source_snap.analysis_json,
            analysis_schema=source_snap.analysis_schema,
            summary_md=source_snap.summary_md,
            go_nogo_result_json=source_snap.go_nogo_result_json,
            is_active=True,
            created_by=user.username,
        )
        db.add(cloned)
        await db.flush()
        project.active_analysis_snapshot_id = cloned.id

    await db.commit()
    await db.refresh(project)

    return _project_to_response(project)


@router.get("/projects", response_model=list[StudioProjectResponse])
async def list_studio_projects(
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """List Studio projects visible to the current user.

    Org owner/admin: see all org Studio projects.
    Other roles: only projects with a ProjectAccess row.
    """
    if user.role in ("owner", "admin"):
        stmt = (
            select(BidProject)
            .where(
                BidProject.org_id == user.org_id,
                BidProject.project_type == "studio",
            )
            .order_by(BidProject.created_at.desc())
        )
    else:
        stmt = (
            select(BidProject)
            .join(ProjectAccess, ProjectAccess.project_id == BidProject.id)
            .where(
                BidProject.org_id == user.org_id,
                BidProject.project_type == "studio",
                ProjectAccess.user_id == user.username,
            )
            .order_by(BidProject.created_at.desc())
        )
    result = await db.execute(stmt)
    projects = result.scalars().all()
    return [_project_to_response(p) for p in projects]


@router.get("/projects/{project_id}", response_model=StudioProjectResponse)
async def get_studio_project(
    project_id: str,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """Get a single Studio project."""
    await require_project_access(project_id, "viewer", user, db)
    result = await db.execute(
        select(BidProject).where(
            BidProject.id == project_id,
            BidProject.project_type == "studio",
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Studio 프로젝트를 찾을 수 없습니다")
    return _project_to_response(project)


@router.patch("/projects/{project_id}/stage", response_model=StudioProjectResponse)
async def update_studio_stage(
    project_id: str,
    req: UpdateStudioStageRequest,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """Update the current studio stage for a project."""
    await require_project_access(project_id, "editor", user, db)
    result = await db.execute(
        select(BidProject).where(
            BidProject.id == project_id,
            BidProject.project_type == "studio",
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Studio 프로젝트를 찾을 수 없습니다")

    project.studio_stage = req.studio_stage
    await db.commit()
    await db.refresh(project)
    return _project_to_response(project)


@router.post("/projects/{project_id}/analyze")
async def analyze_rfp_text(
    project_id: str,
    req: AnalyzeRfpTextRequest,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """Analyze RFP text and create an AnalysisSnapshot for the project.

    Uses rfx_analyzer (multipass extraction) + generate_rfp_summary (5-section GFM).
    Stores result as active snapshot on the project.
    """
    await require_project_access(project_id, "editor", user, db)

    result = await db.execute(
        select(BidProject).where(
            BidProject.id == project_id,
            BidProject.project_type == "studio",
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Studio 프로젝트를 찾을 수 없습니다")

    # Run rfx_analyzer + summary in thread (blocking LLM calls)
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise HTTPException(500, "OPENAI_API_KEY가 설정되지 않았습니다")

    from rfx_analyzer import RFxAnalyzer
    from services.web_app.api.analysis_serializer import serialize_analysis_for_db

    analyzer = RFxAnalyzer(
        api_key=api_key,
        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
    )

    analysis = await asyncio.to_thread(analyzer.analyze_text, req.document_text)

    # Generate 5-section summary
    summary_md = ""
    try:
        from rfx_analyzer import generate_rfp_summary
        summary_md = await asyncio.to_thread(
            generate_rfp_summary, analysis, api_key,
        )
    except Exception as exc:
        logger.warning("RFP summary generation failed (non-fatal): %s", exc)

    # Serialize and store snapshot
    analysis_json = serialize_analysis_for_db(analysis)

    # Deactivate existing active snapshots
    existing = await db.execute(
        select(AnalysisSnapshot).where(
            AnalysisSnapshot.project_id == project_id,
            AnalysisSnapshot.is_active == True,
        )
    )
    for old_snap in existing.scalars().all():
        old_snap.is_active = False

    # Compute next version
    ver_result = await db.execute(
        select(AnalysisSnapshot.version)
        .where(AnalysisSnapshot.project_id == project_id)
        .order_by(AnalysisSnapshot.version.desc())
        .limit(1)
    )
    prev_version = ver_result.scalar_one_or_none() or 0

    snapshot = AnalysisSnapshot(
        id=new_cuid(),
        org_id=user.org_id,
        project_id=project_id,
        version=prev_version + 1,
        analysis_json=analysis_json,
        analysis_schema="rfx_analysis_v1",
        summary_md=summary_md,
        is_active=True,
        created_by=user.username,
    )
    db.add(snapshot)
    await db.flush()

    project.active_analysis_snapshot_id = snapshot.id
    project.status = "ready_for_generation"

    # Update title from analysis if project title is generic
    if analysis.title and project.title.startswith("새 입찰 프로젝트"):
        project.title = analysis.title

    db.add(AuditLog(
        org_id=user.org_id,
        user_id=user.username,
        project_id=project_id,
        action="studio_rfp_analyzed",
        target_type="analysis_snapshot",
        target_id=snapshot.id,
    ))

    await db.commit()
    await db.refresh(project)

    return {
        "snapshot_id": snapshot.id,
        "version": snapshot.version,
        "title": analysis.title,
        "summary_md": summary_md,
        "project": _project_to_response(project),
    }


@router.post("/projects/{project_id}/classify", response_model=ClassifyResponse)
async def classify_project_package(
    project_id: str,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """Classify submission package from the project's active analysis snapshot.

    Runs the package classifier on analysis_json + summary_md, then
    persists PackageItems to DB. Replaces any existing items for this project.
    Advances studio_stage to 'package'.
    """
    await require_project_access(project_id, "editor", user, db)

    # Load project + active snapshot
    result = await db.execute(
        select(BidProject).where(
            BidProject.id == project_id,
            BidProject.project_type == "studio",
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Studio 프로젝트를 찾을 수 없습니다")

    if not project.active_analysis_snapshot_id:
        raise HTTPException(400, "분석 스냅샷이 없습니다. 먼저 공고를 분석해주세요.")

    snap_result = await db.execute(
        select(AnalysisSnapshot).where(
            AnalysisSnapshot.id == project.active_analysis_snapshot_id,
        )
    )
    snapshot = snap_result.scalar_one_or_none()
    if not snapshot:
        raise HTTPException(404, "분석 스냅샷을 찾을 수 없습니다")

    # Classify
    classification, item_specs = classify_and_build(
        snapshot.analysis_json,
        snapshot.summary_md,
    )

    # Delete existing package items for this project (re-classification)
    existing = await db.execute(
        select(ProjectPackageItem).where(
            ProjectPackageItem.project_id == project_id,
        )
    )
    for old_item in existing.scalars().all():
        await db.delete(old_item)
    await db.flush()

    # Persist new package items
    db_items: list[ProjectPackageItem] = []
    for spec in item_specs:
        # generated_document with generation_target → ready_to_generate; others → missing
        initial_status = (
            "ready_to_generate"
            if spec.package_category == "generated_document" and spec.generation_target
            else "missing"
        )
        item = ProjectPackageItem(
            project_id=project_id,
            org_id=user.org_id,
            package_category=spec.package_category,
            document_code=spec.document_code,
            document_label=spec.document_label,
            required=spec.required,
            status=initial_status,
            generation_target=spec.generation_target,
            sort_order=spec.sort_order,
        )
        db.add(item)
        db_items.append(item)

    # Advance stage
    project.studio_stage = "package"

    # Audit
    db.add(AuditLog(
        org_id=user.org_id,
        user_id=user.username,
        project_id=project_id,
        action="package_classified",
        target_type="bid_project",
        target_id=project_id,
        detail_json={
            "procurement_domain": classification.procurement_domain,
            "contract_method": classification.contract_method,
            "confidence": classification.confidence,
            "item_count": len(db_items),
        },
    ))

    await db.commit()

    return ClassifyResponse(
        procurement_domain=classification.procurement_domain,
        contract_method=classification.contract_method,
        confidence=classification.confidence,
        detection_method=classification.detection_method,
        package_items=[
            PackageItemResponse(
                id=i.id,
                package_category=i.package_category,
                document_code=i.document_code,
                document_label=i.document_label,
                required=i.required,
                status=i.status,
                generation_target=i.generation_target,
                sort_order=i.sort_order,
            )
            for i in db_items
        ],
    )


@router.get("/projects/{project_id}/package-items", response_model=list[PackageItemResponse])
async def list_package_items(
    project_id: str,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """List package items for a Studio project."""
    await require_project_access(project_id, "viewer", user, db)
    result = await db.execute(
        select(ProjectPackageItem)
        .where(ProjectPackageItem.project_id == project_id)
        .order_by(ProjectPackageItem.sort_order)
    )
    items = result.scalars().all()
    return [
        PackageItemResponse(
            id=i.id,
            package_category=i.package_category,
            document_code=i.document_code,
            document_label=i.document_label,
            required=i.required,
            status=i.status,
            generation_target=i.generation_target,
            sort_order=i.sort_order,
        )
        for i in items
    ]


# --- Helpers ---

async def _get_snapshot_for_clone(
    db: AsyncSession, snapshot_id: str, org_id: str,
) -> AnalysisSnapshot:
    """Load and validate a snapshot for cloning into a Studio project."""
    result = await db.execute(
        select(AnalysisSnapshot).where(
            AnalysisSnapshot.id == snapshot_id,
            AnalysisSnapshot.org_id == org_id,
        )
    )
    snap = result.scalar_one_or_none()
    if snap is None:
        raise HTTPException(404, "분석 스냅샷을 찾을 수 없습니다")
    return snap


def _project_to_response(project: BidProject) -> StudioProjectResponse:
    return StudioProjectResponse(
        id=project.id,
        title=project.title,
        status=project.status,
        project_type=project.project_type,
        studio_stage=project.studio_stage,
        pinned_style_skill_id=project.pinned_style_skill_id,
        active_analysis_snapshot_id=project.active_analysis_snapshot_id,
        rfp_source_type=project.rfp_source_type,
        rfp_source_ref=project.rfp_source_ref,
        created_at=project.created_at.isoformat(),
        updated_at=project.updated_at.isoformat(),
    )
