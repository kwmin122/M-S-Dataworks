"""HWPX parser tests — TDD-first for hwpx_parser.py.

HWPX files are ZIP archives with Contents/section*.xml containing
paragraph XML in the Hancom HWPML 2011 namespace.
"""
from __future__ import annotations

import os
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from hwpx_parser import extract_hwpx_styles, extract_hwpx_text, is_hwpx_file


# ---------------------------------------------------------------------------
# Helpers — build minimal HWPX archives in tmp_path
# ---------------------------------------------------------------------------

SECTION_XML_TWO_PARAGRAPHS = """\
<?xml version="1.0" encoding="UTF-8"?>
<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"
         xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">
  <hp:p>
    <hp:run>
      <hp:t>본 사업은 클라우드 전환입니다.</hp:t>
    </hp:run>
  </hp:p>
  <hp:p>
    <hp:run>
      <hp:t>두 번째 문단입니다.</hp:t>
    </hp:run>
  </hp:p>
</hs:sec>"""

SECTION_XML_WITH_STYLES = """\
<?xml version="1.0" encoding="UTF-8"?>
<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"
         xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">
  <hp:p>
    <hp:run>
      <hp:rPr>
        <hp:fontRef hangul="함초롬바탕" latin="Times New Roman"/>
        <hp:sz val="2200"/>
      </hp:rPr>
      <hp:t>본문 텍스트</hp:t>
    </hp:run>
  </hp:p>
  <hp:p>
    <hp:run>
      <hp:rPr>
        <hp:fontRef hangul="함초롬바탕"/>
        <hp:sz val="2200"/>
      </hp:rPr>
      <hp:t>또 다른 본문</hp:t>
    </hp:run>
  </hp:p>
  <hp:p>
    <hp:run>
      <hp:rPr>
        <hp:fontRef hangul="함초롬돋움"/>
        <hp:sz val="3200"/>
      </hp:rPr>
      <hp:t>제목</hp:t>
    </hp:run>
  </hp:p>
</hs:sec>"""


def _make_hwpx(tmp_path, name: str, section_xml: str | None = None) -> str:
    """Create a minimal HWPX ZIP archive and return its path."""
    hwpx_path = str(tmp_path / name)
    with zipfile.ZipFile(hwpx_path, "w") as zf:
        if section_xml is not None:
            zf.writestr("Contents/section0.xml", section_xml)
        zf.writestr("Contents/content.hpf", "<hpf/>")
    return hwpx_path


# ===========================================================================
# is_hwpx_file
# ===========================================================================


class TestIsHwpxFile:
    """Tests for is_hwpx_file()."""

    def test_valid_hwpx(self, tmp_path):
        """HWPX (ZIP with Contents/) file detected."""
        hwpx_path = str(tmp_path / "test.hwpx")
        with zipfile.ZipFile(hwpx_path, "w") as zf:
            zf.writestr("Contents/section0.xml", "<sec/>")
            zf.writestr("Contents/content.hpf", "<hpf/>")
        assert is_hwpx_file(hwpx_path) is True

    def test_invalid_plain_text(self, tmp_path):
        """Non-HWPX file rejected."""
        txt_path = str(tmp_path / "test.txt")
        with open(txt_path, "w") as f:
            f.write("hello")
        assert is_hwpx_file(txt_path) is False

    def test_nonexistent_file(self):
        """Nonexistent file returns False."""
        assert is_hwpx_file("/nonexistent/file.hwpx") is False

    def test_zip_without_contents_dir(self, tmp_path):
        """ZIP file without Contents/ directory is not HWPX."""
        zip_path = str(tmp_path / "notahwpx.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("readme.txt", "hello")
        assert is_hwpx_file(zip_path) is False


# ===========================================================================
# extract_hwpx_text
# ===========================================================================


class TestExtractHwpxText:
    """Tests for extract_hwpx_text()."""

    def test_extract_text(self, tmp_path):
        """Extract text from HWPX section XML."""
        hwpx_path = _make_hwpx(tmp_path, "test.hwpx", SECTION_XML_TWO_PARAGRAPHS)
        text = extract_hwpx_text(hwpx_path)
        assert "클라우드 전환" in text
        assert "두 번째 문단" in text

    def test_paragraphs_separated_by_newline(self, tmp_path):
        """Each paragraph should be on its own line."""
        hwpx_path = _make_hwpx(tmp_path, "test.hwpx", SECTION_XML_TWO_PARAGRAPHS)
        text = extract_hwpx_text(hwpx_path)
        lines = [line for line in text.split("\n") if line.strip()]
        assert len(lines) >= 2

    def test_empty_hwpx(self, tmp_path):
        """HWPX without section XML returns empty string."""
        hwpx_path = _make_hwpx(tmp_path, "empty.hwpx", section_xml=None)
        text = extract_hwpx_text(hwpx_path)
        assert text == ""

    def test_invalid_file(self):
        """Invalid file returns empty string."""
        assert extract_hwpx_text("/nonexistent") == ""

    def test_multiple_runs_in_paragraph(self, tmp_path):
        """Multiple <hp:run> elements in one <hp:p> are concatenated."""
        section_xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"
         xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">
  <hp:p>
    <hp:run>
      <hp:t>첫 번째 </hp:t>
    </hp:run>
    <hp:run>
      <hp:t>런 텍스트</hp:t>
    </hp:run>
  </hp:p>
</hs:sec>"""
        hwpx_path = _make_hwpx(tmp_path, "multi_run.hwpx", section_xml)
        text = extract_hwpx_text(hwpx_path)
        assert "첫 번째 런 텍스트" in text

    def test_multiple_sections(self, tmp_path):
        """Text from multiple section*.xml files is extracted."""
        section0 = """\
<?xml version="1.0" encoding="UTF-8"?>
<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"
         xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">
  <hp:p><hp:run><hp:t>섹션 0 텍스트</hp:t></hp:run></hp:p>
</hs:sec>"""
        section1 = """\
<?xml version="1.0" encoding="UTF-8"?>
<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"
         xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">
  <hp:p><hp:run><hp:t>섹션 1 텍스트</hp:t></hp:run></hp:p>
</hs:sec>"""
        hwpx_path = str(tmp_path / "multi_sec.hwpx")
        with zipfile.ZipFile(hwpx_path, "w") as zf:
            zf.writestr("Contents/section0.xml", section0)
            zf.writestr("Contents/section1.xml", section1)
            zf.writestr("Contents/content.hpf", "<hpf/>")
        text = extract_hwpx_text(hwpx_path)
        assert "섹션 0 텍스트" in text
        assert "섹션 1 텍스트" in text


# ===========================================================================
# extract_hwpx_styles
# ===========================================================================


class TestExtractHwpxStyles:
    """Tests for extract_hwpx_styles()."""

    def test_extract_font_info(self, tmp_path):
        """Extract font info from HWPX."""
        hwpx_path = _make_hwpx(tmp_path, "styled.hwpx", SECTION_XML_WITH_STYLES)
        styles = extract_hwpx_styles(hwpx_path)
        # body_font = most frequent font
        assert styles.get("body_font") == "함초롬바탕"
        # body_font_size = most frequent size (2200/100 = 22.0)
        assert styles.get("body_font_size") == 22.0
        # heading_font_size = largest size (3200/100 = 32.0)
        assert styles.get("heading_font_size") == 32.0

    def test_fonts_counter(self, tmp_path):
        """The 'fonts' key contains a Counter of font names."""
        hwpx_path = _make_hwpx(tmp_path, "styled.hwpx", SECTION_XML_WITH_STYLES)
        styles = extract_hwpx_styles(hwpx_path)
        fonts = styles.get("fonts")
        assert fonts is not None
        assert fonts["함초롬바탕"] == 2
        assert fonts["함초롬돋움"] == 1

    def test_font_sizes_counter(self, tmp_path):
        """The 'font_sizes' key contains a Counter of sizes in pt."""
        hwpx_path = _make_hwpx(tmp_path, "styled.hwpx", SECTION_XML_WITH_STYLES)
        styles = extract_hwpx_styles(hwpx_path)
        font_sizes = styles.get("font_sizes")
        assert font_sizes is not None
        assert font_sizes[22.0] == 2
        assert font_sizes[32.0] == 1

    def test_heading_font(self, tmp_path):
        """heading_font is the font used at the largest size."""
        hwpx_path = _make_hwpx(tmp_path, "styled.hwpx", SECTION_XML_WITH_STYLES)
        styles = extract_hwpx_styles(hwpx_path)
        assert styles.get("heading_font") == "함초롬돋움"

    def test_empty_hwpx(self, tmp_path):
        """HWPX without section XML returns empty dict."""
        hwpx_path = _make_hwpx(tmp_path, "empty.hwpx", section_xml=None)
        styles = extract_hwpx_styles(hwpx_path)
        assert styles == {}

    def test_invalid_file(self):
        """Invalid file returns empty dict."""
        styles = extract_hwpx_styles("/nonexistent")
        assert styles == {}

    def test_no_font_info_in_xml(self, tmp_path):
        """Section XML with text but no rPr returns empty dict."""
        hwpx_path = _make_hwpx(
            tmp_path, "no_style.hwpx", SECTION_XML_TWO_PARAGRAPHS
        )
        styles = extract_hwpx_styles(hwpx_path)
        assert styles == {}
