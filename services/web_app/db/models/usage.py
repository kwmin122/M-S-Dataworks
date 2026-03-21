"""UsageEvent — operational telemetry for billing, observability, and performance."""
from __future__ import annotations

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Integer, Numeric, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, CreatedAtMixin

_EVENT_TYPES = "event_type IN ('analyze','classify','generate','upload','search','relearn','download')"
_STATUS_TYPES = "status IN ('success','failure','timeout')"


class UsageEvent(CreatedAtMixin, Base):
    __tablename__ = "usage_events"

    # Use BigInteger auto-increment PK (append-only, high volume)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str | None] = mapped_column(Text)
    project_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("bid_projects.id", ondelete="SET NULL")
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    doc_type: Mapped[str | None] = mapped_column(Text)
    model_name: Mapped[str | None] = mapped_column(Text)
    token_count: Mapped[int | None] = mapped_column(Integer)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Numeric(10, 6))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    detail_json: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        CheckConstraint(_EVENT_TYPES, name="ck_usage_events_type"),
        CheckConstraint(_STATUS_TYPES, name="ck_usage_events_status"),
        Index("idx_usage_org_month", "org_id", text("created_at DESC")),
        Index("idx_usage_user_day", "user_id", text("created_at DESC")),
        Index("idx_usage_doc_type", "doc_type", "event_type"),
        Index("idx_usage_model", "model_name", text("created_at DESC")),
    )
