#!/usr/bin/env python3
"""Step 8: Search test — verify the knowledge DB works correctly.

Runs sample queries against the built ChromaDB and prints results.
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "rag_engine"))

from knowledge_db import KnowledgeDB
from knowledge_models import KnowledgeCategory

DB_PATH = os.path.join(BASE_DIR, "data/knowledge_db")

TEST_QUERIES = [
    ("제안서 목차 구성은 어떻게 해야 하나요?", None),
    ("기술 평가에서 높은 점수를 받으려면?", KnowledgeCategory.EVALUATION),
    ("제안서 요약문 작성 팁", KnowledgeCategory.WRITING),
    ("사업 수행 계획서 일정 작성법", KnowledgeCategory.STRUCTURE),
    ("입찰 참가 자격 요건 확인 방법", KnowledgeCategory.COMPLIANCE),
    ("경쟁 PT 발표 전략", KnowledgeCategory.STRATEGY),
    ("제안서 시각 디자인 가이드", KnowledgeCategory.VISUAL),
    ("흔히 하는 제안서 실수", KnowledgeCategory.PITFALL),
]


def main():
    if not os.path.exists(DB_PATH):
        print(f"DB not found: {DB_PATH}")
        print("Run layer1_build_vectordb.py first.")
        sys.exit(1)

    db = KnowledgeDB(persist_directory=DB_PATH)
    total = db.count()
    print(f"=== Knowledge DB Search Test ===")
    print(f"Total units in DB: {total}")
    print()

    for query, category in TEST_QUERIES:
        cat_label = category.value if category else "ALL"
        print(f"--- Query: \"{query}\" [category={cat_label}] ---")

        results = db.search(query, top_k=3, category=category)
        if not results:
            print("  (no results)")
        else:
            for i, unit in enumerate(results, 1):
                score = unit.effective_score()
                print(f"  [{i}] ({unit.category.value}/{unit.source_type.value}) "
                      f"score={score:.3f} count={unit.source_count}")
                print(f"      rule: {unit.rule[:100]}")
                if unit.condition:
                    print(f"      condition: {unit.condition[:80]}")
        print()

    print("=== Search Test Complete ===")


if __name__ == "__main__":
    main()
