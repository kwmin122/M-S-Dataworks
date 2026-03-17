from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

logger = logging.getLogger(__name__)
from sqlalchemy.ext.asyncio import AsyncSession

from services.web_app.db.engine import get_async_session
from services.web_app.db.models.document import DocumentAsset
from services.web_app.db.models.audit import AuditLog
from services.web_app.storage.s3 import get_s3_client
from services.web_app.api.deps import CurrentUser, resolve_org_membership, require_project_access

router = APIRouter(prefix="/api/assets", tags=["assets"])


def check_download_policy(asset) -> None:
    """Enforce download readiness policy based on asset origin.

    Generated assets (have revision_id): require "verified" — integrity matters for AI output.
    Source uploads (no revision_id): allow "uploaded" — user-uploaded, integrity is their responsibility.

    Raises HTTPException(409) if asset is not ready for download.
    Extracted as pure function for testability.
    """
    if asset.revision_id:
        if asset.upload_status != "verified":
            raise HTTPException(
                status_code=409,
                detail="생성 문서 검증 대기 중입니다. 잠시 후 다시 시도하세요.",
            )
    else:
        if asset.upload_status not in ("uploaded", "verified"):
            raise HTTPException(status_code=409, detail="파일 업로드 진행 중입니다")


@router.get("/{asset_id}/download")
async def download_asset(
    asset_id: str,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """ACL-verified asset download via presigned URL."""
    result = await db.execute(
        select(DocumentAsset).where(
            DocumentAsset.id == asset_id,
            DocumentAsset.org_id == user.org_id,
            DocumentAsset.is_deleted == False,
        )
    )
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다")

    # ACL: viewer or above can download project assets
    if asset.project_id:
        await require_project_access(asset.project_id, "viewer", user, db)

    # Download readiness check (policy extracted for testability)
    check_download_policy(asset)

    s3 = get_s3_client()
    key = s3.parse_storage_uri(asset.storage_uri)
    url = s3.generate_presigned_download_url(
        key=key,
        original_filename=asset.original_filename,
        expires_in=3600,
    )

    # Audit log
    audit = AuditLog(
        org_id=user.org_id,
        user_id=user.username,
        project_id=asset.project_id,
        action="download_asset",
        target_type="document_asset",
        target_id=asset_id,
    )
    db.add(audit)
    await db.commit()

    return {"download_url": url, "filename": asset.original_filename}


@router.post("/{asset_id}/confirm-upload")
async def confirm_upload(
    asset_id: str,
    content_hash: str | None = None,
    size_bytes: int | None = None,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """Client confirms upload completion. Transitions upload_status → uploaded → verified."""
    result = await db.execute(
        select(DocumentAsset).where(
            DocumentAsset.id == asset_id,
            DocumentAsset.org_id == user.org_id,
        )
    )
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=404)

    # ACL: editor or above can confirm uploads
    if asset.project_id:
        await require_project_access(asset.project_id, "editor", user, db)

    if asset.upload_status not in ("presigned_issued", "uploading"):
        raise HTTPException(status_code=409, detail=f"Invalid status: {asset.upload_status}")

    # Step 1: Verify file exists in S3 + get server-side metadata
    s3 = get_s3_client()
    try:
        key = s3.parse_storage_uri(asset.storage_uri)
        head = s3.head_object(key)
        actual_size = head.get("ContentLength", 0)
        s3_etag = head.get("ETag", "").strip('"')
    except Exception:
        asset.upload_status = "failed"
        await db.commit()
        raise HTTPException(status_code=422, detail="S3 파일 확인 실패")

    # Step 2: Transition to "uploaded" (S3 head confirmed file exists)
    asset.upload_status = "uploaded"
    asset.size_bytes = actual_size
    await db.flush()

    # Step 3: Integrity verification
    if s3_etag:
        asset.content_hash = f"etag:{s3_etag}"
        asset.upload_status = "verified"
        if content_hash:
            asset.content_hash = f"etag:{s3_etag},client:{content_hash}"
            if content_hash != s3_etag:
                logger.info(
                    "ETag/client hash differ for asset %s (expected for multipart): "
                    "etag=%s, client=%s", asset_id, s3_etag, content_hash,
                )
    else:
        logger.warning("No ETag from S3 for asset %s — leaving as 'uploaded'", asset_id)

    await db.commit()

    return {
        "status": asset.upload_status,
        "size_bytes": actual_size,
        "content_hash": asset.content_hash,
    }
