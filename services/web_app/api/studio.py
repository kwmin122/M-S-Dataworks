"""Studio project control plane — CRUD + snapshot clone."""
from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.web_app.db.engine import get_async_session
from services.web_app.db.models.base import new_cuid
from services.web_app.db.models.project import BidProject, AnalysisSnapshot
from services.web_app.db.models.studio import ProjectCompanyAsset, ProjectStyleSkill, ProjectPackageItem
from services.web_app.api.deps import CurrentUser, resolve_org_membership, require_project_access

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/studio", tags=["studio"])


# --- Request / Response schemas ---

class CreateStudioProjectRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    from_analysis_snapshot_id: str | None = None
    rfp_source_type: str | None = None
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


@router.get("/projects", response_model=List[StudioProjectResponse])
async def list_studio_projects(
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """List all Studio projects for the user's organization."""
    result = await db.execute(
        select(BidProject)
        .where(
            BidProject.org_id == user.org_id,
            BidProject.project_type == "studio",
        )
        .order_by(BidProject.created_at.desc())
    )
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
