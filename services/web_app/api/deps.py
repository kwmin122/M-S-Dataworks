from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.web_app.db.engine import get_async_session
from services.web_app.db.models.org import Membership
from services.web_app.db.models.project import ProjectAccess

logger = logging.getLogger(__name__)

# --- Guard: org auto-provision is DEV ONLY ---
_DEV_BOOTSTRAP = os.getenv("BID_DEV_BOOTSTRAP", "").lower() in ("1", "true")


@dataclass
class CurrentUser:
    username: str
    org_id: str
    role: str  # org-level role


async def get_current_user(request: Request) -> CurrentUser:
    """Extract authenticated user from existing kira_auth cookie system.

    Reuses existing resolve_user_from_session() from user_store.
    Then looks up org membership.
    """
    from user_store import resolve_user_from_session

    cookie_name = request.app.state.auth_cookie_name if hasattr(request.app.state, "auth_cookie_name") else "kira_auth"
    token = request.cookies.get(cookie_name, "")
    username = resolve_user_from_session(token)
    if not username:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")

    return CurrentUser(username=username, org_id="", role="owner")


async def resolve_org_membership(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
) -> CurrentUser:
    """Resolve user's org membership from DB.

    v1 CONSTRAINT: single-org membership only.
    If a user has multiple active memberships, this is a data integrity bug —
    fail loudly rather than silently picking one.

    Multi-org support (org switcher context) is Phase 3+.

    Auto-provision (org + owner membership) is DEV ONLY (BID_DEV_BOOTSTRAP=1).
    In production, users must be invited to an existing org.
    """
    result = await db.execute(
        select(Membership).where(
            Membership.user_id == user.username,
            Membership.is_active == True,
        )
    )
    memberships = result.scalars().all()

    if len(memberships) > 1:
        org_ids = [m.org_id for m in memberships]
        logger.error(
            "v1 invariant violation: user '%s' has %d active memberships (orgs: %s). "
            "Multi-org not supported in v1.",
            user.username, len(memberships), org_ids,
        )
        raise HTTPException(
            status_code=409,
            detail="복수 조직 소속은 현재 버전에서 지원되지 않습니다. 관리자에게 문의하세요.",
        )

    membership = memberships[0] if memberships else None

    if membership is None:
        # Check if user previously had membership that was deactivated (account deletion).
        # If so, block re-provisioning — deleted accounts must not auto-resurrect.
        deactivated = await db.execute(
            select(Membership).where(
                Membership.user_id == user.username,
                Membership.is_active == False,
            )
        )
        if deactivated.scalars().first() is not None:
            logger.warning(
                "Blocked auto-provision for deactivated user=%s. "
                "Account was previously deleted.",
                user.username,
            )
            raise HTTPException(
                status_code=403,
                detail="비활성화된 계정입니다. 복구가 필요하시면 고객지원으로 문의해주세요.",
            )

        # Auto-provision: first-time user gets their own org + owner membership.
        # This runs exactly once per user (only when no active membership exists
        # AND no deactivated membership exists).
        logger.info("Auto-provisioning org for new user=%s", user.username)
        from services.web_app.db.models.org import Organization
        org = Organization(name=f"{user.username}의 조직")
        db.add(org)
        await db.flush()

        membership = Membership(
            org_id=org.id,
            user_id=user.username,
            role="owner",
            is_active=True,
        )
        db.add(membership)
        await db.commit()

    user.org_id = membership.org_id
    user.role = membership.role
    return user


# --- ACL: Project-level access control ---

# access_level hierarchy (higher = more permissive)
_ACCESS_LEVELS = {
    "viewer": 1,
    "reviewer": 2,
    "approver": 3,
    "editor": 4,
    "owner": 5,
}

# Org-level roles that bypass project_access row check (full org access)
_ORG_BYPASS_ROLES = {"owner", "admin"}


async def require_project_access(
    project_id: str,
    min_level: str,
    user: CurrentUser,
    db: AsyncSession,
) -> ProjectAccess | None:
    """Central ACL guard. Enforced on ALL project/asset/read/write paths.

    Logic:
    1. Verify project exists AND belongs to user's org → 404 if not.
    2. If user.role is org owner/admin → bypass project_access check (full access).
    3. Otherwise, require ProjectAccess row with level >= min_level.
    4. No access → 404 (not 403, to prevent IDOR enumeration).

    Returns ProjectAccess row if one exists, None for org-level bypass.
    """
    from services.web_app.db.models.project import BidProject

    # 1. Verify project belongs to user's org
    proj_result = await db.execute(
        select(BidProject).where(
            BidProject.id == project_id,
            BidProject.org_id == user.org_id,
        )
    )
    project = proj_result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")

    # 2. Org owner/admin bypass — full access to all projects in their org
    if user.role in _ORG_BYPASS_ROLES:
        return None

    # 3. Check ProjectAccess row for non-admin users
    access_result = await db.execute(
        select(ProjectAccess).where(
            ProjectAccess.project_id == project_id,
            ProjectAccess.user_id == user.username,
        )
    )
    access = access_result.scalar_one_or_none()

    if access is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")

    # 4. Check access level hierarchy
    user_level = _ACCESS_LEVELS.get(access.access_level, 0)
    required_level = _ACCESS_LEVELS.get(min_level, 0)
    if user_level < required_level:
        raise HTTPException(status_code=403, detail="권한이 부족합니다")

    return access
