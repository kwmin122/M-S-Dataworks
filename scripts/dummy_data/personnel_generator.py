"""인력 정보 합성 생성기"""
from faker import Faker
import random

fake = Faker('ko_KR')

POSITIONS = [
    "책임PM", "수석컨설턴트", "선임연구원", "책임연구원",
    "선임개발자", "책임엔지니어", "수석아키텍트", "기술총괄"
]

EDUCATIONS = [
    "서울대 컴퓨터공학 석사", "KAIST 전산학 박사", "연세대 정보시스템 석사",
    "고려대 소프트웨어학 석사", "포항공대 컴퓨터공학 박사", "성균관대 정보통신 석사"
]

EXPERTISE_AREAS = {
    "클라우드": ["클라우드 아키텍처", "DevOps", "Kubernetes", "컨테이너 오케스트레이션"],
    "AI/빅데이터": ["머신러닝", "딥러닝", "데이터 엔지니어링", "빅데이터 플랫폼"],
    "보안": ["정보보안", "침해대응", "보안관제", "취약점 분석"],
    "금융IT": ["뱅킹시스템", "핀테크", "금융보안", "레거시 마이그레이션"],
    "공공SI": ["전자정부", "행정시스템", "공공데이터", "디지털전환"]
}

def generate_personnel_for_company(company_profile: dict, count: int = 8) -> list:
    """
    회사 프로필 기반 인력 정보 합성 생성

    Args:
        company_profile: 회사 프로필 dict
        count: 생성할 인력 수 (기본 8명)

    Returns:
        list of dict: 인력 정보 리스트
    """
    personnel = []
    available_certs = list(company_profile.get("certifications", {}).keys())
    business_areas = company_profile.get("business_areas", ["공공SI"])

    for i in range(count):
        # 경력 연수 (3~20년, 정규분포)
        career_years = max(3, min(20, int(random.gauss(10, 4))))

        # 자격증 (1~3개)
        num_certs = random.choices([1, 2, 3], weights=[0.3, 0.5, 0.2])[0]
        certifications = random.sample(available_certs, min(num_certs, len(available_certs)))

        # 전문 분야 (사업 영역 기반)
        expertise = []
        for area in business_areas[:2]:  # 상위 2개 영역
            if area in EXPERTISE_AREAS:
                expertise.extend(random.sample(EXPERTISE_AREAS[area], 2))

        personnel.append({
            "name": fake.name(),
            "position": random.choice(POSITIONS),
            "career_years": career_years,
            "education": random.choice(EDUCATIONS),
            "certifications": certifications,
            "expertise": expertise[:3],  # 최대 3개
            "major_projects": []  # 나중에 프로젝트 생성 시 채움
        })

    return personnel
