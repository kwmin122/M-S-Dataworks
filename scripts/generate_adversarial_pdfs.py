"""
Generate adversarial PDF fixtures for RFx E2E validation.

Outputs (language-specific):
- company_adversarial_ko.pdf / rfx_adversarial_ko.pdf
- company_adversarial_en.pdf / rfx_adversarial_en.pdf
"""

from __future__ import annotations

import argparse
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _register_font_for_lang(lang: str) -> str:
    """Register a font suitable for the requested language."""

    if lang == "en":
        return "Helvetica"

    # CID fonts are more stable for Korean text extraction with PyMuPDF/pdfplumber.
    for cid_name in ["HYGothic-Medium", "HYSMyeongJo-Medium"]:
        try:
            if cid_name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(UnicodeCIDFont(cid_name))
            return cid_name
        except Exception:
            continue

    raise RuntimeError("Korean CID font registration failed.")


def _styles(font_name: str) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "TitleAdv",
            parent=base["Heading1"],
            fontName=font_name,
            fontSize=15,
            leading=20,
            spaceAfter=10,
        ),
        "h2": ParagraphStyle(
            "Heading2Adv",
            parent=base["Heading2"],
            fontName=font_name,
            fontSize=12,
            leading=16,
            spaceBefore=8,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "BodyAdv",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=10,
            leading=14,
        ),
        "small": ParagraphStyle(
            "SmallAdv",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=9,
            leading=12,
            textColor=colors.darkslategray,
        ),
    }


def _table_style(font_name: str) -> TableStyle:
    return TableStyle(
        [
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f2f6fa")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ]
    )


def _company_content(lang: str) -> dict:
    if lang == "ko":
        return {
            "title": "회사소개서(적대적 테스트용) - 아크라인정보기술(주)",
            "purpose": "목적: 경계값/인증 혼동/요건 조합 오판정을 검증하기 위한 테스트 문서",
            "h1": "1) 인증 및 자격 현황",
            "cert_rows": [
                ["구분", "보유 현황", "비고"],
                ["ISO 9001", "2019년 취득, 2022년 갱신 만료", "유효기간 경과"],
                ["ISO 27001", "미보유", "-"],
                ["ISMS", "보유 (ISMS-2024-117)", "ISMS-P 아님"],
                ["ISMS-P", "미보유", "개인정보 범위 미포함"],
                ["정보시스템감리사", "1명", "내부 문서에는 감리원급으로 병기"],
            ],
            "h2": "2) 기술인력 현황",
            "staff_rows": [
                ["자격", "인원", "비고"],
                ["정보처리기사", "9명", "요건 10명 이상 대비 1명 부족"],
                ["정보통신기사", "3명", "-"],
                ["CCNA", "2명", "-"],
            ],
            "h3": "3) 공공 SI 실적",
            "perf_rows": [
                ["사업명", "총 사업비", "수행 형태", "당사 인정 금액", "비고"],
                ["A시 스마트교통 통합플랫폼", "25억원", "단독", "25억원", "요건 충족 가능"],
                ["B군 통합민원 정보화", "18억원", "단독", "18억원", "20억 기준 미달"],
                ["C구 CCTV 고도화", "20억원", "컨소시엄", "8억원", "분담금만 인정 시 미달"],
            ],
            "h4": "4) 신용",
            "credit": "- 기업신용등급: BBB0 (경계값 테스트)",
            "credit_note": "- 일부 발주기관은 BBB 계열로 인정, 일부는 엄격 기준 적용",
            "h5": "5) 모호한 서술",
            "ambiguous": [
                "- 당사는 핵심 자격요건을 대체로 충족하는 편입니다.",
                "- 정보보호 체계는 ISMS 기반이며 필요 시 ISMS-P 전환을 추진합니다.",
                "- 감리 역량은 감리원급 인력을 포함해 안정적으로 확보되어 있습니다.",
            ],
        }

    return {
        "title": "Company Profile (Adversarial Test Set) - ArcLine IT",
        "purpose": "Purpose: validate boundary handling, certification confusion, and requirement logic failures.",
        "h1": "1) Certifications and Qualifications",
        "cert_rows": [
            ["Category", "Status", "Note"],
            ["ISO 9001", "Acquired 2019, renewal expired in 2022", "No longer valid"],
            ["ISO 27001", "Not held", "-"],
            ["ISMS", "Held (ISMS-2024-117)", "Not ISMS-P"],
            ["ISMS-P", "Not held", "PII scope missing"],
            ["Information Systems Auditor", "1 person", "Sometimes described as auditor-level"],
        ],
        "h2": "2) Technical Workforce",
        "staff_rows": [
            ["Qualification", "Headcount", "Note"],
            ["Engineer (Information Processing)", "9", "Requirement often asks >= 10"],
            ["Network Engineer", "3", "-"],
            ["CCNA", "2", "-"],
        ],
        "h3": "3) Public SI Project History",
        "perf_rows": [
            ["Project", "Total Budget", "Execution Type", "Recognized Amount", "Note"],
            ["City A smart transport platform", "2.5B KRW", "Prime", "2.5B KRW", "Qualifies"],
            ["County B civil service system", "1.8B KRW", "Prime", "1.8B KRW", "Below 2.0B threshold"],
            ["District C CCTV modernization", "2.0B KRW", "Consortium", "0.8B KRW", "Only share should count"],
        ],
        "h4": "4) Credit",
        "credit": "- Corporate credit rating: BBB0 (boundary case)",
        "credit_note": "- Some agencies treat BBB0 as BBB family; others apply stricter mapping.",
        "h5": "5) Ambiguous Narrative",
        "ambiguous": [
            "- We generally satisfy key qualification requirements.",
            "- Security operations are based on ISMS and can be extended to ISMS-P if needed.",
            "- Audit capability is stable with auditor-level personnel.",
        ],
    }


def _rfx_content(lang: str) -> dict:
    if lang == "ko":
        return {
            "title": "제안요청서(RFx) - 방범 CCTV 자가통신망 광다중화장비 교체",
            "contract": "사업기간: 계약일로부터 8개월",
            "h1": "1) 입찰참가 자격요건 (표-1, 1페이지)",
            "req1": [
                ["ID", "요건", "레벨"],
                ["A-1", "ISO 9001 유효 인증 보유", "필수"],
                ["A-2", "(ISO 27001 또는 ISMS-P) 그리고 ISO 9001", "필수"],
                ["A-3", "정보처리기사 10명 이상 상시 보유", "필수"],
                ["A-4", "최근 3년 내 공공 SI 단일사업 20억원 이상 2건", "필수"],
            ],
            "footnote": "* 각주: 벤처기업 확인서 보유 시 A-4는 20억원 이상 1건으로 갈음 가능",
            "h2": "2) 입찰참가 자격요건 (표-1 계속, 2페이지)",
            "req2": [
                ["ID", "요건", "레벨"],
                ["A-5", "컨소시엄 실적은 참여지분(분담금)만 인정", "필수"],
                ["A-6", "기업신용등급 BBB 이상", "필수"],
                ["A-7", "감리원 또는 감리사 보유 시 가점 검토", "권장"],
                ["A-8", "보안관제 전담조직 운영이 바람직함", "권장"],
            ],
            "h3": "3) 평가기준 (표-2: 기술/가격/가점)",
            "declared": "총점 표기: 100점 (기술 90 + 가격 10)",
            "nested": [["소항목", "배점"], ["품질/보안", "18"], ["(참고) ISMS-P", "+2 가점 검토"]],
            "eval_rows": [
                ["대항목(병합)", "소항목", "배점", "비고"],
                ["기술", "사업이해도", "15", "-"],
                ["", "수행전략", "20", "-"],
                ["", "수행실적", "15", "증빙기준"],
                ["", "인력구성", "20", "자격/투입계획"],
                ["", None, "18", "중첩 표 포함"],
                ["가격", "입찰가격", "10", "상대평가"],
                ["가점", "지역기업", "2", "본사 소재지"],
            ],
            "score_note1": "- 표 기준 기술 소계: 88",
            "score_note2": "- 서두 표기: 기술 90 + 가격 10 = 100 (의도적 불일치)",
            "h4": "4) 모호한 표현",
            "ambiguous": [
                "- 보안관제 조직은 상시 운영되는 것이 바람직하다.",
                "- 감리역량은 확보를 권장한다.",
                "- 인증은 원칙적으로 유효 상태를 요구하나 계약 전 보완계획 제출 시 검토 가능.",
            ],
        }

    return {
        "title": "RFx - CCTV Optical Multiplexer Replacement Project",
        "contract": "Contract duration: 8 months from contract date",
        "h1": "1) Bid Qualification Requirements (Table-1, Page 1)",
        "req1": [
            ["ID", "Requirement", "Level"],
            ["A-1", "Valid ISO 9001 certificate", "Required"],
            ["A-2", "(ISO 27001 OR ISMS-P) AND ISO 9001", "Required"],
            ["A-3", "At least 10 certified information-processing engineers", "Required"],
            ["A-4", "At least two single public SI projects >= 2.0B KRW in last 3 years", "Required"],
        ],
        "footnote": "* Footnote: Venture-certified firm may replace A-4 with one project >= 2.0B KRW.",
        "h2": "2) Bid Qualification Requirements (Table-1 continued, Page 2)",
        "req2": [
            ["ID", "Requirement", "Level"],
            ["A-5", "For consortium records, only contribution share is recognized", "Required"],
            ["A-6", "Corporate credit rating BBB or above", "Required"],
            ["A-7", "Auditor/audit engineer availability may receive bonus consideration", "Recommended"],
            ["A-8", "A dedicated security operations team is desirable", "Recommended"],
        ],
        "h3": "3) Evaluation Rubric (Table-2: Technical/Price/Bonus)",
        "declared": "Declared total: 100 (Technical 90 + Price 10)",
        "nested": [["Sub-item", "Points"], ["Quality/Security", "18"], ["(Reference) ISMS-P", "+2 bonus review"]],
        "eval_rows": [
            ["Category (Merged)", "Sub-item", "Points", "Note"],
            ["Technical", "Business understanding", "15", "-"],
            ["", "Execution strategy", "20", "-"],
            ["", "Track record", "15", "Certificate-based"],
            ["", "Workforce", "20", "Qualification + staffing plan"],
            ["", None, "18", "Nested table included"],
            ["Price", "Bid price", "10", "Relative scoring"],
            ["Bonus", "Local company", "2", "HQ location"],
        ],
        "score_note1": "- Technical subtotal in table: 88",
        "score_note2": "- Header declaration says Technical 90 + Price 10 = 100 (intentional inconsistency)",
        "h4": "4) Ambiguous Wording",
        "ambiguous": [
            "- A security operations team is desirable.",
            "- Audit capability is recommended.",
            "- Certificates should be valid in principle, but pre-award remediation plans may be reviewed.",
        ],
    }


def build_company_pdf(output_path: Path, lang: str, font_name: str) -> None:
    style = _styles(font_name)
    content = _company_content(lang)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    story = [
        Paragraph(content["title"], style["title"]),
        Paragraph(content["purpose"], style["body"]),
        Spacer(1, 10),
        Paragraph(content["h1"], style["h2"]),
    ]

    cert_table = Table(content["cert_rows"], colWidths=[110, 230, 150])
    cert_table.setStyle(_table_style(font_name))
    story.extend([cert_table, Spacer(1, 10), Paragraph(content["h2"], style["h2"])])

    staff_table = Table(content["staff_rows"], colWidths=[180, 80, 230])
    staff_table.setStyle(_table_style(font_name))
    story.extend([staff_table, Spacer(1, 10), Paragraph(content["h3"], style["h2"])])

    perf_table = Table(content["perf_rows"], colWidths=[175, 75, 90, 90, 60])
    perf_table.setStyle(_table_style(font_name))
    story.extend([
        perf_table,
        Spacer(1, 8),
        Paragraph(content["h4"], style["h2"]),
        Paragraph(content["credit"], style["body"]),
        Paragraph(content["credit_note"], style["small"]),
        Spacer(1, 8),
        Paragraph(content["h5"], style["h2"]),
    ])

    for line in content["ambiguous"]:
        story.append(Paragraph(line, style["body"]))

    doc.build(story)


def build_rfx_pdf(output_path: Path, lang: str, font_name: str) -> None:
    style = _styles(font_name)
    content = _rfx_content(lang)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    story = [
        Paragraph(content["title"], style["title"]),
        Paragraph(content["contract"], style["body"]),
        Spacer(1, 8),
        Paragraph(content["h1"], style["h2"]),
    ]

    t1 = Table(content["req1"], colWidths=[45, 360, 70])
    t1.setStyle(_table_style(font_name))
    story.extend([t1, Paragraph(content["footnote"], style["small"]), PageBreak(), Paragraph(content["h2"], style["h2"])])

    t2 = Table(content["req2"], colWidths=[45, 360, 70])
    t2.setStyle(_table_style(font_name))
    story.extend([t2, Spacer(1, 10), Paragraph(content["h3"], style["h2"]), Paragraph(content["declared"], style["body"])])

    nested_sub_table = Table(content["nested"], colWidths=[130, 90])
    nested_sub_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f7f7f7")),
            ]
        )
    )

    eval_rows = []
    for row in content["eval_rows"]:
        row = list(row)
        if row[1] is None:
            row[1] = nested_sub_table
        eval_rows.append(row)

    eval_table = Table(eval_rows, colWidths=[90, 220, 50, 115])
    eval_style = _table_style(font_name)
    eval_style.add("SPAN", (0, 1), (0, 5))
    eval_style.add("ALIGN", (0, 1), (0, 5), "CENTER")
    eval_table.setStyle(eval_style)

    story.extend(
        [
            eval_table,
            Spacer(1, 8),
            Paragraph(content["score_note1"], style["body"]),
            Paragraph(content["score_note2"], style["body"]),
            Spacer(1, 8),
            Paragraph(content["h4"], style["h2"]),
        ]
    )

    for line in content["ambiguous"]:
        story.append(Paragraph(line, style["body"]))

    doc.build(story)


def _parse_langs(raw: str) -> list[str]:
    langs = []
    for lang in [x.strip().lower() for x in raw.split(",") if x.strip()]:
        if lang not in {"ko", "en"}:
            raise ValueError(f"Unsupported language: {lang}. Use ko,en")
        if lang not in langs:
            langs.append(lang)
    if not langs:
        raise ValueError("At least one language is required.")
    return langs


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate adversarial company/RFx PDFs")
    parser.add_argument(
        "--out-dir",
        type=str,
        default="testdata/adversarial",
        help="Output directory for generated PDFs",
    )
    parser.add_argument(
        "--langs",
        type=str,
        default="ko,en",
        help="Comma-separated languages. Example: ko,en or ko or en",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    langs = _parse_langs(args.langs)
    for lang in langs:
        font_name = _register_font_for_lang(lang)
        company_pdf = out_dir / f"company_adversarial_{lang}.pdf"
        rfx_pdf = out_dir / f"rfx_adversarial_{lang}.pdf"

        build_company_pdf(company_pdf, lang, font_name)
        build_rfx_pdf(rfx_pdf, lang, font_name)

        print(f"Generated ({lang}): {company_pdf}")
        print(f"Generated ({lang}): {rfx_pdf}")


if __name__ == "__main__":
    main()
