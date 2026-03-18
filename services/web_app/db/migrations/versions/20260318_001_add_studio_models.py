"""Add Studio models: project_type/studio_stage on bid_projects,
project_company_assets, project_style_skills, project_package_items.

Revision ID: 20260318_001
Revises:
Create Date: 2026-03-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260318_001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- 1. New tables (create style_skills FIRST — bid_projects FK references it) ---

    op.create_table(
        "project_style_skills",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("project_id", sa.Text(), sa.ForeignKey("bid_projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column("org_id", sa.Text(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False, server_default="uploaded"),
        sa.Column("derived_from_id", sa.Text(), sa.ForeignKey("project_style_skills.id", ondelete="SET NULL"), nullable=True),
        sa.Column("profile_md_content", sa.Text(), nullable=True),
        sa.Column("style_json", postgresql.JSONB(), nullable=True),
        sa.Column("is_shared_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("source_type IN ('uploaded','derived','promoted')", name="ck_proj_style_skills_source_type"),
        sa.UniqueConstraint("project_id", "version", name="uq_style_skill_project_version"),
    )
    op.create_index("idx_style_skills_project", "project_style_skills", ["project_id"])
    op.create_index("idx_style_skills_org", "project_style_skills", ["org_id"])
    # Partial unique index: prevent duplicate (org_id, version) for shared defaults (project_id IS NULL)
    op.create_index(
        "uq_shared_style_org_version", "project_style_skills",
        ["org_id", "version"], unique=True,
        postgresql_where=sa.text("project_id IS NULL"),
    )
    # Exactly one shared default per org
    op.create_index(
        "uq_shared_default_per_org", "project_style_skills",
        ["org_id"], unique=True,
        postgresql_where=sa.text("is_shared_default = true"),
    )

    op.create_table(
        "project_company_assets",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("project_id", sa.Text(), sa.ForeignKey("bid_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", sa.Text(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_category", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("content_json", postgresql.JSONB(), nullable=False),
        sa.Column("source_document_id", sa.Text(), sa.ForeignKey("source_documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("promoted_to_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("asset_category IN ('track_record','personnel','technology','certification','raw_document')", name="ck_proj_company_assets_category"),
    )
    op.create_index("idx_proj_company_assets_project", "project_company_assets", ["project_id"])
    op.create_index("idx_proj_company_assets_org", "project_company_assets", ["org_id"])

    op.create_table(
        "project_package_items",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("project_id", sa.Text(), sa.ForeignKey("bid_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", sa.Text(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("package_category", sa.Text(), nullable=False),
        sa.Column("document_code", sa.Text(), nullable=False),
        sa.Column("document_label", sa.Text(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("status", sa.Text(), nullable=False, server_default="missing"),
        sa.Column("generation_target", sa.Text(), nullable=True),
        sa.Column("asset_id", sa.Text(), sa.ForeignKey("document_assets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_document_id", sa.Text(), sa.ForeignKey("source_documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("notes_json", postgresql.JSONB(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("package_category IN ('generated_document','evidence','administrative','price')", name="ck_pkg_items_category"),
        sa.CheckConstraint("status IN ('missing','ready_to_generate','generated','uploaded','verified','waived')", name="ck_pkg_items_status"),
        sa.UniqueConstraint("project_id", "document_code", name="uq_pkg_item_project_code"),
    )
    op.create_index("idx_pkg_items_project", "project_package_items", ["project_id"])
    op.create_index("idx_pkg_items_org", "project_package_items", ["org_id"])

    # --- 2. Add Studio columns to bid_projects ---

    op.add_column("bid_projects", sa.Column("project_type", sa.Text(), nullable=False, server_default="chat"))
    op.add_column("bid_projects", sa.Column("studio_stage", sa.Text(), nullable=True))
    op.add_column("bid_projects", sa.Column(
        "pinned_style_skill_id", sa.Text(),
        sa.ForeignKey("project_style_skills.id", deferrable=True, initially="DEFERRED"),
        nullable=True,
    ))
    op.create_check_constraint("ck_bid_projects_project_type", "bid_projects", "project_type IN ('chat','studio')")
    op.create_check_constraint(
        "ck_bid_projects_studio_stage", "bid_projects",
        "studio_stage IN ('rfp','package','company','style','generate','review','relearn') OR studio_stage IS NULL",
    )
    op.create_index("idx_bid_projects_org_type", "bid_projects", ["org_id", "project_type"])


def downgrade() -> None:
    op.drop_index("idx_bid_projects_org_type", table_name="bid_projects")
    op.drop_constraint("ck_bid_projects_studio_stage", "bid_projects", type_="check")
    op.drop_constraint("ck_bid_projects_project_type", "bid_projects", type_="check")
    op.drop_column("bid_projects", "pinned_style_skill_id")
    op.drop_column("bid_projects", "studio_stage")
    op.drop_column("bid_projects", "project_type")

    op.drop_table("project_package_items")
    op.drop_table("project_company_assets")
    op.drop_index("uq_shared_default_per_org", table_name="project_style_skills")
    op.drop_index("uq_shared_style_org_version", table_name="project_style_skills")
    op.drop_table("project_style_skills")
