"""ChromaDB wrapper for the proposal_knowledge collection (Layer 1)."""
from __future__ import annotations

import hashlib
from typing import Optional

import chromadb

from knowledge_models import KnowledgeCategory, KnowledgeUnit, SourceType


class KnowledgeDB:
    """ChromaDB wrapper for the proposal_knowledge collection (Layer 1)."""

    COLLECTION_NAME = "proposal_knowledge"

    def __init__(
        self,
        persist_directory: str = "./data/knowledge_db",
    ):
        self._client = chromadb.PersistentClient(path=persist_directory)
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def _make_id(self, unit: KnowledgeUnit) -> str:
        content = f"{unit.source_type.value}:{unit.category.value}:{unit.rule}"
        h = hashlib.sha256(content.encode()).hexdigest()[:12]
        return f"{unit.source_type.value}_{h}"

    def _make_document(self, unit: KnowledgeUnit) -> str:
        """Concatenate rule + explanation for embedding. Include condition for contextual matching."""
        parts = [unit.rule]
        if unit.condition:
            parts.append(f"[조건: {unit.condition}]")
        parts.append(unit.explanation)
        if unit.example_good:
            parts.append(f"좋은 예시: {unit.example_good}")
        if unit.example_bad:
            parts.append(f"나쁜 예시: {unit.example_bad}")
        return "\n".join(parts)

    def _make_metadata(self, unit: KnowledgeUnit) -> dict:
        return {
            "category": unit.category.value,
            "subcategory": unit.subcategory,
            "rule": unit.rule,
            "source_type": unit.source_type.value,
            "raw_confidence": unit.raw_confidence,
            "source_count": unit.source_count,
            "source_date": unit.source_date,
            "is_law_based": unit.is_law_based,
            "condition": unit.condition,
            "has_conflict_flag": unit.has_conflict_flag,
        }

    def add(self, unit: KnowledgeUnit) -> None:
        doc_id = self._make_id(unit)
        self._collection.upsert(
            ids=[doc_id],
            documents=[self._make_document(unit)],
            metadatas=[self._make_metadata(unit)],
        )

    def add_batch(self, units: list[KnowledgeUnit]) -> None:
        if not units:
            return
        ids = [self._make_id(u) for u in units]
        docs = [self._make_document(u) for u in units]
        metas = [self._make_metadata(u) for u in units]
        self._collection.upsert(ids=ids, documents=docs, metadatas=metas)

    def search(
        self,
        query: str,
        top_k: int = 10,
        category: Optional[KnowledgeCategory] = None,
    ) -> list[KnowledgeUnit]:
        where = {"category": category.value} if category else None
        results = self._collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where,
        )
        units = []
        for meta in (results.get("metadatas") or [[]])[0]:
            units.append(KnowledgeUnit(
                category=KnowledgeCategory(meta["category"]),
                subcategory=meta.get("subcategory", ""),
                rule=meta.get("rule", ""),
                explanation="",  # stored in document text, not metadata
                source_type=SourceType(meta["source_type"]) if meta.get("source_type") else SourceType.BLOG,
                raw_confidence=meta.get("raw_confidence", 0.5),
                source_count=meta.get("source_count", 1),
                source_date=meta.get("source_date", ""),
                is_law_based=meta.get("is_law_based", False),
                condition=meta.get("condition", ""),
                has_conflict_flag=meta.get("has_conflict_flag", False),
            ))
        units.sort(key=lambda u: u.effective_score(), reverse=True)
        return units

    def count(self) -> int:
        return self._collection.count()
