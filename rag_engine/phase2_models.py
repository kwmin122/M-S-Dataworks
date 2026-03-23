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
    quality_report: dict = field(default_factory=dict)


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
    slides_metadata: list[dict] = field(default_factory=list)  # Contract adapter metadata
    quality_report: dict = field(default_factory=dict)


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
    match_reason: str = ""         # 선정 사유 (왜 이 실적이 관련 있는지)
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
    relevance_score: float = 0.0   # RFP 유사도 (0~1)
    match_reason: str = ""         # 선정 사유
    generated_text: str = ""     # LLM 생성 경력 서술


@dataclass
class TrackRecordDocResult:
    """실적/경력 기술서 생성 결과."""
    docx_path: str = ""
    track_record_count: int = 0
    personnel_count: int = 0
    generation_time_sec: float = 0.0
    records_data: list[dict] = field(default_factory=list)  # Contract adapter metadata
    personnel_data: list[dict] = field(default_factory=list)  # Contract adapter metadata


# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------

def _extract_meta(rfx_result: dict[str, Any], key: str, fallback: str = "") -> str:
    """rfx_result에서 메타데이터 추출 (serialize 또는 to_dict 형식 모두 지원)."""
    val = rfx_result.get(key, "")
    if val:
        return str(val)
    # to_dict 형식: {"기본정보": {"사업명": ..., "발주기관": ...}}
    _kr = {"title": "사업명", "issuing_org": "발주기관", "budget": "사업비", "project_period": "사업기간"}
    kr_key = _kr.get(key, "")
    if kr_key:
        basic = rfx_result.get("기본정보", {})
        if isinstance(basic, dict):
            return str(basic.get(kr_key, fallback))
    return fallback


def build_rfp_context(rfx_result: dict[str, Any]) -> str:
    """RFP 컨텍스트 문자열 조립.

    메타데이터 + 자격요건 + 평가기준 + 특이사항 + RFP 원문을 포함하여
    LLM이 실제 사업 내용 기반으로 작성하도록 한다.
    """
    title = _extract_meta(rfx_result, "title")
    issuing_org = _extract_meta(rfx_result, "issuing_org")
    budget = _extract_meta(rfx_result, "budget")
    period = _extract_meta(rfx_result, "project_period")

    parts = [
        f"사업명: {title}",
        f"발주기관: {issuing_org}",
        f"사업비: {budget}",
        f"사업기간: {period}",
    ]

    # 자격요건
    reqs = rfx_result.get("requirements", rfx_result.get("자격요건", []))
    if reqs:
        parts.append("\n## 자격요건")
        for i, r in enumerate(reqs[:15], 1):
            desc = r.get("description", r.get("내용", "")) if isinstance(r, dict) else str(r)
            if desc:
                parts.append(f"  {i}. {desc}")

    # 평가기준
    evals = rfx_result.get("evaluation_criteria", rfx_result.get("평가기준", []))
    if evals:
        parts.append("\n## 평가기준")
        for e in evals[:20]:
            if isinstance(e, dict):
                name = e.get("category", e.get("항목", ""))
                score = e.get("max_score", e.get("배점", ""))
                desc = e.get("description", e.get("세부내용", ""))
                parts.append(f"  - {name} ({score}점): {desc}")

    # 특이사항
    notes = rfx_result.get("special_notes", rfx_result.get("특이사항", []))
    if notes:
        parts.append("\n## 특이사항")
        for n in notes[:10]:
            parts.append(f"  - {n}")

    # RFP 요약 또는 원문
    summary = rfx_result.get("rfp_text_summary", "")
    raw_text = rfx_result.get("raw_text", "")
    if summary:
        parts.append(f"\n## RFP 요약\n{summary}")
    elif raw_text:
        parts.append(f"\n## RFP 원문 (발췌)\n{raw_text[:4000]}")

    return "\n".join(parts)
