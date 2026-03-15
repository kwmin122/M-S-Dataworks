"""GenerationContract — unified interface for all document generation pipelines.

Spec: docs/superpowers/specs/2026-03-14-bid-workspace-v1-design.md Section 8.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


# --- doc_type canonical values (single source of truth for rag_engine) ---

DOC_TYPE_CANONICAL = ["proposal", "execution_plan", "presentation", "track_record", "checklist"]

_DOC_TYPE_ALIASES: dict[str, str] = {
    "wbs": "execution_plan",
    "ppt": "presentation",
}


def normalize_doc_type(doc_type: str) -> str:
    """Convert doc_type to canonical name. Accepts legacy aliases.

    Raises ValueError for unknown doc_type.
    """
    if doc_type in DOC_TYPE_CANONICAL:
        return doc_type
    canonical = _DOC_TYPE_ALIASES.get(doc_type)
    if canonical is not None:
        return canonical
    raise ValueError(f"Unknown doc_type: {doc_type!r}. Valid: {DOC_TYPE_CANONICAL}")


# --- Contract dataclasses ---

@dataclass
class CompanyContext:
    """Company information injected into all generation pipelines."""
    profile_summary: str = ""
    similar_projects: list[dict] = field(default_factory=list)
    matching_personnel: list[dict] = field(default_factory=list)
    licenses: list[str] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)


@dataclass
class QualityRules:
    """Quality gate configuration."""
    blind_words: list[str] = field(default_factory=list)
    custom_forbidden: list[str] = field(default_factory=list)
    min_section_length: int = 0
    max_ambiguity_score: float = 1.0


@dataclass
class GenerationContract:
    """Unified interface consumed by all 4 document generation pipelines.

    web_app builds this from DB data, serializes to JSON, sends to rag_engine.
    rag_engine dispatches to the appropriate orchestrator based on doc_type.
    """
    # 1. Company Context
    company_context: CompanyContext = field(default_factory=CompanyContext)
    company_profile_md: str | None = None
    writing_style: dict | None = None

    # 2. Skill Retrieval
    knowledge_units: list[dict] = field(default_factory=list)
    learned_patterns: list[dict] = field(default_factory=list)
    pack_config: dict | None = None

    # 3. Mode Selection
    mode: Literal["strict_template", "starter", "upgrade"] = "starter"
    template_source: str | None = None

    # 4. Quality Contract
    quality_rules: QualityRules = field(default_factory=QualityRules)
    required_checks: list[str] = field(default_factory=list)
    pass_threshold: float = 0.0


@dataclass
class UploadTarget:
    """Presigned URL target for rag_engine to upload generated files."""
    asset_id: str
    presigned_url: str
    asset_type: str  # docx, xlsx, pptx, pdf, png, json
    content_type: str = "application/octet-stream"


@dataclass
class OutputFile:
    """Metadata for a generated file uploaded to S3."""
    asset_id: str
    asset_type: str
    size_bytes: int = 0
    content_hash: str = ""


@dataclass
class GenerationResult:
    """Unified return type from all generation pipelines."""
    doc_type: str
    output_files: list[OutputFile] = field(default_factory=list)
    content_json: dict = field(default_factory=dict)
    content_schema: str = ""
    quality_report: dict | None = None
    quality_schema: str | None = None
    upgrade_report: dict | None = None
    metadata: dict = field(default_factory=dict)
    generation_time_sec: float = 0.0
