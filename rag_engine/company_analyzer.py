"""Company Document Analyzer — extract writing style from past proposals.

Analyzes uploaded past proposals to extract writing style, structure patterns,
strengths emphasis, and terminology. Feeds Layer 2 company profile.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class StyleProfile:
    """Extracted writing style from company's past proposals."""
    tone: str = "격식체"                    # 격식체 | 경어체 | 혼합
    avg_sentence_length: float = 0.0        # 평균 문장 길이 (자)
    structure_pattern: str = ""             # 구조 패턴 요약
    strength_keywords: list[str] = field(default_factory=list)
    terminology: dict[str, str] = field(default_factory=dict)   # 자사 용어 매핑
    common_phrases: list[str] = field(default_factory=list)     # 빈출 표현
    section_weight_pattern: dict[str, float] = field(default_factory=dict)  # 섹션별 비중


def analyze_company_style(documents: list[str]) -> StyleProfile:
    """Extract writing style profile from company's past proposals.

    Args:
        documents: List of parsed text from past proposals.

    Returns:
        StyleProfile with extracted patterns.
    """
    if not documents:
        return StyleProfile()

    all_text = "\n\n".join(documents)
    sentences = _split_sentences(all_text)

    # Tone detection
    tone = _detect_tone(sentences)

    # Average sentence length
    avg_len = sum(len(s) for s in sentences) / max(len(sentences), 1)

    # Strength keywords — frequent nouns/terms (>= 3 occurrences)
    strength_keywords = _extract_frequent_terms(all_text, min_count=3)

    # Common phrases — repeated 3+ word sequences
    common_phrases = _extract_common_phrases(all_text, min_count=2)

    # Section weight pattern from heading analysis
    section_weights = _analyze_section_weights(documents)

    structure_pattern = " → ".join(
        f"{k}({v:.0%})" for k, v in sorted(section_weights.items(), key=lambda x: -x[1])
    ) if section_weights else ""

    return StyleProfile(
        tone=tone,
        avg_sentence_length=round(avg_len, 1),
        structure_pattern=structure_pattern,
        strength_keywords=strength_keywords[:20],
        terminology={},
        common_phrases=common_phrases[:15],
        section_weight_pattern=section_weights,
    )


def _split_sentences(text: str) -> list[str]:
    """Split Korean text into sentences."""
    parts = re.split(r'[.。!?]\s*|\n{2,}', text)
    return [s.strip() for s in parts if len(s.strip()) >= 5]


def _detect_tone(sentences: list[str]) -> str:
    """Detect writing tone from sentence endings."""
    formal_count = 0
    polite_count = 0
    for s in sentences:
        s = s.rstrip()
        # Check polite first (합니다 ends with 다 too, so order matters)
        if re.search(r'(합니다|입니다|됩니다|습니다|세요)\s*$', s):
            polite_count += 1
        elif re.search(r'(이다|한다|된다|있다|한다|였다|함|임|됨|있음)\s*$', s):
            formal_count += 1
    total = formal_count + polite_count
    if total == 0:
        return "혼합"
    ratio = formal_count / total
    if ratio > 0.7:
        return "격식체"
    elif ratio < 0.3:
        return "경어체"
    return "혼합"


def _extract_frequent_terms(text: str, min_count: int = 3) -> list[str]:
    """Extract frequently used Korean terms (2~6 chars)."""
    # Simple approach: extract Korean word sequences
    words = re.findall(r'[가-힣]{2,6}', text)
    counts: dict[str, int] = {}
    stopwords = {"하여", "있는", "되는", "하는", "위한", "대한", "통한", "따른", "관한",
                 "본사", "해당", "이에", "또한", "그리고", "따라서", "이를"}
    for w in words:
        if w not in stopwords:
            counts[w] = counts.get(w, 0) + 1
    return [w for w, c in sorted(counts.items(), key=lambda x: -x[1]) if c >= min_count]


def _extract_common_phrases(text: str, min_count: int = 2) -> list[str]:
    """Extract commonly used multi-word phrases."""
    # Extract phrases of 8~30 chars that repeat
    phrases: dict[str, int] = {}
    sentences = _split_sentences(text)
    for s in sentences:
        # Sliding window for common expressions
        for length in range(8, min(31, len(s) + 1)):
            for start in range(0, len(s) - length + 1, 4):
                chunk = s[start:start + length].strip()
                if len(chunk) >= 8:
                    phrases[chunk] = phrases.get(chunk, 0) + 1
    return [p for p, c in sorted(phrases.items(), key=lambda x: -x[1]) if c >= min_count]


def _analyze_section_weights(documents: list[str]) -> dict[str, float]:
    """Analyze section weight distribution across documents."""
    section_chars: dict[str, int] = {}
    heading_pattern = re.compile(r'^#{1,3}\s+(.+)$|^(\d+\.)\s+(.+)$', re.MULTILINE)

    for doc in documents:
        headings = list(heading_pattern.finditer(doc))
        for i, match in enumerate(headings):
            name = (match.group(1) or match.group(3) or "").strip()
            if not name:
                continue
            start = match.end()
            end = headings[i + 1].start() if i + 1 < len(headings) else len(doc)
            char_count = end - start
            section_chars[name] = section_chars.get(name, 0) + char_count

    total = sum(section_chars.values())
    if total == 0:
        return {}
    return {k: round(v / total, 3) for k, v in section_chars.items()}
