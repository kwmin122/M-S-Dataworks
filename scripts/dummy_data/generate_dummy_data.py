"""
Kira Bot 더미 데이터 생성 메인 오케스트레이터

20개 회사 × (프로필 + PDF + CompanyDB) 전체 처리
"""
import sys
import os
import json
import random
from datetime import datetime

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from company_generator import generate_company_profile_pdf
from personnel_generator import generate_personnel_for_company
from company_data_builder import load_company_to_db


def load_company_profiles():
    """Load company profiles from JSON"""
    profiles_path = os.path.join(current_dir, "company_profiles.json")
    with open(profiles_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_project_templates():
    """Load project templates from JSON"""
    templates_path = os.path.join(current_dir, "project_templates.json")
    with open(templates_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def generate_projects_for_company(company_profile: dict, templates: dict, count: int = 12) -> list:
    """
    회사 프로필 기반으로 12개 프로젝트 생성

    Args:
        company_profile: 회사 프로필 dict (from company_profiles.json)
        templates: 프로젝트 템플릿 dict (from project_templates.json)
        count: 생성할 프로젝트 수 (기본 12)

    Returns:
        list of dict: 프로젝트 실적 리스트
    """
    projects = []
    business_areas = company_profile.get("business_areas", [])
    revenue = company_profile.get("revenue", 10000000000)

    # 템플릿 카테고리 매핑
    category_map = {
        "공공SI": "공공SI",
        "IT서비스": "공공SI",
        "클라우드": "클라우드",
        "물류": "공공SI",
        "AI/빅데이터": "AI/빅데이터",
        "AI": "AI/빅데이터",
        "빅데이터": "AI/빅데이터",
        "빅데이터분석": "AI/빅데이터",
        "데이터분석": "AI/빅데이터",
        "보안": "보안",
        "정보보안": "보안",
        "네트워크보안": "보안",
        "금융IT": "금융IT",
        "DX컨설팅": "공공SI",
        "스마트팩토리": "공공SI",
    }

    # 회사 사업 분야에 맞는 카테고리 결정
    available_categories = []
    for area in business_areas[:3]:  # 상위 3개 영역만 사용
        if area in category_map:
            cat = category_map[area]
            if cat not in available_categories:
                available_categories.append(cat)

    # 카테고리 없으면 공공SI 기본
    if not available_categories:
        available_categories = ["공공SI"]

    # 12개 프로젝트 생성
    for i in range(count):
        # 카테고리 선택 (80% 메인 카테고리, 20% 서브 카테고리)
        if i < int(count * 0.8):
            category = available_categories[0]
        else:
            category = random.choice(available_categories)

        # 템플릿 키워드 선택
        template_category = templates["categories"].get(category, templates["categories"]["공공SI"])
        keyword = random.choice(template_category["keywords"])
        client = random.choice(template_category["clients"])

        # 프로젝트 금액 스케일링 (회사 매출 대비)
        amount_scale = revenue / 100000000000  # 1000억 기준
        amount_ranges = templates["amount_ranges"]

        if amount_scale > 50:  # 초대형 (5조+)
            min_amt, max_amt = amount_ranges["대형"]
        elif amount_scale > 5:  # 대형 (500억+)
            min_amt, max_amt = amount_ranges["중형"]
        elif amount_scale > 0.5:  # 중형 (50억+)
            min_amt, max_amt = amount_ranges["소형"]
        else:  # 소형
            min_amt, max_amt = [500000000, 2000000000]

        amount = random.randint(min_amt, max_amt)

        # 기간 (6~24개월)
        duration_months = random.choice([6, 9, 12, 18, 24])
        start_year = random.randint(2020, 2024)
        start_month = random.randint(1, 12)
        end_month = (start_month + duration_months - 1) % 12 + 1
        end_year = start_year + (start_month + duration_months - 1) // 12
        period = f"{start_year}.{start_month:02d} ~ {end_year}.{end_month:02d}"

        # 역할 (회사 규모에 따라)
        if amount_scale > 10:
            role = "총괄 수행사"
        elif amount_scale > 1:
            role = random.choice(["주관사", "총괄 수행사", "공동 수행사"])
        else:
            role = random.choice(["단독 수행", "공동 수행사"])

        # 기술 스택 (카테고리별)
        tech_stacks = {
            "공공SI": ["Java", "Spring Framework", "Oracle", "PostgreSQL", "Linux"],
            "클라우드": ["AWS", "Kubernetes", "Docker", "Terraform", "Python"],
            "금융IT": ["Java", "Spring Boot", "Oracle RAC", "WebLogic", "MSA"],
            "보안": ["방화벽", "IPS/IDS", "SIEM", "EDR", "망분리"],
            "AI/빅데이터": ["Python", "TensorFlow", "Hadoop", "Spark", "Elasticsearch"]
        }
        tech_stack = random.sample(tech_stacks.get(category, tech_stacks["공공SI"]), 3)

        # 프로젝트 설명
        description = f"{keyword} 솔루션 구축 및 운영"

        # 성과
        outcomes = [
            "시스템 안정성 99.9% 달성",
            "사용자 만족도 95점 이상",
            "장애 제로 운영",
            "성능 30% 향상",
            "비용 20% 절감"
        ]
        outcome = random.choice(outcomes)

        projects.append({
            "name": f"{client} {keyword} 사업",
            "client": client,
            "amount": amount,
            "period": period,
            "role": role,
            "description": description,
            "tech_stack": tech_stack,
            "outcome": outcome
        })

    return projects


def ensure_output_directory():
    """Ensure output directory exists"""
    output_dir = os.path.join(os.path.dirname(current_dir), "..", "data", "company_docs")
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def main():
    """Main orchestrator"""
    print("=" * 60)
    print("Kira Bot 더미 데이터 생성 시작")
    print("=" * 60)
    print()

    # Load configurations
    company_profiles = load_company_profiles()
    project_templates = load_project_templates()

    print(f"✅ {len(company_profiles)}개 회사 프로필 로드 완료")
    print()

    # Ensure output directory
    output_dir = ensure_output_directory()

    # Statistics
    total_pdfs = 0
    total_projects = 0
    total_personnel = 0

    # Process each company
    for company_id, profile in company_profiles.items():
        company_name = profile["name"]

        print("=" * 60)
        print(f"Processing: {company_name} ({company_id})")
        print("=" * 60)

        # 1. Generate 12 projects
        print("  - 프로젝트 실적: 생성 중...", end=" ")
        projects = generate_projects_for_company(profile, project_templates, count=12)
        print(f"{len(projects)}건 완료")

        # 2. Generate 8 personnel
        print("  - 인력 정보: 생성 중...", end=" ")
        personnel = generate_personnel_for_company(profile, count=8)
        print(f"{len(personnel)}명 완료")

        # 3. Generate PDF (10 pages)
        pdf_filename = f"{company_name}_회사소개서.pdf"
        pdf_path = os.path.join(output_dir, pdf_filename)
        print(f"  - PDF 생성: {pdf_path}...", end=" ")

        # Prepare company_data for PDF
        company_data = {
            "company_name": company_name,
            "establishment_year": int(profile["established"][:4]),
            "representative": f"{company_name} 대표이사",
            "employee_count": profile["employees"],
            "address": "서울특별시 강남구 테헤란로 123",
            "website": f"www.{profile.get('name_en', company_name).lower().replace(' ', '')}.com",
            "business_areas": profile["business_areas"]
        }

        generate_company_profile_pdf(company_data, projects, pdf_path)
        print("완료")

        # 4. Load to CompanyDB
        print("  - CompanyDB 적재: ", end="")
        profile_for_db = {
            "name": company_name,
            "registration_number": f"{company_id}-{random.randint(1000000, 9999999)}",
            "licenses": ["정보통신공사업", "소프트웨어사업자"],
            "certifications": list(profile["certifications"].keys()),
            "capital": profile["revenue"] * 0.1,  # 자본금 = 매출의 10%
            "employees": profile["employees"],
            "writing_style": {
                "tone": "formal",
                "length": "detailed",
                "technical_depth": "high"
            }
        }

        load_company_to_db(company_id, profile_for_db, projects, personnel)

        # Update statistics
        total_pdfs += 1
        total_projects += len(projects)
        total_personnel += len(personnel)

        print()

    # Final summary
    print("=" * 60)
    print("🎉 더미 데이터 생성 완료!")
    print("=" * 60)
    print(f"- 회사소개서 PDF: {total_pdfs}개")
    print(f"- CompanyDB 실적: ~{total_projects}건")
    print(f"- CompanyDB 인력: ~{total_personnel}명")
    print()
    print("다음 단계:")
    print("  1. PDF 파일 확인: ls data/company_docs/")
    print("  2. CompanyDB 확인: python -c 'from rag_engine.company_db import CompanyDB; db = CompanyDB(); print(len(db.get_all_track_records()))'")
    print("  3. 테스트 시나리오 작성: docs/test/TEST_SCENARIOS.md")
    print()


if __name__ == "__main__":
    main()
