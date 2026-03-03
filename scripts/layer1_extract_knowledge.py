#!/usr/bin/env python3
"""Step 5: LLM Pass 1 — Extract knowledge units from all raw text.

Reads all .txt files from raw_transcripts/, raw_blogs/, raw_documents/,
calls knowledge_harvester.extract_knowledge_units() for each,
saves results to data/layer1/extracted/knowledge.jsonl.
"""
import glob
import json
import os
import sys
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "rag_engine"))

from knowledge_harvester import extract_knowledge_units
from knowledge_models import SourceType

RAW_DIRS = {
    "raw_transcripts": SourceType.YOUTUBE,
    "raw_blogs": SourceType.BLOG,
    "raw_documents": SourceType.OFFICIAL_GUIDE,
}
OUTPUT_PATH = os.path.join(BASE_DIR, "data/layer1/extracted/knowledge.jsonl")


def detect_source_type_from_header(text: str, default: SourceType) -> SourceType:
    """Detect more specific source type from file header metadata."""
    first_500 = text[:500].lower()
    if "grade: s" in first_500 and "youtube" in first_500:
        # S-grade YouTube = winner stories or evaluator perspectives
        return SourceType.WINNER_STORY
    if "grade: a" in first_500 and ("조달청" in first_500 or "나라장터" in first_500):
        return SourceType.EVALUATOR_YOUTUBE
    if "official document" in first_500 or "공식" in first_500:
        return SourceType.OFFICIAL_GUIDE
    return default


def extract_source_id(filepath: str) -> str:
    """Extract a source ID from the filename."""
    return os.path.splitext(os.path.basename(filepath))[0]


def load_done_source_ids(path: str) -> set[str]:
    """Load source_ids already extracted (for resume support)."""
    done = set()
    if not os.path.exists(path):
        return done
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                if "source_id" in d:
                    done.add(d["source_id"])
            except json.JSONDecodeError:
                continue
    return done


def main():
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    # Collect all files
    all_files = []
    for subdir, src_type in RAW_DIRS.items():
        pattern = os.path.join(BASE_DIR, "data/layer1", subdir, "*.txt")
        for fpath in sorted(glob.glob(pattern)):
            if os.path.getsize(fpath) > 100:
                all_files.append((fpath, src_type))

    total = len(all_files)
    if total == 0:
        print("No raw text files found. Run collection scripts first.")
        sys.exit(1)

    # Resume: skip already-processed source_ids
    done_ids = load_done_source_ids(OUTPUT_PATH)

    print(f"=== LLM Pass 1: Knowledge Extraction ===")
    print(f"Files to process: {total} ({len(done_ids)} already done, resuming)")
    print(f"Output: {OUTPUT_PATH}")
    print()

    total_units = 0
    errors = 0
    skipped = 0

    with open(OUTPUT_PATH, "a", encoding="utf-8") as out:
        for i, (fpath, default_type) in enumerate(all_files, 1):
            fname = os.path.basename(fpath)
            source_id = extract_source_id(fpath)

            if source_id in done_ids:
                skipped += 1
                print(f"[{i}/{total}] {fname}... CACHED")
                continue

            print(f"[{i}/{total}] {fname}...", end="", flush=True)

            try:
                with open(fpath, encoding="utf-8") as f:
                    text = f.read()

                src_type = detect_source_type_from_header(text, default_type)

                units = extract_knowledge_units(
                    text=text,
                    source_type=src_type,
                    source_id=source_id,
                    source_date="2026-02",
                )

                for unit in units:
                    out.write(json.dumps(unit.to_dict(), ensure_ascii=False) + "\n")
                out.flush()

                total_units += len(units)
                print(f" {len(units)} units extracted")

            except Exception as e:
                errors += 1
                print(f" ERROR: {e}")

            # Small delay between API calls
            time.sleep(0.3)

    print()
    print(f"=== Results ===")
    print(f"Processed: {total - errors - skipped}/{total} files (new)")
    print(f"Resumed from cache: {skipped}")
    print(f"Total new knowledge units: {total_units}")
    print(f"Errors: {errors}")
    print(f"Output: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
