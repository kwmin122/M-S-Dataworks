from __future__ import annotations

from datetime import datetime
from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, CuidPkMixin, CreatedAtMixin, TimestampMixin, DocType

_DOC_TYPE_CHECK = f"doc_type IN ('{DocType.PROPOSAL}','{DocType.EXECUTION_PLAN}','{DocType.PRESENTATION}','{DocType.TRACK_RECORD}','{DocType.CHECKLIST}')"
_RUN_STATUSES = "status IN ('queued','running','completed','failed','superseded')"
_REV_STATUSES = "status IN ('draft','review_requested','in_review','changes_requested','approved','locked','submitted')"
_REV_SOURCES = "source IN ('ai_generated','user_edited','reassembled','imported_final')"
_UPLOAD_STATUSES = "upload_status IN ('presigned_issued','uploading','uploaded','verified','failed')"
_MODE_USED = "mode_used IN ('strict_template','starter','upgrade') OR mode_used IS NULL"
_ASSET_TYPES = "asset_type IN ('original','docx','xlsx','pptx','pdf','png','json')"


class DocumentRun(CuidPkMixin, CreatedAtMixin, Base):
    __tablename__ = "document_runs"

    org_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        Text, ForeignKey("bid_projects.id", ondelete="CASCADE"), nullable=False
    )
    analysis_snapshot_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("analysis_snapshots.id")
    )
    doc_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="queued"
    )
    params_json: Mapped[dict | None] = mapped_column(JSONB)
    engine_version: Mapped[str | None] = mapped_column(Text)
    mode_used: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint(_DOC_TYPE_CHECK, name="ck_doc_runs_doc_type"),
        CheckConstraint(_RUN_STATUSES, name="ck_doc_runs_status"),
        CheckConstraint(_MODE_USED, name="ck_doc_runs_mode_used"),
    )


class DocumentRevision(CuidPkMixin, CreatedAtMixin, Base):
    __tablename__ = "document_revisions"

    org_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        Text, ForeignKey("bid_projects.id", ondelete="CASCADE"), nullable=False
    )
    doc_type: Mapped[str] = mapped_column(Text, nullable=False)
    run_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("document_runs.id")
    )
    derived_from_revision_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("document_revisions.id")
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source: Mapped[str] = mapped_column(
        Text, nullable=False, default="ai_generated"
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="draft"
    )
    title: Mapped[str | None] = mapped_column(Text)
    content_json: Mapped[dict | None] = mapped_column(JSONB)
    content_schema: Mapped[str | None] = mapped_column(Text)
    quality_report_json: Mapped[dict | None] = mapped_column(JSONB)
    quality_schema: Mapped[str | None] = mapped_column(Text)
    upgrade_report_json: Mapped[dict | None] = mapped_column(JSONB)
    created_by: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(_DOC_TYPE_CHECK, name="ck_doc_revisions_doc_type"),
        CheckConstraint(_REV_STATUSES, name="ck_doc_revisions_status"),
        CheckConstraint(_REV_SOURCES, name="ck_doc_revisions_source"),
        Index(
            "idx_doc_revisions_project_type",
            "project_id", "doc_type", text("revision_number DESC"),
        ),
    )


class DocumentAsset(CuidPkMixin, CreatedAtMixin, Base):
    __tablename__ = "document_assets"

    org_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("bid_projects.id", ondelete="SET NULL")
    )
    revision_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("document_revisions.id")
    )
    asset_type: Mapped[str] = mapped_column(Text, nullable=False)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    upload_status: Mapped[str] = mapped_column(
        Text, nullable=False, default="presigned_issued"
    )
    original_filename: Mapped[str | None] = mapped_column(Text)
    mime_type: Mapped[str | None] = mapped_column(Text)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    content_hash: Mapped[str | None] = mapped_column(Text)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        CheckConstraint(_UPLOAD_STATUSES, name="ck_doc_assets_upload_status"),
        CheckConstraint(_ASSET_TYPES, name="ck_doc_assets_asset_type"),
        Index("idx_doc_assets_org_project", "org_id", "project_id"),
        Index("idx_doc_assets_revision", "revision_id"),
    )


class ProjectCurrentDocument(CuidPkMixin, Base):
    __tablename__ = "project_current_documents"

    org_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        Text, ForeignKey("bid_projects.id", ondelete="CASCADE"), nullable=False
    )
    doc_type: Mapped[str] = mapped_column(Text, nullable=False)
    current_revision_id: Mapped[str] = mapped_column(
        Text, ForeignKey("document_revisions.id"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(_DOC_TYPE_CHECK, name="ck_current_docs_doc_type"),
        UniqueConstraint("project_id", "doc_type", name="uq_current_doc_project_type"),
        Index("idx_current_docs_org", "org_id"),
    )
