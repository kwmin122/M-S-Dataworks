from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.web_app.db.models.org import Organization, Membership
from services.web_app.db.models.project import BidProject, AnalysisSnapshot
from services.web_app.db.models.base import new_cuid


class SessionAdapter:
    """Thin bridge: session_id -> bid_project.

    Rules (from spec):
    1. READ/WRITE-THROUGH ONLY — adapter calls bid_project API internally.
    2. NEW FEATURE ADDITION PROHIBITED — new features go to /api/projects/* only.
    3. SOURCE OF TRUTH = Workspace API — session memory is cache only.
    4. REMOVAL: Phase 3 deprecated, Phase 4 removed.
    """

    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_or_create_project(
        self,
        session_id: str,
        username: str,
        title: str = "대화 기반 프로젝트",
    ) -> BidProject:
        """Map existing session_id to a bid_project.

        Uses dedicated legacy_session_id column for lookup.
        rfp_source_ref is a business field — NOT used for session mapping.
        Creates org + membership if user has none (Phase 1 dev-bootstrap).
        """
        result = await self._db.execute(
            select(BidProject).where(
                BidProject.legacy_session_id == session_id,
            )
        )
        project = result.scalar_one_or_none()
        if project is not None:
            return project

        org_id = await self._ensure_org(username)

        project = BidProject(
            org_id=org_id,
            created_by=username,
            title=title,
            status="draft",
            rfp_source_type="upload",
            legacy_session_id=session_id,
        )
        self._db.add(project)
        await self._db.flush()
        return project

    async def save_analysis(
        self,
        project_id: str,
        org_id: str,
        analysis_json: dict,
        summary_md: str | None = None,
        go_nogo_json: dict | None = None,
        username: str | None = None,
    ) -> AnalysisSnapshot:
        """Save analysis result as immutable snapshot.

        Deactivates previous active snapshot, creates new one.
        """
        result = await self._db.execute(
            select(AnalysisSnapshot).where(
                AnalysisSnapshot.project_id == project_id,
                AnalysisSnapshot.is_active == True,
            )
        )
        current = result.scalar_one_or_none()
        next_version = 1
        if current is not None:
            current.is_active = False
            next_version = current.version + 1

        snapshot = AnalysisSnapshot(
            org_id=org_id,
            project_id=project_id,
            version=next_version,
            analysis_json=analysis_json,
            analysis_schema="rfx_analysis_v1",
            summary_md=summary_md,
            go_nogo_result_json=go_nogo_json,
            is_active=True,
            created_by=username,
        )
        self._db.add(snapshot)
        await self._db.flush()

        proj_result = await self._db.execute(
            select(BidProject).where(BidProject.id == project_id)
        )
        project = proj_result.scalar_one()
        project.active_analysis_snapshot_id = snapshot.id
        project.status = "ready_for_generation"

        await self._db.commit()
        return snapshot

    async def get_analysis(self, project_id: str) -> dict | None:
        """Get active analysis snapshot for a project."""
        result = await self._db.execute(
            select(AnalysisSnapshot).where(
                AnalysisSnapshot.project_id == project_id,
                AnalysisSnapshot.is_active == True,
            )
        )
        snapshot = result.scalar_one_or_none()
        if snapshot is None:
            return None
        return {
            "id": snapshot.id,
            "version": snapshot.version,
            "analysis_json": snapshot.analysis_json,
            "summary_md": snapshot.summary_md,
            "go_nogo_result_json": snapshot.go_nogo_result_json,
        }

    async def _ensure_org(self, username: str) -> str:
        """Ensure user has an org. Auto-create ONLY in dev (BID_DEV_BOOTSTRAP=1).

        In production, users MUST already have an org+membership (created via
        admin invite flow). Unconditional org creation = ghost org risk.
        """
        import os
        import logging as _logging

        result = await self._db.execute(
            select(Membership).where(
                Membership.user_id == username,
                Membership.is_active == True,
            )
        )
        memberships = result.scalars().all()

        if len(memberships) > 1:
            org_ids = [m.org_id for m in memberships]
            _logging.getLogger(__name__).error(
                "v1 invariant violation in adapter: user '%s' has %d active memberships (orgs: %s)",
                username, len(memberships), org_ids,
            )
            raise ValueError(
                f"User '{username}' has multiple active memberships. "
                "Multi-org not supported in v1."
            )

        if memberships:
            return memberships[0].org_id

        dev_bootstrap = os.getenv("BID_DEV_BOOTSTRAP", "").lower() in ("1", "true")
        if not dev_bootstrap:
            raise ValueError(
                f"User '{username}' has no org membership and BID_DEV_BOOTSTRAP is not enabled. "
                "In production, users must be invited to an existing org."
            )

        _logging.getLogger(__name__).warning(
            "DEV_BOOTSTRAP: adapter auto-creating org for user=%s", username
        )

        org = Organization(name=f"{username}의 조직")
        self._db.add(org)
        await self._db.flush()

        membership = Membership(
            org_id=org.id,
            user_id=username,
            role="owner",
            is_active=True,
        )
        self._db.add(membership)
        await self._db.flush()
        return org.id
