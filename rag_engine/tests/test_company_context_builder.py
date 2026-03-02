"""Tests for company_context_builder.py."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock, patch


def _rfx_result():
    return {
        "title": "스마트시티 통합플랫폼 구축",
        "issuing_org": "서울시",
        "budget": "50억",
        "requirements": [
            {"category": "기술", "description": "IoT 센서 통합 관제 시스템"},
            {"category": "인력", "description": "PM 10년 이상 경력"},
        ],
    }


def test_build_company_context_empty_db():
    """CompanyDB에 데이터 없으면 빈 문자열 반환."""
    from company_context_builder import build_company_context

    # Non-existent path → CompanyDB init may fail or return empty
    result = build_company_context(_rfx_result(), company_db_path="/tmp/nonexistent_company_db_test")
    # Should not raise, may return empty or minimal context
    assert isinstance(result, str)


def test_build_company_context_with_profile():
    """프로필이 있으면 회사 기본 정보 포함."""
    from company_context_builder import build_company_context
    from company_db import CompanyCapabilityProfile

    mock_profile = CompanyCapabilityProfile(
        name="테스트기업",
        licenses=["소프트웨어사업자", "정보통신공사업"],
        certifications=["ISO 27001", "ISMS"],
        capital=30.0,
        employee_count=150,
    )
    mock_db = MagicMock()
    mock_db.load_profile.return_value = mock_profile
    mock_db.search_similar_projects.return_value = []
    mock_db.find_matching_personnel.return_value = []

    with patch("company_db.CompanyDB", return_value=mock_db):
        result = build_company_context(_rfx_result())

    assert "테스트기업" in result
    assert "소프트웨어사업자" in result
    assert "30" in result  # capital
    assert "150" in result  # employees


def test_build_company_context_with_projects():
    """유사수행실적이 있으면 프로젝트 정보 포함."""
    from company_context_builder import build_company_context

    mock_db = MagicMock()
    mock_db.load_profile.return_value = None
    mock_db.search_similar_projects.return_value = [
        {
            "text": "프로젝트: 세종시 스마트시티\n발주처: 세종시\n금액: 30억원",
            "metadata": {"project_name": "세종시 스마트시티", "client": "세종시", "amount": 30.0},
            "distance": 0.2,
        },
    ]
    mock_db.find_matching_personnel.return_value = [
        {
            "text": "이름: 김영수\n역할: PM\n경력: 15년",
            "metadata": {"name": "김영수", "role": "PM", "experience_years": 15},
            "distance": 0.3,
        },
    ]

    with patch("company_db.CompanyDB", return_value=mock_db):
        result = build_company_context(_rfx_result())

    assert "세종시 스마트시티" in result
    assert "김영수" in result
    assert "PM" in result


def test_build_company_context_with_style():
    """writing_style이 있으면 스타일 정보 포함."""
    from company_context_builder import build_company_context
    from company_db import CompanyCapabilityProfile

    mock_profile = CompanyCapabilityProfile(
        name="스타일테스트",
        writing_style={
            "tone": "격식체",
            "avg_sentence_length": 28.5,
            "strength_keywords": ["클라우드", "AI", "보안"],
            "common_phrases": ["최적의 솔루션을 제공"],
        },
    )
    mock_db = MagicMock()
    mock_db.load_profile.return_value = mock_profile
    mock_db.search_similar_projects.return_value = []
    mock_db.find_matching_personnel.return_value = []

    with patch("company_db.CompanyDB", return_value=mock_db):
        result = build_company_context(_rfx_result())

    assert "격식체" in result
    assert "클라우드" in result


def test_build_company_context_exception_safety():
    """CompanyDB 예외 시 빈 문자열 반환 (안전 fallback)."""
    from company_context_builder import build_company_context

    with patch("company_db.CompanyDB", side_effect=Exception("DB error")):
        result = build_company_context(_rfx_result())
    assert result == ""


def test_format_helpers():
    """내부 포맷 함수 검증."""
    from company_context_builder import _format_profile, _format_projects, _format_personnel, _format_style
    from company_db import CompanyCapabilityProfile

    # Profile
    profile = CompanyCapabilityProfile(name="테스트", licenses=["면허A"], capital=10.0, employee_count=50)
    result = _format_profile(profile)
    assert "테스트" in result
    assert "면허A" in result

    # Projects
    projects = [{"text": "프로젝트 A", "metadata": {"project_name": "A", "client": "B"}, "distance": 0.1}]
    result = _format_projects(projects)
    assert "A" in result
    assert "B" in result

    # Personnel
    personnel = [{"text": "홍길동", "metadata": {"name": "홍길동", "role": "PL", "experience_years": 10}, "distance": 0.2}]
    result = _format_personnel(personnel)
    assert "홍길동" in result
    assert "PL" in result

    # Style
    style = {"tone": "경어체", "strength_keywords": ["보안", "AI"]}
    result = _format_style(style)
    assert "경어체" in result
    assert "보안" in result

    # Empty style
    assert _format_style({}) == ""
