from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, CreatedAtMixin


class AuditLog(CreatedAtMixin, Base):
    __tablename__ = "audit_logs"

    # Use BigInteger auto-increment PK instead of cuid2 (append-only, high volume)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str | None] = mapped_column(Text)
    project_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("bid_projects.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    target_type: Mapped[str | None] = mapped_column(Text)
    target_id: Mapped[str | None] = mapped_column(Text)
    detail_json: Mapped[dict | None] = mapped_column(JSONB)
    # PostgreSQL INET — validates IP format at DB level. No SQLite fallback needed.
    ip_address: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("idx_audit_org_time", "org_id", text("created_at DESC")),
        Index("idx_audit_project_time", "project_id", text("created_at DESC")),
        Index("idx_audit_target", "target_type", "target_id"),
    )
