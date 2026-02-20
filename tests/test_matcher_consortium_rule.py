from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from matcher import QualificationMatcher
from rfx_analyzer import RFxRequirement


def _build_matcher() -> QualificationMatcher:
    # LLM 초기화 없이 규칙형 로직만 테스트하기 위한 경량 인스턴스
    return QualificationMatcher.__new__(QualificationMatcher)


def test_detect_consortium_share_requirement_ko() -> None:
    matcher = _build_matcher()
    req = RFxRequirement(
        category="필수자격",
        description="컨소시엄 실적은 참여지분(분담금)만 인정",
        is_mandatory=True,
    )
    assert matcher._is_consortium_share_requirement(req) is True


def test_detect_consortium_share_requirement_en() -> None:
    matcher = _build_matcher()
    req = RFxRequirement(
        category="required",
        description="For consortium records, only contribution share is recognized",
        is_mandatory=True,
    )
    assert matcher._is_consortium_share_requirement(req) is True


def test_rule_based_judgment_returns_met_with_consortium_and_share() -> None:
    matcher = _build_matcher()
    req = RFxRequirement(
        category="필수자격",
        description="컨소시엄 실적은 참여지분(분담금)만 인정",
        is_mandatory=True,
    )
    context = "C구 CCTV 고도화 프로젝트는 컨소시엄으로 수행했고 분담금 8억원을 인정 금액으로 기재함."

    judgment = matcher._apply_rule_based_judgment(req, context)

    assert judgment is not None
    assert judgment["status"] == "충족"


def test_rule_based_judgment_returns_partially_met_with_only_consortium() -> None:
    matcher = _build_matcher()
    req = RFxRequirement(
        category="required",
        description="For consortium records, only contribution share is recognized",
        is_mandatory=True,
    )
    context = "Company participated in a consortium project but no financial split is stated."

    judgment = matcher._apply_rule_based_judgment(req, context)

    assert judgment is not None
    assert judgment["status"] == "부분충족"


def test_rule_based_judgment_returns_none_for_other_requirements() -> None:
    matcher = _build_matcher()
    req = RFxRequirement(
        category="필수자격",
        description="ISO 9001 유효 인증 보유",
        is_mandatory=True,
    )
    context = "ISO 9001 is expired."

    judgment = matcher._apply_rule_based_judgment(req, context)

    assert judgment is None
