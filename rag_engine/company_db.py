"""Company Knowledge DB — structured storage for company capabilities.

Stores track records, personnel, certifications, and past proposal styles.
Uses JSON for structured data + ChromaDB for semantic search.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional

import chromadb


@dataclass
class TrackRecord:
    project_name: str
    client: str
    period: str          # "2024.03 ~ 2024.12"
    amount: float        # 억원
    description: str
    technologies: list[str] = field(default_factory=list)
    outcome: str = ""


@dataclass
class Personnel:
    name: str
    role: str            # PM, PL, 개발자, QA
    experience_years: int
    certifications: list[str] = field(default_factory=list)
    key_projects: list[str] = field(default_factory=list)
    specialties: list[str] = field(default_factory=list)


@dataclass
class CompanyCapabilityProfile:
    """Company capability profile for Layer 2 proposal generation."""
    name: str
    registration_number: str = ""
    licenses: list[str] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)
    capital: float = 0.0         # 억원
    employee_count: int = 0
    track_records: list[TrackRecord] = field(default_factory=list)
    personnel: list[Personnel] = field(default_factory=list)
    writing_style: dict = field(default_factory=dict)


class CompanyDB:
    """ChromaDB-backed company knowledge store."""

    def __init__(self, persist_directory: str = "./data/company_db"):
        if persist_directory:
            self._client = chromadb.PersistentClient(path=persist_directory)
        else:
            self._client = chromadb.Client()
        self._collection = self._client.get_or_create_collection(
            name="company_capabilities",
            metadata={"hnsw:space": "cosine"},
        )
        self._profile_path = os.path.join(persist_directory, "profile.json") if persist_directory else ""

    def add_track_record(self, record: TrackRecord) -> str:
        """Add a track record to the vector DB for semantic search."""
        doc_text = (
            f"프로젝트: {record.project_name}\n"
            f"발주처: {record.client}\n"
            f"기간: {record.period}\n"
            f"금액: {record.amount}억원\n"
            f"내용: {record.description}\n"
            f"기술: {', '.join(record.technologies)}"
        )
        doc_id = f"tr_{hashlib.sha256((record.project_name + record.client).encode()).hexdigest()[:8]}"
        self._collection.upsert(
            ids=[doc_id],
            documents=[doc_text],
            metadatas=[{
                "type": "track_record",
                "project_name": record.project_name,
                "client": record.client,
                "amount": record.amount,
            }],
        )
        return doc_id

    def add_personnel(self, person: Personnel) -> str:
        """Add personnel info to the vector DB."""
        doc_text = (
            f"이름: {person.name}\n"
            f"역할: {person.role}\n"
            f"경력: {person.experience_years}년\n"
            f"자격증: {', '.join(person.certifications)}\n"
            f"전문분야: {', '.join(person.specialties)}\n"
            f"주요프로젝트: {', '.join(person.key_projects)}"
        )
        doc_id = f"ps_{hashlib.sha256((person.name + person.role).encode()).hexdigest()[:8]}"
        self._collection.upsert(
            ids=[doc_id],
            documents=[doc_text],
            metadatas=[{
                "type": "personnel",
                "name": person.name,
                "role": person.role,
                "experience_years": person.experience_years,
            }],
        )
        return doc_id

    def search_similar_projects(self, query: str, top_k: int = 5) -> list[dict]:
        """Semantic search for similar track records."""
        results = self._collection.query(
            query_texts=[query],
            n_results=top_k,
            where={"type": "track_record"},
        )
        items = []
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i]
            dist = results["distances"][0][i] if results.get("distances") else 0
            items.append({"text": doc, "metadata": meta, "distance": dist})
        return items

    def find_matching_personnel(self, requirements: str, top_k: int = 5) -> list[dict]:
        """Find personnel matching given requirements."""
        results = self._collection.query(
            query_texts=[requirements],
            n_results=top_k,
            where={"type": "personnel"},
        )
        items = []
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i]
            dist = results["distances"][0][i] if results.get("distances") else 0
            items.append({"text": doc, "metadata": meta, "distance": dist})
        return items

    def list_track_records(self) -> list[dict]:
        """List all track records from profile."""
        profile = self.load_profile()
        if not profile:
            return []
        result = []
        for r in profile.track_records:
            doc_id = f"tr_{hashlib.sha256((r.project_name + r.client).encode()).hexdigest()[:8]}"
            result.append({
                "doc_id": doc_id,
                "project_name": r.project_name,
                "client": r.client,
                "period": r.period,
                "amount": r.amount,
                "description": r.description,
                "technologies": r.technologies,
                "outcome": r.outcome,
            })
        return result

    def list_personnel(self) -> list[dict]:
        """List all personnel from profile."""
        profile = self.load_profile()
        if not profile:
            return []
        result = []
        for p in profile.personnel:
            doc_id = f"ps_{hashlib.sha256((p.name + p.role).encode()).hexdigest()[:8]}"
            result.append({
                "doc_id": doc_id,
                "name": p.name,
                "role": p.role,
                "experience_years": p.experience_years,
                "certifications": p.certifications,
                "key_projects": p.key_projects,
                "specialties": p.specialties,
            })
        return result

    def delete_item(self, doc_id: str) -> bool:
        """Delete a track record or personnel by doc_id from both ChromaDB and profile."""
        # Delete from ChromaDB
        try:
            self._collection.delete(ids=[doc_id])
        except Exception:
            pass

        # Delete from profile
        profile = self.load_profile()
        if not profile:
            return False

        if doc_id.startswith("tr_"):
            original_len = len(profile.track_records)
            profile.track_records = [
                r for r in profile.track_records
                if f"tr_{hashlib.sha256((r.project_name + r.client).encode()).hexdigest()[:8]}" != doc_id
            ]
            if len(profile.track_records) < original_len:
                self.save_profile(profile)
                return True
        elif doc_id.startswith("ps_"):
            original_len = len(profile.personnel)
            profile.personnel = [
                p for p in profile.personnel
                if f"ps_{hashlib.sha256((p.name + p.role).encode()).hexdigest()[:8]}" != doc_id
            ]
            if len(profile.personnel) < original_len:
                self.save_profile(profile)
                return True
        return False

    def save_profile(self, profile: CompanyCapabilityProfile) -> None:
        """Save full company profile to JSON (atomic write)."""
        if not self._profile_path:
            return
        os.makedirs(os.path.dirname(self._profile_path), exist_ok=True)
        data = asdict(profile)
        tmp_path = self._profile_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self._profile_path)

    def load_profile(self) -> CompanyCapabilityProfile | None:
        """Load company profile from JSON."""
        if not self._profile_path or not os.path.exists(self._profile_path):
            return None
        with open(self._profile_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        records = [TrackRecord(**r) for r in data.pop("track_records", [])]
        personnel = [Personnel(**p) for p in data.pop("personnel", [])]
        return CompanyCapabilityProfile(**data, track_records=records, personnel=personnel)

    def count(self) -> int:
        return self._collection.count()
