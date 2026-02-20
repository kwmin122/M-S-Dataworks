from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rfx_analyzer import RFxAnalyzer, RFxAnalysisResult, RFxRequirement, RFxEvaluationCriteria


def _build_analyzer() -> RFxAnalyzer:
    analyzer = RFxAnalyzer.__new__(RFxAnalyzer)
    analyzer.routing_enabled = True
    analyzer.small_model = "gpt-4o-mini"
    analyzer.large_model = "gpt-4o"
    analyzer.large_doc_char_threshold = 28000
    analyzer.large_doc_page_threshold = 35
    return analyzer


def test_split_text_for_multipass_splits_large_text() -> None:
    analyzer = _build_analyzer()
    long_text = "A" * 90000
    chunks = analyzer._split_text_for_multipass(long_text)
    assert len(chunks) >= 2
    assert sum(len(c) for c in chunks) > len(long_text)  # overlap 포함


def test_merge_partial_results_dedups_requirements_and_criteria() -> None:
    analyzer = _build_analyzer()
    part1 = RFxAnalysisResult(
        title="문서 A",
        requirements=[
            RFxRequirement(category="필수자격", description="ISO 9001 유효 인증 보유", is_mandatory=True, detail="필수"),
            RFxRequirement(category="필수자격", description="정보처리기사 10명 이상", is_mandatory=True, detail=""),
        ],
        evaluation_criteria=[
            RFxEvaluationCriteria(category="기술평가", item="사업이해도", score=15.0, detail=""),
        ],
        required_documents=["사업자등록증"],
        special_notes=["컨소시엄 분담금 기준"],
    )
    part2 = RFxAnalysisResult(
        issuing_org="기관 B",
        requirements=[
            RFxRequirement(category="필수자격", description="ISO 9001 유효 인증 보유", is_mandatory=False, detail="중복"),
        ],
        evaluation_criteria=[
            RFxEvaluationCriteria(category="기술평가", item="사업이해도", score=10.0, detail="중복"),
            RFxEvaluationCriteria(category="가격평가", item="입찰가격", score=10.0, detail=""),
        ],
        required_documents=["사업자등록증", "실적증명서"],
        special_notes=["컨소시엄 분담금 기준", "벤처 면제 조건"],
    )

    merged = analyzer._merge_partial_results([part1, part2])

    assert merged.title == "문서 A"
    assert merged.issuing_org == "기관 B"
    assert len(merged.requirements) == 2
    iso = [r for r in merged.requirements if "ISO 9001" in r.description][0]
    assert iso.is_mandatory is True
    assert len(merged.evaluation_criteria) == 2
    assert sorted(merged.required_documents) == ["사업자등록증", "실적증명서"]
    assert sorted(merged.special_notes) == ["벤처 면제 조건", "컨소시엄 분담금 기준"]


def test_select_extraction_model_prefers_large_for_big_docs() -> None:
    analyzer = _build_analyzer()
    model = analyzer._select_extraction_model(
        char_count=50000,
        page_count=60,
        is_rfx_like=True,
    )
    assert model == "gpt-4o"
