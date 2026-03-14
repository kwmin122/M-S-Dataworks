from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from services.web_app.db.engine import get_async_session
from services.web_app.db.models.project import BidProject, ProjectAccess, SourceDocument
from services.web_app.db.models.document import DocumentAsset, ProjectCurrentDocument
from services.web_app.db.models.audit import AuditLog
from services.web_app.storage.s3 import get_s3_client
from services.web_app.api.deps import CurrentUser, resolve_org_membership, require_project_access

router = APIRouter(prefix="/api/projects", tags=["projects"])


class CreateProjectRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    rfp_source_type: str | None = None
    rfp_source_ref: str | None = None
    generation_mode: str | None = None


class UploadSourceRequest(BaseModel):
    document_kind: str = Field(
        pattern="^(rfp|company_profile|template|past_proposal|track_record|personnel|supporting_material|final_upload)$"
    )
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = "application/octet-stream"


@router.post("/")
async def create_project(
    req: CreateProjectRequest,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    project = BidProject(
        org_id=user.org_id,
        created_by=user.username,
        title=req.title,
        status="draft",
        rfp_source_type=req.rfp_source_type,
        rfp_source_ref=req.rfp_source_ref,
        generation_mode=req.generation_mode,
    )
    db.add(project)
    await db.flush()

    # Creator gets owner access
    access = ProjectAccess(
        project_id=project.id,
        user_id=user.username,
        access_level="owner",
    )
    db.add(access)

    # Audit
    audit = AuditLog(
        org_id=user.org_id,
        user_id=user.username,
        project_id=project.id,
        action="create_project",
        target_type="bid_project",
        target_id=project.id,
        detail_json={"title": req.title},
    )
    db.add(audit)
    await db.commit()

    return {
        "id": project.id,
        "title": project.title,
        "status": project.status,
        "created_at": project.created_at.isoformat() if project.created_at else None,
    }


@router.get("/")
async def list_projects(
    status: str | None = None,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """List projects the user has access to."""
    if user.role in ("owner", "admin"):
        query = select(BidProject).where(BidProject.org_id == user.org_id)
    else:
        query = (
            select(BidProject)
            .join(ProjectAccess, ProjectAccess.project_id == BidProject.id)
            .where(
                BidProject.org_id == user.org_id,
                ProjectAccess.user_id == user.username,
            )
        )

    if status:
        query = query.where(BidProject.status == status)
    query = query.order_by(BidProject.created_at.desc())

    result = await db.execute(query)
    projects = result.scalars().all()

    return {
        "projects": [
            {
                "id": p.id,
                "title": p.title,
                "status": p.status,
                "rfp_source_type": p.rfp_source_type,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in projects
        ]
    }


@router.get("/{project_id}")
async def get_project(
    project_id: str,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    await require_project_access(project_id, "viewer", user, db)

    result = await db.execute(
        select(BidProject).where(
            BidProject.id == project_id,
            BidProject.org_id == user.org_id,
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404)

    return {
        "id": project.id,
        "title": project.title,
        "status": project.status,
        "rfp_source_type": project.rfp_source_type,
        "rfp_source_ref": project.rfp_source_ref,
        "generation_mode": project.generation_mode,
        "settings_json": project.settings_json,
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None,
    }


@router.patch("/{project_id}")
async def update_project(
    project_id: str,
    title: str | None = None,
    status: str | None = None,
    generation_mode: str | None = None,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    await require_project_access(project_id, "editor", user, db)

    result = await db.execute(
        select(BidProject).where(
            BidProject.id == project_id,
            BidProject.org_id == user.org_id,
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404)

    if title is not None:
        project.title = title
    if status is not None:
        project.status = status
    if generation_mode is not None:
        project.generation_mode = generation_mode

    await db.commit()
    return {"id": project.id, "status": project.status}


@router.delete("/{project_id}")
async def archive_project(
    project_id: str,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    await require_project_access(project_id, "owner", user, db)

    result = await db.execute(
        select(BidProject).where(
            BidProject.id == project_id,
            BidProject.org_id == user.org_id,
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404)

    project.status = "archived"

    audit = AuditLog(
        org_id=user.org_id,
        user_id=user.username,
        project_id=project.id,
        action="archive_project",
        target_type="bid_project",
        target_id=project.id,
    )
    db.add(audit)
    await db.commit()

    return {"id": project.id, "status": "archived"}


@router.post("/{project_id}/sources")
async def upload_source(
    project_id: str,
    req: UploadSourceRequest,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """Create document_asset + presigned upload URL for source document."""
    await require_project_access(project_id, "editor", user, db)

    from services.web_app.db.models.base import new_cuid
    asset_id = new_cuid()
    s3 = get_s3_client()
    key = s3.build_source_storage_key(
        org_id=user.org_id,
        source_doc_id=asset_id,
        filename=req.filename,
    )
    storage_uri = s3.build_full_uri(key)

    asset = DocumentAsset(
        id=asset_id,
        org_id=user.org_id,
        project_id=project_id,
        asset_type="original",
        storage_uri=storage_uri,
        upload_status="presigned_issued",
        original_filename=req.filename,
        mime_type=req.content_type,
    )
    db.add(asset)

    source_doc = SourceDocument(
        org_id=user.org_id,
        project_id=project_id,
        document_kind=req.document_kind,
        uploaded_by=user.username,
        asset_id=asset_id,
        parse_status="pending",
    )
    db.add(source_doc)
    await db.flush()  # generate source_doc.id before using it in audit

    audit = AuditLog(
        org_id=user.org_id,
        user_id=user.username,
        project_id=project_id,
        action="upload_source",
        target_type="source_document",
        target_id=source_doc.id,
        detail_json={"filename": req.filename, "kind": req.document_kind},
    )
    db.add(audit)
    await db.commit()

    presigned_url = s3.generate_presigned_upload_url(
        key=key,
        content_type=req.content_type,
    )

    return {
        "asset_id": asset_id,
        "source_document_id": source_doc.id,
        "presigned_url": presigned_url,
        "storage_key": key,
    }
