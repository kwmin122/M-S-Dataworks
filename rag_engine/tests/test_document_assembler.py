from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from document_assembler import assemble_docx


def test_assemble_basic_docx(tmp_path):
    sections = [
        ("제안 개요", "## 제안 개요\n\n본 사업은 XX기관의 정보시스템 구축을 위한 제안입니다."),
        ("기술적 접근방안", "## 기술적 접근방안\n\n### 시스템 아키텍처\n\n3-tier 구조로 구성합니다.\n\n- 웹서버: Nginx\n- WAS: Spring Boot\n- DB: PostgreSQL"),
    ]
    out_path = str(tmp_path / "proposal.docx")
    result = assemble_docx(
        title="XX기관 정보시스템 구축 제안서",
        sections=sections,
        output_path=out_path,
    )
    assert os.path.exists(result)
    assert result.endswith(".docx")
    assert os.path.getsize(result) > 1000


def test_assemble_empty_sections(tmp_path):
    out_path = str(tmp_path / "empty.docx")
    result = assemble_docx(
        title="빈 제안서",
        sections=[],
        output_path=out_path,
    )
    assert os.path.exists(result)
