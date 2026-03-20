"""Add 'profile' to project_company_assets asset_category CHECK constraint.

Revision ID: 20260318_002
Revises: 20260318_001
Create Date: 2026-03-18
"""
from alembic import op

revision = "20260318_002"
down_revision = "20260318_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_proj_company_assets_category", "project_company_assets", type_="check")
    op.create_check_constraint(
        "ck_proj_company_assets_category",
        "project_company_assets",
        "asset_category IN ('track_record','personnel','profile','technology','certification','raw_document')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_proj_company_assets_category", "project_company_assets", type_="check")
    op.create_check_constraint(
        "ck_proj_company_assets_category",
        "project_company_assets",
        "asset_category IN ('track_record','personnel','technology','certification','raw_document')",
    )
