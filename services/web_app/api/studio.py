"""Studio project control plane — CRUD + snapshot clone + analyze + classify + company assets + generate."""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.web_app.db.engine import get_async_session
from services.web_app.db.models.base import new_cuid
from services.web_app.db.models.project import BidProject, ProjectAccess, AnalysisSnapshot
from services.web_app.db.models.studio import ProjectCompanyAsset, ProjectPackageItem, ProjectStyleSkill
from services.web_app.db.models.company import CompanyProfile, CompanyTrackRecord, CompanyPersonnel
from services.web_app.db.models.document import DocumentRun, DocumentRevision, DocumentAsset
from services.web_app.db.models.audit import AuditLog
from services.web_app.api.deps import CurrentUser, resolve_org_membership, require_project_access
from services.web_app.rate_limit import limiter
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
    review_required: bool = False
    matched_signals: list[str] = []
    warnings: list[str] = []
    package_items: list[PackageItemResponse]


# --- Chat handoff schema ---

class ChatHandoffRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    analysis_json: dict
    summary_md: str = ""
    go_nogo_result_json: dict | None = None


# --- Endpoints ---

@router.post("/handoff-from-chat", response_model=StudioProjectResponse, status_code=201)
async def handoff_from_chat(
    req: ChatHandoffRequest,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """Create a Studio project from Chat analysis data.

    One-call handoff: creates project + snapshot from inline analysis.
    No need to pass a snapshot ID — the analysis data is embedded directly.
    """
    project = BidProject(
        org_id=user.org_id,
        created_by=user.username,
        title=req.title,
        status="ready_for_generation",
        project_type="studio",
        studio_stage="package",
        rfp_source_type="manual",
    )
    db.add(project)
    await db.flush()

    db.add(ProjectAccess(
        project_id=project.id,
        user_id=user.username,
        access_level="owner",
    ))

    snapshot = AnalysisSnapshot(
        id=new_cuid(),
        org_id=user.org_id,
        project_id=project.id,
        version=1,
        analysis_json=req.analysis_json,
        analysis_schema="rfx_analysis_v1",
        summary_md=req.summary_md,
        go_nogo_result_json=req.go_nogo_result_json,
        is_active=True,
        created_by=user.username,
    )
    db.add(snapshot)
    await db.flush()
    project.active_analysis_snapshot_id = snapshot.id

    db.add(AuditLog(
        org_id=user.org_id,
        user_id=user.username,
        project_id=project.id,
        action="studio_handoff_from_chat",
        target_type="bid_project",
        target_id=project.id,
    ))

    await db.commit()
    await db.refresh(project)

    return _project_to_response(project)


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


# --- Nara Search (proxy for Studio) ---

class NaraSearchRequest(BaseModel):
    keywords: str = Field(min_length=1, max_length=200)
    category: Literal['all', 'service', 'goods', 'construction', 'foreign', 'etc'] = "all"
    region: str = Field(default="", max_length=100)
    min_amt: float | None = Field(default=None, ge=0)
    max_amt: float | None = Field(default=None, ge=0)
    period: Literal['1w', '1m', '3m', '6m', '12m'] = "1m"
    page: int = Field(default=1, ge=1, le=100)
    page_size: int = Field(default=10, ge=1, le=50)


@router.post("/search-bids")
@limiter.limit("10/minute")
async def studio_search_bids(
    request: Request,
    req: NaraSearchRequest,
    user: CurrentUser = Depends(resolve_org_membership),
):
    """Search 나라장터 bids from Studio context."""
    from services.web_app.nara_api import search_bids
    result = await search_bids(
        keywords=req.keywords,
        category=req.category,
        region=req.region,
        min_amt=req.min_amt,
        max_amt=req.max_amt,
        period=req.period,
        page=req.page,
        page_size=req.page_size,
    )
    return result


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


@router.post("/projects/{project_id}/upload-rfp")
async def upload_and_analyze_rfp(
    project_id: str,
    file: UploadFile = File(...),
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """Upload an RFP file (PDF/DOCX/HWP/HWPX/TXT), parse it, and analyze."""
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

    # Validate file extension
    ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.hwp', '.hwpx', '.txt', '.xlsx', '.pptx'}
    import pathlib
    ext = pathlib.Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"지원하지 않는 파일 형식입니다: {ext}. 지원: {', '.join(sorted(ALLOWED_EXTENSIONS))}")

    # Save to temp file
    import re
    safe_name = re.sub(r'[^a-zA-Z0-9가-힣._-]', '_', file.filename or 'upload')[:100]
    tmp_dir = os.path.join("data", "studio_uploads", project_id)
    os.makedirs(tmp_dir, exist_ok=True)
    tmp_path = os.path.join(tmp_dir, safe_name)

    # Path traversal guard
    resolved = os.path.realpath(tmp_path)
    if not resolved.startswith(os.path.realpath(tmp_dir)):
        raise HTTPException(400, "잘못된 파일명입니다")

    MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB
    size = 0
    with open(tmp_path, "wb") as f:
        while chunk := await file.read(8192):
            size += len(chunk)
            if size > MAX_UPLOAD_SIZE:
                f.close()
                os.unlink(tmp_path)
                raise HTTPException(400, "파일 크기가 50MB를 초과합니다")
            f.write(chunk)
    # Validate file magic bytes
    MAGIC_BYTES = {
        '.pdf': [b'%PDF'],
        '.docx': [b'PK\x03\x04'],
        '.xlsx': [b'PK\x03\x04'],
        '.pptx': [b'PK\x03\x04'],
    }
    with open(tmp_path, "rb") as check_f:
        header = check_f.read(8)
    expected_magic = MAGIC_BYTES.get(ext, [])
    if expected_magic and not any(header.startswith(m) for m in expected_magic):
        os.unlink(tmp_path)
        raise HTTPException(400, "파일 내용이 확장자와 일치하지 않습니다")

    try:
        # Parse document to extract text
        try:
            from document_parser import DocumentParser
            parser = DocumentParser()
            parsed = await asyncio.to_thread(parser.parse, tmp_path)
            document_text = parsed.text
        except Exception as exc:
            logger.error("File parsing failed for %s: %s", safe_name, exc)
            raise HTTPException(400, f"파일 파싱 실패: {str(exc)}")

        if len(document_text.strip()) < 50:
            raise HTTPException(400, "파일에서 추출된 텍스트가 너무 짧습니다 (50자 미만)")

        # Run same analysis pipeline as text-based analyze
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise HTTPException(500, "OPENAI_API_KEY가 설정되지 않았습니다")

        from rfx_analyzer import RFxAnalyzer
        from services.web_app.api.analysis_serializer import serialize_analysis_for_db

        analyzer = RFxAnalyzer(
            api_key=api_key,
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        )

        analysis = await asyncio.to_thread(analyzer.analyze_text, document_text)

        # Generate summary
        summary_md = ""
        try:
            from rfx_analyzer import generate_rfp_summary
            summary_md = await asyncio.to_thread(generate_rfp_summary, analysis, api_key)
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
        project.rfp_source_type = "upload"

        if analysis.title and project.title.startswith("새 입찰 프로젝트"):
            project.title = analysis.title

        db.add(AuditLog(
            org_id=user.org_id,
            user_id=user.username,
            project_id=project_id,
            action="studio_rfp_file_uploaded",
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
            "filename": safe_name,
            "project": _project_to_response(project),
        }
    finally:
        # Clean up uploaded file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


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
            "review_required": classification.review_required,
            "matched_signals": classification.matched_signals,
            "warnings": classification.warnings,
            "item_count": len(db_items),
        },
    ))

    await db.commit()

    return ClassifyResponse(
        procurement_domain=classification.procurement_domain,
        contract_method=classification.contract_method,
        confidence=classification.confidence,
        detection_method=classification.detection_method,
        review_required=classification.review_required,
        matched_signals=classification.matched_signals,
        warnings=classification.warnings,
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


# --- Package manual override ---

class OverrideClassificationRequest(BaseModel):
    procurement_domain: str | None = None  # override domain
    contract_method: str | None = None     # override method
    include_presentation: bool | None = None  # force include/exclude PPT
    add_items: list[dict[str, Any]] | None = None  # [{document_label, package_category?, required?}]
    remove_item_ids: list[str] | None = None  # item IDs to remove


@router.patch("/projects/{project_id}/package-override")
async def override_package_classification(
    project_id: str,
    req: OverrideClassificationRequest,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """Manual override of classifier results. Logs to AuditLog for corpus improvement."""
    await require_project_access(project_id, "editor", user, db)

    result = await db.execute(
        select(BidProject).where(BidProject.id == project_id, BidProject.project_type == "studio")
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "프로젝트를 찾을 수 없습니다")

    changes: dict[str, Any] = {}

    # Remove items
    if req.remove_item_ids:
        for item_id in req.remove_item_ids:
            item_result = await db.execute(
                select(ProjectPackageItem).where(
                    ProjectPackageItem.id == item_id,
                    ProjectPackageItem.project_id == project_id,
                )
            )
            item = item_result.scalar_one_or_none()
            if item:
                await db.delete(item)
                changes[f"removed_{item_id}"] = item.document_label

    # Add items
    if req.add_items:
        for spec in req.add_items:
            label = spec.get("document_label")
            if not label or not isinstance(label, str) or len(label.strip()) == 0:
                raise HTTPException(400, "document_label은 필수입니다")
            category = spec.get("package_category", "evidence")
            if category not in ("generated_document", "evidence", "administrative", "price"):
                raise HTTPException(400, f"유효하지 않은 패키지 카테고리: {category}")
            new_item = ProjectPackageItem(
                project_id=project_id,
                org_id=user.org_id,
                package_category=category,
                document_code=spec.get("document_code", f"manual_{new_cuid()[:8]}"),
                document_label=label.strip(),
                required=bool(spec.get("required", True)),
                status="missing",
                sort_order=99,
            )
            db.add(new_item)
            changes[f"added_{new_item.document_code}"] = label.strip()

    # Override domain/method — stored in audit for corpus improvement
    if req.procurement_domain:
        changes["domain_override"] = {"from": "auto", "to": req.procurement_domain}
    if req.contract_method:
        changes["method_override"] = {"from": "auto", "to": req.contract_method}

    # Include/exclude presentation
    if req.include_presentation is not None:
        if req.include_presentation:
            existing_ppt = await db.execute(
                select(ProjectPackageItem).where(
                    ProjectPackageItem.project_id == project_id,
                    ProjectPackageItem.generation_target == "presentation",
                )
            )
            if not existing_ppt.scalar_one_or_none():
                ppt_item = ProjectPackageItem(
                    project_id=project_id,
                    org_id=user.org_id,
                    package_category="generated_document",
                    document_code="ppt_presentation",
                    document_label="발표자료 (PPT)",
                    required=True,
                    status="ready_to_generate",
                    generation_target="presentation",
                    sort_order=4,
                )
                db.add(ppt_item)
                changes["presentation_added"] = True
        else:
            ppt_result = await db.execute(
                select(ProjectPackageItem).where(
                    ProjectPackageItem.project_id == project_id,
                    ProjectPackageItem.generation_target == "presentation",
                )
            )
            ppt_item = ppt_result.scalar_one_or_none()
            if ppt_item:
                await db.delete(ppt_item)
                changes["presentation_removed"] = True

    if not changes:
        raise HTTPException(400, "변경사항이 없습니다")

    # Audit log
    db.add(AuditLog(
        org_id=user.org_id,
        user_id=user.username,
        project_id=project_id,
        action="package_manual_override",
        target_type="bid_project",
        target_id=project_id,
        detail_json=changes,
    ))

    await db.commit()

    # Return updated items
    items_result = await db.execute(
        select(ProjectPackageItem).where(
            ProjectPackageItem.project_id == project_id,
        ).order_by(ProjectPackageItem.sort_order)
    )
    updated_items = items_result.scalars().all()

    return {
        "changes": changes,
        "package_items": [
            PackageItemResponse(
                id=i.id,
                package_category=i.package_category,
                document_code=i.document_code,
                document_label=i.document_label,
                required=i.required,
                status=i.status,
                generation_target=i.generation_target,
                sort_order=i.sort_order,
            ).model_dump()
            for i in updated_items
        ],
    }


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


# --- Studio project type guard ---

async def _require_studio_project_access(
    project_id: str, min_level: str, user: CurrentUser, db: AsyncSession,
) -> None:
    """require_project_access + verify project_type == 'studio'.

    All company-asset endpoints must call this instead of bare require_project_access,
    so staging data cannot be attached to non-Studio projects.
    """
    await require_project_access(project_id, min_level, user, db)
    result = await db.execute(
        select(BidProject.project_type).where(BidProject.id == project_id)
    )
    ptype = result.scalar_one_or_none()
    if ptype != "studio":
        raise HTTPException(400, "Studio 프로젝트에서만 사용할 수 있습니다")


# --- Company Asset schemas ---

_VALID_ASSET_CATEGORIES = frozenset({
    "track_record", "personnel", "profile",
    "technology", "certification", "raw_document",
})
_PROMOTABLE_CATEGORIES = frozenset({"track_record", "personnel", "profile"})


class CompanyAssetRequest(BaseModel):
    asset_category: str = Field(pattern="^(track_record|personnel|profile|technology|certification|raw_document)$")
    label: str = Field(min_length=1, max_length=500)
    content_json: dict


class CompanyAssetResponse(BaseModel):
    id: str
    asset_category: str
    label: str
    content_json: dict
    promoted_at: str | None
    promoted_to_id: str | None
    created_at: str

    class Config:
        from_attributes = True


# --- Company Asset endpoints ---

@router.post("/projects/{project_id}/company-assets", response_model=CompanyAssetResponse, status_code=201)
async def add_company_asset(
    project_id: str,
    req: CompanyAssetRequest,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """Add a company asset to project staging. Does NOT touch shared CompanyDB."""
    await _require_studio_project_access(project_id, "editor", user, db)

    asset = ProjectCompanyAsset(
        project_id=project_id,
        org_id=user.org_id,
        asset_category=req.asset_category,
        label=req.label,
        content_json=req.content_json,
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)

    return _asset_to_response(asset)


@router.get("/projects/{project_id}/company-assets", response_model=list[CompanyAssetResponse])
async def list_company_assets(
    project_id: str,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """List staging company assets for this project."""
    await _require_studio_project_access(project_id, "viewer", user, db)

    result = await db.execute(
        select(ProjectCompanyAsset)
        .where(ProjectCompanyAsset.project_id == project_id)
        .order_by(ProjectCompanyAsset.created_at)
    )
    assets = result.scalars().all()
    return [_asset_to_response(a) for a in assets]


@router.get("/projects/{project_id}/company-merged")
async def get_company_merged(
    project_id: str,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """Return shared + staging merged view of company data."""
    await _require_studio_project_access(project_id, "viewer", user, db)

    # --- Shared data ---
    profile_result = await db.execute(
        select(CompanyProfile).where(CompanyProfile.org_id == user.org_id)
    )
    shared_profile = profile_result.scalar_one_or_none()

    shared_tracks_result = await db.execute(
        select(CompanyTrackRecord).where(CompanyTrackRecord.org_id == user.org_id)
    )
    shared_tracks = shared_tracks_result.scalars().all()

    shared_personnel_result = await db.execute(
        select(CompanyPersonnel).where(CompanyPersonnel.org_id == user.org_id)
    )
    shared_personnel = shared_personnel_result.scalars().all()

    # --- Staging data ---
    staging_result = await db.execute(
        select(ProjectCompanyAsset)
        .where(
            ProjectCompanyAsset.project_id == project_id,
            ProjectCompanyAsset.promoted_at.is_(None),
        )
        .order_by(ProjectCompanyAsset.created_at)
    )
    staging_assets = staging_result.scalars().all()

    # --- Build merged response ---
    # Profile: shared profile or staging profile override
    profile_data = None
    if shared_profile:
        profile_data = {
            "id": shared_profile.id,
            "company_name": shared_profile.company_name,
            "business_type": shared_profile.business_type,
            "business_number": shared_profile.business_number,
            "capital": shared_profile.capital,
            "headcount": shared_profile.headcount,
            "source": "shared",
        }

    # Track records: shared + staging
    track_records = []
    for t in shared_tracks:
        track_records.append({
            "id": t.id,
            "project_name": t.project_name,
            "client_name": t.client_name,
            "contract_amount": t.contract_amount,
            "description": t.description,
            "source": "shared",
        })

    # Personnel: shared + staging
    personnel = []
    for p in shared_personnel:
        personnel.append({
            "id": p.id,
            "name": p.name,
            "role": p.role,
            "years_experience": p.years_experience,
            "description": p.description,
            "source": "shared",
        })

    # Other categories
    other_assets = []

    for asset in staging_assets:
        item = {
            "id": asset.id,
            "source": "staging",
            "asset_category": asset.asset_category,
            "label": asset.label,
            **asset.content_json,
        }
        if asset.asset_category == "track_record":
            track_records.append(item)
        elif asset.asset_category == "personnel":
            personnel.append(item)
        elif asset.asset_category == "profile":
            # Staging profile overrides display (but doesn't write shared yet)
            profile_data = {
                "id": asset.id,
                "source": "staging",
                **asset.content_json,
            }
        else:
            other_assets.append(item)

    return {
        "profile": profile_data,
        "track_records": track_records,
        "personnel": personnel,
        "other_assets": other_assets,
    }


@router.post("/projects/{project_id}/company-assets/{asset_id}/promote")
async def promote_company_asset(
    project_id: str,
    asset_id: str,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """Promote a staging asset to shared CompanyDB.

    Only track_record, personnel, profile are promotable in this phase.
    """
    await _require_studio_project_access(project_id, "editor", user, db)

    # Load the staging asset
    result = await db.execute(
        select(ProjectCompanyAsset).where(
            ProjectCompanyAsset.id == asset_id,
            ProjectCompanyAsset.project_id == project_id,
        )
    )
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(404, "스테이징 자산을 찾을 수 없습니다")

    # Check already promoted
    if asset.promoted_at is not None:
        raise HTTPException(409, "이미 승격된 자산입니다")

    # Check promotable category
    if asset.asset_category not in _PROMOTABLE_CATEGORIES:
        raise HTTPException(
            400,
            f"'{asset.asset_category}' 카테고리는 현재 공유 DB 승격을 지원하지 않습니다",
        )

    # Promote based on category
    promoted_to_id: str | None = None
    content = asset.content_json

    if asset.asset_category == "track_record":
        record = CompanyTrackRecord(
            org_id=user.org_id,
            project_name=content.get("project_name"),
            client_name=content.get("client_name"),
            contract_amount=content.get("contract_amount"),
            description=content.get("description"),
            technologies=content.get("technologies"),
        )
        # Parse dates if provided
        if content.get("period_start"):
            try:
                record.period_start = _parse_date(content["period_start"])
            except (ValueError, TypeError):
                pass
        if content.get("period_end"):
            try:
                record.period_end = _parse_date(content["period_end"])
            except (ValueError, TypeError):
                pass
        db.add(record)
        await db.flush()
        promoted_to_id = record.id

    elif asset.asset_category == "personnel":
        person = CompanyPersonnel(
            org_id=user.org_id,
            name=content.get("name"),
            role=content.get("role"),
            years_experience=content.get("years_experience"),
            certifications=content.get("certifications"),
            skills=content.get("skills"),
            description=content.get("description"),
        )
        db.add(person)
        await db.flush()
        promoted_to_id = person.id

    elif asset.asset_category == "profile":
        # Profile is org-level singleton — upsert
        existing = (await db.execute(
            select(CompanyProfile).where(CompanyProfile.org_id == user.org_id)
        )).scalar_one_or_none()

        if existing:
            # Update existing profile
            if content.get("company_name") is not None:
                existing.company_name = content["company_name"]
            if content.get("business_type") is not None:
                existing.business_type = content["business_type"]
            if content.get("business_number") is not None:
                existing.business_number = content["business_number"]
            if content.get("capital") is not None:
                existing.capital = content["capital"]
            if content.get("headcount") is not None:
                existing.headcount = content["headcount"]
            if content.get("licenses") is not None:
                existing.licenses = content["licenses"]
            if content.get("certifications") is not None:
                existing.certifications = content["certifications"]
            if content.get("writing_style") is not None:
                existing.writing_style = content["writing_style"]
            promoted_to_id = existing.id
        else:
            # Create new profile
            profile = CompanyProfile(
                org_id=user.org_id,
                company_name=content.get("company_name"),
                business_type=content.get("business_type"),
                business_number=content.get("business_number"),
                capital=content.get("capital"),
                headcount=content.get("headcount"),
                licenses=content.get("licenses"),
                certifications=content.get("certifications"),
                writing_style=content.get("writing_style"),
            )
            db.add(profile)
            await db.flush()
            promoted_to_id = profile.id

    # Mark staging asset as promoted
    asset.promoted_at = datetime.now(timezone.utc)
    asset.promoted_to_id = promoted_to_id

    # Audit log
    db.add(AuditLog(
        org_id=user.org_id,
        user_id=user.username,
        project_id=project_id,
        action="company_asset_promoted",
        target_type="project_company_asset",
        target_id=asset_id,
        detail_json={
            "asset_category": asset.asset_category,
            "promoted_to_id": promoted_to_id,
        },
    ))

    await db.commit()

    return {"promoted": True, "promoted_to_id": promoted_to_id}


def _asset_to_response(asset: ProjectCompanyAsset) -> CompanyAssetResponse:
    return CompanyAssetResponse(
        id=asset.id,
        asset_category=asset.asset_category,
        label=asset.label,
        content_json=asset.content_json,
        promoted_at=asset.promoted_at.isoformat() if asset.promoted_at else None,
        promoted_to_id=asset.promoted_to_id,
        created_at=asset.created_at.isoformat(),
    )


def _parse_date(val: str):
    """Parse a date string (YYYY-MM-DD) to date object."""
    from datetime import date as date_type
    return date_type.fromisoformat(val)


# --- Style Skill schemas ---

class CreateStyleSkillRequest(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    style_json: dict | None = None
    profile_md_content: str | None = None


class DeriveStyleSkillRequest(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    style_json: dict | None = None
    profile_md_content: str | None = None


class StyleSkillResponse(BaseModel):
    id: str
    project_id: str | None
    version: int
    name: str
    source_type: str
    derived_from_id: str | None
    profile_md_content: str | None
    style_json: dict | None
    is_shared_default: bool
    created_at: str

    class Config:
        from_attributes = True


# --- Style Skill endpoints ---

@router.post("/projects/{project_id}/style-skills", response_model=StyleSkillResponse, status_code=201)
async def create_style_skill(
    project_id: str,
    req: CreateStyleSkillRequest,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """Create a project-scoped style skill."""
    await _require_studio_project_access(project_id, "editor", user, db)

    # Compute next version for this project
    ver_result = await db.execute(
        select(ProjectStyleSkill.version)
        .where(ProjectStyleSkill.project_id == project_id)
        .order_by(ProjectStyleSkill.version.desc())
        .limit(1)
    )
    prev_version = ver_result.scalar_one_or_none() or 0

    skill = ProjectStyleSkill(
        project_id=project_id,
        org_id=user.org_id,
        version=prev_version + 1,
        name=req.name,
        source_type="uploaded",
        style_json=req.style_json,
        profile_md_content=req.profile_md_content,
    )
    db.add(skill)
    await db.flush()

    db.add(AuditLog(
        org_id=user.org_id,
        user_id=user.username,
        project_id=project_id,
        action="style_skill_created",
        target_type="project_style_skill",
        target_id=skill.id,
    ))

    await db.commit()
    await db.refresh(skill)

    return _skill_to_response(skill)


@router.get("/projects/{project_id}/style-skills", response_model=list[StyleSkillResponse])
async def list_style_skills(
    project_id: str,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """List style skills for a project (project-scoped + org shared defaults)."""
    await _require_studio_project_access(project_id, "viewer", user, db)

    result = await db.execute(
        select(ProjectStyleSkill)
        .where(
            ProjectStyleSkill.org_id == user.org_id,
            (ProjectStyleSkill.project_id == project_id) | (ProjectStyleSkill.project_id.is_(None)),
        )
        .order_by(ProjectStyleSkill.version)
    )
    skills = result.scalars().all()
    return [_skill_to_response(s) for s in skills]


@router.post("/projects/{project_id}/style-skills/{skill_id}/pin")
async def pin_style_skill(
    project_id: str,
    skill_id: str,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """Pin a style skill to the project."""
    await _require_studio_project_access(project_id, "editor", user, db)

    # Verify skill exists and belongs to this project or is org-shared
    skill = (await db.execute(
        select(ProjectStyleSkill).where(
            ProjectStyleSkill.id == skill_id,
            ProjectStyleSkill.org_id == user.org_id,
            (ProjectStyleSkill.project_id == project_id) | (ProjectStyleSkill.project_id.is_(None)),
        )
    )).scalar_one_or_none()
    if skill is None:
        raise HTTPException(404, "스타일 스킬을 찾을 수 없습니다")

    # Update project pin
    project = (await db.execute(
        select(BidProject).where(BidProject.id == project_id)
    )).scalar_one()
    project.pinned_style_skill_id = skill_id

    db.add(AuditLog(
        org_id=user.org_id,
        user_id=user.username,
        project_id=project_id,
        action="style_skill_pinned",
        target_type="project_style_skill",
        target_id=skill_id,
    ))

    await db.commit()

    return {"pinned_style_skill_id": skill_id}


@router.delete("/projects/{project_id}/style-skills/pin")
async def unpin_style_skill(
    project_id: str,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """Unpin the style skill from the project."""
    await _require_studio_project_access(project_id, "editor", user, db)

    project = (await db.execute(
        select(BidProject).where(BidProject.id == project_id)
    )).scalar_one()
    old_skill_id = project.pinned_style_skill_id
    project.pinned_style_skill_id = None

    db.add(AuditLog(
        org_id=user.org_id,
        user_id=user.username,
        project_id=project_id,
        action="style_skill_unpinned",
        target_type="project_style_skill",
        target_id=old_skill_id,
    ))

    await db.commit()

    return {"pinned_style_skill_id": None}


@router.post("/projects/{project_id}/style-skills/{skill_id}/derive", response_model=StyleSkillResponse, status_code=201)
async def derive_style_skill(
    project_id: str,
    skill_id: str,
    req: DeriveStyleSkillRequest,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """Derive a new version from an existing style skill."""
    await _require_studio_project_access(project_id, "editor", user, db)

    # Load parent skill
    parent = (await db.execute(
        select(ProjectStyleSkill).where(
            ProjectStyleSkill.id == skill_id,
            ProjectStyleSkill.org_id == user.org_id,
        )
    )).scalar_one_or_none()
    if parent is None:
        raise HTTPException(404, "원본 스타일 스킬을 찾을 수 없습니다")

    # Compute next version
    ver_result = await db.execute(
        select(ProjectStyleSkill.version)
        .where(ProjectStyleSkill.project_id == project_id)
        .order_by(ProjectStyleSkill.version.desc())
        .limit(1)
    )
    prev_version = ver_result.scalar_one_or_none() or 0

    derived = ProjectStyleSkill(
        project_id=project_id,
        org_id=user.org_id,
        version=prev_version + 1,
        name=req.name,
        source_type="derived",
        derived_from_id=skill_id,
        style_json=req.style_json if req.style_json is not None else parent.style_json,
        profile_md_content=req.profile_md_content if req.profile_md_content is not None else parent.profile_md_content,
    )
    db.add(derived)
    await db.commit()
    await db.refresh(derived)

    return _skill_to_response(derived)


@router.post("/projects/{project_id}/style-skills/{skill_id}/promote")
async def promote_style_skill(
    project_id: str,
    skill_id: str,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """Promote a project-scoped style skill to org-level shared default.

    If a shared default already exists, demotes it first (is_shared_default=False).
    """
    await _require_studio_project_access(project_id, "editor", user, db)

    # Load source skill
    source = (await db.execute(
        select(ProjectStyleSkill).where(
            ProjectStyleSkill.id == skill_id,
            ProjectStyleSkill.org_id == user.org_id,
        )
    )).scalar_one_or_none()
    if source is None:
        raise HTTPException(404, "스타일 스킬을 찾을 수 없습니다")

    # Demote existing shared default(s)
    existing_defaults = (await db.execute(
        select(ProjectStyleSkill).where(
            ProjectStyleSkill.org_id == user.org_id,
            ProjectStyleSkill.is_shared_default == True,
        )
    )).scalars().all()
    for old in existing_defaults:
        old.is_shared_default = False
    if existing_defaults:
        await db.flush()

    # Compute shared version
    shared_ver_result = await db.execute(
        select(ProjectStyleSkill.version)
        .where(
            ProjectStyleSkill.org_id == user.org_id,
            ProjectStyleSkill.project_id.is_(None),
        )
        .order_by(ProjectStyleSkill.version.desc())
        .limit(1)
    )
    prev_shared_version = shared_ver_result.scalar_one_or_none() or 0

    # Create shared default
    shared = ProjectStyleSkill(
        project_id=None,
        org_id=user.org_id,
        version=prev_shared_version + 1,
        name=source.name,
        source_type="promoted",
        derived_from_id=source.id,
        style_json=source.style_json,
        profile_md_content=source.profile_md_content,
        is_shared_default=True,
    )
    db.add(shared)
    await db.flush()

    # Audit log
    db.add(AuditLog(
        org_id=user.org_id,
        user_id=user.username,
        project_id=project_id,
        action="style_skill_promoted",
        target_type="project_style_skill",
        target_id=skill_id,
        detail_json={
            "shared_skill_id": shared.id,
            "source_skill_id": skill_id,
        },
    ))

    await db.commit()

    return {"promoted": True, "shared_skill_id": shared.id}


def _skill_to_response(skill: ProjectStyleSkill) -> StyleSkillResponse:
    return StyleSkillResponse(
        id=skill.id,
        project_id=skill.project_id,
        version=skill.version,
        name=skill.name,
        source_type=skill.source_type,
        derived_from_id=skill.derived_from_id,
        profile_md_content=skill.profile_md_content,
        style_json=skill.style_json,
        is_shared_default=skill.is_shared_default,
        created_at=skill.created_at.isoformat(),
    )


# --- Proposal Generation schemas ---

class GenerateProposalRequest(BaseModel):
    doc_type: Literal["proposal", "execution_plan", "track_record", "presentation"] = "proposal"
    total_pages: int = Field(default=50, ge=10, le=200)
    # PPT-specific params
    target_slide_count: int = Field(default=15, ge=5, le=50)
    duration_min: int = Field(default=25, ge=5, le=120)
    qna_count: int = Field(default=10, ge=0, le=30)


_PPT_ASSET_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "ppt_assets")


# --- Proposal Generation endpoint ---

@router.post("/projects/{project_id}/generate")
async def generate_proposal(
    project_id: str,
    req: GenerateProposalRequest,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """Generate a proposal document for a Studio project.

    Builds effective company context from shared + staging,
    applies pinned style, and creates DocumentRun + DocumentRevision.
    Returns the generation contract for transparency.
    """
    await _require_studio_project_access(project_id, "editor", user, db)

    # Concurrent generation guard
    existing_running = (await db.execute(
        select(DocumentRun).where(
            DocumentRun.project_id == project_id,
            DocumentRun.status == "running",
        )
    )).scalar_one_or_none()
    if existing_running:
        raise HTTPException(409, "이미 생성 중인 문서가 있습니다.")

    # Load project
    project = (await db.execute(
        select(BidProject).where(BidProject.id == project_id)
    )).scalar_one()

    # Require analysis snapshot
    if not project.active_analysis_snapshot_id:
        raise HTTPException(400, "분석 스냅샷이 없습니다. 먼저 공고를 분석해주세요.")

    snap = (await db.execute(
        select(AnalysisSnapshot).where(
            AnalysisSnapshot.id == project.active_analysis_snapshot_id,
        )
    )).scalar_one_or_none()
    if snap is None:
        raise HTTPException(400, "분석 스냅샷을 찾을 수 없습니다.")

    # --- Build generation contract ---

    # 1. Company context: shared + staging merged into narrative
    company_context, company_assets_count, company_name = await _build_company_context(db, project_id, user.org_id)

    # 2. Pinned style
    pinned_style = None
    style_profile_md = ""
    if project.pinned_style_skill_id:
        pinned_style = (await db.execute(
            select(ProjectStyleSkill).where(
                ProjectStyleSkill.id == project.pinned_style_skill_id,
            )
        )).scalar_one_or_none()
        if pinned_style:
            style_profile_md = pinned_style.profile_md_content or ""

    generation_contract: dict[str, Any] = {
        "snapshot_id": snap.id,
        "snapshot_version": snap.version,
        "company_assets_count": company_assets_count,
        "company_context_length": len(company_context),
        "pinned_style_skill_id": project.pinned_style_skill_id,
        "pinned_style_name": pinned_style.name if pinned_style else None,
        "pinned_style_version": pinned_style.version if pinned_style else None,
        "doc_type": req.doc_type,
        "total_pages": req.total_pages,
    }

    # PPT-specific: load proposal/execution_plan revisions for enriched input
    proposal_rev = None
    exec_plan_rev = None
    if req.doc_type == "presentation":
        from services.web_app.db.models.document import ProjectCurrentDocument
        for dt, attr in [("proposal", "proposal_rev"), ("execution_plan", "exec_plan_rev")]:
            cur = (await db.execute(
                select(ProjectCurrentDocument).where(
                    ProjectCurrentDocument.project_id == project_id,
                    ProjectCurrentDocument.doc_type == dt,
                )
            )).scalar_one_or_none()
            if cur:
                rev = (await db.execute(
                    select(DocumentRevision).where(DocumentRevision.id == cur.current_revision_id)
                )).scalar_one_or_none()
                if attr == "proposal_rev":
                    proposal_rev = rev
                else:
                    exec_plan_rev = rev

        generation_contract.update({
            "proposal_revision_id": proposal_rev.id if proposal_rev else None,
            "execution_plan_revision_id": exec_plan_rev.id if exec_plan_rev else None,
            "target_slide_count": req.target_slide_count,
            "duration_min": req.duration_min,
            "qna_count": req.qna_count,
            "available_inputs": {
                "proposal": proposal_rev is not None,
                "execution_plan": exec_plan_rev is not None,
            },
        })

    # --- Create DocumentRun ---
    run = DocumentRun(
        org_id=user.org_id,
        project_id=project_id,
        analysis_snapshot_id=snap.id,
        doc_type=req.doc_type,
        status="running",
        params_json=generation_contract,
        created_by=user.username,
        started_at=datetime.now(timezone.utc),
    )
    db.add(run)
    await db.flush()

    # --- Run generation (dispatched by doc_type, mocked in tests) ---
    try:
        if req.doc_type == "execution_plan":
            gen_result = await asyncio.to_thread(
                _run_wbs_generation,
                rfx_result=snap.analysis_json,
                company_context=company_context,
                style_profile_md=style_profile_md,
                company_name=company_name,
            )
            sections = [(t.phase, t.task_name) for t in (gen_result.tasks or [])]
            content_json_extra = {}
            quality_issues: list[str] = []
            generation_time_sec = getattr(gen_result, 'generation_time_sec', None)
        elif req.doc_type == "track_record":
            gen_result = await asyncio.to_thread(
                _run_track_record_generation,
                rfx_result=snap.analysis_json,
                company_context=company_context,
                style_profile_md=style_profile_md,
                company_name=company_name,
            )
            sections = []  # track record uses records/personnel, not sections
            content_json_extra = {
                "records": gen_result.records_data or [],
                "personnel": gen_result.personnel_data or [],
            }
            quality_issues = []
            generation_time_sec = getattr(gen_result, 'generation_time_sec', None)
        elif req.doc_type == "presentation":
            # Build proposal_sections from current revision + exec plan enrichment
            prop_sections: list[dict[str, str]] = []
            if proposal_rev and proposal_rev.content_json:
                prop_sections = proposal_rev.content_json.get("sections", [])
            # Merge execution plan sections as supplementary context
            if exec_plan_rev and exec_plan_rev.content_json:
                exec_sections = exec_plan_rev.content_json.get("sections", [])
                for es in exec_sections:
                    prop_sections.append({
                        "name": f"[수행계획] {es.get('name', '')}",
                        "text": es.get("text", ""),
                    })

            gen_result = await asyncio.to_thread(
                _run_ppt_generation,
                rfx_result=snap.analysis_json,
                proposal_sections=prop_sections if prop_sections else None,
                company_context=company_context,
                style_profile_md=style_profile_md,
                company_name=company_name,
                target_slide_count=req.target_slide_count,
                duration_min=req.duration_min,
                qna_count=req.qna_count,
            )
            sections = []
            content_json_extra = {
                "slides": gen_result.slides_metadata or [],
                "qna_pairs": [
                    {"question": q.question, "answer": q.answer, "category": q.category}
                    for q in (gen_result.qna_pairs or [])
                ],
                "slide_count": gen_result.slide_count,
                "total_duration_min": gen_result.total_duration_min,
            }
            quality_issues = []
            generation_time_sec = getattr(gen_result, 'generation_time_sec', None)

            # Persist .pptx as DocumentAsset
            if gen_result.pptx_path and os.path.isfile(gen_result.pptx_path):
                import shutil
                ppt_dest_dir = os.path.join(_PPT_ASSET_DIR, project_id)
                os.makedirs(ppt_dest_dir, exist_ok=True)
                ppt_filename = os.path.basename(gen_result.pptx_path)
                ppt_dest = os.path.join(ppt_dest_dir, ppt_filename)
                shutil.copy2(gen_result.pptx_path, ppt_dest)

                ppt_asset = DocumentAsset(
                    org_id=user.org_id,
                    project_id=project_id,
                    asset_type="pptx",
                    storage_uri=f"local://ppt_assets/{project_id}/{ppt_filename}",
                    upload_status="uploaded",
                    original_filename=ppt_filename,
                    mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    size_bytes=os.path.getsize(ppt_dest),
                )
                db.add(ppt_asset)
                await db.flush()
        else:
            gen_result = await asyncio.to_thread(
                _run_proposal_generation,
                rfx_result=snap.analysis_json,
                company_context=company_context,
                style_profile_md=style_profile_md,
                total_pages=req.total_pages,
                company_name=company_name,
            )
            sections = gen_result.sections or []
            content_json_extra = {}
            quality_issues = [str(i) for i in (gen_result.quality_issues or [])]
            generation_time_sec = getattr(gen_result, 'generation_time_sec', None)

        # Extract quality gate report if available (proposal orchestrator provides it)
        quality_gate_report = getattr(gen_result, 'quality_report', None) or {}

        # --- Create DocumentRevision ---
        # Compute revision number
        rev_count_result = await db.execute(
            select(DocumentRevision.revision_number)
            .where(
                DocumentRevision.project_id == project_id,
                DocumentRevision.doc_type == req.doc_type,
            )
            .order_by(DocumentRevision.revision_number.desc())
            .limit(1)
        )
        prev_rev = rev_count_result.scalar_one_or_none() or 0

        revision = DocumentRevision(
            org_id=user.org_id,
            project_id=project_id,
            doc_type=req.doc_type,
            run_id=run.id,
            revision_number=prev_rev + 1,
            source="ai_generated",
            status="draft",
            title=snap.analysis_json.get("title", {
                "proposal": "제안서", "execution_plan": "수행계획서",
                "track_record": "실적기술서", "presentation": "발표자료",
            }.get(req.doc_type, "문서")),
            content_json={
                "sections": [
                    {"name": name, "text": text}
                    for name, text in sections
                ],
                **content_json_extra,
            },
            content_schema={
                "proposal": "proposal_sections_v1",
                "execution_plan": "execution_plan_tasks_v1",
                "track_record": "track_record_entries_v1",
                "presentation": "presentation_slides_v1",
            }.get(req.doc_type, "unknown_v1"),
            quality_report_json={
                "issues": quality_issues,
                **quality_gate_report,
            },
            created_by=user.username,
        )
        db.add(revision)
        await db.flush()

        # Update run status
        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)

        # Update package item status if applicable
        pkg_result = await db.execute(
            select(ProjectPackageItem).where(
                ProjectPackageItem.project_id == project_id,
                ProjectPackageItem.generation_target == req.doc_type,
            )
        )
        for pkg_item in pkg_result.scalars().all():
            pkg_item.status = "generated"

    except Exception as exc:
        logger.exception("Document generation failed for project=%s doc_type=%s", project_id, req.doc_type)
        run.status = "failed"
        run.completed_at = datetime.now(timezone.utc)
        run.error_message = str(exc)[:1000]
        db.add(AuditLog(
            org_id=user.org_id,
            user_id=user.username,
            project_id=project_id,
            action="document_generation_failed",
            target_type="document_run",
            target_id=run.id,
            detail_json={"error": str(exc)[:500], **generation_contract},
        ))
        await db.commit()
        raise HTTPException(500, "문서 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")

    # Update ProjectCurrentDocument (upsert)
    from services.web_app.db.models.document import ProjectCurrentDocument
    current_doc = (await db.execute(
        select(ProjectCurrentDocument).where(
            ProjectCurrentDocument.project_id == project_id,
            ProjectCurrentDocument.doc_type == req.doc_type,
        )
    )).scalar_one_or_none()
    if current_doc:
        current_doc.current_revision_id = revision.id
    else:
        db.add(ProjectCurrentDocument(
            org_id=user.org_id,
            project_id=project_id,
            doc_type=req.doc_type,
            current_revision_id=revision.id,
        ))

    # Audit log
    db.add(AuditLog(
        org_id=user.org_id,
        user_id=user.username,
        project_id=project_id,
        action="document_generated",
        target_type="document_run",
        target_id=run.id,
        detail_json=generation_contract,
    ))

    await db.commit()

    return {
        "run_id": run.id,
        "revision_id": revision.id,
        "status": run.status,
        "generation_contract": generation_contract,
        "sections_count": len(sections),
        "generation_time_sec": generation_time_sec,
    }


@router.get("/projects/{project_id}/documents/{doc_type}/current")
async def get_current_revision(
    project_id: str,
    doc_type: Literal["proposal", "execution_plan", "track_record", "presentation"],
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """Get the current revision for a document type in a Studio project.

    Returns revision metadata + sections content for preview.
    """
    await _require_studio_project_access(project_id, "viewer", user, db)

    from services.web_app.db.models.document import ProjectCurrentDocument

    current = (await db.execute(
        select(ProjectCurrentDocument).where(
            ProjectCurrentDocument.project_id == project_id,
            ProjectCurrentDocument.doc_type == doc_type,
        )
    )).scalar_one_or_none()
    if current is None:
        raise HTTPException(404, "현재 리비전이 없습니다. 먼저 문서를 생성해주세요.")

    revision = (await db.execute(
        select(DocumentRevision).where(DocumentRevision.id == current.current_revision_id)
    )).scalar_one_or_none()
    if revision is None:
        raise HTTPException(404, "리비전을 찾을 수 없습니다.")

    content = revision.content_json or {}

    return {
        "revision_id": revision.id,
        "revision_number": revision.revision_number,
        "doc_type": revision.doc_type,
        "source": revision.source,
        "status": revision.status,
        "title": revision.title,
        "sections": content.get("sections", []),
        "records": content.get("records", []),
        "personnel": content.get("personnel", []),
        "slides": content.get("slides", []),
        "qna_pairs": content.get("qna_pairs", []),
        "slide_count": content.get("slide_count"),
        "total_duration_min": content.get("total_duration_min"),
        "quality_report": revision.quality_report_json,
        "created_at": revision.created_at.isoformat() if revision.created_at else None,
    }


# --- Proposal review/relearn schemas ---

class EditedSection(BaseModel):
    name: str = Field(min_length=1)
    text: str


class SaveEditedProposalRequest(BaseModel):
    sections: list[EditedSection] = Field(min_length=1)


# --- Proposal review/relearn endpoints ---

@router.post("/projects/{project_id}/documents/proposal/edited")
async def save_edited_proposal(
    project_id: str,
    req: SaveEditedProposalRequest,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """Save user-edited proposal as a new revision (source=user_edited)."""
    await _require_studio_project_access(project_id, "editor", user, db)

    from services.web_app.db.models.document import ProjectCurrentDocument

    # Get current AI-generated revision to determine next version
    current = (await db.execute(
        select(ProjectCurrentDocument).where(
            ProjectCurrentDocument.project_id == project_id,
            ProjectCurrentDocument.doc_type == "proposal",
        )
    )).scalar_one_or_none()
    if current is None:
        raise HTTPException(400, "먼저 제안서를 생성해주세요.")

    prev_rev = (await db.execute(
        select(DocumentRevision).where(DocumentRevision.id == current.current_revision_id)
    )).scalar_one()

    # Compute next revision number
    ver_result = await db.execute(
        select(DocumentRevision.revision_number)
        .where(DocumentRevision.project_id == project_id, DocumentRevision.doc_type == "proposal")
        .order_by(DocumentRevision.revision_number.desc())
        .limit(1)
    )
    prev_num = ver_result.scalar_one_or_none() or 0

    revision = DocumentRevision(
        org_id=user.org_id,
        project_id=project_id,
        doc_type="proposal",
        run_id=None,
        derived_from_revision_id=prev_rev.id,
        revision_number=prev_num + 1,
        source="user_edited",
        status="draft",
        title=prev_rev.title,
        content_json={"sections": [{"name": s.name, "text": s.text} for s in req.sections]},
        content_schema="proposal_sections_v1",
        created_by=user.username,
    )
    db.add(revision)
    await db.flush()

    # Update current pointer
    current.current_revision_id = revision.id

    await db.commit()

    return {
        "revision_id": revision.id,
        "revision_number": revision.revision_number,
        "source": revision.source,
    }


@router.get("/projects/{project_id}/documents/proposal/diff")
async def get_proposal_diff(
    project_id: str,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """Get section-level diff between latest AI-generated and user-edited revisions."""
    await _require_studio_project_access(project_id, "viewer", user, db)

    ai_rev, edited_rev, original_sections, edited_sections, all_names = await _get_proposal_diff_pair(db, project_id)

    diff_sections = []
    changed_count = 0
    total_original_len = 0
    total_edit_distance = 0

    for name in all_names:
        orig = original_sections.get(name, "")
        edit = edited_sections.get(name, "")
        changed = orig != edit
        if changed:
            changed_count += 1
        total_original_len += len(orig) or 1
        total_edit_distance += _simple_edit_distance(orig, edit)
        diff_sections.append({
            "name": name,
            "original": orig,
            "edited": edit,
            "changed": changed,
        })

    edit_rate = round(total_edit_distance / max(total_original_len, 1), 3)

    return {
        "sections": diff_sections,
        "changed_sections_count": changed_count,
        "total_sections": len(all_names),
        "edit_rate": min(edit_rate, 1.0),
    }


@router.post("/projects/{project_id}/relearn")
async def relearn_proposal_style(
    project_id: str,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """Derive a new project-scoped style skill from edited proposal diff.

    Takes the diff between AI-generated and user-edited proposal,
    appends edit patterns to the pinned style's profile_md_content,
    and creates a new derived ProjectStyleSkill.
    """
    await _require_studio_project_access(project_id, "editor", user, db)

    # Load project
    project = (await db.execute(
        select(BidProject).where(BidProject.id == project_id)
    )).scalar_one()

    if not project.pinned_style_skill_id:
        raise HTTPException(400, "핀 설정된 스타일이 없습니다.")

    # Get pinned style
    pinned = (await db.execute(
        select(ProjectStyleSkill).where(ProjectStyleSkill.id == project.pinned_style_skill_id)
    )).scalar_one_or_none()
    if pinned is None:
        raise HTTPException(404, "핀 설정된 스타일을 찾을 수 없습니다.")

    # Get diff pair (shared helper)
    _, _, original_sections, edited_sections, all_names = await _get_proposal_diff_pair(db, project_id)

    # Build edit summary for profile augmentation — iterate union of keys
    edit_notes: list[str] = []
    for name in all_names:
        orig = original_sections.get(name, "")
        edit = edited_sections.get(name, "")
        if orig != edit:
            orig_sample = orig[:150].replace("\n", " ")
            edit_sample = edit[:150].replace("\n", " ")
            edit_notes.append(
                f"- [{name}] 수정됨\n"
                f"  원본: \"{orig_sample}{'...' if len(orig) > 150 else ''}\"\n"
                f"  수정: \"{edit_sample}{'...' if len(edit) > 150 else ''}\""
            )

    if not edit_notes:
        raise HTTPException(400, "편집된 내용이 없습니다.")

    # Augment profile with edit patterns
    base_profile = pinned.profile_md_content or ""
    augmented_profile = (
        base_profile + "\n\n"
        "## 사용자 수정 패턴 (자동 학습)\n"
        + "\n".join(edit_notes) + "\n"
        "위 수정 패턴을 향후 제안서 생성 시 반영하세요."
    )

    # Compute next version
    ver_result = await db.execute(
        select(ProjectStyleSkill.version)
        .where(ProjectStyleSkill.project_id == project_id)
        .order_by(ProjectStyleSkill.version.desc())
        .limit(1)
    )
    prev_version = ver_result.scalar_one_or_none() or 0

    new_skill = ProjectStyleSkill(
        project_id=project_id,
        org_id=user.org_id,
        version=prev_version + 1,
        name=f"{pinned.name} (학습 v{prev_version + 1})",
        source_type="derived",
        derived_from_id=pinned.id,
        profile_md_content=augmented_profile,
        style_json=pinned.style_json,
    )
    db.add(new_skill)
    await db.flush()

    db.add(AuditLog(
        org_id=user.org_id,
        user_id=user.username,
        project_id=project_id,
        action="style_skill_relearned",
        target_type="project_style_skill",
        target_id=new_skill.id,
        detail_json={
            "derived_from_id": pinned.id,
            "edit_notes_count": len(edit_notes),
        },
    ))

    await db.commit()

    return {
        "new_skill_id": new_skill.id,
        "new_skill_version": new_skill.version,
        "derived_from_id": pinned.id,
        "edit_notes_count": len(edit_notes),
    }


async def _get_proposal_diff_pair(
    db: AsyncSession, project_id: str,
) -> tuple[DocumentRevision, DocumentRevision, dict[str, str], dict[str, str], list[str]]:
    """Fetch latest AI-generated and user-edited proposal revisions.

    Returns: (ai_rev, edited_rev, original_sections, edited_sections, all_section_names)
    """
    ai_rev = (await db.execute(
        select(DocumentRevision)
        .where(
            DocumentRevision.project_id == project_id,
            DocumentRevision.doc_type == "proposal",
            DocumentRevision.source == "ai_generated",
        )
        .order_by(DocumentRevision.revision_number.desc())
        .limit(1)
    )).scalar_one_or_none()

    edited_rev = (await db.execute(
        select(DocumentRevision)
        .where(
            DocumentRevision.project_id == project_id,
            DocumentRevision.doc_type == "proposal",
            DocumentRevision.source == "user_edited",
        )
        .order_by(DocumentRevision.revision_number.desc())
        .limit(1)
    )).scalar_one_or_none()

    if ai_rev is None or edited_rev is None:
        raise HTTPException(400, "원본과 편집본이 모두 필요합니다.")

    original_sections = {s["name"]: s["text"] for s in (ai_rev.content_json or {}).get("sections", [])}
    edited_sections = {s["name"]: s["text"] for s in (edited_rev.content_json or {}).get("sections", [])}
    all_names = list(dict.fromkeys(list(original_sections.keys()) + list(edited_sections.keys())))

    return ai_rev, edited_rev, original_sections, edited_sections, all_names


def _simple_edit_distance(a: str, b: str) -> int:
    """Character-level edit distance approximation (fast, not Levenshtein)."""
    if a == b:
        return 0
    # Use length difference + changed character count as approximation
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    changes = len(longer) - len(shorter)
    for i in range(len(shorter)):
        if shorter[i] != longer[i]:
            changes += 1
    return changes


# --- Package item lifecycle schemas ---

_VALID_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "missing": {"waived"},  # uploaded only via attach_evidence
    "ready_to_generate": {"generated"},
    "generated": {"verified"},
    "uploaded": {"verified"},
    "verified": set(),  # terminal
    "waived": {"missing"},  # can un-waive
}

_COMPLETED_STATUSES = frozenset({"generated", "uploaded", "verified"})


class UpdatePackageItemStatusRequest(BaseModel):
    status: Literal["missing", "waived", "verified"]  # uploaded only via attach_evidence


_EVIDENCE_STORAGE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "package_evidence")


# --- Package item lifecycle endpoints ---

@router.patch("/projects/{project_id}/package-items/{item_id}/status")
async def update_package_item_status(
    project_id: str,
    item_id: str,
    req: UpdatePackageItemStatusRequest,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """Update package item status with server-enforced transition rules."""
    await _require_studio_project_access(project_id, "editor", user, db)

    item = (await db.execute(
        select(ProjectPackageItem).where(
            ProjectPackageItem.id == item_id,
            ProjectPackageItem.project_id == project_id,
        )
    )).scalar_one_or_none()
    if item is None:
        raise HTTPException(404, "패키지 항목을 찾을 수 없습니다")

    allowed = _VALID_STATUS_TRANSITIONS.get(item.status, set())
    if req.status not in allowed:
        raise HTTPException(
            400,
            f"'{item.status}' → '{req.status}' 상태 전환은 허용되지 않습니다",
        )

    item.status = req.status
    await db.commit()

    return {"id": item.id, "status": item.status, "document_code": item.document_code}


@router.post("/projects/{project_id}/package-items/{item_id}/evidence")
async def attach_evidence(
    project_id: str,
    item_id: str,
    file: UploadFile = File(...),
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """Attach evidence file to a package item via multipart upload.

    Saves file to local storage, creates DocumentAsset, links via asset_id.
    """
    await _require_studio_project_access(project_id, "editor", user, db)

    item = (await db.execute(
        select(ProjectPackageItem).where(
            ProjectPackageItem.id == item_id,
            ProjectPackageItem.project_id == project_id,
        )
    )).scalar_one_or_none()
    if item is None:
        raise HTTPException(404, "패키지 항목을 찾을 수 없습니다")

    # Guard: only evidence/administrative/price categories accept evidence
    if item.package_category == "generated_document":
        raise HTTPException(400, "자동 생성 문서에는 증빙을 첨부할 수 없습니다")

    # Guard: only missing items accept evidence
    if item.status != "missing":
        raise HTTPException(400, f"'{item.status}' 상태의 항목에는 증빙을 첨부할 수 없습니다")

    # Read file content
    content = await file.read()
    _MAX_EVIDENCE_SIZE = 50 * 1024 * 1024  # 50MB
    _ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".hwp", ".hwpx", ".xlsx", ".xls", ".pptx", ".ppt", ".jpg", ".jpeg", ".png", ".gif", ".zip"}
    if len(content) == 0:
        raise HTTPException(400, "빈 파일은 첨부할 수 없습니다")
    if len(content) > _MAX_EVIDENCE_SIZE:
        raise HTTPException(400, f"파일 크기가 제한({_MAX_EVIDENCE_SIZE // (1024*1024)}MB)을 초과합니다")

    # Validate file extension
    import pathlib
    file_ext = pathlib.Path(file.filename or "").suffix.lower()
    if file_ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"허용되지 않는 파일 형식입니다: {file_ext}")

    # Sanitize filename + generate storage path
    import re as _re
    original_filename = file.filename or "unnamed"
    safe_name = _re.sub(r"[^a-zA-Z0-9가-힣._-]", "_", original_filename)[:100]
    if not safe_name:
        safe_name = "file"
    # Add unique suffix to prevent collisions
    import hashlib
    content_hash = hashlib.sha256(content).hexdigest()[:12]
    stored_name = f"{content_hash}_{safe_name}"

    # Save to local storage
    storage_subdir = os.path.join("package_evidence", project_id, item_id)
    storage_abs_dir = os.path.join(_EVIDENCE_STORAGE_DIR, project_id, item_id)
    os.makedirs(storage_abs_dir, exist_ok=True)

    file_path = os.path.join(storage_abs_dir, stored_name)
    with open(file_path, "wb") as f:
        f.write(content)

    storage_uri = f"local://{storage_subdir}/{stored_name}"

    # Create DocumentAsset
    asset = DocumentAsset(
        org_id=user.org_id,
        project_id=project_id,
        asset_type="original",
        storage_uri=storage_uri,
        upload_status="uploaded",
        original_filename=original_filename,
        mime_type=file.content_type,
        size_bytes=len(content),
        content_hash=content_hash,
    )
    db.add(asset)
    await db.flush()

    # Link and transition
    item.asset_id = asset.id
    item.status = "uploaded"

    db.add(AuditLog(
        org_id=user.org_id,
        user_id=user.username,
        project_id=project_id,
        action="evidence_attached",
        target_type="project_package_item",
        target_id=item_id,
        detail_json={
            "asset_id": asset.id,
            "filename": original_filename,
            "size_bytes": len(content),
        },
    ))

    await db.commit()

    return {
        "asset_id": asset.id,
        "status": item.status,
        "document_code": item.document_code,
    }


@router.get("/projects/{project_id}/package-completeness")
async def get_package_completeness(
    project_id: str,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """Get package completeness summary (server-computed)."""
    await _require_studio_project_access(project_id, "viewer", user, db)

    result = await db.execute(
        select(ProjectPackageItem).where(ProjectPackageItem.project_id == project_id)
    )
    items = result.scalars().all()

    total = len(items)
    completed = sum(1 for i in items if i.status in _COMPLETED_STATUSES)
    waived = sum(1 for i in items if i.status == "waived")
    required_items = [i for i in items if i.required]
    required_remaining = sum(1 for i in required_items if i.status not in _COMPLETED_STATUSES and i.status != "waived")
    completeness_pct = round((completed + waived) / total * 100, 1) if total > 0 else 0

    return {
        "total": total,
        "completed": completed,
        "waived": waived,
        "required_remaining": required_remaining,
        "completeness_pct": completeness_pct,
    }


@router.get("/projects/{project_id}/documents/presentation/download")
async def download_presentation(
    project_id: str,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """Download the generated .pptx file for a project."""
    from fastapi.responses import FileResponse

    await _require_studio_project_access(project_id, "viewer", user, db)

    # Find the latest pptx asset for this project
    asset = (await db.execute(
        select(DocumentAsset)
        .where(
            DocumentAsset.project_id == project_id,
            DocumentAsset.asset_type == "pptx",
        )
        .order_by(DocumentAsset.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    if asset is None:
        raise HTTPException(404, "발표자료 파일이 없습니다. 먼저 발표자료를 생성해주세요.")

    # Resolve file path with traversal guard
    local_path = asset.storage_uri.replace("local://", "")
    file_path = os.path.join(_PPT_ASSET_DIR, *local_path.split("ppt_assets/", 1)[-1].split("/"))
    resolved = os.path.realpath(file_path)
    if not resolved.startswith(os.path.realpath(_PPT_ASSET_DIR)):
        raise HTTPException(403, "잘못된 파일 경로입니다")
    if not os.path.isfile(resolved):
        raise HTTPException(404, "서버에서 파일을 찾을 수 없습니다")

    return FileResponse(
        path=resolved,
        filename=asset.original_filename or "presentation.pptx",
        media_type=asset.mime_type or "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )


@router.get("/projects/{project_id}/package-items/{item_id}/evidence/download")
async def download_evidence(
    project_id: str,
    item_id: str,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """Download evidence file attached to a package item."""
    from fastapi.responses import FileResponse

    await _require_studio_project_access(project_id, "viewer", user, db)

    item = (await db.execute(
        select(ProjectPackageItem).where(
            ProjectPackageItem.id == item_id,
            ProjectPackageItem.project_id == project_id,
        )
    )).scalar_one_or_none()
    if item is None:
        raise HTTPException(404, "패키지 항목을 찾을 수 없습니다")
    if not item.asset_id:
        raise HTTPException(404, "첨부된 파일이 없습니다")

    asset = (await db.execute(
        select(DocumentAsset).where(DocumentAsset.id == item.asset_id)
    )).scalar_one_or_none()
    if asset is None:
        raise HTTPException(404, "파일 자산을 찾을 수 없습니다")

    # Resolve local file path with traversal guard
    local_path = asset.storage_uri.replace("local://", "")
    file_path = os.path.join(_EVIDENCE_STORAGE_DIR, *local_path.split("package_evidence/", 1)[-1].split("/"))
    resolved = os.path.realpath(file_path)
    if not resolved.startswith(os.path.realpath(_EVIDENCE_STORAGE_DIR)):
        raise HTTPException(403, "잘못된 파일 경로입니다")
    if not os.path.isfile(resolved):
        raise HTTPException(404, "서버에서 파일을 찾을 수 없습니다")

    return FileResponse(
        path=resolved,
        filename=asset.original_filename or "download",
        media_type=asset.mime_type or "application/octet-stream",
    )


async def _build_company_context(db: AsyncSession, project_id: str, org_id: str) -> tuple[str, int, str | None]:
    """Build effective company context from shared + staging assets.

    Returns (context_narrative, total_asset_count, company_name).
    """
    parts: list[str] = []
    asset_count = 0
    company_name: str | None = None

    # Shared profile
    profile = (await db.execute(
        select(CompanyProfile).where(CompanyProfile.org_id == org_id)
    )).scalar_one_or_none()
    if profile:
        company_name = profile.company_name
        asset_count += 1
        items = []
        if profile.company_name:
            items.append(f"회사명: {profile.company_name}")
        if profile.business_type:
            items.append(f"업종: {profile.business_type}")
        if profile.headcount:
            items.append(f"직원 수: {profile.headcount}명")
        if items:
            parts.append("## 회사 기본정보\n" + "\n".join(f"- {i}" for i in items))

    # Shared track records
    shared_tracks = (await db.execute(
        select(CompanyTrackRecord).where(CompanyTrackRecord.org_id == org_id)
    )).scalars().all()
    for t in shared_tracks:
        asset_count += 1
        parts.append(f"- 실적: {t.project_name or '(무제)'} ({t.client_name or '미상'})")

    # Shared personnel
    shared_personnel = (await db.execute(
        select(CompanyPersonnel).where(CompanyPersonnel.org_id == org_id)
    )).scalars().all()
    for p in shared_personnel:
        asset_count += 1
        parts.append(f"- 인력: {p.name or '(무명)'} / {p.role or ''} / {p.years_experience or 0}년")

    # Project staging assets (not yet promoted)
    staging = (await db.execute(
        select(ProjectCompanyAsset)
        .where(
            ProjectCompanyAsset.project_id == project_id,
            ProjectCompanyAsset.promoted_at.is_(None),
        )
        .order_by(ProjectCompanyAsset.created_at)
    )).scalars().all()
    for a in staging:
        asset_count += 1
        content = a.content_json
        if a.asset_category == "track_record":
            parts.append(f"- 실적(스테이징): {content.get('project_name', '(무제)')} ({content.get('client_name', '')})")
        elif a.asset_category == "personnel":
            parts.append(f"- 인력(스테이징): {content.get('name', '(무명)')} / {content.get('role', '')}")
        elif a.asset_category == "profile":
            if content.get("company_name"):
                company_name = content["company_name"]  # staging overrides shared
                parts.insert(0, f"## 회사 기본정보 (스테이징)\n- 회사명: {content['company_name']}")

    return "\n".join(parts), asset_count, company_name


def _run_proposal_generation(
    rfx_result: dict[str, Any],
    company_context: str,
    style_profile_md: str,
    total_pages: int,
    company_name: str | None = None,
) -> Any:
    """Run proposal generation using existing orchestrator.

    This function runs in a thread (called via asyncio.to_thread).
    """
    import tempfile
    from proposal_orchestrator import generate_proposal as _gen

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다")

    # Write style profile to temp dir for orchestrator (auto-cleaned)
    if style_profile_md:
        with tempfile.TemporaryDirectory(prefix="studio_style_") as style_dir:
            with open(os.path.join(style_dir, "profile.md"), "w", encoding="utf-8") as f:
                f.write(style_profile_md)
            return _gen(
                rfx_result=rfx_result,
                company_context=company_context,
                company_name=company_name,
                total_pages=total_pages,
                api_key=api_key,
                company_skills_dir=style_dir,
            )

    return _gen(
        rfx_result=rfx_result,
        company_context=company_context,
        company_name=company_name,
        total_pages=total_pages,
        api_key=api_key,
        company_skills_dir="",
    )


def _run_wbs_generation(
    rfx_result: dict[str, Any],
    company_context: str,
    style_profile_md: str,
    company_name: str | None = None,
) -> Any:
    """Run WBS/execution plan generation using existing orchestrator.

    This function runs in a thread (called via asyncio.to_thread).
    """
    import tempfile
    from wbs_orchestrator import generate_wbs

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다")

    if style_profile_md:
        with tempfile.TemporaryDirectory(prefix="studio_wbs_style_") as style_dir:
            with open(os.path.join(style_dir, "profile.md"), "w", encoding="utf-8") as f:
                f.write(style_profile_md)
            return generate_wbs(
                rfx_result=rfx_result,
                company_session_context=company_context,
                api_key=api_key,
                company_skills_dir=style_dir,
            )

    return generate_wbs(
        rfx_result=rfx_result,
        company_session_context=company_context,
        api_key=api_key,
        company_skills_dir="",
    )


def _run_track_record_generation(
    rfx_result: dict[str, Any],
    company_context: str,
    style_profile_md: str,
    company_name: str | None = None,
) -> Any:
    """Run track record generation using existing orchestrator."""
    import tempfile
    from track_record_orchestrator import generate_track_record_doc

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다")

    if style_profile_md:
        with tempfile.TemporaryDirectory(prefix="studio_tr_style_") as style_dir:
            with open(os.path.join(style_dir, "profile.md"), "w", encoding="utf-8") as f:
                f.write(style_profile_md)
            return generate_track_record_doc(
                rfx_result=rfx_result,
                company_name=company_name,
                api_key=api_key,
                company_skills_dir=style_dir,
            )

    return generate_track_record_doc(
        rfx_result=rfx_result,
        company_name=company_name,
        api_key=api_key,
        company_skills_dir="",
    )


def _run_ppt_generation(
    rfx_result: dict[str, Any],
    proposal_sections: list[dict[str, str]] | None,
    company_context: str,
    style_profile_md: str,
    company_name: str | None = None,
    target_slide_count: int = 15,
    duration_min: int = 25,
    qna_count: int = 10,
) -> Any:
    """Run PPT generation using existing ppt_orchestrator."""
    import tempfile
    from ppt_orchestrator import generate_ppt

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다")

    if style_profile_md:
        with tempfile.TemporaryDirectory(prefix="studio_ppt_style_") as style_dir:
            with open(os.path.join(style_dir, "profile.md"), "w", encoding="utf-8") as f:
                f.write(style_profile_md)
            return generate_ppt(
                rfx_result=rfx_result,
                proposal_sections=proposal_sections,
                company_name=company_name or "",
                target_slide_count=target_slide_count,
                duration_min=duration_min,
                qna_count=qna_count,
                api_key=api_key,
                company_skills_dir=style_dir,
            )

    return generate_ppt(
        rfx_result=rfx_result,
        proposal_sections=proposal_sections,
        company_name=company_name or "",
        target_slide_count=target_slide_count,
        duration_min=duration_min,
        qna_count=qna_count,
        api_key=api_key,
        company_skills_dir="",
    )


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


# --- Account deletion ---

@router.delete("/account")
async def request_account_deletion(
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """Request account deletion. Deactivates membership and logs the request."""
    from services.web_app.db.models.org import Membership

    result = await db.execute(
        select(Membership).where(
            Membership.user_id == user.username,
            Membership.is_active == True,  # noqa: E712
        )
    )
    for m in result.scalars().all():
        m.is_active = False

    db.add(AuditLog(
        org_id=user.org_id,
        user_id=user.username,
        action="account_deletion_requested",
        target_type="user",
        target_id=user.username,
    ))
    await db.commit()
    return {"status": "deleted", "message": "계정이 비활성화되었습니다"}
