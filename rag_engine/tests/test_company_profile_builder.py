from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from company_analyzer import StyleProfile
from company_profile_builder import build_profile_md, save_profile_md, load_profile_md


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def rich_style() -> StyleProfile:
    """A StyleProfile populated with realistic data."""
    return StyleProfile(
        tone="격식체",
        avg_sentence_length=42.5,
        structure_pattern="사업이해(35%) → 수행방안(40%) → 기대효과(25%)",
        strength_keywords=["클라우드", "마이그레이션", "보안", "자동화"],
        terminology={"CI/CD": "지속적 통합/배포", "IaC": "코드형 인프라"},
        common_phrases=["최적의 솔루션을 제공", "안정적 운영 환경 구축"],
        section_weight_pattern={"사업이해": 0.35, "수행방안": 0.40, "기대효과": 0.25},
    )


@pytest.fixture
def hwpx_styles_dict() -> dict:
    """A sample HWPX styles dictionary."""
    return {
        "body_font": "맑은 고딕",
        "heading_font": "맑은 고딕 Bold",
        "line_spacing": 160,
        "margins": {"top": 20, "bottom": 15, "left": 30, "right": 30},
        "header_text": "○○기관 제안서",
        "footer_text": "㈜키라소프트",
        "page_number_format": "- {page} -",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_build_profile_md_from_style(rich_style: StyleProfile):
    """StyleProfile -> md conversion produces all required sections."""
    md = build_profile_md("키라소프트", style=rich_style)

    # Must include all 6 required sections
    assert "# 키라소프트 회사 프로필" in md
    assert "## 문서 스타일" in md
    assert "## 문체" in md
    assert "## 강점 표현 패턴" in md
    assert "## 평가항목별 전략" in md
    assert "## HWPX 생성 규칙" in md
    assert "## 학습 이력" in md

    # Tone info appears in 문체 section
    assert "격식체" in md

    # Average sentence length
    assert "42.5" in md

    # Strength keywords listed
    assert "클라우드" in md
    assert "마이그레이션" in md

    # Terminology mapping
    assert "CI/CD" in md
    assert "지속적 통합/배포" in md

    # Common phrases
    assert "최적의 솔루션을 제공" in md

    # Section weight pattern
    assert "사업이해" in md
    assert "수행방안" in md

    # HWPX placeholder when no hwpx_styles provided
    assert "HWPX 템플릿 업로드 시 자동 채움" in md


def test_build_profile_md_empty_style():
    """Empty/None StyleProfile still produces valid markdown with all sections."""
    # With style=None (no StyleProfile at all)
    md_none = build_profile_md("테스트기업", style=None)

    assert "# 테스트기업 회사 프로필" in md_none
    assert "## 문서 스타일" in md_none
    assert "## 문체" in md_none
    assert "## 강점 표현 패턴" in md_none
    assert "## 평가항목별 전략" in md_none
    assert "## HWPX 생성 규칙" in md_none
    assert "## 학습 이력" in md_none

    # With default StyleProfile (empty fields)
    md_default = build_profile_md("테스트기업", style=StyleProfile())

    assert "## 문체" in md_default
    # Default tone should still appear
    assert "격식체" in md_default
    assert "## HWPX 생성 규칙" in md_default


def test_build_profile_md_with_hwpx_styles(rich_style: StyleProfile, hwpx_styles_dict: dict):
    """When hwpx_styles dict is provided, HWPX section is populated (no placeholder)."""
    md = build_profile_md("키라소프트", style=rich_style, hwpx_styles=hwpx_styles_dict)

    # HWPX section should contain actual style info, NOT placeholder
    assert "HWPX 템플릿 업로드 시 자동 채움" not in md

    # Actual HWPX style values should be present
    assert "맑은 고딕" in md
    assert "160" in md
    assert "○○기관 제안서" in md
    assert "㈜키라소프트" in md
    assert "- {page} -" in md


def test_save_and_load_profile_md(tmp_path):
    """Round-trip: save profile.md then load it back."""
    company_dir = str(tmp_path / "company_skills" / "company_abc")

    content = build_profile_md("테스트기업", style=StyleProfile(tone="경어체"))

    # save
    saved_path = save_profile_md(company_dir, content)
    assert os.path.isfile(saved_path)
    assert saved_path.endswith("profile.md")

    # load
    loaded = load_profile_md(company_dir)
    assert loaded == content
    assert "테스트기업" in loaded
    assert "경어체" in loaded


def test_load_profile_md_missing(tmp_path):
    """Loading from a non-existent directory returns empty string."""
    missing_dir = str(tmp_path / "does_not_exist")
    result = load_profile_md(missing_dir)
    assert result == ""


def test_build_profile_md_with_body_font_size():
    """body_font_size appears in profile.md HWPX section."""
    hwpx_styles = {
        "body_font": "함초롬바탕",
        "heading_font": "함초롬돋움",
        "body_font_size": 11.0,
    }
    md = build_profile_md("테스트기업", hwpx_styles=hwpx_styles)
    assert "함초롬바탕" in md
    assert "함초롬돋움" in md
    assert "11.0" in md
    assert "본문 글꼴 크기" in md
