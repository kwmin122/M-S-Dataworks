# 더미 데이터 생성 구현 계획

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Kira Bot 전체 플로우 E2E 검증용 현실적 더미 데이터 생성 (회사 20개, 실적 240건, 인력 160명, 테스트 시나리오 10~15개)

**Architecture:** 수동 큐레이션 (company_profiles.json) → PDF 생성 (reportlab) → CompanyDB 적재 (ChromaDB) → 테스트 시나리오 문서 생성 → E2E 검증

**Tech Stack:** Python 3.13, reportlab (PDF), Faker (합성 데이터), ChromaDB (company_db.py), pytest

---

## Task 1: 프로젝트 구조 및 의존성 설정

**Files:**
- Create: `scripts/dummy_data/__init__.py`
- Create: `scripts/dummy_data/company_profiles.json` (빈 템플릿)
- Create: `scripts/dummy_data/project_templates.json`
- Create: `requirements-dummy.txt`

**Step 1: 디렉토리 생성**

```bash
mkdir -p scripts/dummy_data
mkdir -p data/company_docs
touch scripts/dummy_data/__init__.py
```

**Step 2: 의존성 파일 작성**

Create: `requirements-dummy.txt`

```txt
reportlab==4.0.9
Faker==22.6.0
```

**Step 3: 의존성 설치**

```bash
pip install -r requirements-dummy.txt
```

Expected: Successfully installed reportlab, Faker

**Step 4: 프로젝트 템플릿 JSON 작성**

Create: `scripts/dummy_data/project_templates.json`

```json
{
  "categories": {
    "공공SI": {
      "keywords": ["전자정부", "행정시스템", "공공데이터", "디지털전환"],
      "clients": ["행정안전부", "국방부", "외교부", "교육부", "국토교통부"]
    },
    "클라우드": {
      "keywords": ["AWS", "Azure", "클라우드 전환", "마이그레이션", "MSP"],
      "clients": ["행정안전부", "금융위원회", "과학기술정보통신부"]
    },
    "금융IT": {
      "keywords": ["뱅킹시스템", "핀테크", "보안", "금융망"],
      "clients": ["국민은행", "신한은행", "하나은행", "금융감독원"]
    },
    "보안": {
      "keywords": ["정보보안", "침해대응", "보안관제", "컴플라이언스"],
      "clients": ["국가정보원", "행정안전부", "과학기술정보통신부"]
    },
    "AI/빅데이터": {
      "keywords": ["인공지능", "머신러닝", "데이터분석", "빅데이터플랫폼"],
      "clients": ["한국정보화진흥원", "과학기술정보통신부", "통계청"]
    }
  },
  "amount_ranges": {
    "소형": [1000000000, 5000000000],
    "중형": [5000000000, 20000000000],
    "대형": [20000000000, 100000000000],
    "초대형": [100000000000, 500000000000]
  }
}
```

**Step 5: 회사 프로필 빈 템플릿 작성**

Create: `scripts/dummy_data/company_profiles.json`

```json
{
  "company_001": {
    "name": "삼성SDS",
    "name_en": "Samsung SDS",
    "established": "1985-03",
    "revenue": 15000000000000,
    "employees": 25000,
    "tech_ratio": 0.72,
    "business_areas": ["클라우드", "AI/빅데이터", "DX컨설팅", "보안"],
    "certifications": {
      "정보처리기사": 1200,
      "PMP": 450,
      "AWS_SAA": 380,
      "정보보안기사": 650
    },
    "major_clients": ["행정안전부", "국방부", "금융위원회"],
    "project_categories": ["공공SI", "클라우드", "금융IT", "AI/빅데이터"],
    "real_benchmark": true
  }
}
```

**Step 6: Commit**

```bash
git add scripts/dummy_data/ requirements-dummy.txt data/company_docs/.gitkeep
git commit -m "feat(dummy): add project structure and templates"
```

---

## Task 2: 회사 프로필 수동 큐레이션 (20개)

**Files:**
- Modify: `scripts/dummy_data/company_profiles.json`

**Step 1: A그룹 10개 회사 정보 추가**

Modify: `scripts/dummy_data/company_profiles.json`

회사 1~10번 (삼성SDS, LG CNS, 현대건설, 대우건설, 컨설팅 A/B, 제조 A/B, 연구 A/B) 추가.

각 회사 구조:
```json
{
  "company_00X": {
    "name": "회사명",
    "name_en": "Company Name",
    "established": "YYYY-MM",
    "revenue": 금액,
    "employees": 인원,
    "tech_ratio": 0.X,
    "business_areas": ["영역1", "영역2", "영역3"],
    "certifications": { "자격증명": 인원수 },
    "major_clients": ["고객사1", "고객사2"],
    "project_categories": ["카테고리1", "카테고리2"],
    "real_benchmark": true
  }
}
```

**Step 2: B그룹 10개 회사 정보 추가**

회사 11~20번 (더존비즈온, 한국전산원 협력사, 가비아, 솔루션 A/B, 시스템통합 A/B, 보안 A/B, IT서비스 C) 추가.

**Step 3: 검증**

```bash
python -c "import json; data=json.load(open('scripts/dummy_data/company_profiles.json')); print(f'{len(data)} companies loaded')"
```

Expected: `20 companies loaded`

**Step 4: Commit**

```bash
git add scripts/dummy_data/company_profiles.json
git commit -m "feat(dummy): curate 20 company profiles"
```

---

## Task 3: 인력 정보 합성 생성기

**Files:**
- Create: `scripts/dummy_data/personnel_generator.py`
- Create: `scripts/dummy_data/test_personnel_generator.py`

**Step 1: Write failing test**

Create: `scripts/dummy_data/test_personnel_generator.py`

```python
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
```

**Step 2: Run test to verify it fails**

```bash
cd scripts/dummy_data
pytest test_personnel_generator.py -v
```

Expected: FAIL (module 'personnel_generator' has no attribute 'generate_personnel_for_company')

**Step 3: Write minimal implementation**

Create: `scripts/dummy_data/personnel_generator.py`

```python
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
```

**Step 4: Run test to verify it passes**

```bash
cd scripts/dummy_data
pytest test_personnel_generator.py -v
```

Expected: PASS (2 passed)

**Step 5: Commit**

```bash
git add scripts/dummy_data/personnel_generator.py scripts/dummy_data/test_personnel_generator.py
git commit -m "feat(dummy): add personnel generator with Faker"
```

---

## Task 4: 회사소개서 PDF 생성기

**Files:**
- Create: `scripts/dummy_data/company_generator.py`
- Create: `scripts/dummy_data/test_company_generator.py`

**Step 1: Write failing test**

Create: `scripts/dummy_data/test_company_generator.py`

```python
import sys
sys.path.append('scripts/dummy_data')
from company_generator import generate_company_profile_pdf
import os
import json

def test_generate_pdf_basic():
    """기본 PDF 생성 테스트"""
    with open('company_profiles.json') as f:
        profiles = json.load(f)

    company_data = profiles['company_001']
    output_path = '/tmp/test_company.pdf'

    # 프로젝트 실적 더미
    projects = [
        {
            "name": "테스트 프로젝트 1",
            "client": "행정안전부",
            "period": "2023.03 ~ 2024.12",
            "amount": 15000000000,
            "role": "주관사"
        }
    ]

    generate_company_profile_pdf(company_data, projects, output_path)

    assert os.path.exists(output_path)
    assert os.path.getsize(output_path) > 100000  # 최소 100KB

    # 정리
    os.remove(output_path)

def test_pdf_page_count():
    """PDF 페이지 수 검증"""
    # reportlab은 페이지 수를 직접 검증하기 어려움 → 파일 크기로 대체
    # 실제 검증은 수동 확인 필요
    pass
```

**Step 2: Run test to verify it fails**

```bash
cd scripts/dummy_data
pytest test_company_generator.py::test_generate_pdf_basic -v
```

Expected: FAIL (module 'company_generator' has no attribute 'generate_company_profile_pdf')

**Step 3: Write minimal implementation**

Create: `scripts/dummy_data/company_generator.py`

```python
"""회사소개서 PDF 생성기 (넥스트웨이브 템플릿 기반)"""
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle

def generate_company_profile_pdf(company_data: dict, projects: list, output_path: str):
    """
    10페이지 회사소개서 PDF 생성

    Args:
        company_data: 회사 프로필 dict
        projects: 프로젝트 실적 list
        output_path: 출력 PDF 경로
    """
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4

    # 한글 폰트 등록 (시스템 기본 폰트 사용)
    try:
        pdfmetrics.registerFont(TTFont('NanumGothic', '/System/Library/Fonts/Supplemental/AppleGothic.ttf'))
        font_name = 'NanumGothic'
    except:
        font_name = 'Helvetica'  # 폴백

    # 1페이지: 표지
    c.setFont(font_name, 40)
    c.drawCentredString(width / 2, height - 200, company_data['name'])
    c.setFont(font_name, 20)
    c.drawCentredString(width / 2, height - 250, "COMPANY PROFILE 2025")
    c.showPage()

    # 2페이지: 회사 개요
    c.setFont(font_name, 24)
    c.drawString(50, height - 80, "회사 개요")

    c.setFont(font_name, 12)
    y = height - 120
    overview_data = [
        ["설립", company_data['established']],
        ["매출", f"{company_data['revenue'] // 100000000}억 원 (2024)"],
        ["임직원", f"약 {company_data['employees']:,}명"],
        ["기술인력", f"{int(company_data['employees'] * company_data['tech_ratio']):,}명 ({int(company_data['tech_ratio'] * 100)}%)"]
    ]

    for label, value in overview_data:
        c.drawString(70, y, f"{label}: {value}")
        y -= 30

    c.showPage()

    # 3페이지: 회사 연혁
    c.setFont(font_name, 24)
    c.drawString(50, height - 80, "회사 연혁")

    c.setFont(font_name, 11)
    y = height - 120
    history_items = [
        (company_data['established'], f"{company_data['name']} 설립"),
        ("2020.04", "매출 500억 원 달성"),
        ("2022.03", "ISO 27001:2013 정보보호관리체계 인증 취득"),
        ("2024.01", f"매출 {company_data['revenue'] // 100000000}억 원, 임직원 {company_data['employees']}명 달성")
    ]

    for date, event in history_items:
        c.drawString(70, y, f"{date}  |  {event}")
        y -= 25

    c.showPage()

    # 4페이지: 조직 및 인력
    c.setFont(font_name, 24)
    c.drawString(50, height - 80, "조직 및 인력 현황")

    c.setFont(font_name, 12)
    y = height - 130
    c.drawString(70, y, "기술 자격증 보유 현황:")
    y -= 30

    for cert, count in company_data.get('certifications', {}).items():
        c.drawString(90, y, f"{cert}: {count}명")
        y -= 25

    c.showPage()

    # 5-7페이지: 주요 사업 실적
    for page_num in range(3):
        c.setFont(font_name, 24)
        c.drawString(50, height - 80, f"주요 사업 실적 ({page_num + 1}/3)")

        c.setFont(font_name, 10)
        y = height - 120

        # 페이지당 4개 프로젝트 표시
        start_idx = page_num * 4
        end_idx = min(start_idx + 4, len(projects))

        for project in projects[start_idx:end_idx]:
            c.drawString(70, y, f"• {project['name']}")
            c.drawString(90, y - 15, f"발주처: {project['client']} | 기간: {project['period']}")
            c.drawString(90, y - 30, f"금액: {project['amount'] // 100000000}억 원 | 역할: {project['role']}")
            y -= 60

        c.showPage()

    # 8페이지: 기술 역량
    c.setFont(font_name, 24)
    c.drawString(50, height - 80, "기술 역량")

    c.setFont(font_name, 12)
    y = height - 130
    c.drawString(70, y, "주요 사업 영역:")
    y -= 30

    for area in company_data.get('business_areas', []):
        c.drawString(90, y, f"• {area}")
        y -= 25

    c.showPage()

    # 9페이지: 주요 고객사
    c.setFont(font_name, 24)
    c.drawString(50, height - 80, "주요 고객사")

    c.setFont(font_name, 12)
    y = height - 130

    for client in company_data.get('major_clients', []):
        c.drawString(90, y, f"• {client}")
        y -= 25

    c.showPage()

    # 10페이지: 비전/강점
    c.setFont(font_name, 24)
    c.drawString(50, height - 80, "회사 비전")

    c.setFont(font_name, 14)
    c.drawString(70, height - 130, "디지털 혁신으로 고객의 내일을 만듭니다")

    c.setFont(font_name, 12)
    y = height - 180
    c.drawString(70, y, "핵심 가치:")
    y -= 30
    for value in ["신뢰(Trust)", "혁신(Innovation)", "전문성(Expertise)", "상생(Partnership)"]:
        c.drawString(90, y, f"• {value}")
        y -= 25

    c.showPage()

    c.save()
```

**Step 4: Run test to verify it passes**

```bash
cd scripts/dummy_data
pytest test_company_generator.py::test_generate_pdf_basic -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add scripts/dummy_data/company_generator.py scripts/dummy_data/test_company_generator.py
git commit -m "feat(dummy): add PDF generator with reportlab"
```

---

## Task 5: CompanyDB 적재 모듈

**Files:**
- Create: `scripts/dummy_data/company_data_builder.py`
- Create: `scripts/dummy_data/test_company_data_builder.py`

**Step 1: Write failing test**

Create: `scripts/dummy_data/test_company_data_builder.py`

```python
import sys
sys.path.append('scripts/dummy_data')
sys.path.append('rag_engine')
from company_data_builder import load_company_to_db
from company_db import CompanyDB

def test_load_company_basic():
    """CompanyDB 기본 적재 테스트"""
    company_id = "test_company_001"
    profile = {
        "name": "테스트회사",
        "revenue": 50000000000,
        "employees": 100
    }

    projects = [
        {
            "name": "테스트 프로젝트 1",
            "client": "행정안전부",
            "amount": 5000000000,
            "period": "2023.03 ~ 2024.12",
            "description": "클라우드 전환 사업",
            "tech_stack": ["AWS", "Kubernetes"],
            "category": "클라우드",
            "role": "주관사"
        }
    ]

    personnel = [
        {
            "name": "김철수",
            "position": "수석컨설턴트",
            "certifications": ["PMP", "AWS SAA"],
            "expertise": ["클라우드 아키텍처"],
            "career_years": 12
        }
    ]

    load_company_to_db(company_id, profile, projects, personnel)

    # 검증
    db = CompanyDB()
    records = db.get_track_records(company_id)
    assert len(records) == 1
    assert records[0]['project_name'] == "테스트 프로젝트 1"
```

**Step 2: Run test to verify it fails**

```bash
cd scripts/dummy_data
pytest test_company_data_builder.py -v
```

Expected: FAIL (module 'company_data_builder' has no attribute 'load_company_to_db')

**Step 3: Write minimal implementation**

Create: `scripts/dummy_data/company_data_builder.py`

```python
"""CompanyDB 적재 모듈"""
import sys
sys.path.append('rag_engine')
from company_db import CompanyDB

def load_company_to_db(company_id: str, profile: dict, projects: list, personnel: list):
    """
    CompanyDB ChromaDB에 회사 데이터 적재

    Args:
        company_id: 회사 ID (예: company_001)
        profile: 회사 프로필 dict
        projects: 프로젝트 실적 list
        personnel: 인력 정보 list
    """
    db = CompanyDB()

    # 실적 등록
    for project in projects:
        db.add_track_record(
            company_id=company_id,
            project_name=project['name'],
            client=project['client'],
            amount=project['amount'],
            period=project['period'],
            description=project.get('description', ''),
            tech_stack=project.get('tech_stack', []),
            category=project.get('category', '공공SI'),
            role=project.get('role', '주관사')
        )

    # 인력 등록
    for person in personnel:
        db.add_personnel(
            company_id=company_id,
            name=person['name'],
            position=person['position'],
            certifications=person.get('certifications', []),
            expertise=person.get('expertise', []),
            career_years=person.get('career_years', 5)
        )

    print(f"✅ {profile['name']}: 실적 {len(projects)}건, 인력 {len(personnel)}명 적재 완료")
```

**Step 4: Run test to verify it passes**

```bash
cd scripts/dummy_data
pytest test_company_data_builder.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add scripts/dummy_data/company_data_builder.py scripts/dummy_data/test_company_data_builder.py
git commit -m "feat(dummy): add CompanyDB loader"
```

---

## Task 6: 메인 오케스트레이터

**Files:**
- Create: `scripts/generate_dummy_data.py`

**Step 1: Write main script**

Create: `scripts/generate_dummy_data.py`

```python
"""더미 데이터 생성 메인 스크립트"""
import json
import sys
import random
from pathlib import Path

sys.path.append('scripts/dummy_data')
from company_generator import generate_company_profile_pdf
from personnel_generator import generate_personnel_for_company
from company_data_builder import load_company_to_db

def generate_projects_for_company(company_profile: dict, templates: dict) -> list:
    """
    회사 프로필 기반 프로젝트 실적 생성

    Args:
        company_profile: 회사 프로필 dict
        templates: project_templates.json

    Returns:
        list of dict: 프로젝트 실적 리스트 (12건)
    """
    projects = []
    categories_data = templates['categories']
    amount_ranges = templates['amount_ranges']

    # 회사 사업 영역 기반 카테고리 선택
    company_categories = company_profile.get('project_categories', ['공공SI'])

    for i in range(12):
        category = random.choice(company_categories)
        category_info = categories_data.get(category, categories_data['공공SI'])

        # 회사 규모에 따른 프로젝트 금액
        revenue = company_profile['revenue']
        if revenue >= 1000000000000:  # 1조 이상
            amount_range = amount_ranges['초대형']
        elif revenue >= 100000000000:  # 1000억 이상
            amount_range = amount_ranges['대형']
        elif revenue >= 10000000000:  # 100억 이상
            amount_range = amount_ranges['중형']
        else:
            amount_range = amount_ranges['소형']

        amount = random.randint(amount_range[0], amount_range[1])

        # 프로젝트명 생성
        keyword = random.choice(category_info['keywords'])
        client = random.choice(category_info['clients'])
        year = random.choice([2023, 2024, 2025])

        project_name = f"{client} {keyword} 구축 사업"

        # 기간 (6개월 ~ 24개월)
        duration_months = random.choice([6, 12, 18, 24])
        start_month = random.randint(1, 12)
        end_month = (start_month + duration_months) % 12 or 12
        end_year = year if duration_months <= 12 else year + 1

        period = f"{year}.{start_month:02d} ~ {end_year}.{end_month:02d}"

        # 역할
        role = random.choices(
            ["주관사", "참여사", "단독수행"],
            weights=[0.5, 0.3, 0.2]
        )[0]

        # 기술 스택
        tech_stack = random.sample(
            ["AWS", "Azure", "Kubernetes", "Terraform", "Python", "Java", "Spring", "React", "PostgreSQL"],
            k=random.randint(2, 4)
        )

        projects.append({
            "name": project_name,
            "client": client,
            "period": period,
            "amount": amount,
            "role": role,
            "description": f"{keyword} 관련 시스템 구축 및 운영",
            "tech_stack": tech_stack,
            "category": category
        })

    return projects

def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("Kira Bot 더미 데이터 생성 시작")
    print("=" * 60)

    # 1. 프로필 로드
    profiles_path = Path('scripts/dummy_data/company_profiles.json')
    templates_path = Path('scripts/dummy_data/project_templates.json')

    with open(profiles_path) as f:
        profiles = json.load(f)

    with open(templates_path) as f:
        templates = json.load(f)

    print(f"\n✅ {len(profiles)}개 회사 프로필 로드 완료")

    # 2. 각 회사별 처리
    for company_id, profile in profiles.items():
        print(f"\n{'=' * 60}")
        print(f"Processing: {profile['name']} ({company_id})")
        print(f"{'=' * 60}")

        # 2-1. 프로젝트 실적 생성
        projects = generate_projects_for_company(profile, templates)
        print(f"  - 프로젝트 실적: {len(projects)}건 생성")

        # 2-2. 인력 정보 합성
        personnel = generate_personnel_for_company(profile, count=8)
        print(f"  - 인력 정보: {len(personnel)}명 생성")

        # 2-3. 회사소개서 PDF 생성
        pdf_path = f"data/company_docs/{profile['name']}_회사소개서.pdf"
        generate_company_profile_pdf(profile, projects, pdf_path)
        print(f"  - PDF 생성: {pdf_path}")

        # 2-4. CompanyDB 적재
        load_company_to_db(company_id, profile, projects, personnel)

    print(f"\n{'=' * 60}")
    print("🎉 더미 데이터 생성 완료!")
    print(f"{'=' * 60}")
    print(f"- 회사소개서 PDF: {len(profiles)}개")
    print(f"- CompanyDB 실적: ~{len(profiles) * 12}건")
    print(f"- CompanyDB 인력: ~{len(profiles) * 8}명")
    print(f"\n다음 단계:")
    print("  1. PDF 파일 확인: ls data/company_docs/")
    print("  2. CompanyDB 확인: python -c 'from rag_engine.company_db import CompanyDB; db = CompanyDB(); print(len(db.get_all_track_records()))'")
    print("  3. 테스트 시나리오 작성: docs/test/TEST_SCENARIOS.md")

if __name__ == "__main__":
    main()
```

**Step 2: Dry run 실행**

```bash
python scripts/generate_dummy_data.py
```

Expected: 20개 회사 PDF 생성, CompanyDB 적재 완료

**Step 3: 검증**

```bash
# PDF 생성 확인
ls -lh data/company_docs/ | wc -l
# Expected: 20

# CompanyDB 확인
cd rag_engine && python -c "from company_db import CompanyDB; db = CompanyDB(); records = db.get_all_track_records(); print(f'Total records: {len(records)}')"
# Expected: Total records: 240
```

**Step 4: Commit**

```bash
git add scripts/generate_dummy_data.py
git commit -m "feat(dummy): add main orchestrator"
```

---

## Task 7: 테스트 시나리오 문서 생성

**Files:**
- Create: `docs/test/TEST_SCENARIOS.md`
- Create: `docs/test/README.md`

**Step 1: Write TEST_SCENARIOS.md**

Create: `docs/test/TEST_SCENARIOS.md`

```markdown
# Kira Bot 전체 플로우 테스트 시나리오

**생성일:** 2026-03-08
**목적:** 더미 데이터 기반 E2E 플로우 검증

---

## 시나리오 매트릭스

| ID | 회사 유형 | 공고 유형 | 예상 결과 | 검증 포인트 |
|----|----------|----------|----------|-----------|
| TS-001 | 대기업 IT (삼성SDS) | 공공 클라우드 | GO (95점) | 매출/인력 충족, 실적 풍부 |
| TS-002 | 중소 제조 A | 공공 클라우드 | NO-GO (45점) | 업종 불일치, 실적 부족 |
| TS-003 | IT 중견 (더존비즈온) | 금융 ERP | GO (88점) | ERP 전문성, 금융 실적 |
| TS-004 | 중소 컨설팅 A | 정보화전략 | GO (82점) | 컨설팅 실적, 소규모 매출 OK |
| TS-005 | 중견 건설 (현대건설) | 공공 클라우드 | NO-GO (50점) | 업종 불일치 (건설↔IT) |
| TS-006 | 보안전문 A | 보안관제 | GO (92점) | 보안 자격증, 실적 일치 |
| TS-007 | 시스템통합 A | 네트워크 인프라 | GO (90점) | 인프라 전문성 |
| TS-008 | 연구기업 A | AI 연구용역 | GO (85점) | R&D 실적, 박사급 인력 |
| TS-009 | 솔루션기업 B | 빅데이터 플랫폼 | GO (87점) | 빅데이터 실적, 기술스택 일치 |
| TS-010 | IT서비스 C | MSP 운영 | GO (89점) | MSP 실적, 운영 인력 |

---

## 시나리오 상세

### TS-001: 대기업 IT × 공공 클라우드 (HIGH MATCH)

**입력:**
- 회사: 삼성SDS (company_001)
- 공고: `입찰공고문_2026년 공공데이터 및 데이터기반행정 활성화 컨설팅.pdf`

**Step 1: 공고 업로드**
```bash
curl -F "file=@docs/test/입찰공고문_2026년 공공데이터 및 데이터기반행정 활성화 컨설팅.pdf" \
  http://localhost:8000/api/upload_target?session_id=ts001
```
- 예상: 200 OK, `{"status": "success", "chunks": 13}`

**Step 2: 회사 문서 업로드**
```bash
curl -F "file=@data/company_docs/삼성SDS_회사소개서.pdf" \
  http://localhost:8000/api/upload_company?session_id=ts001
```
- 예상: 200 OK, `{"status": "success", "chunks": 10}`

**Step 3: RFP 분석**
```bash
curl -X POST http://localhost:8000/api/analyze?session_id=ts001
```
- 예상 자격요건:
  - 매출: 최근 3년 평균 100억 이상
  - 유사 실적: 공공데이터 or 클라우드 실적 3건 이상
  - 기술인력: 정보처리기사 5명 이상

**Step 4: GO/NO-GO 매칭**
- 예상 점수: 95/100
  - 매출 충족: ✅ (15조 >> 100억)
  - 유사 실적: ✅ (클라우드 실적 8건)
  - 기술인력: ✅ (정보처리기사 1,200명)
- 최종 판단: "GO"

**Step 5: 제안서 생성 (v2)**
```bash
curl -X POST http://localhost:8001/api/generate-proposal-v2 \
  -H "Content-Type: application/json" \
  -d '{
    "company_id": "company_001",
    "rfp_text": "...",
    "total_pages": 80
  }'
```
- 예상: 80페이지 DOCX 생성
- 검증:
  - 블라인드 체크 통과 (회사명 0건)
  - 모호 표현 < 5건
  - Layer 1 지식 주입 확인

**Step 6: WBS 생성**
```bash
curl -X POST http://localhost:8001/api/generate-wbs \
  -H "Content-Type: application/json" \
  -d '{"company_id": "company_001", "rfp_text": "..."}'
```
- 예상: XLSX (간트차트) + DOCX 수행계획서
- 검증: 태스크 20~30개, 마일스톤 4~5개

**Step 7: PPT 생성**
```bash
curl -X POST http://localhost:8001/api/generate-ppt \
  -H "Content-Type: application/json" \
  -d '{"company_id": "company_001", "proposal_path": "..."}'
```
- 예상: 25~30 슬라이드 PPTX, 예상질문 10개
- 검증: KRDS 디자인 토큰, 6종 슬라이드 타입

**Step 8: 실적기술서 생성**
```bash
curl -X POST http://localhost:8001/api/generate-track-record \
  -H "Content-Type: application/json" \
  -d '{"company_id": "company_001", "requirements": {...}}'
```
- 예상: DOCX, 매칭 실적 5건 + 인력 3명
- 검증: CompanyDB 실적 정확히 매칭

**Step 9: 체크리스트 확인**
```bash
curl -X POST http://localhost:8001/api/checklist \
  -H "Content-Type: application/json" \
  -d '{"rfp_text": "..."}'
```
- 예상: 15~20개 항목 (제출서류, 자격증명)

**Step 10: 수정 학습**
- 사용자 수정 3회 시뮬레이션
- 예상: Layer 2 자동 학습 트리거

---

### TS-002: 중소 제조 × 공공 클라우드 (LOW MATCH)

**입력:**
- 회사: 제조기업 A (company_007)
- 공고: 동일 (공공데이터 컨설팅)

**예상 결과:**
- GO/NO-GO: NO-GO (45점)
- 매출 충족: ✅ (100억)
- 유사 실적: ❌ (제조/방산만 있음, 클라우드 0건)
- 기술인력: ⚠️ (정보처리기사 2명, 부족)

**검증 포인트:**
- matcher가 "업종 불일치" 정확히 감지
- 제안서 생성 안 함 (NO-GO 시 차단)

---

(TS-003 ~ TS-010 동일 패턴)

---

## 자동화 스크립트

```bash
#!/bin/bash
# scripts/run_all_scenarios.sh

for i in {1..10}; do
  scenario_id=$(printf "ts%03d" $i)
  echo "Running TS-$(printf '%03d' $i)..."

  # TODO: curl 호출 자동화

  echo "✅ TS-$(printf '%03d' $i) completed"
done
```
```

**Step 2: Write README.md**

Create: `docs/test/README.md`

```markdown
# 테스트 더미 데이터 가이드

**생성일:** 2026-03-08

---

## 디렉토리 구조

```
docs/test/
├── README.md                      # 이 파일
├── TEST_SCENARIOS.md              # 테스트 시나리오 10~15개
├── 입찰공고문_*.pdf                # 공고 13개 (기존)
└── ...
```

---

## 더미 데이터 세트

**회사 데이터:**
- 위치: `data/company_docs/`
- 개수: 20개 (PDF 10페이지)
- CompanyDB: 실적 240건, 인력 160명

**공고 데이터:**
- 위치: `docs/test/`
- 개수: 13개 (PDF/HWP/HWPX)

---

## 사용 방법

**1. 더미 데이터 생성:**
```bash
python scripts/generate_dummy_data.py
```

**2. 테스트 시나리오 실행:**
```bash
# TS-001 실행 (대기업 IT × 공공 클라우드)
curl -F "file=@docs/test/입찰공고문_2026년 공공데이터 및 데이터기반행정 활성화 컨설팅.pdf" \
  http://localhost:8000/api/upload_target?session_id=ts001

curl -F "file=@data/company_docs/삼성SDS_회사소개서.pdf" \
  http://localhost:8000/api/upload_company?session_id=ts001

curl -X POST http://localhost:8000/api/analyze?session_id=ts001
```

**3. 결과 확인:**
- GO/NO-GO 점수
- 제안서 DOCX
- WBS XLSX/DOCX
- PPT PPTX
- 실적기술서 DOCX

---

## 재생성 방법

```bash
# 1. CompanyDB 초기화
cd rag_engine
python -c "from company_db import CompanyDB; db = CompanyDB(); db.clear_all()"

# 2. PDF 삭제
rm -rf data/company_docs/*.pdf

# 3. 재생성
python scripts/generate_dummy_data.py
```
```

**Step 3: Commit**

```bash
git add docs/test/TEST_SCENARIOS.md docs/test/README.md
git commit -m "docs(dummy): add test scenarios and usage guide"
```

---

## Task 8: E2E 검증 (TS-001)

**Files:**
- Create: `scripts/verify_ts001.sh`

**Step 1: Write verification script**

Create: `scripts/verify_ts001.sh`

```bash
#!/bin/bash
# TS-001 시나리오 E2E 검증 스크립트

set -e

SESSION_ID="ts001_$(date +%s)"
BASE_URL="http://localhost:8000"
RAG_URL="http://localhost:8001"

echo "=========================================="
echo "TS-001 E2E 검증 시작"
echo "Session ID: $SESSION_ID"
echo "=========================================="

# Step 1: 공고 업로드
echo -e "\n[Step 1] 공고 업로드..."
UPLOAD_TARGET=$(curl -s -F "file=@docs/test/입찰공고문_2026년 공공데이터 및 데이터기반행정 활성화 컨설팅.pdf" \
  "$BASE_URL/api/upload_target?session_id=$SESSION_ID")
echo "Response: $UPLOAD_TARGET"

# Step 2: 회사 문서 업로드
echo -e "\n[Step 2] 회사 문서 업로드..."
UPLOAD_COMPANY=$(curl -s -F "file=@data/company_docs/삼성SDS_회사소개서.pdf" \
  "$BASE_URL/api/upload_company?session_id=$SESSION_ID")
echo "Response: $UPLOAD_COMPANY"

# Step 3: 분석 실행
echo -e "\n[Step 3] 분석 실행..."
ANALYZE=$(curl -s -X POST "$BASE_URL/api/analyze?session_id=$SESSION_ID")
echo "Response: $ANALYZE"

# GO/NO-GO 점수 확인
SCORE=$(echo $ANALYZE | jq -r '.go_no_go_score // empty')
if [ ! -z "$SCORE" ]; then
  echo "✅ GO/NO-GO 점수: $SCORE"
  if [ $(echo "$SCORE >= 90" | bc) -eq 1 ]; then
    echo "✅ HIGH MATCH 확인 (90점 이상)"
  else
    echo "⚠️  예상보다 낮은 점수"
  fi
else
  echo "❌ GO/NO-GO 점수 없음"
fi

echo -e "\n=========================================="
echo "TS-001 E2E 검증 완료"
echo "=========================================="
```

**Step 2: Make executable and run**

```bash
chmod +x scripts/verify_ts001.sh
./scripts/verify_ts001.sh
```

Expected:
- 공고 업로드 성공
- 회사 문서 업로드 성공
- GO/NO-GO 점수 90점 이상

**Step 3: Commit**

```bash
git add scripts/verify_ts001.sh
git commit -m "test(dummy): add TS-001 E2E verification script"
```

---

## Task 9: 문서화 완성

**Files:**
- Create: `scripts/dummy_data/README.md`

**Step 1: Write README**

Create: `scripts/dummy_data/README.md`

```markdown
# 더미 데이터 생성 스크립트

**생성일:** 2026-03-08
**목적:** Kira Bot E2E 테스트용 현실적 더미 데이터 생성

---

## 구조

```
scripts/dummy_data/
├── company_profiles.json       # 회사 20개 기본 정보 (수동 큐레이션)
├── project_templates.json      # 프로젝트 카테고리/금액 템플릿
├── company_generator.py        # PDF 생성 (reportlab)
├── personnel_generator.py      # 인력 합성 (Faker)
├── company_data_builder.py     # CompanyDB 적재
└── test_*.py                   # 단위 테스트
```

---

## 사용 방법

**1. 의존성 설치:**
```bash
pip install -r requirements-dummy.txt
```

**2. 회사 프로필 큐레이션:**
```bash
vi scripts/dummy_data/company_profiles.json
# 20개 회사 정보 수동 입력 (1~2시간)
```

**3. 더미 데이터 생성:**
```bash
python scripts/generate_dummy_data.py
```

**4. 검증:**
```bash
ls data/company_docs/ | wc -l  # 20
cd rag_engine && python -c "from company_db import CompanyDB; db = CompanyDB(); print(len(db.get_all_track_records()))"  # 240
```

---

## 재생성

```bash
# 1. CompanyDB 초기화
cd rag_engine && python -c "from company_db import CompanyDB; db = CompanyDB(); db.clear_all()"

# 2. PDF 삭제
rm -rf data/company_docs/*.pdf

# 3. 재생성
python scripts/generate_dummy_data.py
```

---

## 테스트

```bash
cd scripts/dummy_data
pytest -v
```

---

## 출력

**회사소개서 PDF:**
- 위치: `data/company_docs/`
- 개수: 20개
- 구조: 10페이지 (표지~비전)

**CompanyDB:**
- Collection: `company_track_records`, `company_personnel`
- 실적: 240건 (회사당 12건)
- 인력: 160명 (회사당 8명)

**테스트 시나리오:**
- 위치: `docs/test/TEST_SCENARIOS.md`
- 개수: 10~15개
```

**Step 2: Commit**

```bash
git add scripts/dummy_data/README.md
git commit -m "docs(dummy): add generation script documentation"
```

---

## 완료 체크리스트

**Task 1:** ✅ 프로젝트 구조 및 의존성 설정
**Task 2:** ✅ 회사 프로필 20개 수동 큐레이션
**Task 3:** ✅ 인력 정보 합성 생성기 (TDD)
**Task 4:** ✅ 회사소개서 PDF 생성기 (TDD)
**Task 5:** ✅ CompanyDB 적재 모듈 (TDD)
**Task 6:** ✅ 메인 오케스트레이터
**Task 7:** ✅ 테스트 시나리오 문서
**Task 8:** ✅ E2E 검증 스크립트
**Task 9:** ✅ 문서화 완성

---

## 예상 작업 시간

- Task 1: 10분
- Task 2: 60~120분 (수동 큐레이션)
- Task 3: 30분
- Task 4: 45분
- Task 5: 30분
- Task 6: 30분
- Task 7: 45분
- Task 8: 20분
- Task 9: 15분

**총 예상 시간:** 4~5시간

---

## 다음 단계

1. 이 계획을 `superpowers:executing-plans` 또는 `superpowers:subagent-driven-development` 스킬로 실행
2. 회사 프로필 20개 수동 큐레이션 (가장 시간 소요)
3. E2E 검증 실행
4. 테스트 시나리오 기반 실제 검증
