#!/usr/bin/env python3
"""
HWP 공고문 E2E 파이프라인 스모크 테스트.

사용법:
  python scripts/smoke_test_hwp_rfx.py

환경변수:
  OPENAI_API_KEY  (필수) - 실제 LLM 호출
  HWP_PATH        (선택) - 기본값: 내장 공고문 경로

테스트 대상:
  1. HWP 파싱 (document_parser)
  2. RFx 분석 (rfx_analyzer - real LLM)
  3. Company A (적격): 고양시 + 정보통신 면허
  4. Company B (비적격): 서울 + 면허 없음
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import uuid
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

# ── 설정 ──────────────────────────────────────────────────────────────────────
HWP_PATH = Path(os.getenv(
    "HWP_PATH",
    "/Users/min-kyungwook/Downloads/"
    "[공고문] [9권역]학교 유무선 네트워크 개선 3차 정보통신공사 감리용역.hwp"
))
COMPANY_A = Path(__file__).parent.parent / "testdata" / "company_a_goyang.txt"
COMPANY_B = Path(__file__).parent.parent / "testdata" / "company_b_seoul.txt"
REPORT_DIR = Path(__file__).parent.parent / "reports"
API_KEY = os.getenv("OPENAI_API_KEY", "")


def header(msg: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")


def check_prerequisites() -> None:
    header("전제 조건 확인")
    errors = []
    if not HWP_PATH.exists():
        errors.append(f"HWP 파일 없음: {HWP_PATH}")
    if not COMPANY_A.exists():
        errors.append(f"Company A 파일 없음: {COMPANY_A}")
    if not COMPANY_B.exists():
        errors.append(f"Company B 파일 없음: {COMPANY_B}")
    if not API_KEY or API_KEY == "your_openai_api_key_here":
        errors.append("OPENAI_API_KEY 미설정 (.env 파일 확인)")
    if errors:
        for e in errors:
            print(f"  ❌ {e}")
        sys.exit(1)
    print(f"  ✅ HWP: {HWP_PATH.name}")
    print(f"  ✅ Company A: {COMPANY_A.name}")
    print(f"  ✅ Company B: {COMPANY_B.name}")
    print(f"  ✅ API KEY: {'*' * 8}{API_KEY[-4:]}")


def step1_parse_hwp() -> str:
    header("STEP 1: HWP 파싱")
    from document_parser import DocumentParser
    parser = DocumentParser()
    doc = parser.parse(str(HWP_PATH))
    print(f"  파일: {doc.filename}")
    print(f"  텍스트: {doc.char_count:,}자, {doc.page_count} 페이지")
    print(f"  앞 300자: {doc.text[:300]}")
    assert doc.char_count > 500, "텍스트 추출 실패"
    print("  ✅ HWP 파싱 성공")
    return doc.text


def step2_analyze_rfx(text: str) -> object:
    header("STEP 2: RFx 분석 (LLM 호출)")
    from rfx_analyzer import RFxAnalyzer
    # analyze()는 파일 경로 기반이므로 임시 txt 파일 생성
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", encoding="utf-8", delete=False) as f:
        f.write(text)
        tmp_path = f.name
    try:
        analyzer = RFxAnalyzer(api_key=API_KEY)
        result = analyzer.analyze(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    print(f"  공고명: {result.title or '(없음)'}")
    print(f"  발주기관: {result.issuing_org or '(없음)'}")
    print(f"  문서유형: {result.document_type}")
    print(f"  자격요건 {len(result.requirements)}개:")
    for i, req in enumerate(result.requirements, 1):
        mandatory = "필수" if req.is_mandatory else "권장"
        print(f"    {i}. [{mandatory}][{req.category}] {req.description}")
        if req.constraints:
            for c in req.constraints:
                print(f"       → constraint: {c.metric}/{c.op}/{c.value} ({c.raw})")
    assert len(result.requirements) >= 1, "자격요건 추출 실패"
    print("  ✅ RFx 분석 성공")
    return result


def step3_match_company(company_name: str, company_file: Path, rfx_result: object) -> dict:
    header(f"STEP 3: 회사 매칭 - {company_name}")
    from engine import RAGEngine
    from matcher import QualificationMatcher

    # 독립적인 임시 컬렉션 사용
    col_name = f"smoke_test_{uuid.uuid4().hex[:8]}"
    persist_dir = f"/tmp/smoke_test_{col_name}"

    engine = RAGEngine(
        persist_directory=persist_dir,
        collection_name=col_name,
    )
    engine.add_document(str(company_file))
    print(f"  회사 정보 로드: {engine.collection.count()}개 청크")

    matcher = QualificationMatcher(engine, api_key=API_KEY)
    matching = matcher.match(rfx_result)

    print(f"  종합 점수: {matching.overall_score:.0f}%")
    print(f"  권고사항: {matching.recommendation}")
    print(f"  요건별 결과:")
    for req_match in matching.matches:
        status_icon = {"MET": "✅", "NOT_MET": "❌", "PARTIALLY_MET": "🟡", "UNKNOWN": "❓"}.get(
            req_match.status.value if hasattr(req_match.status, "value") else str(req_match.status), "?"
        )
        print(f"    {status_icon} [{req_match.requirement.category}] {req_match.requirement.description}")
        print(f"       근거: {req_match.evidence[:80] if req_match.evidence else '없음'}")

    return {
        "company": company_name,
        "file": str(company_file.name),
        "overall_score": matching.overall_score,
        "recommendation": matching.recommendation,
        "requirements": [
            {
                "category": m.requirement.category,
                "description": m.requirement.description,
                "status": str(m.status),
                "confidence": m.confidence,
                "evidence": m.evidence,
            }
            for m in matching.matches
        ],
    }


def main() -> None:
    print(f"\n🔬 HWP 공고문 E2E 파이프라인 스모크 테스트")
    print(f"   실행 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    check_prerequisites()

    # Step 1: HWP 파싱
    rfx_text = step1_parse_hwp()

    # Step 2: RFx 분석
    rfx_result = step2_analyze_rfx(rfx_text)

    # Step 3: 두 회사 매칭
    results = []
    results.append(step3_match_company("Company A (고양시·적격)", COMPANY_A, rfx_result))
    results.append(step3_match_company("Company B (서울·비적격)", COMPANY_B, rfx_result))

    # 결과 저장
    REPORT_DIR.mkdir(exist_ok=True)
    report = {
        "date": datetime.now().isoformat(),
        "hwp_file": str(HWP_PATH.name),
        "rfx_title": rfx_result.title,
        "rfx_issuing_org": rfx_result.issuing_org,
        "requirements_count": len(rfx_result.requirements),
        "company_results": results,
        "note": "overall_score: 0~100% 점수, recommendation: GO/CONDITIONAL/NO-GO",
    }
    report_path = REPORT_DIR / f"smoke_hwp_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 최종 요약
    header("최종 요약")
    for r in results:
        status_icon = "✅" if r["overall_score"] >= 60 else "❌"
        print(f"  {status_icon} {r['company']}: {r['overall_score']:.0f}% - {r['recommendation']}")
    print(f"\n  📄 리포트 저장: {report_path}")
    print("\n  ✅ 스모크 테스트 완료\n")


if __name__ == "__main__":
    main()
