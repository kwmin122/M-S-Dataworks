from pathlib import Path
import sys

from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from matcher import MatchingResult
from rfx_analyzer import RFxAnalysisResult

APP_PATH = str(PROJECT_ROOT / "app.py")


def _collect_markdown_texts(at: AppTest) -> str:
    texts: list[str] = []
    texts.extend(
        md.value for md in at.markdown if hasattr(md, "value") and isinstance(md.value, str)
    )
    texts.extend(
        cap.value for cap in at.caption if hasattr(cap, "value") and isinstance(cap.value, str)
    )
    return "\n".join(texts)


def _set_radio_value(at: AppTest, label: str, value: str) -> None:
    for radio in at.radio:
        if getattr(radio, "label", "") == label:
            radio.set_value(value)
            return
    raise AssertionError(f"radio label not found: {label}")


def test_analysis_tab_renders_summary_and_disclaimer() -> None:
    at = AppTest.from_file(APP_PATH)
    at.session_state["is_authenticated"] = True
    at.session_state["auth_username"] = "tester"
    at.session_state["api_key"] = ""
    at.session_state["company_docs_loaded"] = True
    at.session_state["rfx_loaded"] = True
    at.session_state["analysis_opinion_mode"] = "balanced"
    at.session_state["rfx_analysis"] = RFxAnalysisResult(
        title="테스트 공고",
        issuing_org="기관",
    )
    at.session_state["matching_result"] = MatchingResult(
        rfx_title="테스트 공고",
        rfx_org="기관",
        summary="요약 본문",
        recommendation="🟡 CONDITIONAL",
        assistant_opinions={
            "balanced": {
                "opinion": "균형 의견 본문",
                "actions": ["실행항목 A"],
                "risk_notes": ["주의사항 A"],
                "generated_at": "now",
            }
        },
    )

    at.run(timeout=30)
    texts = _collect_markdown_texts(at)
    assert "사실 기반 요약" in texts
    assert "요약 본문" in texts
    assert "균형 의견 본문" in texts
    assert "Kira의 의견은 AI 참고용" in texts


def test_opinion_mode_switch_uses_cached_payload() -> None:
    at = AppTest.from_file(APP_PATH)
    at.session_state["is_authenticated"] = True
    at.session_state["auth_username"] = "tester"
    at.session_state["api_key"] = ""
    at.session_state["company_docs_loaded"] = True
    at.session_state["rfx_loaded"] = True
    at.session_state["analysis_opinion_mode"] = "balanced"
    at.session_state["rfx_analysis"] = RFxAnalysisResult(
        title="테스트 공고",
        issuing_org="기관",
    )
    at.session_state["matching_result"] = MatchingResult(
        rfx_title="테스트 공고",
        rfx_org="기관",
        summary="요약",
        recommendation="🟢 GO",
        assistant_opinions={
            "balanced": {"opinion": "균형 의견", "actions": [], "risk_notes": [], "generated_at": "now"},
            "conservative": {"opinion": "보수 의견", "actions": [], "risk_notes": [], "generated_at": "now"},
        },
    )

    at.run(timeout=30)
    _set_radio_value(at, "판단 강도", "🛡️ 보수적")
    at.run(timeout=30)
    texts = _collect_markdown_texts(at)
    assert "보수 의견" in texts


def test_cache_miss_for_mode_generates_empty_payload_without_api_key() -> None:
    at = AppTest.from_file(APP_PATH)
    at.session_state["is_authenticated"] = True
    at.session_state["auth_username"] = "tester"
    at.session_state["api_key"] = ""  # 캐시 미스 시 외부 호출 없이 빈값 반환 경로
    at.session_state["company_docs_loaded"] = True
    at.session_state["rfx_loaded"] = True
    at.session_state["analysis_opinion_mode"] = "balanced"
    at.session_state["rfx_analysis"] = RFxAnalysisResult(
        title="테스트 문서",
        issuing_org="기관",
    )
    at.session_state["matching_result"] = MatchingResult(
        rfx_title="테스트 문서",
        rfx_org="기관",
        summary="요약",
        recommendation="🟡 CONDITIONAL",
        assistant_opinions={
            "balanced": {
                "opinion": "균형 의견",
                "actions": ["근거 검토"],
                "risk_notes": [],
                "generated_at": "now",
            }
        },
    )

    at.run(timeout=30)
    # 공격적 모드 캐시 미스 -> 빈 페이로드 캐시 생성 경로 확인
    _set_radio_value(at, "판단 강도", "🚀 공격적")
    at.run(timeout=30)
    matching_result = at.session_state["matching_result"]
    assert "aggressive" in matching_result.assistant_opinions
