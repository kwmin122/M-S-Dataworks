"""Company Profile Builder — convert StyleProfile + HWPX styles to profile.md.

Generates a structured markdown file that captures a company's document style,
writing tone, strength expression patterns, evaluation strategy, HWPX generation
rules, and learning history.  This profile is consumed by the section_writer and
document_assembler modules to produce company-customized proposals.

Storage path: data/company_skills/{company_id}/profile.md
"""
from __future__ import annotations

import logging
import os
import tempfile
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROFILE_FILENAME = "profile.md"

_HWPX_PLACEHOLDER = "(HWPX 템플릿 업로드 시 자동 채움)"

_HWPX_FIELD_LABELS: dict[str, str] = {
    "body_font": "본문 글꼴",
    "heading_font": "제목 글꼴",
    "line_spacing": "줄 간격 (%)",
    "margins": "여백 (mm)",
    "header_text": "머리말",
    "footer_text": "꼬리말",
    "page_number_format": "쪽 번호 형식",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_profile_md(
    company_name: str,
    style: Optional[object] = None,
    hwpx_styles: Optional[dict] = None,
) -> str:
    """Convert StyleProfile + optional HWPX styles into a profile.md markdown string.

    Args:
        company_name: Display name of the company.
        style: A ``StyleProfile`` instance (or any object with the same attributes).
               ``None`` produces a skeleton with default / empty values.
        hwpx_styles: Optional dict with HWPX template style keys such as
                     ``body_font``, ``heading_font``, ``line_spacing``,
                     ``margins``, ``header_text``, ``footer_text``,
                     ``page_number_format``.

    Returns:
        A UTF-8 markdown string with all 6 required sections.
    """
    sections: list[str] = []

    # Title
    sections.append(f"# {company_name} 회사 프로필\n")
    sections.append(
        f"> 생성일: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
    )

    # --- 1. 문서 스타일 -------------------------------------------------
    sections.append(_build_document_style_section(style, hwpx_styles))

    # --- 2. 문체 --------------------------------------------------------
    sections.append(_build_tone_section(style))

    # --- 3. 강점 표현 패턴 -----------------------------------------------
    sections.append(_build_strength_section(style))

    # --- 4. 평가항목별 전략 -----------------------------------------------
    sections.append(_build_strategy_section(style))

    # --- 5. HWPX 생성 규칙 -----------------------------------------------
    sections.append(_build_hwpx_rules_section(hwpx_styles))

    # --- 6. 학습 이력 ----------------------------------------------------
    sections.append(_build_learning_history_section())

    return "\n".join(sections)


def save_profile_md(company_dir: str, content: str) -> str:
    """Atomically save *content* as ``profile.md`` in *company_dir*.

    Creates *company_dir* if it does not exist.  Uses a write-to-tmp-then-rename
    strategy to prevent partial writes.

    Args:
        company_dir: Absolute or relative directory path for the company.
        content: The markdown string to persist.

    Returns:
        The absolute path to the written file.
    """
    os.makedirs(company_dir, exist_ok=True)
    target_path = os.path.join(company_dir, PROFILE_FILENAME)

    # Atomic write: write to a temp file in the same directory, then rename.
    fd, tmp_path = tempfile.mkstemp(
        suffix=".tmp", prefix="profile_", dir=company_dir
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, target_path)
        logger.info("Saved profile.md to %s", target_path)
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    return target_path


def load_profile_md(company_dir: str) -> str:
    """Load ``profile.md`` from *company_dir*.

    Args:
        company_dir: Directory that should contain ``profile.md``.

    Returns:
        The file contents as a string, or an empty string if the file or
        directory does not exist.
    """
    target_path = os.path.join(company_dir, PROFILE_FILENAME)
    try:
        with open(target_path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.debug("profile.md not found at %s", target_path)
        return ""
    except OSError as exc:
        logger.warning("Failed to read profile.md at %s: %s", target_path, exc)
        return ""


# ---------------------------------------------------------------------------
# Private section builders
# ---------------------------------------------------------------------------

def _safe_getattr(obj: Optional[object], name: str, default=None):
    """Safely read an attribute from *obj* (which may be ``None``)."""
    if obj is None:
        return default
    return getattr(obj, name, default)


def _build_document_style_section(
    style: Optional[object],
    hwpx_styles: Optional[dict],
) -> str:
    """Section 1: 문서 스타일 — structure pattern + terminology."""
    lines: list[str] = ["## 문서 스타일\n"]

    # Structure pattern
    structure = _safe_getattr(style, "structure_pattern", "")
    if structure:
        lines.append(f"**구조 패턴**: {structure}\n")
    else:
        lines.append("**구조 패턴**: (분석 데이터 없음)\n")

    # Terminology
    terminology: dict = _safe_getattr(style, "terminology", {}) or {}
    if terminology:
        lines.append("**용어 매핑**:\n")
        for term, meaning in terminology.items():
            lines.append(f"- {term} → {meaning}")
        lines.append("")
    else:
        lines.append("**용어 매핑**: (등록된 용어 없음)\n")

    return "\n".join(lines)


def _build_tone_section(style: Optional[object]) -> str:
    """Section 2: 문체 — tone, avg sentence length, common phrases."""
    lines: list[str] = ["## 문체\n"]

    tone = _safe_getattr(style, "tone", "미분석")
    avg_len = _safe_getattr(style, "avg_sentence_length", 0.0)
    lines.append(f"- **문체 유형**: {tone}")
    lines.append(f"- **평균 문장 길이**: {avg_len}자")

    # Common phrases
    phrases: list = _safe_getattr(style, "common_phrases", []) or []
    if phrases:
        lines.append("\n**빈출 표현**:\n")
        for p in phrases:
            lines.append(f"- \"{p}\"")
    else:
        lines.append("\n**빈출 표현**: (수집된 표현 없음)")

    lines.append("")
    return "\n".join(lines)


def _build_strength_section(style: Optional[object]) -> str:
    """Section 3: 강점 표현 패턴 — keywords."""
    lines: list[str] = ["## 강점 표현 패턴\n"]

    keywords: list = _safe_getattr(style, "strength_keywords", []) or []
    if keywords:
        lines.append("**강점 키워드**:\n")
        for kw in keywords:
            lines.append(f"- {kw}")
    else:
        lines.append("**강점 키워드**: (분석 데이터 없음)")

    lines.append("")
    return "\n".join(lines)


def _build_strategy_section(style: Optional[object]) -> str:
    """Section 4: 평가항목별 전략 — section weight pattern."""
    lines: list[str] = ["## 평가항목별 전략\n"]

    weights: dict = _safe_getattr(style, "section_weight_pattern", {}) or {}
    if weights:
        lines.append("| 평가항목 | 비중 |")
        lines.append("|---------|------|")
        for section, weight in sorted(weights.items(), key=lambda x: -x[1]):
            lines.append(f"| {section} | {weight:.1%} |")
    else:
        lines.append("(평가항목 분석 데이터 없음)")

    lines.append("")
    return "\n".join(lines)


def _build_hwpx_rules_section(hwpx_styles: Optional[dict]) -> str:
    """Section 5: HWPX 생성 규칙 — template-extracted styles or placeholder."""
    lines: list[str] = ["## HWPX 생성 규칙\n"]

    if not hwpx_styles:
        lines.append(f"{_HWPX_PLACEHOLDER}\n")
        return "\n".join(lines)

    for key, label in _HWPX_FIELD_LABELS.items():
        value = hwpx_styles.get(key)
        if value is None:
            continue
        if isinstance(value, dict):
            # e.g. margins dict
            formatted = ", ".join(f"{k}: {v}" for k, v in value.items())
            lines.append(f"- **{label}**: {formatted}")
        else:
            lines.append(f"- **{label}**: {value}")

    lines.append("")
    return "\n".join(lines)


def _build_learning_history_section() -> str:
    """Section 6: 학습 이력 — initially empty, populated by auto_learner."""
    lines: list[str] = ["## 학습 이력\n"]
    lines.append("(아직 학습된 패턴이 없습니다. 제안서 수정 시 자동으로 기록됩니다.)\n")
    return "\n".join(lines)
