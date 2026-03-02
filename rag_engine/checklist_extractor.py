"""Submission Checklist Extractor — extract required documents from RFP.

Parses RFP analysis result to produce a submission checklist with
mandatory/optional documents, format hints, and deadline notes.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ChecklistItem:
    document_name: str        # "사업자등록증 사본"
    is_mandatory: bool = True
    format_hint: str = ""     # "PDF 또는 스캔본"
    deadline_note: str = ""   # "입찰마감일 2일 전까지"
    status: str = "pending"   # pending | uploaded | verified


# Common submission documents in Korean public procurement
_DEFAULT_MANDATORY = [
    ChecklistItem("사업자등록증 사본", True, "PDF/스캔본"),
    ChecklistItem("법인인감증명서", True, "원본 또는 PDF"),
    ChecklistItem("입찰참가신청서", True, "나라장터 양식"),
    ChecklistItem("청렴서약서", True, "나라장터 양식"),
]

_DOCUMENT_KEYWORDS: list[tuple[str, str, bool]] = [
    ("기술제안서", "DOCX/PDF", True),
    ("가격제안서", "나라장터 양식", True),
    ("사업수행계획서", "DOCX/PDF", True),
    ("과업이행계획서", "DOCX/PDF", True),
    ("소프트웨어사업 참여확인서", "PDF", False),
    ("실적증명서", "원본/PDF", True),
    ("재무제표", "최근 3개년", True),
    ("면허증 사본", "PDF/스캔본", True),
    ("인증서 사본", "PDF/스캔본", False),
    ("하도급계획서", "DOCX/PDF", False),
    ("보안서약서", "양식 별도", False),
    ("개인정보처리계획서", "DOCX/PDF", False),
    ("참여인력 경력증명서", "PDF/원본", True),
    ("투입인력 자격증 사본", "PDF/스캔본", True),
    ("컨소시엄 협정서", "원본", True),
    ("공동수급협정서", "나라장터 양식", True),
]


def extract_checklist(
    rfx_result: dict,
    rfp_text: str = "",
) -> list[ChecklistItem]:
    """Extract submission checklist from RFP analysis.

    Args:
        rfx_result: RFP analysis result dict (from rfx_analyzer).
        rfp_text: Optional raw RFP text for additional detection.

    Returns:
        List of ChecklistItem ordered by mandatory first.
    """
    items: list[ChecklistItem] = []
    seen: set[str] = set()

    # 1. From rfx_result.required_documents
    required_docs = rfx_result.get("required_documents", [])
    for doc_name in required_docs:
        if not isinstance(doc_name, str) or not doc_name.strip():
            continue
        name = doc_name.strip()
        if name not in seen:
            hint = _guess_format_hint(name)
            items.append(ChecklistItem(name, True, hint))
            seen.add(name)

    # 2. Keyword-based detection from RFP text
    search_text = rfp_text or rfx_result.get("rfp_text_summary", "")
    for keyword, fmt, mandatory in _DOCUMENT_KEYWORDS:
        if keyword in search_text and keyword not in seen:
            items.append(ChecklistItem(keyword, mandatory, fmt))
            seen.add(keyword)

    # 3. Add default mandatory if not already found
    for default in _DEFAULT_MANDATORY:
        if default.document_name not in seen:
            items.append(default)
            seen.add(default.document_name)

    # 4. Detect deadline notes from text
    deadline = rfx_result.get("deadline", "")
    if deadline:
        for item in items:
            if item.is_mandatory and not item.deadline_note:
                item.deadline_note = f"마감: {deadline}"

    # Sort: mandatory first, then alphabetical
    items.sort(key=lambda x: (not x.is_mandatory, x.document_name))
    return items


def _guess_format_hint(name: str) -> str:
    """Guess format hint from document name."""
    if "사본" in name or "증명" in name or "인증" in name:
        return "PDF/스캔본"
    if "계획서" in name or "제안서" in name:
        return "DOCX/PDF"
    if "양식" in name or "신청서" in name:
        return "나라장터 양식"
    return ""
