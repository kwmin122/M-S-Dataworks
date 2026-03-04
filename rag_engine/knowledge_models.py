"""Knowledge Unit data models for Layer 1 proposal knowledge.

All knowledge is stored as KnowledgeUnit objects — structured JSON with
category, rule, confidence, freshness. These are the atoms of the knowledge DB.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional


class KnowledgeCategory(str, Enum):
    STRUCTURE = "structure"
    EVALUATION = "evaluation"
    WRITING = "writing"
    VISUAL = "visual"
    STRATEGY = "strategy"
    COMPLIANCE = "compliance"
    PITFALL = "pitfall"


class SourceType(str, Enum):
    YOUTUBE = "youtube"
    OFFICIAL_GUIDE = "official_guide"
    BLOG = "blog"
    TEXTBOOK = "textbook"
    EVALUATOR_YOUTUBE = "evaluator_youtube"
    WINNER_STORY = "winner_story"
    CONSULTANT = "consultant"


class DocumentType(str, Enum):
    """문서 타입별 지식 분류."""
    PPT = "ppt"              # PT 발표자료
    WBS = "wbs"              # 수행계획서/WBS
    PROPOSAL = "proposal"    # 기술제안서
    TRACK_RECORD = "track_record"  # 실적기술서
    COMMON = "common"        # 모든 문서 타입 공통


# Source-weighted base confidence (design doc SS2-1 Step 2-A)
SOURCE_BASE_CONFIDENCE: dict[SourceType, float] = {
    SourceType.OFFICIAL_GUIDE: 0.85,
    SourceType.EVALUATOR_YOUTUBE: 0.75,
    SourceType.WINNER_STORY: 0.70,
    SourceType.CONSULTANT: 0.55,
    SourceType.YOUTUBE: 0.55,
    SourceType.BLOG: 0.35,
    SourceType.TEXTBOOK: 0.80,
}


def compute_confidence(base: float, source_count: int) -> float:
    """Source-Weighted Confidence = base x cross_validation_multiplier (cap 0.95)."""
    if source_count >= 3:
        multiplier = 1.4
    elif source_count == 2:
        multiplier = 1.2
    else:
        multiplier = 1.0
    return min(round(base * multiplier, 2), 0.95)


def compute_freshness(
    source_date: date,
    today: Optional[date] = None,
    is_law_based: bool = False,
) -> float:
    """Temporal versioning: freshness score decays over time."""
    if is_law_based:
        return 1.0
    if today is None:
        today = date.today()
    months = (today.year - source_date.year) * 12 + (today.month - source_date.month)
    if months < 6:
        return 1.0
    if months < 12:
        return 0.9
    if months < 24:
        return 0.7
    return 0.5


@dataclass
class KnowledgeUnit:
    """A single atom of proposal knowledge extracted from a source."""

    category: KnowledgeCategory
    subcategory: str
    rule: str
    explanation: str
    source_type: SourceType
    raw_confidence: float = 0.5
    source_count: int = 1
    source_date: str = ""  # "YYYY-MM" format
    source_id: str = ""
    example_good: str = ""
    example_bad: str = ""
    superseded_by: Optional[str] = None
    deprecated_by: Optional[str] = None        # conflict loser -> winner link
    is_law_based: bool = False
    condition: str = ""                         # conditional branch rule (Pass 2 CONDITIONAL)
    has_conflict_flag: bool = False             # true conflict existed (winner)
    tags: list[str] = field(default_factory=list)
    document_type: DocumentType = DocumentType.COMMON  # 문서 타입 분류 (PPT/WBS/PROPOSAL/COMMON)

    def is_valid(self) -> bool:
        return bool(self.rule and self.category and self.explanation)

    def confidence(self) -> float:
        return compute_confidence(self.raw_confidence, self.source_count)

    def freshness(self) -> float:
        if not self.source_date:
            return 0.7  # unknown date -> moderate penalty
        parts = self.source_date.split("-")
        src = date(int(parts[0]), int(parts[1]) if len(parts) > 1 else 1, 1)
        return compute_freshness(src, is_law_based=self.is_law_based)

    def effective_score(self) -> float:
        """confidence x freshness -- used for ranking knowledge during retrieval."""
        return round(self.confidence() * self.freshness(), 3)

    def to_dict(self) -> dict:
        return {
            "category": self.category.value,
            "subcategory": self.subcategory,
            "rule": self.rule,
            "explanation": self.explanation,
            "example_good": self.example_good,
            "example_bad": self.example_bad,
            "source_type": self.source_type.value,
            "source_id": self.source_id,
            "raw_confidence": self.raw_confidence,
            "source_count": self.source_count,
            "source_date": self.source_date,
            "is_law_based": self.is_law_based,
            "condition": self.condition,
            "has_conflict_flag": self.has_conflict_flag,
            "deprecated_by": self.deprecated_by,
            "tags": self.tags,
        }


@dataclass
class ProposalSection:
    """One section of a proposal outline, mapped to an RFP evaluation criterion."""

    name: str                       # e.g. "사업 이해도"
    evaluation_item: str            # e.g. "사업 이해 및 분석"
    max_score: float                # e.g. 15.0
    weight: float                   # relative weight 0~1
    subsections: list[str] = field(default_factory=list)
    instructions: str = ""          # LLM-generated writing instructions


@dataclass
class ProposalOutline:
    """Complete proposal structure derived from RFP analysis."""

    title: str
    issuing_org: str
    sections: list[ProposalSection]
    total_pages_target: int = 50
    format_rules: dict = field(default_factory=dict)  # page size, font, etc.


@dataclass
class StrategyMemo:
    """Per-section strategy generated by ProposalPlanningAgent."""
    section_name: str
    emphasis_points: list[str] = field(default_factory=list)
    differentiators: list[str] = field(default_factory=list)
    risk_notes: list[str] = field(default_factory=list)
    knowledge_hints: list[str] = field(default_factory=list)


@dataclass
class ProposalStrategy:
    """Complete proposal strategy from Planning Agent."""
    overall_approach: str = ""
    strengths_mapping: dict = field(default_factory=dict)
    section_strategies: list[StrategyMemo] = field(default_factory=list)

    def get_memo_for(self, section_name: str) -> StrategyMemo | None:
        for memo in self.section_strategies:
            if memo.section_name == section_name:
                return memo
        return None
