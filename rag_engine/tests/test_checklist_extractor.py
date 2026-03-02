from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from checklist_extractor import extract_checklist, ChecklistItem


def test_extract_from_required_documents():
    rfx = {
        "required_documents": ["기술제안서", "가격제안서", "사업자등록증 사본"],
        "deadline": "2026-03-15",
    }
    items = extract_checklist(rfx)
    names = [it.document_name for it in items]
    assert "기술제안서" in names
    assert "가격제안서" in names
    assert "사업자등록증 사본" in names
    # All should have deadline note
    mandatory = [it for it in items if it.is_mandatory]
    assert all(it.deadline_note for it in mandatory)


def test_keyword_detection_from_text():
    rfx = {
        "required_documents": [],
        "rfp_text_summary": "본 사업의 기술제안서와 실적증명서를 제출해야 합니다.",
    }
    items = extract_checklist(rfx)
    names = [it.document_name for it in items]
    assert "기술제안서" in names
    assert "실적증명서" in names


def test_default_mandatory_included():
    rfx = {"required_documents": []}
    items = extract_checklist(rfx)
    names = [it.document_name for it in items]
    assert "사업자등록증 사본" in names
    assert "입찰참가신청서" in names


def test_no_duplicates():
    rfx = {
        "required_documents": ["사업자등록증 사본"],  # also in defaults
    }
    items = extract_checklist(rfx)
    names = [it.document_name for it in items]
    assert names.count("사업자등록증 사본") == 1


def test_mandatory_first_ordering():
    rfx = {
        "required_documents": [],
        "rfp_text_summary": "소프트웨어사업 참여확인서 제출",  # optional
    }
    items = extract_checklist(rfx)
    # First items should be mandatory
    mandatory_seen = False
    optional_seen = False
    for it in items:
        if it.is_mandatory:
            assert not optional_seen, "Mandatory item after optional"
            mandatory_seen = True
        else:
            optional_seen = True
