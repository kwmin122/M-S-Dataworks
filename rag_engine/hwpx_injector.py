"""HWPX Injector — inject markdown content into HWPX template files.

Takes markdown content and injects it into HWPX templates by:

1. Finding ``{{SECTION:섹션명}}`` placeholders in ``Contents/section*.xml``
2. Converting markdown to HWPX XML elements (hp:p, hp:run, hp:t)
3. Replacing the placeholder paragraphs with the converted content

HWPX files are ZIP archives containing XML-based document content.
The main content lives in ``Contents/section*.xml`` files using the
Hancom HWPML 2011 paragraph namespace.

Usage::

    from hwpx_injector import markdown_to_hwpx_elements, inject_content

    # Convert markdown to HWPX XML strings
    elements = markdown_to_hwpx_elements("# 제목\\n\\n본문 **강조** 포함")

    # Inject into a template
    inject_content(
        template_path="template.hwpx",
        sections={"개요": "## 개요\\n\\n내용...", "기술방안": "- 항목1\\n- 항목2"},
        output_path="output.hwpx",
    )
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import zipfile
from typing import Any

import mistune

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# XML namespaces
# ---------------------------------------------------------------------------

HP_NS = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HS_NS = "http://www.hancom.co.kr/hwpml/2011/section"

_HP_NS_DECL = f'xmlns:hp="{HP_NS}"'

# Pattern to match section XML filenames inside Contents/
_SECTION_PATTERN = re.compile(r"^Contents/section\d+\.xml$")

# Pattern to match {{SECTION:name}} placeholders in XML text
_PLACEHOLDER_PATTERN = re.compile(r"\{\{SECTION:(.+?)\}\}")

# mistune 3.x AST renderer with table plugin
_md_parser = mistune.create_markdown(renderer="ast", plugins=["table"])

# ---------------------------------------------------------------------------
# Font size mapping (1/100 pt units used in HWPX)
# ---------------------------------------------------------------------------

_HEADING_SIZES = {
    1: 2400,  # 24pt
    2: 2000,  # 20pt
    3: 1600,  # 16pt
}


# ---------------------------------------------------------------------------
# XML helpers
# ---------------------------------------------------------------------------


def _xml_escape(text: str) -> str:
    """Escape special XML characters in text content.

    Handles &, <, >, ", and ' — the five predefined XML entities.
    Order matters: & must be escaped first to avoid double-escaping.
    """
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace('"', "&quot;")
    text = text.replace("'", "&apos;")
    return text


def _make_run(text: str, bold: bool = False, italic: bool = False) -> str:
    """Build an ``<hp:run>`` XML string with optional bold/italic formatting.

    Args:
        text: The text content (will be XML-escaped).
        bold: Whether to apply bold formatting.
        italic: Whether to apply italic formatting.

    Returns:
        XML string for ``<hp:run>`` element.
    """
    escaped = _xml_escape(text)

    if bold or italic:
        attrs: list[str] = []
        if bold:
            attrs.append('bold="true"')
        if italic:
            attrs.append('italic="true"')
        rpr = f'<hp:rPr {" ".join(attrs)}/>'
        return f"<hp:run>{rpr}<hp:t>{escaped}</hp:t></hp:run>"

    return f"<hp:run><hp:t>{escaped}</hp:t></hp:run>"


def _make_heading_run(text: str, level: int) -> str:
    """Build an ``<hp:run>`` element for a heading with bold + sized font.

    Args:
        text: Heading text (will be XML-escaped).
        level: Heading level (1, 2, or 3).

    Returns:
        XML string for a heading run element.
    """
    escaped = _xml_escape(text)
    size_val = _HEADING_SIZES.get(level, 1600)
    return (
        f"<hp:run>"
        f'<hp:rPr bold="true"><hp:sz val="{size_val}"/></hp:rPr>'
        f"<hp:t>{escaped}</hp:t>"
        f"</hp:run>"
    )


def _wrap_paragraph(runs_xml: str) -> str:
    """Wrap run XML strings in an ``<hp:p>`` element with namespace declaration.

    Args:
        runs_xml: Concatenated ``<hp:run>`` XML strings.

    Returns:
        Complete ``<hp:p>`` XML string.
    """
    return f"<hp:p {_HP_NS_DECL}>{runs_xml}</hp:p>"


# ---------------------------------------------------------------------------
# AST text extraction (mirrors document_assembler.py pattern)
# ---------------------------------------------------------------------------


def _extract_text(children: list[dict[str, Any]]) -> str:
    """Recursively extract plain text from AST children."""
    parts: list[str] = []
    for child in children:
        ctype = child.get("type", "")
        if ctype == "text":
            parts.append(child.get("raw", ""))
        elif ctype == "codespan":
            parts.append(child.get("raw", ""))
        elif ctype == "softbreak":
            parts.append(" ")
        elif ctype in ("strong", "emphasis", "link"):
            parts.append(_extract_text(child.get("children", [])))
        elif isinstance(child.get("children"), list):
            parts.append(_extract_text(child["children"]))
        elif isinstance(child.get("raw"), str):
            parts.append(child["raw"])
    return "".join(parts)


# ---------------------------------------------------------------------------
# AST inline → HWPX runs conversion
# ---------------------------------------------------------------------------


def _inline_to_runs(
    children: list[dict[str, Any]],
    bold: bool = False,
    italic: bool = False,
) -> str:
    """Convert AST inline children to concatenated ``<hp:run>`` XML strings.

    Recursively processes inline formatting (strong, emphasis, text, codespan).

    Args:
        children: List of AST inline nodes.
        bold: Inherited bold state from parent nodes.
        italic: Inherited italic state from parent nodes.

    Returns:
        Concatenated XML run strings.
    """
    parts: list[str] = []
    for child in children:
        ctype = child.get("type", "")

        if ctype == "text":
            text = child.get("raw", "")
            if text:
                parts.append(_make_run(text, bold=bold, italic=italic))

        elif ctype == "codespan":
            text = child.get("raw", "")
            if text:
                parts.append(_make_run(text, bold=bold, italic=italic))

        elif ctype == "softbreak":
            # Treat soft breaks as spaces
            parts.append(_make_run(" ", bold=bold, italic=italic))

        elif ctype == "strong":
            parts.append(
                _inline_to_runs(
                    child.get("children", []), bold=True, italic=italic
                )
            )

        elif ctype == "emphasis":
            parts.append(
                _inline_to_runs(
                    child.get("children", []), bold=bold, italic=True
                )
            )

        elif ctype == "link":
            parts.append(
                _inline_to_runs(
                    child.get("children", []), bold=bold, italic=italic
                )
            )

        elif isinstance(child.get("children"), list):
            parts.append(
                _inline_to_runs(
                    child["children"], bold=bold, italic=italic
                )
            )
        elif isinstance(child.get("raw"), str):
            text = child["raw"]
            if text:
                parts.append(_make_run(text, bold=bold, italic=italic))

    return "".join(parts)


# ---------------------------------------------------------------------------
# Block-level AST → HWPX XML paragraphs
# ---------------------------------------------------------------------------


def _convert_heading(token: dict[str, Any]) -> str:
    """Convert a heading AST token to an HWPX paragraph XML string."""
    level = min(token.get("attrs", {}).get("level", 1), 3)
    text = _extract_text(token.get("children", []))
    run = _make_heading_run(text, level)
    return _wrap_paragraph(run)


def _convert_paragraph(token: dict[str, Any]) -> str | None:
    """Convert a paragraph AST token to an HWPX paragraph XML string.

    Returns None if the paragraph has no visible text content.
    """
    children = token.get("children", [])
    text = _extract_text(children)
    if not text.strip():
        return None
    runs = _inline_to_runs(children)
    return _wrap_paragraph(runs)


def _convert_list(token: dict[str, Any]) -> list[str]:
    """Convert a list AST token to a list of HWPX paragraph XML strings.

    Each list item becomes a paragraph with a bullet character prepended.
    """
    results: list[str] = []
    ordered = token.get("attrs", {}).get("ordered", False)

    for idx, item in enumerate(token.get("children", []), 1):
        item_children = item.get("children", [])
        # Collect inline children from nested block_text / paragraph nodes
        all_inline: list[dict[str, Any]] = []
        for sub in item_children:
            sub_type = sub.get("type", "")
            if sub_type in ("paragraph", "block_text"):
                all_inline.extend(sub.get("children", []))
            else:
                all_inline.append(sub)

        text = _extract_text(all_inline)
        if not text.strip():
            continue

        # Build marker + content runs
        if ordered:
            marker = f"{idx}. "
        else:
            marker = "  \u2022 "  # bullet character

        marker_run = _make_run(marker)
        content_runs = _inline_to_runs(all_inline)
        results.append(_wrap_paragraph(marker_run + content_runs))

    return results


def _convert_table(token: dict[str, Any]) -> list[str]:
    """Convert a table AST token to HWPX paragraph XML strings.

    Tables are rendered as formatted text paragraphs (header row bold,
    body rows plain). Full ``<hp:tbl>`` support is planned for later.
    """
    results: list[str] = []

    for child in token.get("children", []):
        ctype = child.get("type", "")

        if ctype == "table_head":
            # Header row — bold
            cells: list[str] = []
            for cell in child.get("children", []):
                cells.append(_extract_text(cell.get("children", [])))
            header_text = " | ".join(cells)
            run = _make_run(header_text, bold=True)
            results.append(_wrap_paragraph(run))

        elif ctype == "table_body":
            for row in child.get("children", []):
                cells = []
                for cell in row.get("children", []):
                    cells.append(_extract_text(cell.get("children", [])))
                row_text = " | ".join(cells)
                run = _make_run(row_text)
                results.append(_wrap_paragraph(run))

    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def markdown_to_hwpx_elements(markdown_text: str) -> list[str]:
    """Parse markdown text and convert to HWPX XML element strings.

    Uses mistune 3.x AST renderer to parse markdown, then converts each
    block-level element to one or more ``<hp:p>`` XML strings suitable for
    injection into HWPX section XML files.

    Supported markdown elements:
    - Headings (h1-h3) with sized bold fonts
    - Paragraphs with inline bold/italic formatting
    - Bullet and numbered lists
    - Tables (rendered as formatted text paragraphs)

    Args:
        markdown_text: Markdown content to convert.

    Returns:
        List of XML strings, each representing one ``<hp:p>`` element.
        Empty list for empty input.
    """
    if not markdown_text or not markdown_text.strip():
        return []

    tokens = _md_parser(markdown_text)
    if not isinstance(tokens, list):
        # Fallback — treat as plain text
        return [_wrap_paragraph(_make_run(str(tokens)))]

    elements: list[str] = []

    for token in tokens:
        ttype = token.get("type", "")

        if ttype == "heading":
            elements.append(_convert_heading(token))

        elif ttype == "paragraph":
            result = _convert_paragraph(token)
            if result:
                elements.append(result)

        elif ttype == "list":
            elements.extend(_convert_list(token))

        elif ttype == "table":
            elements.extend(_convert_table(token))

        elif ttype == "block_code":
            code = token.get("raw", "")
            if isinstance(code, str) and code.strip():
                run = _make_run(code.strip())
                elements.append(_wrap_paragraph(run))

        elif ttype == "thematic_break":
            run = _make_run("\u2500" * 40)
            elements.append(_wrap_paragraph(run))

        elif ttype == "blank_line":
            # Skip blank lines — they don't produce visible content
            continue

        else:
            # Fallback for unknown types
            children = token.get("children", [])
            if isinstance(children, list):
                text = _extract_text(children)
            else:
                text = ""
            if not text:
                text = token.get("raw", "")
            if isinstance(text, str) and text.strip():
                run = _make_run(text.strip())
                elements.append(_wrap_paragraph(run))

    return elements


def inject_content(
    template_path: str,
    sections: dict[str, str],
    output_path: str,
) -> str:
    """Inject markdown content into HWPX template by replacing placeholders.

    Copies the template to the output path, then for each
    ``Contents/section*.xml`` file finds ``{{SECTION:name}}`` placeholders
    and replaces the enclosing ``<hp:p>`` paragraphs with HWPX XML elements
    generated from the corresponding markdown content.

    Placeholders for section names not present in *sections* are left as-is.
    Non-section ZIP entries are copied verbatim.

    Args:
        template_path: Path to the source HWPX template file.
        sections: Mapping of section name to markdown content.
        output_path: Where to write the output HWPX file.

    Returns:
        The *output_path* string.

    Raises:
        FileNotFoundError: If *template_path* does not exist.
        zipfile.BadZipFile: If *template_path* is not a valid ZIP.
    """
    # Ensure output directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # Copy template to output first
    shutil.copy2(template_path, output_path)

    # Pre-convert all sections to HWPX XML
    converted: dict[str, list[str]] = {}
    for name, md_text in sections.items():
        converted[name] = markdown_to_hwpx_elements(md_text)

    # Process each section*.xml in the ZIP
    with zipfile.ZipFile(output_path, "r") as zf_in:
        entry_names = zf_in.namelist()
        section_names = sorted(
            n for n in entry_names if _SECTION_PATTERN.match(n)
        )

        if not section_names:
            logger.debug("No section*.xml found in template: %s", template_path)
            return output_path

        # Read all entries into memory
        entries: dict[str, bytes] = {}
        for name in entry_names:
            entries[name] = zf_in.read(name)

    # Process section XMLs — find and replace placeholders
    for sec_name in section_names:
        xml_bytes = entries[sec_name]
        modified_xml = _process_section_xml(xml_bytes, converted)
        entries[sec_name] = modified_xml

    # Write back all entries
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf_out:
        for name in entry_names:
            zf_out.writestr(name, entries[name])

    return output_path


# ---------------------------------------------------------------------------
# Internal: section XML processing
# ---------------------------------------------------------------------------


def _process_section_xml(
    xml_bytes: bytes,
    converted_sections: dict[str, list[str]],
) -> bytes:
    """Find {{SECTION:name}} placeholders in section XML and replace them.

    Each placeholder is expected to be inside an ``<hp:p>`` element.
    The entire paragraph is replaced with the converted HWPX elements.

    Args:
        xml_bytes: Raw XML bytes from the section file.
        converted_sections: Pre-converted section name -> list of XML strings.

    Returns:
        Modified XML as bytes.
    """
    from lxml import etree

    try:
        root = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as exc:
        logger.warning("Failed to parse section XML: %s", exc)
        return xml_bytes

    hp_ns = HP_NS

    # Find all <hp:p> elements that contain a placeholder
    paragraphs_to_replace: list[tuple[Any, str, list[str]]] = []

    for p_elem in root.iter(f"{{{hp_ns}}}p"):
        # Collect all text from <hp:t> in this paragraph
        full_text = ""
        for t_elem in p_elem.iter(f"{{{hp_ns}}}t"):
            if t_elem.text:
                full_text += t_elem.text

        match = _PLACEHOLDER_PATTERN.search(full_text)
        if match:
            section_name = match.group(1)
            if section_name in converted_sections:
                paragraphs_to_replace.append(
                    (p_elem, section_name, converted_sections[section_name])
                )

    # Replace paragraphs in reverse order to avoid index shifting
    for p_elem, section_name, new_elements_xml in reversed(paragraphs_to_replace):
        parent = p_elem.getparent()
        if parent is None:
            continue

        idx = list(parent).index(p_elem)
        parent.remove(p_elem)

        # Insert new elements at the same position
        for i, elem_xml in enumerate(new_elements_xml):
            try:
                new_elem = etree.fromstring(elem_xml.encode("utf-8"))
                parent.insert(idx + i, new_elem)
            except etree.XMLSyntaxError as exc:
                logger.warning(
                    "Failed to parse generated XML for section '%s': %s",
                    section_name,
                    exc,
                )

    # Serialize back to bytes
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8")
