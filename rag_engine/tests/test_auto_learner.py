from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import auto_learner
from auto_learner import process_edit_feedback, get_learned_patterns, LearningResult


def setup_function():
    """Reset global state before each test."""
    auto_learner._histories.clear()
    auto_learner._learned_patterns.clear()


def test_no_change_returns_zero():
    result = process_edit_feedback("c1", "섹션1", "동일한 텍스트", "동일한 텍스트")
    assert result.edit_rate == 0.0
    assert result.new_diffs == 0
    assert result.promoted_patterns == []


def test_first_edit_records_only():
    result = process_edit_feedback("c1", "섹션1", "원본 내용", "수정 내용")
    assert result.new_diffs >= 1
    assert result.promoted_patterns == []  # 1회: 기록만


def test_second_edit_still_candidate():
    process_edit_feedback("c2", "섹션1", "원본 내용 A", "수정 내용 B")
    result = process_edit_feedback("c2", "섹션1", "원본 내용 A", "수정 내용 B")
    assert result.promoted_patterns == []  # 2회: 후보 마킹만


def test_third_edit_promotes_pattern():
    for _ in range(3):
        result = process_edit_feedback("c3", "섹션1", "원본 내용입니다", "수정된 내용입니다")

    assert len(result.promoted_patterns) >= 1
    assert result.notifications  # 사용자 알림 있어야 함
    assert "학습 완료" in result.notifications[0]

    # Verify pattern is stored
    patterns = get_learned_patterns("c3")
    assert len(patterns) >= 1


def test_already_learned_not_promoted_again():
    for _ in range(3):
        process_edit_feedback("c4", "섹션1", "원본 텍스트", "수정 텍스트")

    # 4th time — already learned, should not promote again
    result = process_edit_feedback("c4", "섹션1", "원본 텍스트", "수정 텍스트")
    assert result.promoted_patterns == []


def test_edit_rate_computed():
    result = process_edit_feedback("c5", "섹션1", "긴 원본 텍스트입니다 여러줄", "짧은 수정")
    assert result.edit_rate > 0.0


def test_save_load_round_trip(tmp_path):
    """save_state → load_state round-trip preserves histories + patterns."""
    # Internal composite key: "proposal:rt1" (default doc_type)
    composite_key = "proposal:rt1"

    # 1. Generate enough edits to promote a pattern
    for _ in range(3):
        process_edit_feedback("rt1", "섹션A", "원본 내용입니다", "수정된 내용입니다")

    patterns_before = auto_learner.get_learned_patterns("rt1")
    assert len(patterns_before) >= 1

    # Grab history state before save
    with auto_learner._lock:
        hist_before = auto_learner._histories.get(composite_key)
        pattern_counts_before = dict(hist_before.pattern_counts) if hist_before else {}
        diffs_count_before = len(hist_before.diffs) if hist_before else 0

    # 2. Save
    directory = str(tmp_path / "auto_learning")
    auto_learner.save_state(directory)

    # 3. Clear in-memory state
    auto_learner._histories.clear()
    auto_learner._learned_patterns.clear()

    assert auto_learner.get_learned_patterns("rt1") == []

    # 4. Load back
    auto_learner.load_state(directory)

    # 5. Verify patterns restored
    patterns_after = auto_learner.get_learned_patterns("rt1")
    assert len(patterns_after) == len(patterns_before)
    assert patterns_after[0].pattern_key == patterns_before[0].pattern_key
    assert patterns_after[0].occurrence_count == patterns_before[0].occurrence_count

    # 6. Verify histories restored
    with auto_learner._lock:
        hist_after = auto_learner._histories.get(composite_key)
        assert hist_after is not None
        assert hist_after.pattern_counts == pattern_counts_before
        assert len(hist_after.diffs) <= 50  # capped
        assert len(hist_after.diffs) == min(diffs_count_before, 50)

    # 7. Verify edit-rate history works after restore
    rates = auto_learner.get_edit_rate_history("rt1")
    assert len(rates) > 0


def test_load_state_missing_file(tmp_path):
    """load_state with non-existent directory should be a no-op."""
    auto_learner.load_state(str(tmp_path / "nonexistent"))
    # No crash, no side effects


def test_save_state_atomic(tmp_path):
    """save_state writes atomically (no partial file on crash)."""
    process_edit_feedback("at1", "섹션1", "원본", "수정")
    directory = str(tmp_path / "atomic_test")
    auto_learner.save_state(directory)
    # Verify file exists and is valid JSON
    import json
    state_path = os.path.join(directory, "learning_state.json")
    assert os.path.isfile(state_path)
    with open(state_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "histories" in data
    assert "learned_patterns" in data


def test_doc_type_isolates_patterns():
    """doc_type별 독립 카운터 검증: proposal과 wbs는 별도 패턴."""
    # proposal 3회 → 패턴 승격
    for _ in range(3):
        result = process_edit_feedback("dt1", "섹션1", "원본 내용입니다", "수정된 내용입니다", doc_type="proposal")
    assert len(result.promoted_patterns) >= 1
    assert "제안서" in result.notifications[0]

    # wbs 2회 → 아직 승격 안 됨 (독립 카운터)
    for _ in range(2):
        result = process_edit_feedback("dt1", "섹션1", "원본 내용입니다", "수정된 내용입니다", doc_type="wbs")
    assert result.promoted_patterns == []

    # wbs 3번째 → 승격
    result = process_edit_feedback("dt1", "섹션1", "원본 내용입니다", "수정된 내용입니다", doc_type="wbs")
    assert len(result.promoted_patterns) >= 1
    assert "WBS" in result.notifications[0]


def test_doc_type_get_learned_patterns():
    """get_learned_patterns가 doc_type별 분리 반환."""
    for _ in range(3):
        process_edit_feedback("dt2", "섹션1", "원본 내용입니다", "수정된 내용입니다", doc_type="ppt")

    ppt_patterns = get_learned_patterns("dt2", doc_type="ppt")
    proposal_patterns = get_learned_patterns("dt2", doc_type="proposal")
    assert len(ppt_patterns) >= 1
    assert len(proposal_patterns) == 0


def test_doc_type_invalid_falls_back_to_proposal():
    """유효하지 않은 doc_type은 proposal로 fallback."""
    result = process_edit_feedback("dt3", "섹션1", "원본", "수정", doc_type="invalid_type")
    # Should not crash, falls back to "proposal"
    assert result is not None


def test_promoted_pattern_triggers_profile_callback():
    """3회 반복 패턴 승격 시 콜백 호출."""
    from unittest.mock import MagicMock
    callback = MagicMock()

    for i in range(3):
        result = process_edit_feedback(
            company_id="cb_test",
            section_name="문체",
            original_text="이것은 테스트이다.",
            edited_text="이것은 테스트입니다.",
            doc_type="proposal",
            on_pattern_promoted=callback if i == 2 else None,
        )

    # 3회차에서 콜백 호출
    assert callback.called
    args = callback.call_args[0]
    assert args[0] == "cb_test"  # company_id
    assert len(args[1]) >= 1     # promoted patterns


def test_callback_failure_does_not_break_learning():
    """콜백 실패 시에도 학습 결과는 정상 반환."""
    def failing_callback(company_id, patterns):
        raise RuntimeError("test error")

    for i in range(3):
        result = process_edit_feedback(
            company_id="cb_fail",
            section_name="문체",
            original_text="이것은 테스트이다.",
            edited_text="이것은 테스트입니다.",
            doc_type="proposal",
            on_pattern_promoted=failing_callback if i == 2 else None,
        )

    # Learning result should still be valid despite callback failure
    assert len(result.promoted_patterns) >= 1
    assert result.notifications
