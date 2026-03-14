from __future__ import annotations

from datetime import datetime, timezone
from cuid2 import cuid_wrapper
from sqlalchemy import DateTime, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

generate_cuid = cuid_wrapper()


def new_cuid() -> str:
    return generate_cuid()


class Base(DeclarativeBase):
    pass


# --- Enums (spec section 4: single dictionary across all layers) ---

class DocType:
    """doc_type enum values. Used in CHECK constraints and Python code."""
    PROPOSAL = "proposal"
    EXECUTION_PLAN = "execution_plan"
    PRESENTATION = "presentation"
    TRACK_RECORD = "track_record"
    CHECKLIST = "checklist"
    ALL = [PROPOSAL, EXECUTION_PLAN, PRESENTATION, TRACK_RECORD, CHECKLIST]


class ContentSchema:
    """content_schema version strings for document_revisions."""
    PROPOSAL_V1 = "proposal_sections_v1"
    EXECUTION_PLAN_V1 = "execution_plan_tasks_v1"
    PRESENTATION_V1 = "presentation_slides_v1"
    TRACK_RECORD_V1 = "track_record_v1"
    CHECKLIST_V1 = "checklist_v1"


class CuidPkMixin:
    """Primary key using cuid2."""
    id: Mapped[str] = mapped_column(
        Text, primary_key=True, default=new_cuid
    )


class TimestampMixin:
    """created_at + updated_at auto-managed timestamps."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class CreatedAtMixin:
    """Immutable records — created_at only, no updated_at."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
