"""Tests for relevance_scorer.py — multi-signal RFP-based matching."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from relevance_scorer import (
    score_track_record_relevance,
    score_personnel_relevance,
    extract_rfp_signals,
    _parse_budget,
    _parse_period_year,
    _tokenize,
    _keyword_overlap_score,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _rfx_smart_city():
    return {
        "title": "스마트시티 통합플랫폼 구축",
        "issuing_org": "서울시",
        "budget": "50억",
        "project_period": "12개월",
        "requirements": [
            {"category": "기술", "description": "IoT 센서 통합 클라우드 플랫폼"},
            {"category": "인력", "description": "PM 경력 10년 이상"},
            {"category": "자격", "description": "PMP CISA"},
        ],
    }


def _rfx_ai_analytics():
    return {
        "title": "AI 기반 빅데이터 분석 시스템",
        "issuing_org": "과학기술정보통신부",
        "budget": "30억",
        "requirements": [
            {"category": "기술", "description": "머신러닝 자연어처리 GPU 클러스터"},
        ],
    }


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------

class TestParseBudget:
    def test_억(self):
        assert _parse_budget("50억") == 50.0

    def test_억_with_decimal(self):
        assert _parse_budget("3.5억") == 3.5

    def test_만원(self):
        assert abs(_parse_budget("5000만원") - 0.5) < 0.01

    def test_empty(self):
        assert _parse_budget("") is None

    def test_none(self):
        assert _parse_budget("미정") is None

    def test_comma(self):
        assert _parse_budget("50억") == 50.0


class TestParsePeriodYear:
    def test_range(self):
        assert _parse_period_year("2024.03 ~ 2025.02") == 2025

    def test_single(self):
        assert _parse_period_year("2024.01~2024.12") == 2024

    def test_no_year(self):
        assert _parse_period_year("12개월") is None


class TestTokenize:
    def test_basic(self):
        tokens = _tokenize("IoT 센서 통합 플랫폼")
        assert "iot" in tokens
        assert "센서" in tokens
        assert "플랫폼" in tokens

    def test_removes_short(self):
        tokens = _tokenize("a b 를 IoT")
        assert "a" not in tokens
        assert "iot" in tokens


class TestKeywordOverlap:
    def test_full_overlap(self):
        assert _keyword_overlap_score({"a", "b"}, {"a", "b"}) == 1.0

    def test_partial(self):
        score = _keyword_overlap_score({"a", "b", "c"}, {"a", "b"})
        assert score == 1.0  # 2/min(3,2) = 2/2 = 1.0

    def test_no_overlap(self):
        assert _keyword_overlap_score({"a"}, {"b"}) == 0.0

    def test_empty(self):
        assert _keyword_overlap_score(set(), {"a"}) == 0.0


# ---------------------------------------------------------------------------
# RFP signal extraction
# ---------------------------------------------------------------------------

class TestExtractRfpSignals:
    def test_extracts_keywords(self):
        signals = extract_rfp_signals(_rfx_smart_city())
        assert "스마트시티" in signals["keywords"]
        assert "iot" in signals["keywords"]

    def test_extracts_budget(self):
        signals = extract_rfp_signals(_rfx_smart_city())
        assert signals["budget_억"] == 50.0

    def test_extracts_domains(self):
        signals = extract_rfp_signals(_rfx_smart_city())
        assert "스마트시티" in signals["domains"]

    def test_extracts_technologies(self):
        signals = extract_rfp_signals(_rfx_smart_city())
        assert "iot" in signals["technologies"]

    def test_extracts_required_roles(self):
        signals = extract_rfp_signals(_rfx_smart_city())
        assert "pm" in signals["required_roles"]

    def test_extracts_required_certs(self):
        signals = extract_rfp_signals(_rfx_smart_city())
        assert "pmp" in signals["required_certs"]


# ---------------------------------------------------------------------------
# Track record scoring
# ---------------------------------------------------------------------------

class TestScoreTrackRecordRelevance:
    def test_high_relevance_same_domain(self):
        """Same-domain record with matching tech should score high."""
        result = score_track_record_relevance(
            _rfx_smart_city(),
            "프로젝트: 스마트시티 IoT 관제시스템\n발주처: 부산시\n기간: 2025.01~2025.12\n금액: 40억원\n내용: IoT 센서 기반 스마트시티 관제\n기술: IoT, 클라우드",
            {"project_name": "스마트시티 IoT 관제시스템", "client": "부산시", "amount": 40.0},
            embedding_distance=0.2,
        )
        assert result.score >= 0.6
        assert "스마트시티" in result.match_reason
        assert result.signal_details["semantic"] == 0.8

    def test_low_relevance_different_domain(self):
        """Unrelated domain should score lower."""
        result = score_track_record_relevance(
            _rfx_smart_city(),
            "프로젝트: 재무회계 ERP 시스템\n발주처: 한국전력\n기간: 2020.01~2020.06\n금액: 5억원\n내용: 재무회계 ERP 구축\n기술: SAP, ABAP",
            {"project_name": "재무회계 ERP", "client": "한국전력", "amount": 5.0},
            embedding_distance=0.8,
        )
        assert result.score < 0.4

    def test_scale_match_boosts_score(self):
        """Similar budget should score higher than different budget."""
        base_text = "프로젝트: IoT 플랫폼\n발주처: 서울시\n기간: 2025.01~2025.12\n금액: {amt}억원\n내용: IoT 센서 플랫폼\n기술: IoT"
        r_similar = score_track_record_relevance(
            _rfx_smart_city(),
            base_text.format(amt=45),
            {"project_name": "IoT 플랫폼", "client": "서울시", "amount": 45.0},
            embedding_distance=0.3,
        )
        r_different = score_track_record_relevance(
            _rfx_smart_city(),
            base_text.format(amt=2),
            {"project_name": "IoT 플랫폼", "client": "서울시", "amount": 2.0},
            embedding_distance=0.3,
        )
        assert r_similar.signal_details["scale"] > r_different.signal_details["scale"]

    def test_recency_bonus(self):
        """Recent projects should score higher on recency signal."""
        r_recent = score_track_record_relevance(
            _rfx_smart_city(),
            "프로젝트: A\n기간: 2025.01~2025.12\n금액: 10억원\n내용: IoT\n기술: IoT",
            {"project_name": "A", "client": "X", "amount": 10.0},
            embedding_distance=0.3,
            current_year=2026,
        )
        r_old = score_track_record_relevance(
            _rfx_smart_city(),
            "프로젝트: B\n기간: 2018.01~2018.12\n금액: 10억원\n내용: IoT\n기술: IoT",
            {"project_name": "B", "client": "X", "amount": 10.0},
            embedding_distance=0.3,
            current_year=2026,
        )
        assert r_recent.signal_details["recency"] > r_old.signal_details["recency"]

    def test_match_reason_is_descriptive(self):
        """match_reason should contain the score and explanation."""
        result = score_track_record_relevance(
            _rfx_smart_city(),
            "프로젝트: 스마트시티 관제\n기간: 2025.01~2025.12\n금액: 50억원\n내용: 스마트시티 IoT 관제\n기술: IoT, 센서",
            {"project_name": "스마트시티 관제", "client": "부산시", "amount": 50.0},
            embedding_distance=0.2,
        )
        assert "[" in result.match_reason  # contains score
        assert "스마트시티 관제" in result.match_reason  # contains project name

    def test_returns_all_signal_details(self):
        result = score_track_record_relevance(
            _rfx_smart_city(),
            "프로젝트: X\n내용: 테스트",
            {"project_name": "X", "client": "Y", "amount": 0},
            embedding_distance=0.5,
        )
        expected_keys = {"semantic", "keyword_overlap", "scale", "technology", "recency"}
        assert set(result.signal_details.keys()) == expected_keys

    def test_score_within_bounds(self):
        """Score should always be 0.0-1.0 regardless of inputs."""
        for dist in [0.0, 0.5, 1.0, 1.5, 2.0]:
            result = score_track_record_relevance(
                _rfx_smart_city(), "text", {"project_name": "X"}, dist,
            )
            assert 0.0 <= result.score <= 1.0


# ---------------------------------------------------------------------------
# Personnel scoring
# ---------------------------------------------------------------------------

class TestScorePersonnelRelevance:
    def test_high_relevance_matching_role(self):
        """PM with matching domain and certs should score high."""
        result = score_personnel_relevance(
            _rfx_smart_city(),
            "이름: 홍길동\n역할: PM\n경력: 15년\n자격증: PMP, CISA\n전문분야: 스마트시티, IoT\n주요프로젝트: 스마트시티 관제",
            {"name": "홍길동", "role": "PM", "experience_years": 15},
            embedding_distance=0.2,
        )
        assert result.score >= 0.5
        assert "홍길동" in result.match_reason

    def test_low_relevance_unrelated(self):
        """Unrelated role/domain should score lower."""
        result = score_personnel_relevance(
            _rfx_smart_city(),
            "이름: 김영희\n역할: 디자이너\n경력: 3년\n자격증: \n전문분야: 그래픽디자인\n주요프로젝트: 로고 디자인",
            {"name": "김영희", "role": "디자이너", "experience_years": 3},
            embedding_distance=0.8,
        )
        assert result.score < 0.4

    def test_experience_bonus(self):
        """More experienced personnel should score higher on experience signal."""
        r_senior = score_personnel_relevance(
            _rfx_smart_city(),
            "이름: A\n역할: 개발자\n경력: 15년\n자격증: \n전문분야: \n주요프로젝트: ",
            {"name": "A", "role": "개발자", "experience_years": 15},
            embedding_distance=0.5,
        )
        r_junior = score_personnel_relevance(
            _rfx_smart_city(),
            "이름: B\n역할: 개발자\n경력: 2년\n자격증: \n전문분야: \n주요프로젝트: ",
            {"name": "B", "role": "개발자", "experience_years": 2},
            embedding_distance=0.5,
        )
        assert r_senior.signal_details["experience"] > r_junior.signal_details["experience"]

    def test_certification_match(self):
        """Personnel with matching certs should get cert bonus."""
        r_certs = score_personnel_relevance(
            _rfx_smart_city(),
            "이름: A\n역할: PM\n경력: 10년\n자격증: PMP, CISA\n전문분야: 관리\n주요프로젝트: ",
            {"name": "A", "role": "PM", "experience_years": 10},
            embedding_distance=0.3,
        )
        r_nocerts = score_personnel_relevance(
            _rfx_smart_city(),
            "이름: B\n역할: PM\n경력: 10년\n자격증: \n전문분야: 관리\n주요프로젝트: ",
            {"name": "B", "role": "PM", "experience_years": 10},
            embedding_distance=0.3,
        )
        assert r_certs.signal_details["certification"] > r_nocerts.signal_details["certification"]

    def test_match_reason_contains_explanation(self):
        result = score_personnel_relevance(
            _rfx_smart_city(),
            "이름: 홍길동\n역할: PM\n경력: 15년\n자격증: PMP\n전문분야: 스마트시티\n주요프로젝트: 관제",
            {"name": "홍길동", "role": "PM", "experience_years": 15},
            embedding_distance=0.2,
        )
        assert "홍길동" in result.match_reason
        assert "[" in result.match_reason  # contains score

    def test_score_within_bounds(self):
        for dist in [0.0, 0.5, 1.0, 1.5, 2.0]:
            result = score_personnel_relevance(
                _rfx_smart_city(), "text", {"name": "X", "role": "Y"}, dist,
            )
            assert 0.0 <= result.score <= 1.0

    def test_batch_efficiency_with_precomputed_signals(self):
        """Using pre-computed signals should give same results."""
        rfx = _rfx_smart_city()
        signals = extract_rfp_signals(rfx)
        r1 = score_personnel_relevance(
            rfx,
            "이름: A\n역할: PM\n경력: 10년",
            {"name": "A", "role": "PM", "experience_years": 10},
            0.3,
        )
        r2 = score_personnel_relevance(
            rfx,
            "이름: A\n역할: PM\n경력: 10년",
            {"name": "A", "role": "PM", "experience_years": 10},
            0.3,
            rfp_signals=signals,
        )
        assert r1.score == r2.score


# ---------------------------------------------------------------------------
# Cross-domain scoring validation
# ---------------------------------------------------------------------------

class TestCrossDomainScoring:
    def test_ai_record_scores_high_for_ai_rfp(self):
        """AI track record should score high for AI RFP."""
        result = score_track_record_relevance(
            _rfx_ai_analytics(),
            "프로젝트: AI 자연어처리 분석\n기간: 2025.01~2025.12\n금액: 25억원\n내용: 머신러닝 기반 빅데이터 분석\n기술: ML, NLP, GPU",
            {"project_name": "AI 자연어처리", "client": "과기부", "amount": 25.0},
            embedding_distance=0.2,
        )
        assert result.score >= 0.5
        assert "AI/빅데이터" in result.match_reason

    def test_ai_record_scores_low_for_smart_city_rfp(self):
        """AI record should score lower for smart city RFP."""
        result = score_track_record_relevance(
            _rfx_smart_city(),
            "프로젝트: AI 자연어처리 분석\n기간: 2025.01~2025.12\n금액: 25억원\n내용: 머신러닝 기반 텍스트 분석\n기술: ML, NLP",
            {"project_name": "AI 자연어처리", "client": "과기부", "amount": 25.0},
            embedding_distance=0.7,
        )
        # Should score notably lower than domain-matched record
        matched = score_track_record_relevance(
            _rfx_smart_city(),
            "프로젝트: 스마트시티 IoT\n기간: 2025.01~2025.12\n금액: 45억원\n내용: IoT 센서 스마트시티 관제\n기술: IoT, 센서",
            {"project_name": "스마트시티 IoT", "client": "서울시", "amount": 45.0},
            embedding_distance=0.2,
        )
        assert result.score < matched.score
