#!/usr/bin/env python3
"""Step 6: LLM Pass 2 — Deduplicate and resolve conflicts.

Reads knowledge.jsonl, groups similar rules by embedding similarity,
calls knowledge_dedup for similar pairs, outputs refined_knowledge.jsonl.

For efficiency, we use simple text similarity (SequenceMatcher) as a first pass
to identify potential duplicates, then use LLM only for those pairs.
"""
import json
import os
import sys
from collections import defaultdict
from difflib import SequenceMatcher

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "rag_engine"))

from knowledge_dedup import resolve_and_merge
from knowledge_models import KnowledgeCategory, KnowledgeUnit, SourceType

INPUT_PATH = os.path.join(BASE_DIR, "data/layer1/extracted/knowledge.jsonl")
OUTPUT_PATH = os.path.join(BASE_DIR, "data/layer1/extracted/refined_knowledge.jsonl")
CONFLICT_LOG_PATH = os.path.join(BASE_DIR, "data/layer1/extracted/conflict_log.jsonl")

# Similarity threshold for considering two rules as potential duplicates
SIMILARITY_THRESHOLD = 0.65


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


def text_similarity(a: str, b: str) -> float:
    """Quick text similarity using SequenceMatcher."""
    return SequenceMatcher(None, a, b).ratio()


def main():
    if not os.path.exists(INPUT_PATH):
        print(f"Input not found: {INPUT_PATH}")
        print("Run layer1_extract_knowledge.py first.")
        sys.exit(1)

    units = load_units(INPUT_PATH)
    print(f"=== LLM Pass 2: Dedup & Conflict Resolution ===")
    print(f"Input: {len(units)} knowledge units")

    # Group by category for faster comparison
    by_category: dict[str, list[KnowledgeUnit]] = defaultdict(list)
    for u in units:
        by_category[u.category.value].append(u)

    refined: list[KnowledgeUnit] = []
    conflict_log: list[dict] = []
    llm_calls = 0

    for cat, cat_units in by_category.items():
        print(f"\nCategory: {cat} ({len(cat_units)} units)")

        # Mark which units have been merged into another
        merged = set()
        cat_refined = []

        for i, unit_a in enumerate(cat_units):
            if i in merged:
                continue

            # Find similar units in same category
            similar_indices = []
            for j in range(i + 1, len(cat_units)):
                if j in merged:
                    continue
                sim = text_similarity(unit_a.rule, cat_units[j].rule)
                if sim >= SIMILARITY_THRESHOLD:
                    similar_indices.append(j)

            if not similar_indices:
                cat_refined.append(unit_a)
                continue

            # Process similar pairs with LLM
            current = unit_a
            for j in similar_indices:
                unit_b = cat_units[j]
                print(f"  Comparing: '{current.rule[:40]}...' vs '{unit_b.rule[:40]}...'", end="")

                try:
                    result_units = resolve_and_merge(current, unit_b)
                    llm_calls += 1

                    if len(result_units) == 1:
                        # AGREE: merged
                        current = result_units[0]
                        merged.add(j)
                        print(f" → MERGED (count={current.source_count})")
                    elif len(result_units) == 2:
                        if result_units[0].condition or result_units[1].condition:
                            # CONDITIONAL
                            current = result_units[0]
                            cat_refined.append(result_units[1])
                            merged.add(j)
                            print(f" → CONDITIONAL")
                        elif result_units[0].has_conflict_flag or result_units[1].has_conflict_flag:
                            # CONFLICT
                            current = result_units[0]
                            cat_refined.append(result_units[1])
                            merged.add(j)
                            conflict_log.append({
                                "rule_a": result_units[0].rule,
                                "rule_b": result_units[1].rule,
                                "winner": "A" if result_units[0].has_conflict_flag else "B",
                            })
                            print(f" → CONFLICT")
                        else:
                            merged.add(j)
                            current = result_units[0]
                            print(f" → AGREE (fallback)")

                except Exception as e:
                    print(f" → ERROR: {e}")
                    # On error, keep both
                    pass

            cat_refined.append(current)

        refined.extend(cat_refined)
        print(f"  → {len(cat_units)} → {len(cat_refined)} units")

    # Write refined output
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for unit in refined:
            f.write(json.dumps(unit.to_dict(), ensure_ascii=False) + "\n")

    # Write conflict log
    if conflict_log:
        with open(CONFLICT_LOG_PATH, "w", encoding="utf-8") as f:
            for entry in conflict_log:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print()
    print(f"=== Results ===")
    print(f"Input: {len(units)} units")
    print(f"Output: {len(refined)} units")
    print(f"Reduction: {len(units) - len(refined)} duplicates removed")
    print(f"LLM calls: {llm_calls}")
    print(f"Conflicts: {len(conflict_log)}")
    print(f"Output: {OUTPUT_PATH}")
    if conflict_log:
        print(f"Conflict log: {CONFLICT_LOG_PATH}")


if __name__ == "__main__":
    main()
