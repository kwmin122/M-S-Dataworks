"""Tests for domain detection from RFP text."""
import pathlib
import pytest
from unittest.mock import patch, MagicMock

from domain_detector import detect_domain, _keyword_fallback
from phase2_models import DomainType

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "domain_detection"


class TestKeywordFallback:
    def test_it_build(self):
        text = (FIXTURES / "it_build.txt").read_text()
        assert _keyword_fallback(text) == DomainType.IT_BUILD

    def test_research(self):
        text = (FIXTURES / "research.txt").read_text()
        assert _keyword_fallback(text) == DomainType.RESEARCH

    def test_consulting(self):
        text = (FIXTURES / "consulting.txt").read_text()
        assert _keyword_fallback(text) == DomainType.CONSULTING

    def test_education_oda(self):
        text = (FIXTURES / "education_oda.txt").read_text()
        assert _keyword_fallback(text) == DomainType.EDUCATION_ODA

    def test_empty_text_returns_general(self):
        assert _keyword_fallback("") == DomainType.GENERAL


class TestDetectDomain:
    @patch("domain_detector._call_llm_detect")
    def test_llm_success(self, mock_llm):
        mock_llm.return_value = {"domain_type": "research", "confidence": 0.95}
        result = detect_domain({"title": "연구용역", "full_text": "연구..."})
        assert result == DomainType.RESEARCH

    @patch("domain_detector._call_llm_detect")
    def test_llm_failure_falls_back_to_keyword(self, mock_llm):
        mock_llm.side_effect = Exception("API error")
        text = (FIXTURES / "it_build.txt").read_text()
        result = detect_domain({"title": text, "full_text": text})
        assert result == DomainType.IT_BUILD

    @patch("domain_detector._call_llm_detect")
    def test_llm_low_confidence_falls_back(self, mock_llm):
        mock_llm.return_value = {"domain_type": "research", "confidence": 0.3}
        text = (FIXTURES / "consulting.txt").read_text()
        result = detect_domain({"title": text, "full_text": text})
        assert result == DomainType.CONSULTING  # keyword fallback wins
