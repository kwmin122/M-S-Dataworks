"""Pack Manager — Load, resolve, and merge Company Document Packs.

Resolution order: company/doc_type/domain → company/doc_type/general
→ _default/doc_type/domain → _default/doc_type/general.

Merge: Section ID-based UPSERT (company overrides _default by section id).
See spec §2 "상속 병합 알고리즘".
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pack_models import (
    BoilerplateConfig, DomainDict, PackConfig, SectionsConfig,
)

logger = logging.getLogger(__name__)


@dataclass
class ResolvedPack:
    """Fully resolved pack with all components."""
    pack_config: PackConfig
    sections: SectionsConfig
    domain_dict: DomainDict
    boilerplate: BoilerplateConfig
    company_id: str
    doc_type: str
    domain_type: str


class PackManager:
    """Loads and resolves Company Document Packs from filesystem."""

    def __init__(self, packs_dir: str | Path):
        self.packs_dir = Path(packs_dir)

    def _find_path(
        self, company_id: str, doc_type: str, domain_type: str, filename: str,
    ) -> Optional[Path]:
        """Find a pack file within the given company scope only (no cross-company fallback).

        Searches: company/doc_type/domain_type → company/doc_type/general
        Cross-company fallback (_default) is handled by resolve() explicitly.
        """
        candidates = [
            self.packs_dir / company_id / doc_type / domain_type / filename,
            self.packs_dir / company_id / doc_type / "general" / filename,
        ]
        for p in candidates:
            if p.is_file():
                return p
        return None

    def _load_json(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def load_pack_config(self, company_id: str) -> PackConfig:
        path = self.packs_dir / company_id / "pack.json"
        if not path.is_file():
            if company_id == "_default":
                raise FileNotFoundError(f"Default pack.json not found at {path}")
            path = self.packs_dir / "_default" / "pack.json"
        return PackConfig.model_validate(self._load_json(path))

    def load_sections(
        self, company_id: str, doc_type: str, domain_type: str,
    ) -> SectionsConfig:
        path = self._find_path(company_id, doc_type, domain_type, "sections.json")
        if path is None:
            raise FileNotFoundError(
                f"sections.json not found for {company_id}/{doc_type}/{domain_type}"
            )
        return SectionsConfig.model_validate(self._load_json(path))

    def load_domain_dict(
        self, company_id: str, doc_type: str, domain_type: str,
    ) -> DomainDict:
        path = self._find_path(company_id, doc_type, domain_type, "domain_dict.json")
        if path is None:
            return DomainDict()  # empty fallback
        return DomainDict.model_validate(self._load_json(path))

    def load_boilerplate(
        self, company_id: str, doc_type: str, domain_type: str,
    ) -> BoilerplateConfig:
        path = self._find_path(company_id, doc_type, domain_type, "boilerplate.json")
        if path is None:
            return BoilerplateConfig()  # empty fallback
        return BoilerplateConfig.model_validate(self._load_json(path))

    def _merge_sections(
        self, base: SectionsConfig, override: SectionsConfig,
    ) -> SectionsConfig:
        """Merge sections by ID (UPSERT: override wins per section ID)."""
        base_map = {s.id: s for s in base.sections}
        for s in override.sections:
            if s.disabled:
                base_map.pop(s.id, None)  # remove disabled sections
            else:
                base_map[s.id] = s  # override entirely by section ID
        # Preserve order: keep base order, insert overrides at their base position
        override_ids = {s.id for s in override.sections}
        seen = set()
        ordered = []
        for s in base.sections:
            if s.id in base_map:
                ordered.append(base_map[s.id])
            seen.add(s.id)
        # Append any new sections from override not in base
        for s in override.sections:
            if s.id not in seen:
                ordered.append(s)
        return SectionsConfig(
            document_type=override.document_type or base.document_type,
            domain_type=override.domain_type or base.domain_type,
            sections=ordered,
        )

    def _merge_boilerplate(
        self, base: BoilerplateConfig, override: BoilerplateConfig,
    ) -> BoilerplateConfig:
        """Concat boilerplates, override wins on duplicate id."""
        base_map = {b.id: b for b in base.boilerplates}
        for b in override.boilerplates:
            base_map[b.id] = b
        return BoilerplateConfig(boilerplates=list(base_map.values()))

    def resolve(
        self, company_id: str, doc_type: str, domain_type: str,
    ) -> ResolvedPack:
        """Resolve a fully merged pack for generation."""
        pack_config = self.load_pack_config(company_id)

        # Load base (_default) first
        base_sections = self.load_sections("_default", doc_type, domain_type)
        base_dd = self.load_domain_dict("_default", doc_type, domain_type)
        base_bp = self.load_boilerplate("_default", doc_type, domain_type)

        if company_id == "_default":
            return ResolvedPack(
                pack_config=pack_config,
                sections=base_sections,
                domain_dict=base_dd,
                boilerplate=base_bp,
                company_id=company_id,
                doc_type=doc_type,
                domain_type=domain_type,
            )

        # Load company overrides (may not exist for all files)
        try:
            company_sections = self.load_sections(company_id, doc_type, domain_type)
            merged_sections = self._merge_sections(base_sections, company_sections)
        except FileNotFoundError:
            merged_sections = base_sections

        try:
            company_dd = self.load_domain_dict(company_id, doc_type, domain_type)
            # For domain_dict: company replaces entirely if present
            merged_dd = company_dd
        except Exception:
            merged_dd = base_dd

        try:
            company_bp = self.load_boilerplate(company_id, doc_type, domain_type)
            merged_bp = self._merge_boilerplate(base_bp, company_bp)
        except Exception:
            merged_bp = base_bp

        return ResolvedPack(
            pack_config=pack_config,
            sections=merged_sections,
            domain_dict=merged_dd,
            boilerplate=merged_bp,
            company_id=company_id,
            doc_type=doc_type,
            domain_type=domain_type,
        )
