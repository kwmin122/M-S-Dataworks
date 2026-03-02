from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from diff_tracker import (
    extract_diffs,
    extract_structured_diff,
    update_history,
    detect_recurring_patterns,
    compute_edit_rate,
    EditHistory,
)


def test_no_diff_when_identical():
    diffs = extract_diffs("섹션1", "동일한 텍스트", "동일한 텍스트")
    assert diffs == []


def test_extract_replacement_diff():
    original = "본 사업은 클라우드 전환 프로젝트이다.\n목표는 가용성 향상이다."
    edited = "본 사업은 AWS 클라우드 마이그레이션 프로젝트이다.\n목표는 가용성 향상이다."
    diffs = extract_diffs("제안개요", original, edited)
    assert len(diffs) >= 1
    assert diffs[0].diff_type == "replace"
    assert diffs[0].section_name == "제안개요"


def test_extract_insert_diff():
    original = "첫번째 줄\n세번째 줄"
    edited = "첫번째 줄\n두번째 줄 추가\n세번째 줄"
    diffs = extract_diffs("기술", original, edited)
    assert any(d.diff_type == "insert" for d in diffs)


def test_extract_delete_diff():
    original = "첫번째 줄\n삭제할 줄\n세번째 줄"
    edited = "첫번째 줄\n세번째 줄"
    diffs = extract_diffs("기술", original, edited)
    assert any(d.diff_type == "delete" for d in diffs)


def test_update_history_counts():
    history = EditHistory(company_id="test")
    diffs1 = extract_diffs("s1", "원본 텍스트 A", "수정 텍스트 B")
    updated = update_history(history, diffs1)
    assert all(d.occurrence_count == 1 for d in updated)

    # Same diff again
    diffs2 = extract_diffs("s1", "원본 텍스트 A", "수정 텍스트 B")
    updated2 = update_history(history, diffs2)
    assert all(d.occurrence_count == 2 for d in updated2)


def test_detect_recurring_patterns():
    history = EditHistory(company_id="test")
    for _ in range(3):
        diffs = extract_diffs("s1", "원본 내용입니다", "수정된 내용입니다")
        update_history(history, diffs)

    recurring = detect_recurring_patterns(history, threshold=3)
    assert len(recurring) >= 1
    assert recurring[0].occurrence_count >= 3


def test_compute_edit_rate():
    assert compute_edit_rate("동일", "동일") == 0.0
    assert compute_edit_rate("", "") == 0.0
    assert compute_edit_rate("텍스트", "") == 1.0
    rate = compute_edit_rate("원본 텍스트입니다", "수정된 텍스트입니다")
    assert 0.0 < rate < 1.0


def test_extract_structured_diff_replace():
    """WBS 태스크 기간 변경 등 필드 replace 감지."""
    original = {"task_name": "요구분석", "duration_months": 2, "deliverables": ["요구사항정의서"]}
    edited = {"task_name": "요구분석", "duration_months": 3, "deliverables": ["요구사항정의서", "추가산출물"]}
    diffs = extract_structured_diff("WBS", original, edited)
    assert len(diffs) == 2  # duration_months + deliverables changed
    changed_keys = {d.section_name for d in diffs}
    assert "WBS/duration_months" in changed_keys
    assert "WBS/deliverables" in changed_keys
    assert all(d.diff_type == "replace" for d in diffs)


def test_extract_structured_diff_insert_delete():
    """필드 추가/삭제 감지."""
    original = {"title": "기술 방안", "body": "기존 내용"}
    edited = {"title": "기술 방안", "notes": "새로운 노트"}  # body 삭제, notes 추가
    diffs = extract_structured_diff("PPT", original, edited)
    types = {d.diff_type for d in diffs}
    assert "delete" in types  # body 삭제
    assert "insert" in types  # notes 추가


def test_extract_structured_diff_no_change():
    """변경 없으면 빈 리스트."""
    original = {"task_name": "착수", "duration_months": 1}
    edited = {"task_name": "착수", "duration_months": 1}
    diffs = extract_structured_diff("WBS", original, edited)
    assert diffs == []
