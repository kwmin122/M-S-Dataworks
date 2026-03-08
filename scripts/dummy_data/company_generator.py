"""
Company Profile PDF Generator using reportlab
넥스트웨이브 스타일 10페이지 회사소개서 생성
"""
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
from datetime import datetime


# 한글 폰트 등록 (시스템 폰트 경로)
def register_korean_font():
    """한글 폰트 등록 (macOS AppleGothic 시도, 실패시 Helvetica fallback)"""
    try:
        font_path = "/System/Library/Fonts/Supplemental/AppleGothic.ttf"
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont('KoreanFont', font_path))
            return 'KoreanFont'
    except Exception:
        pass

    # Fallback to Helvetica (한글 표시 안 되지만 에러 방지)
    return 'Helvetica'


def draw_page_header(c, page_num, total_pages=10):
    """페이지 헤더 그리기"""
    c.setFont('Helvetica', 8)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawRightString(560, 800, f"Page {page_num}/{total_pages}")


def draw_page_footer(c, company_name):
    """페이지 푸터 그리기"""
    c.setFont('Helvetica', 8)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawCentredString(297.5, 30, f"© {datetime.now().year} {company_name}. All rights reserved.")


def page1_cover(c, company_data, korean_font):
    """표지 (1페이지)"""
    # 배경색 (진한 파란색)
    c.setFillColorRGB(0, 0.2, 0.4)
    c.rect(0, 0, 595.27, 841.89, fill=1)

    # 제목
    c.setFillColorRGB(1, 1, 1)
    c.setFont(korean_font, 36)
    c.drawCentredString(297.5, 600, "회사소개서")

    c.setFont(korean_font, 28)
    c.drawCentredString(297.5, 500, company_data.get('company_name', 'Company Name'))

    # 연도
    c.setFont('Helvetica', 16)
    c.drawCentredString(297.5, 200, str(datetime.now().year))

    c.showPage()


def page2_overview(c, company_data, korean_font):
    """회사 개요 (2페이지)"""
    draw_page_header(c, 2)

    # 제목
    c.setFont(korean_font, 24)
    c.setFillColorRGB(0, 0.2, 0.4)
    c.drawString(50, 750, "회사 개요")

    # 내용
    c.setFont(korean_font, 12)
    c.setFillColorRGB(0, 0, 0)

    y = 680
    content = [
        ("회사명", company_data.get('company_name', 'N/A')),
        ("설립연도", str(company_data.get('establishment_year', 'N/A'))),
        ("대표이사", company_data.get('representative', 'N/A')),
        ("임직원 수", f"{company_data.get('employee_count', 'N/A')}명"),
        ("주소", company_data.get('address', 'N/A')),
        ("웹사이트", company_data.get('website', 'N/A')),
    ]

    for label, value in content:
        c.setFont(korean_font, 12)
        c.drawString(80, y, f"{label}:")
        c.setFont('Helvetica', 11)
        c.drawString(200, y, str(value))
        y -= 30

    # 사업 분야
    c.setFont(korean_font, 14)
    c.drawString(50, y - 30, "주요 사업 분야")

    y -= 60
    areas = company_data.get('business_areas', [])
    for i, area in enumerate(areas[:5], 1):
        c.setFont(korean_font, 11)
        c.drawString(80, y, f"{i}. {area}")
        y -= 25

    draw_page_footer(c, company_data.get('company_name', ''))
    c.showPage()


def page3_history(c, company_data, korean_font):
    """연혁 (3페이지)"""
    draw_page_header(c, 3)

    c.setFont(korean_font, 24)
    c.setFillColorRGB(0, 0.2, 0.4)
    c.drawString(50, 750, "연혁")

    c.setFont(korean_font, 12)
    c.setFillColorRGB(0, 0, 0)

    # 더미 연혁 생성
    est_year = company_data.get('establishment_year', 2020)
    current_year = datetime.now().year

    y = 680
    milestones = [
        (est_year, "회사 설립"),
        (est_year + 1, "첫 정부 프로젝트 수주"),
        (est_year + 2, "임직원 50명 돌파"),
        (est_year + 3, "기술 인증 획득"),
        (est_year + 4, "누적 매출 100억 달성"),
    ]

    for year, event in milestones:
        if year <= current_year:
            c.setFont('Helvetica-Bold', 11)
            c.drawString(80, y, str(year))
            c.setFont(korean_font, 11)
            c.drawString(150, y, event)
            y -= 30

    draw_page_footer(c, company_data.get('company_name', ''))
    c.showPage()


def page4_organization(c, company_data, korean_font):
    """조직 및 인력 현황 (4페이지)"""
    draw_page_header(c, 4)

    c.setFont(korean_font, 24)
    c.setFillColorRGB(0, 0.2, 0.4)
    c.drawString(50, 750, "조직 및 인력 현황")

    # 조직 구조 (간단히 텍스트로 표현)
    c.setFont(korean_font, 14)
    c.setFillColorRGB(0, 0, 0)
    c.drawString(50, 680, "조직 구조")

    y = 640
    departments = ["경영지원팀", "기술개발팀", "사업개발팀", "품질관리팀"]
    for dept in departments:
        c.setFont(korean_font, 11)
        c.drawString(80, y, f"• {dept}")
        y -= 25

    # 인력 현황
    c.setFont(korean_font, 14)
    c.drawString(50, y - 30, "인력 현황")

    y -= 60
    total_emp = company_data.get('employee_count', 100)
    roles = [
        ("관리직", int(total_emp * 0.2)),
        ("기술직", int(total_emp * 0.5)),
        ("영업직", int(total_emp * 0.2)),
        ("기타", int(total_emp * 0.1)),
    ]

    for role, count in roles:
        c.setFont(korean_font, 11)
        c.drawString(80, y, f"{role}: {count}명")
        y -= 25

    draw_page_footer(c, company_data.get('company_name', ''))
    c.showPage()


def page5_projects_1(c, projects, korean_font):
    """주요 실적 (5페이지 - 1/3)"""
    draw_page_header(c, 5)

    c.setFont(korean_font, 24)
    c.setFillColorRGB(0, 0.2, 0.4)
    c.drawString(50, 750, "주요 프로젝트 실적")

    c.setFont(korean_font, 12)
    c.setFillColorRGB(0, 0, 0)

    y = 680
    for i, proj in enumerate(projects[:3], 1):
        c.setFont(korean_font, 13)
        c.drawString(50, y, f"{i}. {proj['name']}")
        y -= 25

        c.setFont(korean_font, 10)
        c.drawString(70, y, f"발주처: {proj['client']}")
        y -= 20
        c.drawString(70, y, f"기간: {proj['period']}")
        y -= 20
        c.drawString(70, y, f"금액: {proj['amount']:,}원")
        y -= 20
        c.drawString(70, y, f"역할: {proj['role']}")
        y -= 40

    draw_page_footer(c, "")
    c.showPage()


def page6_projects_2(c, projects, korean_font):
    """주요 실적 (6페이지 - 2/3)"""
    draw_page_header(c, 6)

    c.setFont(korean_font, 24)
    c.setFillColorRGB(0, 0.2, 0.4)
    c.drawString(50, 750, "주요 프로젝트 실적 (계속)")

    c.setFont(korean_font, 12)
    c.setFillColorRGB(0, 0, 0)

    y = 680
    for i, proj in enumerate(projects[3:6], 4):
        c.setFont(korean_font, 13)
        c.drawString(50, y, f"{i}. {proj['name']}")
        y -= 25

        c.setFont(korean_font, 10)
        c.drawString(70, y, f"발주처: {proj['client']}")
        y -= 20
        c.drawString(70, y, f"기간: {proj['period']}")
        y -= 20
        c.drawString(70, y, f"금액: {proj['amount']:,}원")
        y -= 20
        c.drawString(70, y, f"역할: {proj['role']}")
        y -= 40

    draw_page_footer(c, "")
    c.showPage()


def page7_projects_3(c, projects, korean_font):
    """주요 실적 (7페이지 - 3/3)"""
    draw_page_header(c, 7)

    c.setFont(korean_font, 24)
    c.setFillColorRGB(0, 0.2, 0.4)
    c.drawString(50, 750, "주요 프로젝트 실적 (계속)")

    c.setFont(korean_font, 12)
    c.setFillColorRGB(0, 0, 0)

    y = 680
    for i, proj in enumerate(projects[6:9], 7):
        c.setFont(korean_font, 13)
        c.drawString(50, y, f"{i}. {proj['name']}")
        y -= 25

        c.setFont(korean_font, 10)
        c.drawString(70, y, f"발주처: {proj['client']}")
        y -= 20
        c.drawString(70, y, f"기간: {proj['period']}")
        y -= 20
        c.drawString(70, y, f"금액: {proj['amount']:,}원")
        y -= 20
        c.drawString(70, y, f"역할: {proj['role']}")
        y -= 40

    draw_page_footer(c, "")
    c.showPage()


def page8_tech_capabilities(c, company_data, korean_font):
    """기술 역량 (8페이지)"""
    draw_page_header(c, 8)

    c.setFont(korean_font, 24)
    c.setFillColorRGB(0, 0.2, 0.4)
    c.drawString(50, 750, "기술 역량")

    c.setFont(korean_font, 12)
    c.setFillColorRGB(0, 0, 0)

    y = 680
    capabilities = [
        "AI/머신러닝 기반 솔루션 개발",
        "클라우드 인프라 설계 및 운영",
        "빅데이터 분석 플랫폼 구축",
        "사이버 보안 컨설팅",
        "레거시 시스템 현대화",
        "DevOps/CI/CD 자동화",
    ]

    for cap in capabilities:
        c.setFont(korean_font, 11)
        c.drawString(70, y, f"• {cap}")
        y -= 30

    # 보유 인증
    c.setFont(korean_font, 14)
    c.drawString(50, y - 30, "보유 인증")

    y -= 60
    certs = ["ISO 9001", "ISO 27001", "CMMI Level 3", "GS 인증"]
    for cert in certs:
        c.setFont(korean_font, 11)
        c.drawString(70, y, f"• {cert}")
        y -= 25

    draw_page_footer(c, company_data.get('company_name', ''))
    c.showPage()


def page9_clients(c, company_data, korean_font):
    """주요 고객사 (9페이지)"""
    draw_page_header(c, 9)

    c.setFont(korean_font, 24)
    c.setFillColorRGB(0, 0.2, 0.4)
    c.drawString(50, 750, "주요 고객사")

    c.setFont(korean_font, 12)
    c.setFillColorRGB(0, 0, 0)

    y = 680
    clients = [
        "행정안전부",
        "국토교통부",
        "과학기술정보통신부",
        "서울특별시",
        "경기도청",
        "한국전력공사",
        "국민건강보험공단",
        "한국철도공사",
    ]

    for i, client in enumerate(clients, 1):
        c.setFont(korean_font, 11)
        c.drawString(70, y, f"{i}. {client}")
        y -= 30

    draw_page_footer(c, company_data.get('company_name', ''))
    c.showPage()


def page10_vision(c, company_data, korean_font):
    """비전 및 마무리 (10페이지)"""
    draw_page_header(c, 10)

    c.setFont(korean_font, 24)
    c.setFillColorRGB(0, 0.2, 0.4)
    c.drawString(50, 750, "비전")

    c.setFont(korean_font, 12)
    c.setFillColorRGB(0, 0, 0)

    y = 680
    vision_text = [
        "우리는 최첨단 기술로 공공 서비스의 디지털 전환을 선도합니다.",
        "",
        "고객과 함께 성장하며, 사회적 가치를 창출하는 기업이 되겠습니다.",
        "",
        "지속 가능한 혁신을 통해 국가 경쟁력 향상에 기여하겠습니다.",
    ]

    for line in vision_text:
        if line:
            c.setFont(korean_font, 11)
            c.drawString(70, y, line)
        y -= 30

    # 연락처
    c.setFont(korean_font, 14)
    c.drawString(50, 200, "Contact")

    c.setFont('Helvetica', 10)
    c.drawString(70, 170, f"Address: {company_data.get('address', 'N/A')}")
    c.drawString(70, 150, f"Website: {company_data.get('website', 'N/A')}")
    c.drawString(70, 130, f"Email: contact@{company_data.get('company_name', 'company')}.com")

    draw_page_footer(c, company_data.get('company_name', ''))
    c.showPage()


def generate_company_profile_pdf(company_data, projects, output_path):
    """
    10페이지 회사소개서 PDF 생성

    Args:
        company_data: 회사 정보 dict
        projects: 프로젝트 실적 list
        output_path: 출력 파일 경로
    """
    # Canvas 생성
    c = canvas.Canvas(output_path, pagesize=A4)

    # 한글 폰트 등록
    korean_font = register_korean_font()

    # 10 pages
    page1_cover(c, company_data, korean_font)
    page2_overview(c, company_data, korean_font)
    page3_history(c, company_data, korean_font)
    page4_organization(c, company_data, korean_font)
    page5_projects_1(c, projects, korean_font)
    page6_projects_2(c, projects, korean_font)
    page7_projects_3(c, projects, korean_font)
    page8_tech_capabilities(c, company_data, korean_font)
    page9_clients(c, company_data, korean_font)
    page10_vision(c, company_data, korean_font)

    # 저장
    c.save()
