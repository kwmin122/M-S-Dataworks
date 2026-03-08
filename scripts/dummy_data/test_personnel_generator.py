import sys
sys.path.append('scripts/dummy_data')
from personnel_generator import generate_personnel_for_company

def test_generate_personnel_basic():
    """기본 인력 생성 테스트"""
    company_profile = {
        "name": "테스트회사",
        "employees": 100,
        "tech_ratio": 0.7,
        "certifications": {"정보처리기사": 30, "PMP": 10}
    }

    personnel = generate_personnel_for_company(company_profile, count=8)

    assert len(personnel) == 8
    assert all("name" in p for p in personnel)
    assert all("position" in p for p in personnel)
    assert all("certifications" in p for p in personnel)
    assert all(isinstance(p["career_years"], int) for p in personnel)
    assert all(3 <= p["career_years"] <= 20 for p in personnel)

def test_certification_distribution():
    """자격증 분포 테스트"""
    company_profile = {
        "name": "테스트회사",
        "employees": 100,
        "tech_ratio": 0.7,
        "certifications": {"정보처리기사": 30, "PMP": 10}
    }

    personnel = generate_personnel_for_company(company_profile, count=8)

    # 최소 1명은 정보처리기사 보유
    cert_holders = [p for p in personnel if "정보처리기사" in p["certifications"]]
    assert len(cert_holders) >= 1
