"""Diff Tracker — track AI-generated vs user-edited text.

Computes diffs, stores edit history, detects recurring patterns
for the RLHF-style proposal learning loop.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EditDiff:
    section_name: str
    original: str          # AI-generated
    edited: str            # user-modified
    diff_type: str         # "replace" | "delete" | "insert"
    pattern_key: str       # normalized pattern for matching
    occurrence_count: int = 1


@dataclass
class EditHistory:
    """Accumulated edit history for a company."""
    company_id: str
    diffs: list[EditDiff] = field(default_factory=list)
    pattern_counts: dict[str, int] = field(default_factory=dict)  # pattern_key → count


def extract_diffs(
    section_name: str,
    original: str,
    edited: str,
) -> list[EditDiff]:
    """Extract diffs between AI-generated and user-edited text.

    Args:
        section_name: Name of the proposal section.
        original: AI-generated text.
        edited: User-modified text.

    Returns:
        List of EditDiff items.
    """
    if original.strip() == edited.strip():
        return []

    diffs: list[EditDiff] = []
    orig_lines = original.splitlines(keepends=True)
    edit_lines = edited.splitlines(keepends=True)

    matcher = difflib.SequenceMatcher(None, orig_lines, edit_lines)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue

        orig_chunk = "".join(orig_lines[i1:i2]).strip()
        edit_chunk = "".join(edit_lines[j1:j2]).strip()

        if tag == "replace":
            diff_type = "replace"
        elif tag == "delete":
            diff_type = "delete"
        elif tag == "insert":
            diff_type = "insert"
        else:
            continue

        pattern_key = _compute_pattern_key(diff_type, orig_chunk, edit_chunk)
        diffs.append(EditDiff(
            section_name=section_name,
            original=orig_chunk,
            edited=edit_chunk,
            diff_type=diff_type,
            pattern_key=pattern_key,
        ))

    return diffs


def update_history(
    history: EditHistory,
    new_diffs: list[EditDiff],
) -> list[EditDiff]:
    """Update edit history with new diffs. Returns diffs with updated counts.

    Each diff's occurrence_count reflects how many times the same pattern
    has been seen across all edits.
    """
    for diff in new_diffs:
        count = history.pattern_counts.get(diff.pattern_key, 0) + 1
        history.pattern_counts[diff.pattern_key] = count
        diff.occurrence_count = count
        history.diffs.append(diff)
    return new_diffs


def detect_recurring_patterns(
    history: EditHistory,
    threshold: int = 3,
) -> list[EditDiff]:
    """Find patterns that recur >= threshold times.

    Returns representative EditDiff for each recurring pattern.
    """
    recurring: list[EditDiff] = []
    seen_keys: set[str] = set()

    for diff in reversed(history.diffs):
        count = history.pattern_counts.get(diff.pattern_key, 0)
        if count >= threshold and diff.pattern_key not in seen_keys:
            diff.occurrence_count = count
            recurring.append(diff)
            seen_keys.add(diff.pattern_key)

    return recurring


def compute_edit_rate(original: str, edited: str) -> float:
    """Compute edit rate (0.0 = no change, 1.0 = completely different).

    Uses character-level similarity ratio.
    """
    if not original and not edited:
        return 0.0
    if not original or not edited:
        return 1.0
    ratio = difflib.SequenceMatcher(None, original, edited).ratio()
    return round(1.0 - ratio, 3)


def _compute_pattern_key(diff_type: str, original: str, edited: str) -> str:
    """Compute a normalized pattern key for grouping similar edits.

    Normalizes by:
    - Removing specific numbers/dates
    - Lowering Korean particles variation
    - Hashing the result
    """
    combined = f"{diff_type}:{_normalize_text(original)}→{_normalize_text(edited)}"
    return hashlib.sha256(combined.encode()).hexdigest()[:12]


def extract_structured_diff(
    section_name: str,
    original_dict: dict,
    edited_dict: dict,
) -> list[EditDiff]:
    """Extract diffs from structured data (WBS tasks, PPT slides, etc.).

    Compares dict fields and generates EditDiff for each changed field.
    Useful for WBS (task duration/deliverables changes) and PPT (slide content changes).

    Args:
        section_name: Name of the document section.
        original_dict: AI-generated structured data.
        edited_dict: User-modified structured data.

    Returns:
        List of EditDiff items for changed fields.
    """
    diffs: list[EditDiff] = []

    all_keys = set(original_dict.keys()) | set(edited_dict.keys())
    for key in sorted(all_keys):
        orig_val = original_dict.get(key)
        edit_val = edited_dict.get(key)

        if orig_val == edit_val:
            continue

        orig_str = json.dumps(orig_val, sort_keys=True, ensure_ascii=False, default=str) if orig_val is not None else ""
        edit_str = json.dumps(edit_val, sort_keys=True, ensure_ascii=False, default=str) if edit_val is not None else ""

        if orig_val is None:
            diff_type = "insert"
        elif edit_val is None:
            diff_type = "delete"
        else:
            diff_type = "replace"

        pattern_key = _compute_pattern_key(
            diff_type,
            f"{section_name}:{key}:{orig_str}",
            edit_str,
        )
        diffs.append(EditDiff(
            section_name=f"{section_name}/{key}",
            original=orig_str,
            edited=edit_str,
            diff_type=diff_type,
            pattern_key=pattern_key,
        ))

    return diffs


def _normalize_text(text: str) -> str:
    """Normalize text for pattern matching."""
    text = re.sub(r'\d+', 'N', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:200]  # Cap length for pattern key
