"""
phase2_models.py

Shared data models for Phase 2 modules:
  B — 수행계획서/WBS
  C — PPT 발표자료
  F — 실적/경력 기술서
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Module B: 수행계획서 / WBS
# ---------------------------------------------------------------------------

class MethodologyType(str, Enum):
    WATERFALL = "waterfall"
    AGILE = "agile"
    HYBRID = "hybrid"


class DomainType(str, Enum):
    IT_BUILD = "it_build"
    RESEARCH = "research"
    CONSULTING = "consulting"
    EDUCATION_ODA = "education_oda"
    GENERAL = "general"


@dataclass
class WbsTask:
    """단일 WBS 항목."""
    phase: str
    task_name: str
    start_month: int          # 1-based
    duration_months: int      # >= 1
    deliverables: list[str] = field(default_factory=list)
    responsible_role: str = ""
    man_months: float = 0.0

    def __post_init__(self):
        if self.start_month < 1:
            self.start_month = 1
        if self.duration_months < 1:
            self.duration_months = 1
        if self.man_months < 0:
            self.man_months = 0.0

    def end_month(self) -> int:
        return self.start_month + self.duration_months - 1


@dataclass
class PersonnelAllocation:
    """투입인력 배치."""
    role: str
    name: str = ""
    grade: str = ""              # 특급/고급/중급/초급
    total_man_months: float = 0.0
    monthly_allocation: list[float] = field(default_factory=list)  # per-month M/M


@dataclass
class WbsResult:
    """WBS 생성 결과."""
    xlsx_path: str = ""
    gantt_path: str = ""         # PNG
    docx_path: str = ""
    tasks: list[WbsTask] = field(default_factory=list)
    personnel: list[PersonnelAllocation] = field(default_factory=list)
    total_months: int = 0
    generation_time_sec: float = 0.0


# ---------------------------------------------------------------------------
# Module C: PPT 발표자료
# ---------------------------------------------------------------------------

class SlideType(str, Enum):
    COVER = "cover"
    TOC = "toc"
    CONTENT = "content"
    BULLET = "bullet"
    TABLE = "table"
    TIMELINE = "timeline"
    TEAM = "team"
    QNA = "qna"
    CLOSING = "closing"
    DIVIDER = "divider"


@dataclass
class SlideContent:
    """단일 슬라이드 내용."""
    slide_type: SlideType
    title: str
    body: str = ""
    bullets: list[str] = field(default_factory=list)
    table_data: list[list[str]] = field(default_factory=list)
    speaker_notes: str = ""
    duration_sec: int = 60       # 발표 시간(초)
    image_path: str = ""         # 삽입 이미지 (간트차트 등)


@dataclass
class QnaPair:
    """예상질문 + 모범답변."""
    question: str
    answer: str
    category: str = ""           # 기술/관리/비용 등


@dataclass
class PptResult:
    """PPT 생성 결과."""
    pptx_path: str = ""
    slide_count: int = 0
    qna_pairs: list[QnaPair] = field(default_factory=list)
    total_duration_min: float = 0.0
    generation_time_sec: float = 0.0


# ---------------------------------------------------------------------------
# Module F: 실적/경력 기술서
# ---------------------------------------------------------------------------

@dataclass
class TrackRecordEntry:
    """유사수행실적 항목."""
    project_name: str
    client: str
    period: str = ""
    amount: float = 0.0
    description: str = ""
    technologies: list[str] = field(default_factory=list)
    relevance_score: float = 0.0   # RFP 유사도 (0~1)
    generated_text: str = ""       # LLM 생성 서술형


@dataclass
class PersonnelEntry:
    """투입인력 항목."""
    name: str
    role: str
    grade: str = ""              # 특급/고급/중급/초급
    experience_years: int = 0
    certifications: list[str] = field(default_factory=list)
    key_projects: list[str] = field(default_factory=list)
    generated_text: str = ""     # LLM 생성 경력 서술


@dataclass
class TrackRecordDocResult:
    """실적/경력 기술서 생성 결과."""
    docx_path: str = ""
    track_record_count: int = 0
    personnel_count: int = 0
    generation_time_sec: float = 0.0


# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------

def build_rfp_context(rfx_result: dict[str, Any]) -> str:
    """RFP 컨텍스트 문자열 조립 (공통 유틸리티)."""
    parts = [
        f"사업명: {rfx_result.get('title', '')}",
        f"발주기관: {rfx_result.get('issuing_org', '')}",
        f"사업비: {rfx_result.get('budget', '')}",
        f"사업기간: {rfx_result.get('project_period', '')}",
    ]
    if rfx_result.get("rfp_text_summary"):
        parts.append(f"RFP 요약: {rfx_result['rfp_text_summary']}")
    return "\n".join(parts)
