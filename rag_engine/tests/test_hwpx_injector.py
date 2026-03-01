"""Tests for hwpx_injector — markdown → HWPX XML injection into templates.

TDD red-phase: all tests written before implementation.
"""
from __future__ import annotations

import os
import sys
import zipfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_template(tmp_path, sections_content=None):
    """Create test HWPX template with placeholders."""
    if sections_content is None:
        sections_content = '''<?xml version="1.0" encoding="UTF-8"?>
<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"
         xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">
  <hp:p>
    <hp:run><hp:t>표지 내용</hp:t></hp:run>
  </hp:p>
  <hp:p>
    <hp:run><hp:t>{{SECTION:개요}}</hp:t></hp:run>
  </hp:p>
  <hp:p>
    <hp:run><hp:t>{{SECTION:기술방안}}</hp:t></hp:run>
  </hp:p>
</hs:sec>'''
    path = str(tmp_path / "template.hwpx")
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("Contents/section0.xml", sections_content)
        zf.writestr("Contents/content.hpf", "<hpf/>")
    return path


# ---------------------------------------------------------------------------
# markdown_to_hwpx_elements tests
# ---------------------------------------------------------------------------


class TestMarkdownToHwpxElements:
    """Unit tests for markdown_to_hwpx_elements."""

    def test_heading(self):
        from hwpx_injector import markdown_to_hwpx_elements

        elements = markdown_to_hwpx_elements("# 제안 개요\n\n본문입니다.")
        assert len(elements) >= 2
        # heading should have bold or large font
        heading_xml = elements[0]
        assert "제안 개요" in heading_xml

    def test_heading_levels(self):
        from hwpx_injector import markdown_to_hwpx_elements

        h1 = markdown_to_hwpx_elements("# H1")[0]
        h2 = markdown_to_hwpx_elements("## H2")[0]
        h3 = markdown_to_hwpx_elements("### H3")[0]
        # h1 should have val="2400", h2 val="2000", h3 val="1600"
        assert 'val="2400"' in h1
        assert 'val="2000"' in h2
        assert 'val="1600"' in h3

    def test_bold(self):
        from hwpx_injector import markdown_to_hwpx_elements

        elements = markdown_to_hwpx_elements("이것은 **중요한** 텍스트입니다.")
        xml_str = "\n".join(elements)
        assert "bold" in xml_str.lower()
        assert "중요한" in xml_str

    def test_italic(self):
        from hwpx_injector import markdown_to_hwpx_elements

        elements = markdown_to_hwpx_elements("이것은 *이탤릭* 텍스트입니다.")
        xml_str = "\n".join(elements)
        assert "italic" in xml_str.lower()
        assert "이탤릭" in xml_str

    def test_bullet(self):
        from hwpx_injector import markdown_to_hwpx_elements

        elements = markdown_to_hwpx_elements("- 항목1\n- 항목2\n- 항목3")
        assert len(elements) >= 3
        combined = "\n".join(elements)
        assert "항목1" in combined
        assert "항목3" in combined

    def test_bullet_contains_marker(self):
        from hwpx_injector import markdown_to_hwpx_elements

        elements = markdown_to_hwpx_elements("- 항목1")
        combined = "\n".join(elements)
        # Should contain bullet character
        assert "\u2022" in combined or "bullet" in combined.lower()

    def test_empty(self):
        from hwpx_injector import markdown_to_hwpx_elements

        elements = markdown_to_hwpx_elements("")
        assert elements == []

    def test_plain_paragraph(self):
        from hwpx_injector import markdown_to_hwpx_elements

        elements = markdown_to_hwpx_elements("일반 텍스트 문단입니다.")
        assert len(elements) == 1
        assert "일반 텍스트 문단입니다." in elements[0]
        assert "<hp:p" in elements[0]
        assert "<hp:t>" in elements[0]

    def test_xml_namespace_present(self):
        from hwpx_injector import markdown_to_hwpx_elements

        elements = markdown_to_hwpx_elements("테스트 문단")
        for elem in elements:
            assert "hp:" in elem

    def test_xml_escape_special_chars(self):
        from hwpx_injector import markdown_to_hwpx_elements

        elements = markdown_to_hwpx_elements("A < B & C > D")
        xml_str = "\n".join(elements)
        # Raw < and > and & must be escaped
        assert "&lt;" in xml_str
        assert "&amp;" in xml_str
        assert "&gt;" in xml_str

    def test_table_as_text(self):
        from hwpx_injector import markdown_to_hwpx_elements

        md = "| 컬럼1 | 컬럼2 |\n|-------|-------|\n| 값1 | 값2 |"
        elements = markdown_to_hwpx_elements(md)
        combined = "\n".join(elements)
        assert "컬럼1" in combined
        assert "값1" in combined

    def test_mixed_content(self):
        from hwpx_injector import markdown_to_hwpx_elements

        md = "# 제목\n\n본문 **강조** 포함\n\n- 항목A\n- 항목B"
        elements = markdown_to_hwpx_elements(md)
        assert len(elements) >= 4  # heading + paragraph + 2 bullet items
        combined = "\n".join(elements)
        assert "제목" in combined
        assert "강조" in combined
        assert "항목A" in combined


# ---------------------------------------------------------------------------
# inject_content tests
# ---------------------------------------------------------------------------


class TestInjectContent:
    """Integration tests for inject_content."""

    def test_replaces_placeholder(self, tmp_path):
        from hwpx_injector import inject_content
        from hwpx_parser import extract_hwpx_text

        template = _make_template(tmp_path)
        output = str(tmp_path / "output.hwpx")

        inject_content(
            template_path=template,
            sections={
                "개요": "## 제안 개요\n\n본 사업은 **클라우드 전환** 프로젝트입니다.",
                "기술방안": "## 기술적 접근\n\n- React\n- FastAPI\n- PostgreSQL",
            },
            output_path=output,
        )
        assert os.path.exists(output)
        text = extract_hwpx_text(output)
        assert "클라우드 전환" in text
        assert "{{SECTION:" not in text  # placeholders removed

    def test_preserves_non_placeholder(self, tmp_path):
        from hwpx_injector import inject_content
        from hwpx_parser import extract_hwpx_text

        template = _make_template(tmp_path)
        output = str(tmp_path / "output.hwpx")

        inject_content(template, {"개요": "내용", "기술방안": "기술 내용"}, output)
        text = extract_hwpx_text(output)
        assert "표지 내용" in text

    def test_missing_section_keeps_placeholder(self, tmp_path):
        from hwpx_injector import inject_content
        from hwpx_parser import extract_hwpx_text

        template = _make_template(tmp_path)
        output = str(tmp_path / "output.hwpx")

        # Only provide one section
        inject_content(template, {"개요": "개요 내용만"}, output)
        text = extract_hwpx_text(output)
        assert "개요 내용" in text
        # 기술방안 placeholder still present
        assert "기술방안" in text

    def test_creates_output_dir(self, tmp_path):
        from hwpx_injector import inject_content

        template = _make_template(tmp_path)
        output = str(tmp_path / "subdir" / "deep" / "output.hwpx")

        result = inject_content(template, {"개요": "테스트"}, output)
        assert os.path.exists(result)

    def test_preserves_other_zip_entries(self, tmp_path):
        from hwpx_injector import inject_content

        template = _make_template(tmp_path)
        output = str(tmp_path / "output.hwpx")

        inject_content(template, {"개요": "내용"}, output)
        with zipfile.ZipFile(output, "r") as zf:
            names = zf.namelist()
            assert "Contents/content.hpf" in names
            assert "Contents/section0.xml" in names

    def test_returns_output_path(self, tmp_path):
        from hwpx_injector import inject_content

        template = _make_template(tmp_path)
        output = str(tmp_path / "output.hwpx")

        result = inject_content(template, {"개요": "내용"}, output)
        assert result == output

    def test_multiple_sections_in_one_xml(self, tmp_path):
        """Both placeholders in the same section*.xml are replaced."""
        from hwpx_injector import inject_content
        from hwpx_parser import extract_hwpx_text

        template = _make_template(tmp_path)
        output = str(tmp_path / "output.hwpx")

        inject_content(
            template,
            {"개요": "개요 작성됨", "기술방안": "기술방안 작성됨"},
            output,
        )
        text = extract_hwpx_text(output)
        assert "개요 작성됨" in text
        assert "기술방안 작성됨" in text
        assert "{{SECTION:" not in text

    def test_multi_section_files(self, tmp_path):
        """Handles HWPX with multiple section*.xml files."""
        from hwpx_injector import inject_content
        from hwpx_parser import extract_hwpx_text

        sec0 = '''<?xml version="1.0" encoding="UTF-8"?>
<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"
         xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">
  <hp:p><hp:run><hp:t>{{SECTION:파트A}}</hp:t></hp:run></hp:p>
</hs:sec>'''
        sec1 = '''<?xml version="1.0" encoding="UTF-8"?>
<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"
         xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">
  <hp:p><hp:run><hp:t>{{SECTION:파트B}}</hp:t></hp:run></hp:p>
</hs:sec>'''
        path = str(tmp_path / "multi.hwpx")
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("Contents/section0.xml", sec0)
            zf.writestr("Contents/section1.xml", sec1)
            zf.writestr("Contents/content.hpf", "<hpf/>")

        output = str(tmp_path / "output.hwpx")
        inject_content(
            path,
            {"파트A": "A 내용", "파트B": "B 내용"},
            output,
        )
        text = extract_hwpx_text(output)
        assert "A 내용" in text
        assert "B 내용" in text
        assert "{{SECTION:" not in text
