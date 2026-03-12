"""Pydantic models for Company Document Pack data structures.

See spec: docs/superpowers/specs/2026-03-11-company-document-pack-design.md §3
"""
from __future__ import annotations

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


class GenerationTarget(BaseModel):
    min_chars: int = 0
    max_chars: int = 10000
    token_budget: int = 2000


class RenderValidation(BaseModel):
    min_pages: int = 1
    max_pages: int = 99
    action_on_violation: Literal["warn", "retry", "block"] = "warn"


class PackSubsection(BaseModel):
    id: str
    name: str
    dynamic: bool = False
    block_types: list[str] = Field(default_factory=lambda: ["narrative"])
    render_mode: Optional[str] = None
    instructions: str = ""
    conditions: Optional[dict[str, Any]] = None


class PackSection(BaseModel):
    id: str
    name: str
    level: int = 1
    required: bool = True
    weight: float = 0.1
    max_score: float = 0
    conditions: dict[str, Any] = Field(default_factory=lambda: {"always": True})
    generation_target: Optional[GenerationTarget] = None
    render_validation: Optional[RenderValidation] = None
    block_types: list[str] = Field(default_factory=lambda: ["narrative"])
    must_include_facts: list[str] = Field(default_factory=list)
    forbidden_patterns: list[str] = Field(default_factory=list)
    evidence_policy: str = ""
    fallback_text_policy: str = ""
    priority: int = 0
    disabled: bool = False
    subsections: list[PackSubsection] = Field(default_factory=list)


class SectionsConfig(BaseModel):
    document_type: str
    domain_type: str
    sections: list[PackSection]


class DomainDictRole(BaseModel):
    id: str
    name: str
    grade: str = ""
    aliases: list[str] = Field(default_factory=list)


class DomainDictPhase(BaseModel):
    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)


class DomainDictMethodology(BaseModel):
    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)


class CommonRisk(BaseModel):
    risk: str
    mitigation: str


class DomainDict(BaseModel):
    domain_type: str = ""
    roles: list[DomainDictRole] = Field(default_factory=list)
    phases: list[DomainDictPhase] = Field(default_factory=list)
    methodologies: list[DomainDictMethodology] = Field(default_factory=list)
    deliverables_common: list[str] = Field(default_factory=list)
    organization_terms: dict[str, list[str]] = Field(default_factory=dict)
    common_risks: list[CommonRisk] = Field(default_factory=list)
    quality_frameworks: list[str] = Field(default_factory=list)


class BoilerplateEntry(BaseModel):
    id: str
    section_id: str
    mode: Literal["prepend", "append", "replace", "merge"]
    text: str
    tags: list[str] = Field(default_factory=list)


class BoilerplateConfig(BaseModel):
    boilerplates: list[BoilerplateEntry] = Field(default_factory=list)


class PackConfig(BaseModel):
    pack_id: str = ""
    company_id: str = "_default"
    version: int = 1
    status: Literal["draft", "shadow", "active", "archived"] = "active"
    base_pack_ref: Optional[str] = None
    source_documents: list[dict[str, Any]] = Field(default_factory=list)
    active_render_targets: list[str] = Field(default_factory=lambda: ["docx"])
    created_at: str = ""
    updated_at: str = ""
