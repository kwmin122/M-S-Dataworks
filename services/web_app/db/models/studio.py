from __future__ import annotations

from datetime import datetime
from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, CuidPkMixin, TimestampMixin

# --- Enum value strings for CHECK constraints ---

_ASSET_CATEGORIES = "asset_category IN ('track_record','personnel','technology','certification','raw_document')"
_STYLE_SOURCE_TYPES = "source_type IN ('uploaded','derived','promoted')"
_PACKAGE_CATEGORIES = "package_category IN ('generated_document','evidence','administrative','price')"
_PACKAGE_STATUSES = "status IN ('missing','ready_to_generate','generated','uploaded','verified','waived')"


class ProjectCompanyAsset(CuidPkMixin, TimestampMixin, Base):
    """Project-scoped company staging data.

    Holds experimentation data without polluting shared CompanyDB.
    Promote writes selected assets to shared models via explicit action.
    """
    __tablename__ = "project_company_assets"

    project_id: Mapped[str] = mapped_column(
        Text, ForeignKey("bid_projects.id", ondelete="CASCADE"), nullable=False
    )
    org_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    asset_category: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    content_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source_document_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("source_documents.id", ondelete="SET NULL"),
    )
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    promoted_to_id: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(_ASSET_CATEGORIES, name="ck_proj_company_assets_category"),
        Index("idx_proj_company_assets_project", "project_id"),
        Index("idx_proj_company_assets_org", "org_id"),
    )


class ProjectStyleSkill(CuidPkMixin, TimestampMixin, Base):
    """Project-scoped style versions.

    Supports derive/pin/promote/rollback workflows.
    profile_md_content is rendered from structured style_json.
    """
    __tablename__ = "project_style_skills"

    project_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("bid_projects.id", ondelete="CASCADE"),
    )
    org_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False, default="uploaded")
    derived_from_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("project_style_skills.id", ondelete="SET NULL"),
    )
    profile_md_content: Mapped[str | None] = mapped_column(Text)
    style_json: Mapped[dict | None] = mapped_column(JSONB)
    is_shared_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        CheckConstraint(_STYLE_SOURCE_TYPES, name="ck_proj_style_skills_source_type"),
        # Project-local version uniqueness (project_id NOT NULL rows)
        UniqueConstraint("project_id", "version", name="uq_style_skill_project_version"),
        # Shared defaults (project_id IS NULL) — prevent duplicate versions per org
        Index(
            "uq_shared_style_org_version", "org_id", "version",
            unique=True,
            postgresql_where=text("project_id IS NULL"),
        ),
        # Exactly one shared default per org
        Index(
            "uq_shared_default_per_org", "org_id",
            unique=True,
            postgresql_where=text("is_shared_default = true"),
        ),
        Index("idx_style_skills_project", "project_id"),
        Index("idx_style_skills_org", "org_id"),
    )


class ProjectPackageItem(CuidPkMixin, TimestampMixin, Base):
    """Required submission package item for a single Studio project.

    This is the control plane that turns Studio from 'document generator'
    into 'submission package workspace'.
    """
    __tablename__ = "project_package_items"

    project_id: Mapped[str] = mapped_column(
        Text, ForeignKey("bid_projects.id", ondelete="CASCADE"), nullable=False
    )
    org_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    package_category: Mapped[str] = mapped_column(Text, nullable=False)
    document_code: Mapped[str] = mapped_column(Text, nullable=False)
    document_label: Mapped[str] = mapped_column(Text, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="missing")
    generation_target: Mapped[str | None] = mapped_column(Text)
    asset_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("document_assets.id", ondelete="SET NULL"),
    )
    source_document_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("source_documents.id", ondelete="SET NULL"),
    )
    notes_json: Mapped[dict | None] = mapped_column(JSONB)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        CheckConstraint(_PACKAGE_CATEGORIES, name="ck_pkg_items_category"),
        CheckConstraint(_PACKAGE_STATUSES, name="ck_pkg_items_status"),
        UniqueConstraint("project_id", "document_code", name="uq_pkg_item_project_code"),
        Index("idx_pkg_items_project", "project_id"),
        Index("idx_pkg_items_org", "org_id"),
    )
