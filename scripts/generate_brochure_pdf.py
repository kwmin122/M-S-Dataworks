#!/usr/bin/env python3
"""Kira Bot 홍보용 PDF 브로셔 생성 스크립트.

NanumGothic 폰트 사용. 다른 환경에서는 폰트 경로 수정 필요.
실행: python scripts/generate_brochure_pdf.py
출력: docs/kirabot_brochure.pdf
"""
import os
import warnings
from fpdf import FPDF

warnings.filterwarnings("ignore", message=".*NOT subset.*")

# ── 경로 설정 ──
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_PATH = os.path.join(ROOT, "docs", "kirabot_brochure.pdf")

# NanumGothic from Office font cache
_NANUM_DIR = os.path.expanduser(
    "~/Library/Group Containers/UBF8T346G9.Office/FontCache/4/CloudFonts/NanumGothic"
)
FONT_REGULAR = os.path.join(_NANUM_DIR, "29463101760.ttf")
FONT_BOLD = os.path.join(_NANUM_DIR, "29131424179.ttf")
# NanumGothic has only Regular and Bold; reuse for Semi and Light
FONT_SEMI = FONT_BOLD
FONT_LIGHT = FONT_REGULAR

# ── 색상 ──
BLUE_900 = (0, 55, 100)      # #003764
BLUE_700 = (0, 82, 148)      # #005294
BLUE_500 = (0, 122, 204)     # #007ACC
BLUE_100 = (224, 240, 255)   # #E0F0FF
GRAY_900 = (26, 26, 26)      # #1A1A1A
GRAY_700 = (68, 68, 68)      # #444444
GRAY_500 = (128, 128, 128)   # #808080
GRAY_200 = (229, 229, 229)   # #E5E5E5
WHITE = (255, 255, 255)
ACCENT_GREEN = (0, 168, 107) # #00A86B
ACCENT_ORANGE = (255, 140, 0) # #FF8C00


class BrochurePDF(FPDF):
    def __init__(self):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.add_font("KR", "", FONT_REGULAR)
        self.add_font("KR", "B", FONT_BOLD)
        self.add_font("KRSemi", "", FONT_SEMI)
        self.add_font("KRLight", "", FONT_LIGHT)
        self.set_auto_page_break(auto=True, margin=20)
        self.page_num = 0

    def header(self):
        if self.page_no() <= 1:
            return
        self.set_font("KR", "", 7)
        self.set_text_color(*GRAY_500)
        self.cell(0, 6, "Kira Bot - AI 입찰 자동화 플랫폼", align="L")
        self.cell(0, 6, f"{self.page_no()}", align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*BLUE_700)
        self.set_line_width(0.3)
        self.line(10, 12, 200, 12)
        self.ln(3)

    def footer(self):
        self.set_y(-15)
        self.set_font("KRLight", "", 7)
        self.set_text_color(*GRAY_500)
        self.cell(0, 8, "MS Solutions  |  kira-bot.com  |  contact@ms-solutions.kr", align="C")

    # ── 유틸리티 ──
    def section_title(self, num, title, subtitle=""):
        self.set_font("KR", "B", 22)
        self.set_text_color(*BLUE_900)
        self.cell(0, 14, f"{num}. {title}", new_x="LMARGIN", new_y="NEXT")
        if subtitle:
            self.set_font("KRLight", "", 11)
            self.set_text_color(*GRAY_700)
            self.cell(0, 7, subtitle, new_x="LMARGIN", new_y="NEXT")
        self.ln(3)
        # 구분선
        self.set_draw_color(*BLUE_500)
        self.set_line_width(0.8)
        self.line(10, self.get_y(), 80, self.get_y())
        self.ln(6)

    def subsection(self, title):
        self.set_font("KRSemi", "", 13)
        self.set_text_color(*BLUE_700)
        self.cell(0, 9, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def body_text(self, text):
        self.set_font("KR", "", 10)
        self.set_text_color(*GRAY_700)
        self.multi_cell(0, 6, text)
        self.ln(2)

    def bullet(self, text, indent=15):
        x = self.get_x()
        self.set_font("KR", "", 10)
        self.set_text_color(*GRAY_700)
        self.set_x(x + indent)
        self.cell(4, 6, "\u2022")
        self.multi_cell(0, 6, text)
        self.ln(0.5)

    def feature_card(self, icon, title, desc):
        y_start = self.get_y()
        if y_start > 255:
            self.add_page()
            y_start = self.get_y()
        # 배경
        self.set_fill_color(*BLUE_100)
        self.rect(12, y_start, 186, 18, style="F")
        # 아이콘 + 제목
        self.set_xy(16, y_start + 2)
        self.set_font("KR", "B", 11)
        self.set_text_color(*BLUE_900)
        self.cell(0, 7, f"{icon}  {title}", new_x="LMARGIN", new_y="NEXT")
        # 설명
        self.set_x(16)
        self.set_font("KR", "", 9)
        self.set_text_color(*GRAY_700)
        self.cell(0, 6, desc, new_x="LMARGIN", new_y="NEXT")
        self.ln(4)

    def stat_box(self, x, y, w, value, label):
        self.set_fill_color(*BLUE_900)
        self.rect(x, y, w, 28, style="F")
        self.set_xy(x, y + 4)
        self.set_font("KR", "B", 20)
        self.set_text_color(*WHITE)
        self.cell(w, 10, value, align="C", new_x="LEFT", new_y="NEXT")
        self.set_x(x)
        self.set_font("KR", "", 8)
        self.cell(w, 6, label, align="C")

    def pricing_box(self, x, y, w, plan, price, features, highlight=False):
        h = 10 + len(features) * 6 + 8
        if highlight:
            self.set_fill_color(*BLUE_900)
            self.rect(x, y, w, h, style="F")
            title_color = WHITE
            text_color = (200, 220, 255)
        else:
            self.set_fill_color(*GRAY_200)
            self.rect(x, y, w, h, style="F")
            title_color = GRAY_900
            text_color = GRAY_700

        self.set_xy(x, y + 3)
        self.set_font("KR", "B", 12)
        self.set_text_color(*title_color)
        self.cell(w, 7, plan, align="C", new_x="LEFT", new_y="NEXT")
        self.set_x(x)
        self.set_font("KRSemi", "", 10)
        self.cell(w, 6, price, align="C", new_x="LEFT", new_y="NEXT")
        self.ln(2)
        for feat in features:
            self.set_x(x + 4)
            self.set_font("KR", "", 8)
            self.set_text_color(*text_color)
            self.cell(w - 8, 5.5, f"- {feat}", new_x="LEFT", new_y="NEXT")


def build_brochure():
    pdf = BrochurePDF()

    # ════════════════════════════════════════════
    # PAGE 1: 표지
    # ════════════════════════════════════════════
    pdf.add_page()
    # 배경 박스
    pdf.set_fill_color(*BLUE_900)
    pdf.rect(0, 0, 210, 297, style="F")

    # 중앙 타이틀
    pdf.set_y(80)
    pdf.set_font("KR", "B", 40)
    pdf.set_text_color(*WHITE)
    pdf.cell(0, 20, "Kira Bot", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("KRSemi", "", 16)
    pdf.set_text_color(180, 210, 255)
    pdf.cell(0, 10, "AI 공공조달 입찰 자동화 플랫폼", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)

    pdf.set_font("KR", "", 12)
    pdf.set_text_color(160, 195, 240)
    pdf.cell(0, 8, "공고 발견부터 제안서 제출까지, AI가 함께합니다", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(30)

    # 핵심 숫자
    pdf.stat_box(20, 175, 50, "495+", "AI 학습 지식 유닛")
    pdf.stat_box(80, 175, 50, "7단계", "자동화 워크플로우")
    pdf.stat_box(140, 175, 50, "6종", "문서 자동 생성")
    pdf.ln(5)

    # 하단 CI
    pdf.set_y(250)
    pdf.set_font("KR", "", 10)
    pdf.set_text_color(140, 175, 220)
    pdf.cell(0, 8, "MS Solutions", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, "2026", align="C")

    # ════════════════════════════════════════════
    # PAGE 2: 문제 인식 + 솔루션 개요
    # ════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("01", "왜 Kira Bot인가?", "공공조달 입찰의 비효율을 AI로 해결합니다")

    problems = [
        ("낭비되는 시간", "제안서 1건 작성에 평균 2~4주 소요. 반복적인 문서 작업이 전문 인력의 시간을 잠식합니다."),
        ("놓치는 기회", "매일 수백 건의 공고가 올라오지만, 적합한 공고를 찾아 분석하는 데만 하루가 걸립니다."),
        ("비일관적 품질", "담당자에 따라 제안서 품질이 들쭉날쭉. 회사의 핵심 강점이 제대로 전달되지 않습니다."),
        ("학습의 단절", "낙찰/탈락 경험이 조직 지식으로 축적되지 않아, 같은 실수를 반복합니다."),
    ]
    for title, desc in problems:
        pdf.set_font("KR", "B", 11)
        pdf.set_text_color(*BLUE_900)
        pdf.cell(0, 7, f"\u25B6 {title}", new_x="LMARGIN", new_y="NEXT")
        pdf.body_text(desc)

    pdf.ln(5)
    pdf.subsection("Kira Bot의 답")
    pdf.body_text(
        "Kira Bot은 공고 탐색부터 문서 생성, 검토, 학습까지 입찰 전 과정을 AI로 자동화합니다. "
        "495+ 전문 지식 유닛과 회사별 맞춤 학습 모델이 결합되어, "
        "처음부터 높은 품질의 입찰 문서를 빠르게 생성합니다."
    )

    # ════════════════════════════════════════════
    # PAGE 3: 3계층 학습 모델
    # ════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("02", "3계층 AI 학습 모델", "먼저 배우고, 회사를 알고, 그다음 생성합니다")

    layers = [
        ("Layer 1 | 전문가 지식 (495+ 유닛)",
         "공공조달 전문가 블로그, 유튜브 강의, 정부 공식 문서에서 추출한 495+개의 지식 유닛. "
         "제안서 작성 노하우, 평가 기준 해석법, 업종별 핵심 포인트를 AI가 이미 학습하고 있습니다.",
         ["블로그 47건 + 유튜브 40건 + 공식문서 18건 크롤링 및 구조화",
          "7개 카테고리 분류: 전략, 구조, 표현, 평가, 사례, 위험, 팁",
          "ChromaDB 벡터 DB에 영구 저장, 의미 기반 검색"]),
        ("Layer 2 | 회사 맞춤 학습",
         "귀사의 실적, 인력, 강점, 과거 제안서에서 문체와 구조를 학습합니다. "
         "생성된 문서를 수정할 때마다 AI가 패턴을 기억하고, 다음 생성 시 자동 반영합니다.",
         ["회사 실적/인력/자격 DB 자동 구축 (CompanyDB)",
          "과거 제안서 문체 분석 (company_analyzer)",
          "편집 Diff 자동 추적 → 3회 이상 반복 패턴 자동 학습 (auto_learner)",
          "서버 재시작 시에도 학습 상태 영속 유지"]),
        ("Layer 3 | 승패 분석 (예정)",
         "낙찰/탈락 이력을 분석하여, 어떤 표현과 구조가 높은 점수를 받는지 학습합니다. "
         "향후 입찰 전략 수립의 핵심 엔진이 됩니다.",
         ["낙찰/탈락 사례 DB 구축",
          "평가 항목별 점수 상관관계 분석",
          "승률 예측 모델 개발"]),
    ]
    for title, desc, details in layers:
        pdf.subsection(title)
        pdf.body_text(desc)
        for d in details:
            pdf.bullet(d)
        pdf.ln(3)

    # ════════════════════════════════════════════
    # PAGE 4: Chat Hub
    # ════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("03", "Chat Hub - 대화형 탐색", "AI와의 대화로 공고를 찾고, 분석하고, 질문하세요")

    chat_features = [
        ("[검색]", "나라장터 공고 실시간 검색", "키워드, 업무구분(용역/물품/공사/외자), 지역, 금액 범위, 기간 필터로 정확한 공고를 찾습니다."),
        ("[분석]", "RFP 자동 분석", "PDF/DOCX/HWP/HWPX/Excel/PPT 등 다양한 형식의 RFP를 업로드하면, AI가 자격요건/평가기준/특이사항을 자동 추출합니다."),
        ("[판단]", "GO/NO-GO 자동 판단", "회사 역량과 공고 요건을 비교하여 입찰 참여 여부를 AI가 판단합니다. 항목별 충족도와 근거를 제시합니다."),
        ("[요약]", "RFP 요약 리포트", "사업개요, 핵심요건, 평가기준을 3섹션 마크다운으로 구조화하여 한눈에 파악할 수 있습니다."),
        ("[첨부]", "첨부파일 자동 다운로드", "나라장터 e발주 첨부파일을 자동으로 다운로드하여 즉시 분석에 활용합니다."),
        ("[Q&A]", "문서 기반 Q&A", "업로드된 문서에 대해 자유롭게 질문하세요. RAG 하이브리드 검색으로 정확한 답변과 참조 페이지를 제공합니다."),
        ("[일괄]", "일괄 공고 평가", "최대 50개 공고를 동시에 GO/NO-GO 평가합니다. 병렬 처리로 빠르게 결과를 확인하세요."),
        ("[저장]", "검색 결과 CSV 다운로드", "검색한 공고 목록을 CSV 파일로 저장하여 팀과 공유할 수 있습니다."),
    ]
    for icon, title, desc in chat_features:
        pdf.feature_card(icon, title, desc)

    # ════════════════════════════════════════════
    # PAGE 5: Bid Studio 7단계
    # ════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("04", "Bid Studio - 7단계 입찰 워크플로우", "체계적인 단계를 따라 완성도 높은 입찰 서류를 생성합니다")

    stages = [
        ("Stage 1: RFP 분석", "공고 문서를 업로드하거나 텍스트를 입력하면, AI가 자격요건, 평가 항목, 제출 서류, 특이사항을 자동으로 추출합니다. Chat에서 분석한 내용을 Studio로 바로 가져올 수 있습니다."),
        ("Stage 2: 패키지 분류", "AI 패키지 분류기가 필요한 서류를 자동 판별합니다. 생성 문서(제안서, PPT, WBS), 증빙 문서, 행정 문서, 가격 문서로 분류하고, 수의계약/견적 자동 감지, 발표 평가 여부 판단까지 수행합니다."),
        ("Stage 3: 회사 정보 연결", "회사 DB에서 관련 실적, 투입 인력, 자격증, 강점을 자동으로 매칭합니다. 프로젝트별로 회사 자산을 추가/제거하고, 검증 후 공유 DB로 승격할 수 있습니다."),
        ("Stage 4: 스타일 설정", "회사의 제안서 문체, 표현 방식, 구조적 특성을 학습하고 적용합니다. 스타일 기술서를 고정(pin)하여 모든 생성에 일관되게 적용하거나, 프로젝트별로 파생(derive)할 수 있습니다."),
        ("Stage 5: 문서 생성", "4종 문서를 AI가 자동 생성합니다. Layer 1 전문 지식 + Layer 2 회사 맞춤 학습이 결합되어, 처음부터 높은 품질의 문서가 나옵니다."),
        ("Stage 6: 검토/편집", "생성된 문서를 섹션별로 검토하고 편집합니다. 원본과 수정본의 Diff를 시각적으로 비교하고, 편집된 내용으로 DOCX를 재조립할 수 있습니다."),
        ("Stage 7: 학습 반영", "편집한 내용이 다음 생성에 자동으로 반영됩니다. 스타일 파생 → 고정 → 재생성 루프를 통해, 사용할수록 더 정확해지는 AI를 경험하세요."),
    ]
    for title, desc in stages:
        if pdf.get_y() > 250:
            pdf.add_page()
        pdf.set_font("KR", "B", 11)
        pdf.set_text_color(*BLUE_900)
        pdf.cell(0, 7, title, new_x="LMARGIN", new_y="NEXT")
        pdf.body_text(desc)

    # ════════════════════════════════════════════
    # PAGE 6: 4종 문서 생성
    # ════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("05", "4종 문서 자동 생성", "입찰에 필요한 모든 핵심 문서를 AI가 작성합니다")

    docs = [
        ("제안서 (Proposal DOCX)",
         ["RFP 분석 → 섹션 아웃라인 자동 설계 (배점 비례 페이지 배분)",
          "Layer 1(전문 지식) + Layer 2(회사 맞춤) 결합 섹션 작성",
          "품질 검사: 블라인드 위반 감지(한글 조사 인식), 모호 표현 경고",
          "마크다운 → DOCX 자동 변환 (mistune 3.x AST 기반)",
          "섹션별 편집 → DOCX 재조립 → Diff 학습"]),
        ("수행계획서/WBS (XLSX + 간트차트 + DOCX)",
         ["방법론 자동 감지 + LLM WBS 태스크 생성",
          "3시트 Excel: 개요, WBS 테이블, 일정표",
          "간트차트 PNG 시각화 (matplotlib)",
          "수행계획서 DOCX 자동 생성"]),
        ("발표자료 (PPTX)",
         ["KRDS 공공기관 PPT 디자인 가이드 자동 적용",
          "6종 슬라이드: 표지, 목차, 콘텐츠, 데이터, 마무리, 간지",
          "예상 질문 & 답변 10개 자동 생성",
          "16:9 레이아웃, Pretendard 폰트, Blue 900 주색"]),
        ("실적/경력 기술서 (DOCX)",
         ["RFP 요구사항 ↔ 과거 실적 자동 매칭",
          "투입 인력 자동 배치 (경력, 자격증 기반)",
          "실적 기술서 DOCX 자동 생성 (표 + 서술)"]),
    ]
    for title, details in docs:
        pdf.subsection(title)
        for d in details:
            pdf.bullet(d)
        pdf.ln(3)

    # ════════════════════════════════════════════
    # PAGE 7: AI 분석 엔진
    # ════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("06", "AI 분석 엔진", "깊이 있는 분석으로 입찰 의사결정을 지원합니다")

    analysis_features = [
        ("멀티패스 자격요건 추출",
         "RFP 문서를 여러 번 분석(멀티패스)하여 필수/권장 자격, 정량 제약(금액, 건수, 인원, 기간), "
         "평가기준, 필수 서류를 빠짐없이 추출합니다. 17개 카테고리 동의어 사전을 활용하여 정확도를 높입니다."),
        ("GO/NO-GO 자동 판단",
         "결정론적 규칙 우선 비교(ConstraintEvaluator)로 수치 기반 판단을 먼저 수행하고, "
         "복잡한 항목은 LLM이 보완 판단합니다. 항목별 충족도와 근거 텍스트를 제시합니다."),
        ("패키지 자동 분류",
         "키워드 스코어링 + 하드가드(수의계약 감지, 발표평가 증거 게이트)로 필요 서류를 정확히 분류합니다. "
         "18건 회귀 테스트 코퍼스로 분류 품질을 보장합니다. 신뢰도 < 65% 시 수동 검토를 권장합니다."),
        ("하이브리드 검색 엔진",
         "BM25 키워드 검색 + ChromaDB 벡터 검색을 RRF(Reciprocal Rank Fusion)로 결합합니다. "
         "키워드 매칭과 의미 유사도를 동시에 활용하여 가장 관련성 높은 정보를 찾습니다."),
        ("품질 자동 검증",
         "블라인드 위반 감지(한글 조사 인식 정규식), 모호 표현 경고, 섹션 간 문체 일관성 검사를 자동 수행합니다. "
         "생성된 문서의 품질을 인간 검토 전에 사전 검증합니다."),
    ]
    for title, desc in analysis_features:
        if pdf.get_y() > 250:
            pdf.add_page()
        pdf.subsection(title)
        pdf.body_text(desc)

    # ════════════════════════════════════════════
    # PAGE 8: 회사 정보 관리
    # ════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("07", "회사 정보 관리", "체계적인 회사 DB로 모든 문서 생성의 기반을 만듭니다")

    company_features = [
        ("[프로필]", "회사 프로필 관리", "회사명, 설립일, 주요 사업 분야, 강점을 WYSIWYG 마크다운으로 편집. 버전 히스토리와 롤백 지원."),
        ("[실적]", "실적 DB", "프로젝트명, 발주처, 수행 기간, 금액, 기술 스택, 주요 성과를 구조화하여 저장. AI가 입찰 매칭 시 자동 활용."),
        ("[인력]", "인력 DB", "이름, 직급, 경력(년), 자격증, 전문 분야를 등록. 실적기술서 생성 시 최적의 인력을 자동 배치."),
        ("[업로드]", "문서 일괄 업로드", "회사소개서, 실적 증빙, 자격 서류를 드래그앤드롭으로 업로드. AI가 자동 파싱하여 DB에 반영."),
        ("[연결]", "프로젝트-회사 자산 연결", "프로젝트별로 관련 실적/인력을 선별 연결. 검증 후 공유 DB로 승격하여 조직 전체가 활용."),
        ("[학습]", "문체 학습", "과거 제안서에서 회사 고유의 문체, 구조, 표현 패턴을 자동 학습. 일관된 브랜드 보이스를 유지합니다."),
    ]
    for icon, title, desc in company_features:
        pdf.feature_card(icon, title, desc)

    # ════════════════════════════════════════════
    # PAGE 9: 보안 & 인프라
    # ════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("08", "보안 & 인프라", "엔터프라이즈급 보안과 안정성을 제공합니다")

    security_items = [
        ("인증 & 접근 제어", [
            "Google/카카오 OAuth 소셜 로그인",
            "프로젝트별 5단계 ACL (viewer, reviewer, approver, editor, owner)",
            "조직별 멀티테넌트 데이터 격리",
            "자동 조직 프로비저닝 (첫 로그인 시 자동 생성)",
        ]),
        ("데이터 보호", [
            "SSRF 방어: HTTPS 전용, DNS 사전 해석, 사설 IP 차단",
            "CSRF 방어: Origin allowlist 검증",
            "HMAC 웹훅 서명: 타임스탬프 + Nonce + 본문 서명",
            "파일 업로드: 확장자 화이트리스트(14종) + 50MB 제한 + 경로 순회 방어",
        ]),
        ("운영 안정성", [
            "Rate Limiting: IP당 60요청/분 전역 제한",
            "LLM 안정성: 60초 타임아웃 + 2회 재시도 (지수 백오프)",
            "감사 로그: 모든 주요 액션(생성/수정/삭제/접근) 기록",
            "Docker 컨테이너화 + Railway 클라우드 자동 배포",
        ]),
    ]
    for title, items in security_items:
        pdf.subsection(title)
        for item in items:
            pdf.bullet(item)
        pdf.ln(3)

    # ════════════════════════════════════════════
    # PAGE 10: 알림 시스템 + 대시보드
    # ════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("09", "알림 & 대시보드", "놓치는 공고 없이, 한눈에 현황을 파악하세요")

    pdf.subsection("맞춤 공고 알림")
    alert_features = [
        "키워드, 업무구분, 지역, 발주품목, 금액 범위 기반 필터 설정",
        "제외 키워드/지역 필터로 불필요한 알림 제거",
        "이메일 알림: 실시간/일일/정시 스케줄 선택",
        "알림 미리보기: 설정 적용 전 매칭 공고 사전 확인",
        "조용한 시간 설정: 야간/주말 알림 음소거",
    ]
    for f in alert_features:
        pdf.bullet(f)
    pdf.ln(3)

    pdf.subsection("사용 현황 대시보드")
    dashboard_features = [
        "월별 분석/생성/다운로드 횟수 추적",
        "Smart Fit Score: 회사-공고 적합도 점수",
        "인기 기관 TOP 10: 자주 발주하는 기관 추세",
        "기관별 발주 예측: 월별 발주량, 평균 규모, 주요 분야 그래프",
    ]
    for f in dashboard_features:
        pdf.bullet(f)
    pdf.ln(3)

    pdf.subsection("지원 문서 포맷")
    format_features = [
        "입력: PDF, DOCX, HWP, HWPX, TXT, CSV, XLSX, PPT",
        "출력: DOCX(제안서/실적기술서), PPTX(발표자료), XLSX(WBS), PNG(간트차트), JSON(체크리스트), CSV(검색결과)",
    ]
    for f in format_features:
        pdf.bullet(f)

    # ════════════════════════════════════════════
    # PAGE 11: 요금제
    # ════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("10", "요금제", "규모와 필요에 맞는 플랜을 선택하세요")

    y = pdf.get_y() + 5
    pdf.pricing_box(12, y, 58, "FREE", "무료",
                    ["월 5건 공고 분석", "나라장터 공고 검색", "자격요건 추출", "RFP 요약 리포트", "일 20회 채팅"])
    pdf.pricing_box(76, y, 58, "PRO", "99,000원/월",
                    ["무제한 공고 분석", "GO/NO-GO 자동 판단", "제안서 DOCX 생성", "PPT 발표자료 생성",
                     "WBS/수행계획서", "실적기술서 생성", "맞춤 공고 알림", "무제한 채팅", "편집 학습 반영"],
                    highlight=True)
    pdf.pricing_box(140, y, 58, "ENTERPRISE", "별도 협의",
                    ["PRO 전체 기능", "전담 학습 모델", "온프레미스 배포", "SLA 보장", "전담 지원", "커스텀 연동"])

    pdf.set_y(y + 95)
    pdf.ln(10)
    pdf.subsection("기술 사양")
    specs = [
        "AI 엔진: GPT-4 (OpenAI) + ChromaDB 벡터 검색",
        "백엔드: Python FastAPI (비동기) + PostgreSQL + SQLAlchemy",
        "프론트엔드: React 19 + TypeScript + Vite + Tailwind CSS",
        "배포: Docker + Railway 클라우드 (자동 CI/CD)",
        "테스트: 500+ 자동화 테스트 (Python pytest + Jest)",
        "보안: HMAC, CSRF, SSRF, ACL, Rate Limiting, 감사 로그",
    ]
    for s in specs:
        pdf.bullet(s)

    # ════════════════════════════════════════════
    # PAGE 12: 마무리
    # ════════════════════════════════════════════
    pdf.add_page()
    # 배경
    pdf.set_fill_color(*BLUE_900)
    pdf.rect(0, 0, 210, 297, style="F")

    pdf.set_y(80)
    pdf.set_font("KR", "B", 28)
    pdf.set_text_color(*WHITE)
    pdf.cell(0, 16, "입찰의 미래,", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 16, "Kira Bot과 함께 시작하세요", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(15)
    pdf.set_font("KR", "", 13)
    pdf.set_text_color(180, 210, 255)
    pdf.cell(0, 9, "공고 발견 | RFP 분석 | GO/NO-GO 판단 | 문서 자동 생성", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 9, "검토/편집 | AI 학습 | 체크리스트 | 알림", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(30)
    pdf.set_font("KRSemi", "", 14)
    pdf.set_text_color(*WHITE)
    pdf.cell(0, 10, "MS Solutions", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    pdf.set_font("KR", "", 11)
    pdf.set_text_color(160, 195, 240)
    pdf.cell(0, 8, "contact@ms-solutions.kr", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, "kira-bot.com", align="C", new_x="LMARGIN", new_y="NEXT")

    # ── 출력 ──
    pdf.output(OUTPUT_PATH)
    print(f"PDF 브로셔 생성 완료: {OUTPUT_PATH}")
    print(f"총 {pdf.page_no()}페이지")


if __name__ == "__main__":
    build_brochure()
