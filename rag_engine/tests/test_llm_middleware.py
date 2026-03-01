"""LLM Middleware tests — logging, token tracking, error standardization."""
from unittest.mock import MagicMock

import pytest

from llm_middleware import LLMMiddleware, LLMCallRecord, LLMError


class TestLLMCallRecord:
    def test_record_creation(self):
        rec = LLMCallRecord(
            caller="section_writer",
            model="gpt-4o-mini",
            prompt_tokens=100,
            completion_tokens=50,
            latency_ms=1234.5,
            success=True,
        )
        assert rec.caller == "section_writer"
        assert rec.total_tokens == 150

    def test_estimated_cost_gpt4o_mini(self):
        rec = LLMCallRecord(
            caller="test",
            model="gpt-4o-mini",
            prompt_tokens=1000,
            completion_tokens=500,
            latency_ms=500,
            success=True,
        )
        # gpt-4o-mini: $0.15/1M input, $0.60/1M output
        cost = rec.estimated_cost_usd
        assert 0.0 < cost < 0.01

    def test_estimated_cost_unknown_model(self):
        """Unknown model falls back to gpt-4o-mini pricing."""
        rec = LLMCallRecord(
            caller="test", model="gpt-5-turbo",
            prompt_tokens=1000, completion_tokens=500,
            latency_ms=100, success=True,
        )
        expected = LLMCallRecord(
            caller="test", model="gpt-4o-mini",
            prompt_tokens=1000, completion_tokens=500,
            latency_ms=100, success=True,
        )
        assert rec.estimated_cost_usd == expected.estimated_cost_usd


class TestLLMMiddleware:
    def test_wrap_logs_success(self):
        mw = LLMMiddleware()
        mock_response = MagicMock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        mock_response.model = "gpt-4o-mini"

        wrapped = mw.wrap(lambda: mock_response, caller_name="test_caller")
        result = wrapped()
        assert result == mock_response
        assert len(mw.records) == 1
        assert mw.records[0].caller == "test_caller"
        assert mw.records[0].success is True
        assert mw.records[0].prompt_tokens == 100

    def test_wrap_logs_failure(self):
        mw = LLMMiddleware()

        def failing_llm():
            raise RuntimeError("API down")

        wrapped = mw.wrap(failing_llm, caller_name="test_fail")
        with pytest.raises(LLMError) as exc_info:
            wrapped()
        assert "test_fail" in str(exc_info.value)
        assert len(mw.records) == 1
        assert mw.records[0].success is False
        assert mw.records[0].error_message == "API down"

    def test_llm_error_preserves_original(self):
        mw = LLMMiddleware()
        original = ValueError("bad value")

        wrapped = mw.wrap(lambda: (_ for _ in ()).throw(original), caller_name="test")
        with pytest.raises(LLMError) as exc_info:
            wrapped()
        assert exc_info.value.original is original
        assert exc_info.value.caller == "test"

    def test_session_stats(self):
        mw = LLMMiddleware()
        mw.records.append(LLMCallRecord(
            caller="a", model="gpt-4o-mini",
            prompt_tokens=1000, completion_tokens=500,
            latency_ms=100, success=True,
        ))
        mw.records.append(LLMCallRecord(
            caller="b", model="gpt-4o-mini",
            prompt_tokens=2000, completion_tokens=800,
            latency_ms=200, success=True,
        ))
        stats = mw.get_session_stats()
        assert stats["total_calls"] == 2
        assert stats["successful_calls"] == 2
        assert stats["failed_calls"] == 0
        assert stats["total_prompt_tokens"] == 3000
        assert stats["total_completion_tokens"] == 1300
        assert stats["total_tokens"] == 4300
        assert stats["total_cost_usd"] > 0
        assert stats["avg_latency_ms"] == 150.0
        assert "a" in stats["by_caller"]
        assert "b" in stats["by_caller"]

    def test_session_stats_with_failures(self):
        mw = LLMMiddleware()
        mw.records.append(LLMCallRecord(
            caller="x", model="gpt-4o-mini",
            prompt_tokens=0, completion_tokens=0,
            latency_ms=50, success=False, error_message="timeout",
        ))
        stats = mw.get_session_stats()
        assert stats["total_calls"] == 1
        assert stats["failed_calls"] == 1
        assert stats["avg_latency_ms"] == 0  # No successful calls

    def test_wrap_without_usage_attribute(self):
        """LLM response without .usage should still log with 0 tokens."""
        mw = LLMMiddleware()
        wrapped = mw.wrap(lambda: "plain_string", caller_name="no_usage")
        result = wrapped()
        assert result == "plain_string"
        assert len(mw.records) == 1
        assert mw.records[0].prompt_tokens == 0
        assert mw.records[0].completion_tokens == 0

    def test_cache_disabled_by_default(self):
        mw = LLMMiddleware()
        assert mw.enable_cache is False

    def test_by_caller_stats(self):
        mw = LLMMiddleware()
        mw.records.append(LLMCallRecord(
            caller="writer", model="gpt-4o-mini",
            prompt_tokens=500, completion_tokens=200,
            latency_ms=100, success=True,
        ))
        mw.records.append(LLMCallRecord(
            caller="writer", model="gpt-4o-mini",
            prompt_tokens=600, completion_tokens=300,
            latency_ms=150, success=True,
        ))
        mw.records.append(LLMCallRecord(
            caller="agent", model="gpt-4o-mini",
            prompt_tokens=1000, completion_tokens=400,
            latency_ms=200, success=True,
        ))
        stats = mw.get_session_stats()
        assert stats["by_caller"]["writer"]["calls"] == 2
        assert stats["by_caller"]["writer"]["tokens"] == 1600
        assert stats["by_caller"]["agent"]["calls"] == 1
