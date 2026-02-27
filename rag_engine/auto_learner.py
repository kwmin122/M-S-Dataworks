"""Auto-Learning Pipeline — edit diffs to Layer 2 patterns.

When a user repeatedly edits AI-generated text in the same way (3+ times),
the pattern is automatically promoted to Layer 2 company-specific rules.

Flow:
  1회: 기록만 (학습 안 함)
  2회: 후보로 마킹
  3회+: Layer 2 자동 반영 + 사용자 알림 메시지 반환
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field, asdict
from typing import Optional

from diff_tracker import (
    EditDiff,
    EditHistory,
    extract_diffs,
    update_history,
    detect_recurring_patterns,
    compute_edit_rate,
)


@dataclass
class LearnedPattern:
    """A pattern learned from repeated user edits."""
    pattern_key: str
    diff_type: str          # replace | delete | insert
    section_name: str
    original_example: str   # what AI wrote
    edited_example: str     # what user changed it to
    occurrence_count: int
    description: str        # human-readable description


@dataclass
class LearningResult:
    """Result of processing edit feedback."""
    edit_rate: float                      # 0~1, how much was changed
    new_diffs: int                        # number of diffs found
    promoted_patterns: list[LearnedPattern]  # patterns reaching threshold
    notifications: list[str]              # user-facing messages


# In-memory store for edit histories (keyed by company_id)
_histories: dict[str, EditHistory] = {}
_learned_patterns: dict[str, list[LearnedPattern]] = {}
_lock = threading.Lock()

PATTERN_THRESHOLD = 3


def process_edit_feedback(
    company_id: str,
    section_name: str,
    original_text: str,
    edited_text: str,
) -> LearningResult:
    """Process user edits and extract/promote patterns.

    Args:
        company_id: Company identifier.
        section_name: Which proposal section was edited.
        original_text: AI-generated text.
        edited_text: User-modified text.

    Returns:
        LearningResult with edit rate, new diffs, promoted patterns, notifications.
    """
    # Extract diffs (pure computation, no shared state)
    diffs = extract_diffs(section_name, original_text, edited_text)
    if not diffs:
        return LearningResult(
            edit_rate=0.0,
            new_diffs=0,
            promoted_patterns=[],
            notifications=[],
        )

    rate = compute_edit_rate(original_text, edited_text)

    with _lock:
        # Get or create history
        if company_id not in _histories:
            _histories[company_id] = EditHistory(company_id=company_id)
        history = _histories[company_id]

        # Update history with new diffs
        update_history(history, diffs)

        # Check for patterns reaching threshold
        recurring = detect_recurring_patterns(history, threshold=PATTERN_THRESHOLD)
        already_learned = {p.pattern_key for p in _learned_patterns.get(company_id, [])}

        new_promoted: list[LearnedPattern] = []
        notifications: list[str] = []

        for diff in recurring:
            if diff.pattern_key in already_learned:
                continue

            pattern = LearnedPattern(
                pattern_key=diff.pattern_key,
                diff_type=diff.diff_type,
                section_name=diff.section_name,
                original_example=diff.original[:200],
                edited_example=diff.edited[:200],
                occurrence_count=diff.occurrence_count,
                description=_describe_pattern(diff),
            )
            new_promoted.append(pattern)

            if company_id not in _learned_patterns:
                _learned_patterns[company_id] = []
            _learned_patterns[company_id].append(pattern)

            notifications.append(
                f"학습 완료: \"{diff.section_name}\" 섹션에서 반복 수정 패턴을 감지했습니다. "
                f"({diff.occurrence_count}회 반복) 다음 생성 시 자동 반영됩니다."
            )

    return LearningResult(
        edit_rate=rate,
        new_diffs=len(diffs),
        promoted_patterns=new_promoted,
        notifications=notifications,
    )


def get_learned_patterns(company_id: str) -> list[LearnedPattern]:
    """Get all learned patterns for a company."""
    with _lock:
        return list(_learned_patterns.get(company_id, []))


def get_edit_rate_history(company_id: str) -> list[float]:
    """Get historical edit rates for tracking quality improvement."""
    with _lock:
        history = _histories.get(company_id)
        if not history:
            return []
        return [compute_edit_rate(d.original, d.edited) for d in history.diffs if d.original]


def save_state(directory: str) -> None:
    """Persist learning state to disk.

    Saves both pattern_counts and the most recent 50 diffs per company
    so that edit-rate history can be restored on reload.
    """
    os.makedirs(directory, exist_ok=True)
    max_diffs = 50
    with _lock:
        state = {
            "histories": {
                cid: {
                    "company_id": h.company_id,
                    "pattern_counts": h.pattern_counts,
                    "diffs": [
                        {
                            "section_name": d.section_name,
                            "original": d.original[:500],
                            "edited": d.edited[:500],
                            "diff_type": d.diff_type,
                            "pattern_key": d.pattern_key,
                            "occurrence_count": d.occurrence_count,
                        }
                        for d in h.diffs[-max_diffs:]
                    ],
                }
                for cid, h in _histories.items()
            },
            "learned_patterns": {
                cid: [asdict(p) for p in patterns]
                for cid, patterns in _learned_patterns.items()
            },
        }
        path = os.path.join(directory, "learning_state.json")
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)


def load_state(directory: str) -> None:
    """Restore learning state from disk.

    Reads ``learning_state.json`` and repopulates ``_histories`` and
    ``_learned_patterns``.  Safe to call even if the file does not exist.
    """
    path = os.path.join(directory, "learning_state.json")
    if not os.path.isfile(path):
        return

    with open(path, "r", encoding="utf-8") as f:
        state = json.load(f)

    with _lock:
        # Restore histories
        for cid, hdata in state.get("histories", {}).items():
            history = EditHistory(
                company_id=hdata.get("company_id", cid),
                pattern_counts=hdata.get("pattern_counts", {}),
            )
            for d in hdata.get("diffs", []):
                history.diffs.append(EditDiff(
                    section_name=d.get("section_name", ""),
                    original=d.get("original", ""),
                    edited=d.get("edited", ""),
                    diff_type=d.get("diff_type", "replace"),
                    pattern_key=d.get("pattern_key", ""),
                    occurrence_count=d.get("occurrence_count", 1),
                ))
            _histories[cid] = history

        # Restore learned patterns
        for cid, plist in state.get("learned_patterns", {}).items():
            _learned_patterns[cid] = [
                LearnedPattern(
                    pattern_key=p["pattern_key"],
                    diff_type=p["diff_type"],
                    section_name=p["section_name"],
                    original_example=p["original_example"],
                    edited_example=p["edited_example"],
                    occurrence_count=p["occurrence_count"],
                    description=p["description"],
                )
                for p in plist
            ]


def _describe_pattern(diff: EditDiff) -> str:
    """Generate human-readable description of a learned pattern."""
    if diff.diff_type == "replace":
        orig_preview = diff.original[:50]
        edit_preview = diff.edited[:50]
        return f"'{orig_preview}...' → '{edit_preview}...' 형태의 반복 수정"
    elif diff.diff_type == "delete":
        return f"'{diff.original[:50]}...' 삭제 패턴"
    else:
        return f"'{diff.edited[:50]}...' 추가 패턴"
