"""Document Assembler — DOCX output from proposal sections.

Takes list of section texts (markdown) and assembles a .docx file
with proper formatting using python-docx. Markdown is parsed via
mistune AST renderer for reliable heading/list extraction.
"""
from __future__ import annotations

import re
from typing import Any

import mistune
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

# mistune 3.x AST renderer — produces a token tree we walk to emit DOCX elements.
_md_parser = mistune.create_markdown(renderer="ast")


def _extract_text(children: list[dict[str, Any]]) -> str:
    """Recursively extract plain text from AST children."""
    parts: list[str] = []
    for child in children:
        if child["type"] == "text":
            parts.append(child.get("raw", child.get("children", "")))
        elif child["type"] == "codespan":
            parts.append(child.get("raw", child.get("children", "")))
        elif child["type"] in ("strong", "emphasis", "link"):
            parts.append(_extract_text(child.get("children", [])))
        elif isinstance(child.get("children"), list):
            parts.append(_extract_text(child["children"]))
        elif isinstance(child.get("raw"), str):
            parts.append(child["raw"])
    return "".join(parts)


def _add_markdown_content(doc: Document, md_text: str) -> None:
    """Parse markdown via mistune AST and add to DOCX document."""
    tokens = _md_parser(md_text)
    if not isinstance(tokens, list):
        # fallback — if mistune returns raw HTML string, treat as plain text
        doc.add_paragraph(str(tokens))
        return

    for token in tokens:
        ttype = token.get("type", "")

        if ttype == "heading":
            level = min(token.get("attrs", {}).get("level", 1), 3)
            text = _extract_text(token.get("children", []))
            doc.add_heading(text, level=level)

        elif ttype == "paragraph":
            text = _extract_text(token.get("children", []))
            if text.strip():
                doc.add_paragraph(text)

        elif ttype == "list":
            ordered = token.get("attrs", {}).get("ordered", False)
            style = "List Number" if ordered else "List Bullet"
            for item in token.get("children", []):
                # Each list_item has children (usually paragraph children)
                item_children = item.get("children", [])
                parts: list[str] = []
                for sub in item_children:
                    if sub.get("type") == "paragraph":
                        parts.append(_extract_text(sub.get("children", [])))
                    else:
                        parts.append(_extract_text([sub]))
                text = " ".join(parts).strip()
                if text:
                    doc.add_paragraph(text, style=style)

        elif ttype == "block_code":
            code = token.get("raw", token.get("children", ""))
            if isinstance(code, str) and code.strip():
                doc.add_paragraph(code.strip())

        elif ttype == "thematic_break":
            doc.add_paragraph("─" * 40)

        else:
            # Fallback for unknown token types
            text = _extract_text(token.get("children", [])) if isinstance(token.get("children"), list) else ""
            if not text:
                text = token.get("raw", "")
            if isinstance(text, str) and text.strip():
                doc.add_paragraph(text.strip())


def assemble_docx(
    title: str,
    sections: list[tuple[str, str]],  # [(section_name, markdown_text), ...]
    output_path: str,
    author: str = "Kira Bot",
) -> str:
    """Assemble a DOCX proposal from section texts."""
    doc = Document()

    # Title page
    doc.core_properties.author = author
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(title)
    run.font.size = Pt(24)
    run.bold = True
    doc.add_page_break()

    # Table of contents placeholder
    doc.add_heading("목차", level=1)
    for i, (name, _) in enumerate(sections, 1):
        doc.add_paragraph(f"{i}. {name}", style="List Number")
    doc.add_page_break()

    # Sections
    for name, content in sections:
        _add_markdown_content(doc, content)
        doc.add_page_break()

    doc.save(output_path)
    return output_path
