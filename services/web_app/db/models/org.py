from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, CuidPkMixin, TimestampMixin, CreatedAtMixin

_PLAN_TIERS = "plan_tier IN ('free','starter','pro','enterprise') OR plan_tier IS NULL"
_MEMBERSHIP_ROLES = "role IN ('owner','admin','editor','reviewer','approver','viewer')"


class Organization(CuidPkMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    plan_tier: Mapped[str | None] = mapped_column(Text, default="free")
    settings_json: Mapped[dict | None] = mapped_column(JSONB, default=None)

    memberships: Mapped[list[Membership]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(_PLAN_TIERS, name="ck_organizations_plan_tier"),
    )


class Membership(CuidPkMixin, TimestampMixin, Base):
    __tablename__ = "memberships"

    org_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(
        Text, nullable=False, default="viewer"
    )  # owner / admin / editor / reviewer / approver / viewer
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    organization: Mapped[Organization] = relationship(back_populates="memberships")

    __table_args__ = (
        CheckConstraint(_MEMBERSHIP_ROLES, name="ck_memberships_role"),
        Index("idx_memberships_user", "user_id", "org_id", postgresql_where=text("is_active = true")),
        Index("idx_memberships_org_role", "org_id", "role", postgresql_where=text("is_active = true")),
    )
