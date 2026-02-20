from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from matcher import QualificationMatcher, MatchingResult, RequirementMatch, MatchStatus
from rfx_analyzer import RFxAnalysisResult, RFxRequirement


def _build_matcher() -> QualificationMatcher:
    matcher = QualificationMatcher.__new__(QualificationMatcher)
    matcher.opinion_enabled = True
    matcher.opinion_ab_enabled = True
    matcher.opinion_model = "gpt-4o-mini"
    matcher.opinion_temperature = 0.2
    matcher.balanced_variant_default = "a"
    return matcher


def _sample_rfx(is_rfx_like: bool = True) -> RFxAnalysisResult:
    return RFxAnalysisResult(
        title="테스트 공고",
        issuing_org="테스트 기관",
        requirements=[
            RFxRequirement(
                category="필수자격",
                description="ISO 9001 보유",
                is_mandatory=True,
                detail="",
            )
        ],
        document_type="rfx" if is_rfx_like else "research_report",
        is_rfx_like=is_rfx_like,
    )


def test_generate_assistant_opinion_parses_schema() -> None:
    matcher = _build_matcher()

    def _fake_chat_json(**_: object) -> dict:
        return {
            "opinion": "도전 가치가 있으며, 미충족 항목을 먼저 보완하세요.",
            "actions": ["ISO 증빙 업데이트", "유사실적 증명 첨부"],
            "risk_notes": ["마감 2주 전 서류 검증 필요"],
        }

    matcher._chat_json = _fake_chat_json
    result = MatchingResult(overall_score=78.0, recommendation="🟡 CONDITIONAL")
    payload = matcher._generate_assistant_opinion("balanced", result, _sample_rfx())

    assert payload["opinion"]
    assert len(payload["actions"]) == 2
    assert len(payload["risk_notes"]) == 1
    assert "generated_at" in payload


def test_generate_assistant_opinion_fallback_on_error() -> None:
    matcher = _build_matcher()

    def _raise_chat_json(**_: object) -> dict:
        raise RuntimeError("forced error")

    matcher._chat_json = _raise_chat_json
    result = MatchingResult(overall_score=55.0, recommendation="🟠 RISKY")
    payload = matcher._generate_assistant_opinion("balanced", result, _sample_rfx())

    assert payload["opinion"] == ""
    assert payload["actions"] == []
    assert payload["risk_notes"] == []


def test_match_pre_generates_balanced_opinion() -> None:
    matcher = _build_matcher()
    called_modes: list[str] = []

    def _fake_match_single(req: RFxRequirement) -> RequirementMatch:
        return RequirementMatch(requirement=req, status=MatchStatus.MET, confidence=0.9)

    def _fake_generate_mode(result: MatchingResult, rfx: RFxAnalysisResult, mode: str) -> dict:
        called_modes.append(mode)
        payload = {
            "opinion": "균형 의견",
            "actions": ["체크리스트"],
            "risk_notes": [],
            "generated_at": "now",
        }
        result.assistant_opinions[mode] = payload
        result.opinion_mode = mode
        return payload

    matcher._match_single_requirement = _fake_match_single
    matcher._calculate_overall_score = lambda matches: 100.0
    matcher._determine_recommendation = lambda result: "🟢 GO - 적극 참여 권장"
    matcher._calculate_expected_evaluation_score = lambda result, rfx: None
    matcher._generate_summary = lambda result, rfx: "사실요약"
    matcher.generate_opinion_for_mode = _fake_generate_mode

    result = QualificationMatcher.match(matcher, _sample_rfx())
    assert called_modes == ["balanced"]
    assert "balanced" in result.assistant_opinions


def test_generate_opinion_for_mode_uses_cache_key_normalization() -> None:
    matcher = _build_matcher()
    calls = {"count": 0}

    def _fake_generate_assistant_opinion(
        mode: str,
        result: MatchingResult,
        rfx: RFxAnalysisResult,
        balanced_variant: str | None = None,
    ) -> dict:
        calls["count"] += 1
        return {
            "opinion": f"{mode} 의견",
            "actions": [f"{mode} 액션"],
            "risk_notes": [],
            "variant": balanced_variant or "",
            "generated_at": "now",
        }

    matcher._generate_assistant_opinion = _fake_generate_assistant_opinion
    result = MatchingResult()
    rfx = _sample_rfx()

    first = QualificationMatcher.generate_opinion_for_mode(matcher, result, rfx, "균형")
    second = QualificationMatcher.generate_opinion_for_mode(matcher, result, rfx, "balanced")
    third = QualificationMatcher.generate_opinion_for_mode(matcher, result, rfx, "conservative")

    assert calls["count"] == 2
    assert first == second
    assert "balanced" in result.assistant_opinions
    assert "conservative" in result.assistant_opinions
    assert third["opinion"].startswith("conservative")


def test_generate_opinion_for_mode_balanced_ab_cache_keys() -> None:
    matcher = _build_matcher()
    calls = {"count": 0}

    def _fake_generate_assistant_opinion(
        mode: str,
        result: MatchingResult,
        rfx: RFxAnalysisResult,
        balanced_variant: str | None = None,
    ) -> dict:
        calls["count"] += 1
        variant = balanced_variant or ""
        return {
            "opinion": f"{mode}-{variant}",
            "actions": [],
            "risk_notes": [],
            "variant": variant,
            "generated_at": "now",
        }

    matcher._generate_assistant_opinion = _fake_generate_assistant_opinion
    result = MatchingResult()
    rfx = _sample_rfx()

    a_first = QualificationMatcher.generate_opinion_for_mode(matcher, result, rfx, "balanced", balanced_variant="a")
    a_second = QualificationMatcher.generate_opinion_for_mode(matcher, result, rfx, "balanced", balanced_variant="a")
    b_first = QualificationMatcher.generate_opinion_for_mode(matcher, result, rfx, "balanced", balanced_variant="b")

    assert calls["count"] == 2
    assert a_first == a_second
    assert a_first["variant"] == "a"
    assert b_first["variant"] == "b"
    assert "balanced_a" in result.assistant_opinions
    assert "balanced_b" in result.assistant_opinions


def test_generate_opinion_for_mode_balanced_default_variant_config() -> None:
    matcher = _build_matcher()
    matcher.balanced_variant_default = "b"
    captured: dict[str, str] = {}

    def _fake_generate_assistant_opinion(
        mode: str,
        result: MatchingResult,
        rfx: RFxAnalysisResult,
        balanced_variant: str | None = None,
    ) -> dict:
        captured["mode"] = mode
        captured["variant"] = balanced_variant or ""
        return {
            "opinion": "default balanced",
            "actions": [],
            "risk_notes": [],
            "variant": balanced_variant or "",
            "generated_at": "now",
        }

    matcher._generate_assistant_opinion = _fake_generate_assistant_opinion
    result = MatchingResult()
    rfx = _sample_rfx()
    payload = QualificationMatcher.generate_opinion_for_mode(matcher, result, rfx, "balanced")

    assert payload["variant"] == "b"
    assert captured["mode"] == "balanced"
    assert captured["variant"] == "b"
    assert "balanced" in result.assistant_opinions
