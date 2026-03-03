#!/usr/bin/env python3
"""Step 7: Build ChromaDB vectordb from refined knowledge units.

Reads refined_knowledge.jsonl, loads into KnowledgeDB (ChromaDB),
persists to data/knowledge_db/.
"""
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "rag_engine"))

from knowledge_db import KnowledgeDB
from knowledge_models import KnowledgeCategory, KnowledgeUnit, SourceType

INPUT_PATH = os.path.join(BASE_DIR, "data/layer1/extracted/refined_knowledge.jsonl")
DB_PATH = os.path.join(BASE_DIR, "data/knowledge_db")

BATCH_SIZE = 50


def load_units(path: str) -> list[KnowledgeUnit]:
    units = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            unit = KnowledgeUnit(
                category=KnowledgeCategory(d["category"]),
                subcategory=d.get("subcategory", ""),
                rule=d["rule"],
                explanation=d.get("explanation", ""),
                example_good=d.get("example_good", ""),
                example_bad=d.get("example_bad", ""),
                source_type=SourceType(d.get("source_type", "blog")),
                source_id=d.get("source_id", ""),
                raw_confidence=d.get("raw_confidence", 0.5),
                source_count=d.get("source_count", 1),
                source_date=d.get("source_date", ""),
                is_law_based=d.get("is_law_based", False),
                condition=d.get("condition", ""),
                has_conflict_flag=d.get("has_conflict_flag", False),
                deprecated_by=d.get("deprecated_by"),
                tags=d.get("tags", []),
            )
            units.append(unit)
    return units


def main():
    if not os.path.exists(INPUT_PATH):
        print(f"Input not found: {INPUT_PATH}")
        print("Run layer1_refine_knowledge.py first.")
        sys.exit(1)

    units = load_units(INPUT_PATH)
    # Filter out deprecated units
    active_units = [u for u in units if not u.deprecated_by]
    print(f"=== Build ChromaDB Knowledge DB ===")
    print(f"Input: {len(units)} units ({len(units) - len(active_units)} deprecated, skipped)")
    print(f"Active: {len(active_units)} units")
    print(f"DB path: {DB_PATH}")
    print()

    os.makedirs(DB_PATH, exist_ok=True)
    db = KnowledgeDB(persist_directory=DB_PATH)

    # Insert in batches
    for i in range(0, len(active_units), BATCH_SIZE):
        batch = active_units[i:i + BATCH_SIZE]
        db.add_batch(batch)
        print(f"  Inserted batch {i // BATCH_SIZE + 1}: {len(batch)} units")

    # Report stats
    total = db.count()
    print()
    print(f"=== Results ===")
    print(f"Total in DB: {total}")
    print(f"DB path: {DB_PATH}")

    # Category breakdown
    from collections import Counter
    cat_counts = Counter(u.category.value for u in active_units)
    print(f"\nCategory breakdown:")
    for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")

    src_counts = Counter(u.source_type.value for u in active_units)
    print(f"\nSource type breakdown:")
    for src, count in sorted(src_counts.items(), key=lambda x: -x[1]):
        print(f"  {src}: {count}")


if __name__ == "__main__":
    main()
