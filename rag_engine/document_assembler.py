"""Document Assembler — DOCX output from proposal sections.

Takes list of section texts (markdown) and assembles a .docx file
with proper formatting using python-docx.
"""
from __future__ import annotations

import re
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH


def _add_markdown_content(doc: Document, md_text: str) -> None:
    """Parse simplified markdown and add to document."""
    lines = md_text.split("\n")
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("### "):
            doc.add_heading(stripped[4:], level=3)
        elif stripped.startswith("## "):
            doc.add_heading(stripped[3:], level=2)
        elif stripped.startswith("# "):
            doc.add_heading(stripped[2:], level=1)
        elif stripped.startswith("- ") or stripped.startswith("* "):
            doc.add_paragraph(stripped[2:], style="List Bullet")
        elif re.match(r"^\d+\.\s", stripped):
            text = re.sub(r"^\d+\.\s", "", stripped)
            doc.add_paragraph(text, style="List Number")
        else:
            doc.add_paragraph(stripped)


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
