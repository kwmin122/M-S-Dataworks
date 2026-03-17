from __future__ import annotations

from datetime import date
from sqlalchemy import BigInteger, Date, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, CuidPkMixin, TimestampMixin

# PostgreSQL required — pgvector always available. No SQLite fallback.
from pgvector.sqlalchemy import Vector

_VECTOR_TYPE = Vector(1536)


class CompanyProfile(CuidPkMixin, TimestampMixin, Base):
    __tablename__ = "company_profiles"

    org_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    company_name: Mapped[str | None] = mapped_column(Text)
    business_type: Mapped[str | None] = mapped_column(Text)
    business_number: Mapped[str | None] = mapped_column(Text)
    capital: Mapped[str | None] = mapped_column(Text)
    headcount: Mapped[int | None] = mapped_column(Integer)
    licenses: Mapped[dict | None] = mapped_column(JSONB)
    certifications: Mapped[dict | None] = mapped_column(JSONB)
    writing_style: Mapped[dict | None] = mapped_column(JSONB)


class CompanyTrackRecord(CuidPkMixin, TimestampMixin, Base):
    __tablename__ = "company_track_records"

    org_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_name: Mapped[str | None] = mapped_column(Text)
    client_name: Mapped[str | None] = mapped_column(Text)
    contract_amount: Mapped[int | None] = mapped_column(BigInteger)
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
    technologies: Mapped[dict | None] = mapped_column(JSONB)
    embedding = mapped_column(_VECTOR_TYPE, nullable=True)

    __table_args__ = (
        Index("idx_track_records_org", "org_id"),
    )


class CompanyPersonnel(CuidPkMixin, TimestampMixin, Base):
    __tablename__ = "company_personnel"

    org_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str | None] = mapped_column(Text)
    years_experience: Mapped[int | None] = mapped_column(Integer)
    certifications: Mapped[dict | None] = mapped_column(JSONB)
    skills: Mapped[dict | None] = mapped_column(JSONB)
    description: Mapped[str | None] = mapped_column(Text)
    embedding = mapped_column(_VECTOR_TYPE, nullable=True)

    __table_args__ = (
        Index("idx_personnel_org", "org_id"),
    )
