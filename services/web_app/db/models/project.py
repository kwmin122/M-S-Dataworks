from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, CuidPkMixin, TimestampMixin, CreatedAtMixin


_BID_PROJECT_STATUSES = "status IN ('draft','collecting_inputs','analyzing','ready_for_generation','generating','in_review','changes_requested','approved','locked_for_submission','submitted','archived')"
_RFP_SOURCE_TYPES = "rfp_source_type IN ('upload','nara_search','manual') OR rfp_source_type IS NULL"
_GENERATION_MODES = "generation_mode IN ('strict_template','starter','upgrade') OR generation_mode IS NULL"
_ACCESS_LEVELS = "access_level IN ('owner','editor','reviewer','approver','viewer')"
_DOC_KINDS = "document_kind IN ('rfp','company_profile','template','past_proposal','track_record','personnel','supporting_material','final_upload')"
_PARSE_STATUSES = "parse_status IN ('pending','parsing','completed','failed')"


class BidProject(CuidPkMixin, TimestampMixin, Base):
    __tablename__ = "bid_projects"

    org_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="draft"
    )
    rfp_source_type: Mapped[str | None] = mapped_column(Text)
    rfp_source_ref: Mapped[str | None] = mapped_column(Text)
    legacy_session_id: Mapped[str | None] = mapped_column(
        Text, unique=True, index=True, doc="Session adapter lookup key. Phase 4 removed."
    )
    active_analysis_snapshot_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("analysis_snapshots.id", use_alter=True, deferrable=True, initially="DEFERRED"),
    )
    generation_mode: Mapped[str | None] = mapped_column(Text)
    settings_json: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        CheckConstraint(_BID_PROJECT_STATUSES, name="ck_bid_projects_status"),
        CheckConstraint(_RFP_SOURCE_TYPES, name="ck_bid_projects_rfp_source_type"),
        CheckConstraint(_GENERATION_MODES, name="ck_bid_projects_generation_mode"),
        Index("idx_bid_projects_org_status", "org_id", "status"),
        Index("idx_bid_projects_org_created", "org_id", text("created_at DESC")),
    )


class ProjectAccess(CuidPkMixin, TimestampMixin, Base):
    __tablename__ = "project_access"

    project_id: Mapped[str] = mapped_column(
        Text, ForeignKey("bid_projects.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str | None] = mapped_column(Text)
    team_id: Mapped[str | None] = mapped_column(Text)
    access_level: Mapped[str] = mapped_column(
        Text, nullable=False, default="viewer"
    )

    __table_args__ = (
        CheckConstraint(_ACCESS_LEVELS, name="ck_project_access_level"),
        UniqueConstraint(
            "project_id", "user_id",
            name="uq_project_access_project_user",
        ),
        Index("idx_project_access_project", "project_id"),
        Index("idx_project_access_user", "user_id"),
    )


class SourceDocument(CuidPkMixin, CreatedAtMixin, Base):
    __tablename__ = "source_documents"

    org_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("bid_projects.id", ondelete="SET NULL")
    )
    document_kind: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    uploaded_by: Mapped[str] = mapped_column(Text, nullable=False)
    asset_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("document_assets.id")
    )
    parse_status: Mapped[str] = mapped_column(
        Text, nullable=False, default="pending"
    )
    parse_result_json: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        CheckConstraint(_DOC_KINDS, name="ck_source_docs_kind"),
        CheckConstraint(_PARSE_STATUSES, name="ck_source_docs_parse_status"),
        CheckConstraint(
            "document_kind != 'final_upload' OR project_id IS NOT NULL",
            name="ck_source_docs_final_upload_project",
        ),
        Index("idx_source_docs_project_kind", "project_id", "document_kind"),
    )


class AnalysisSnapshot(CuidPkMixin, CreatedAtMixin, Base):
    __tablename__ = "analysis_snapshots"

    org_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        Text, ForeignKey("bid_projects.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    analysis_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    analysis_schema: Mapped[str | None] = mapped_column(Text)
    summary_md: Mapped[str | None] = mapped_column(Text)
    go_nogo_result_json: Mapped[dict | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index(
            "idx_analysis_active", "project_id",
            unique=True, postgresql_where=text("is_active = true"),
        ),
    )
