"""HWPX parser — extract text and style information from HWPX files.

HWPX files are ZIP archives used by Hancom Office (한컴오피스) for the
newer XML-based document format. The document body lives in
``Contents/section*.xml`` files, which contain paragraph XML in the
Hancom HWPML 2011 namespace.

Key XML structure::

    <hp:p>
      <hp:run>
        <hp:rPr>
          <hp:fontRef hangul="폰트명" latin="Latin Font"/>
          <hp:sz val="2200"/>          <!-- size in 1/100 pt -->
        </hp:rPr>
        <hp:t>텍스트 내용</hp:t>
      </hp:run>
    </hp:p>

Usage::

    from hwpx_parser import is_hwpx_file, extract_hwpx_text, extract_hwpx_styles

    if is_hwpx_file("proposal.hwpx"):
        text = extract_hwpx_text("proposal.hwpx")
        styles = extract_hwpx_styles("proposal.hwpx")
"""
from __future__ import annotations

import logging
import os
import re
import zipfile
from collections import Counter
from typing import Any

from lxml import etree

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# XML namespaces used in HWPX section files
# ---------------------------------------------------------------------------
NS = {
    "hs": "http://www.hancom.co.kr/hwpml/2011/section",
    "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
}

# Pattern to match section XML filenames inside Contents/
_SECTION_PATTERN = re.compile(r"^Contents/section\d+\.xml$")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_valid_hwpx_zip(path: str) -> bool:
    """Return True if *path* is a ZIP file that contains a ``Contents/`` directory."""
    if not os.path.isfile(path):
        return False
    try:
        if not zipfile.is_zipfile(path):
            return False
        with zipfile.ZipFile(path, "r") as zf:
            return any(name.startswith("Contents/") for name in zf.namelist())
    except (zipfile.BadZipFile, OSError) as exc:
        logger.debug("Not a valid ZIP/HWPX: %s (%s)", path, exc)
        return False


def _iter_section_xmls(zf: zipfile.ZipFile) -> list[str]:
    """Return sorted list of ``Contents/section*.xml`` entry names."""
    return sorted(
        name for name in zf.namelist() if _SECTION_PATTERN.match(name)
    )


def _parse_section_paragraphs(xml_bytes: bytes) -> list[str]:
    """Parse a single section XML and return a list of paragraph strings.

    Each ``<hp:p>`` element becomes one string.  Multiple ``<hp:run>``
    elements within a paragraph are concatenated.
    """
    try:
        root = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as exc:
        logger.warning("Failed to parse section XML: %s", exc)
        return []

    paragraphs: list[str] = []
    for p_elem in root.iter("{%s}p" % NS["hp"]):
        runs_text: list[str] = []
        for t_elem in p_elem.iter("{%s}t" % NS["hp"]):
            if t_elem.text:
                runs_text.append(t_elem.text)
        line = "".join(runs_text).strip()
        if line:
            paragraphs.append(line)
    return paragraphs


def _collect_style_entries(
    xml_bytes: bytes,
) -> list[tuple[str, float]]:
    """Extract ``(font_name, size_pt)`` tuples from ``<hp:rPr>`` elements.

    Font name comes from ``<hp:fontRef hangul="..."/>`` and size from
    ``<hp:sz val="..."/>`` (the val attribute is in 1/100 pt).
    """
    try:
        root = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as exc:
        logger.warning("Failed to parse section XML for styles: %s", exc)
        return []

    entries: list[tuple[str, float]] = []
    for rpr in root.iter("{%s}rPr" % NS["hp"]):
        font_name: str | None = None
        size_pt: float | None = None

        font_ref = rpr.find("{%s}fontRef" % NS["hp"])
        if font_ref is not None:
            font_name = font_ref.get("hangul")

        sz_elem = rpr.find("{%s}sz" % NS["hp"])
        if sz_elem is not None:
            val = sz_elem.get("val")
            if val is not None:
                try:
                    size_pt = int(val) / 100.0
                except (ValueError, TypeError):
                    pass

        if font_name and size_pt is not None:
            entries.append((font_name, size_pt))

    return entries


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_hwpx_file(path: str) -> bool:
    """Check if *path* is a valid HWPX archive (ZIP with ``Contents/`` directory).

    Returns ``False`` for nonexistent files, non-ZIP files, or ZIP files
    without the expected HWPX directory structure.
    """
    return _is_valid_hwpx_zip(path)


def extract_hwpx_text(path: str) -> str:
    """Extract all text from HWPX ``Contents/section*.xml`` files.

    Returns newline-joined paragraphs.  Returns an empty string on any
    failure (file not found, corrupt ZIP, missing sections, etc.).
    """
    if not _is_valid_hwpx_zip(path):
        if os.path.exists(path):
            logger.warning("Not a valid HWPX file: %s", path)
        else:
            logger.debug("File not found: %s", path)
        return ""

    all_paragraphs: list[str] = []
    try:
        with zipfile.ZipFile(path, "r") as zf:
            section_names = _iter_section_xmls(zf)
            if not section_names:
                logger.debug("No section*.xml found in HWPX: %s", path)
                return ""

            for section_name in section_names:
                xml_bytes = zf.read(section_name)
                paragraphs = _parse_section_paragraphs(xml_bytes)
                all_paragraphs.extend(paragraphs)
    except (zipfile.BadZipFile, OSError, KeyError) as exc:
        logger.error("HWPX text extraction failed: %s (%s)", path, exc)
        return ""

    return "\n".join(all_paragraphs)


def extract_hwpx_styles(path: str) -> dict[str, Any]:
    """Extract font and size info from HWPX.

    Returns a dict with the following keys (or an empty dict on failure /
    when no style information is found):

    - ``body_font`` (str): the most frequently used hangul font name
    - ``heading_font`` (str): the font used at the largest size
    - ``fonts`` (Counter): ``{font_name: count}``
    - ``body_font_size`` (float): the most frequent font size in pt
    - ``heading_font_size`` (float): the largest font size in pt
    - ``font_sizes`` (Counter): ``{size_pt: count}``
    """
    if not _is_valid_hwpx_zip(path):
        return {}

    all_entries: list[tuple[str, float]] = []
    try:
        with zipfile.ZipFile(path, "r") as zf:
            section_names = _iter_section_xmls(zf)
            for section_name in section_names:
                xml_bytes = zf.read(section_name)
                entries = _collect_style_entries(xml_bytes)
                all_entries.extend(entries)
    except (zipfile.BadZipFile, OSError, KeyError) as exc:
        logger.error("HWPX style extraction failed: %s (%s)", path, exc)
        return {}

    if not all_entries:
        return {}

    # Build counters
    font_counter: Counter[str] = Counter()
    size_counter: Counter[float] = Counter()
    # Track which font is used at the largest size
    size_to_fonts: dict[float, Counter[str]] = {}

    for font_name, size_pt in all_entries:
        font_counter[font_name] += 1
        size_counter[size_pt] += 1
        if size_pt not in size_to_fonts:
            size_to_fonts[size_pt] = Counter()
        size_to_fonts[size_pt][font_name] += 1

    # body_font = most frequent font overall
    body_font = font_counter.most_common(1)[0][0]
    # body_font_size = most frequent size overall
    body_font_size = size_counter.most_common(1)[0][0]
    # heading_font_size = largest size
    heading_font_size = max(size_counter.keys())
    # heading_font = most frequent font at the largest size
    heading_font = size_to_fonts[heading_font_size].most_common(1)[0][0]

    return {
        "body_font": body_font,
        "heading_font": heading_font,
        "fonts": font_counter,
        "body_font_size": body_font_size,
        "heading_font_size": heading_font_size,
        "font_sizes": size_counter,
    }
