# RAG Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Kira Bot의 2개 RAG 시스템에 Middleware Chain, Self-Correction Loop, Planning Agent, ReAct Pattern 4가지 개선을 적용

**Architecture:** 공유 LLM Middleware를 인프라로 깔고, Proposal RAG에 Self-Correction + Planning Agent, Chat RAG에 ReAct를 구현. 각 개선은 독립 모듈로 기존 코드 최소 변경.

**Tech Stack:** Python 3.11, FastAPI 0.115, OpenAI GPT-4o-mini, ChromaDB, ThreadPoolExecutor, pytest

---

## Task 1: LLM Middleware — 공유 인프라

**Files:**
- Create: `rag_engine/llm_middleware.py`
- Test: `rag_engine/tests/test_llm_middleware.py`

### Step 1: Write the failing tests

```python
# rag_engine/tests/test_llm_middleware.py
"""LLM Middleware tests — logging, token tracking, error standardization."""
import time
from unittest.mock import MagicMock, patch

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


class TestLLMMiddleware:
    def test_wrap_logs_success(self):
        mw = LLMMiddleware()
        mock_response = MagicMock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50

        def fake_llm():
            return mock_response

        wrapped = mw.wrap(fake_llm, caller_name="test_caller")
        result = wrapped()
        assert result == mock_response
        assert len(mw.records) == 1
        assert mw.records[0].caller == "test_caller"
        assert mw.records[0].success is True

    def test_wrap_logs_failure(self):
        mw = LLMMiddleware()

        def failing_llm():
            raise RuntimeError("API down")

        wrapped = mw.wrap(failing_llm, caller_name="test_fail")
        with pytest.raises(LLMError):
            wrapped()
        assert len(mw.records) == 1
        assert mw.records[0].success is False

    def test_session_stats(self):
        mw = LLMMiddleware()
        # Manually add records
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
        assert stats["total_prompt_tokens"] == 3000
        assert stats["total_completion_tokens"] == 1300
        assert stats["total_cost_usd"] > 0

    def test_wrap_without_usage_attribute(self):
        """LLM response without .usage should still log."""
        mw = LLMMiddleware()
        wrapped = mw.wrap(lambda: "plain_string", caller_name="no_usage")
        result = wrapped()
        assert result == "plain_string"
        assert len(mw.records) == 1
        assert mw.records[0].prompt_tokens == 0

    def test_cache_disabled_by_default(self):
        mw = LLMMiddleware()
        assert mw.enable_cache is False
```

### Step 2: Run tests to verify they fail

Run: `cd rag_engine && python -m pytest tests/test_llm_middleware.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'llm_middleware'`

### Step 3: Write implementation

```python
# rag_engine/llm_middleware.py
"""LLM Middleware — shared logging, token tracking, error standardization.

Wraps any LLM call function to add observability without changing call semantics.
Existing call_with_retry is preserved (retry != middleware responsibility).
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)
T = TypeVar("T")

# GPT-4o-mini pricing (USD per 1M tokens, as of 2025-01)
_PRICING = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
}


class LLMError(Exception):
    """Standardized LLM error with caller context."""

    def __init__(self, message: str, caller: str = "", original: Exception | None = None):
        super().__init__(message)
        self.caller = caller
        self.original = original


@dataclass
class LLMCallRecord:
    caller: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    success: bool
    error_message: str = ""

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def estimated_cost_usd(self) -> float:
        pricing = _PRICING.get(self.model, _PRICING["gpt-4o-mini"])
        return (
            self.prompt_tokens * pricing["input"] / 1_000_000
            + self.completion_tokens * pricing["output"] / 1_000_000
        )


class LLMMiddleware:
    """Decorator-based middleware for LLM calls.

    Usage:
        mw = LLMMiddleware()
        wrapped = mw.wrap(openai_call_fn, caller_name="section_writer")
        result = wrapped(messages=[...])
    """

    def __init__(
        self,
        enable_logging: bool = True,
        enable_token_tracking: bool = True,
        enable_cache: bool = False,
    ):
        self.enable_logging = enable_logging
        self.enable_token_tracking = enable_token_tracking
        self.enable_cache = enable_cache
        self.records: list[LLMCallRecord] = []

    def wrap(self, fn: Callable[..., T], caller_name: str = "unknown") -> Callable[..., T]:
        """Wrap an LLM call function with logging and tracking."""

        def wrapped(*args: Any, **kwargs: Any) -> T:
            start = time.time()
            try:
                result = fn(*args, **kwargs)
                latency = (time.time() - start) * 1000

                # Extract usage if available
                prompt_tokens = 0
                completion_tokens = 0
                model = "gpt-4o-mini"
                usage = getattr(result, "usage", None)
                if usage:
                    prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
                    completion_tokens = getattr(usage, "completion_tokens", 0) or 0
                model_attr = getattr(result, "model", None)
                if model_attr:
                    model = model_attr

                record = LLMCallRecord(
                    caller=caller_name,
                    model=model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    latency_ms=round(latency, 1),
                    success=True,
                )
                self.records.append(record)

                if self.enable_logging:
                    logger.info(
                        "LLM [%s] %s: %d+%d tokens, %.0fms",
                        caller_name,
                        model,
                        prompt_tokens,
                        completion_tokens,
                        latency,
                    )

                return result

            except Exception as exc:
                latency = (time.time() - start) * 1000
                record = LLMCallRecord(
                    caller=caller_name,
                    model="gpt-4o-mini",
                    prompt_tokens=0,
                    completion_tokens=0,
                    latency_ms=round(latency, 1),
                    success=False,
                    error_message=str(exc),
                )
                self.records.append(record)

                if self.enable_logging:
                    logger.error("LLM [%s] FAILED: %s (%.0fms)", caller_name, exc, latency)

                raise LLMError(
                    f"LLM call failed in {caller_name}: {exc}",
                    caller=caller_name,
                    original=exc,
                ) from exc

        return wrapped  # type: ignore[return-value]

    def get_session_stats(self) -> dict[str, Any]:
        """Return aggregated stats for billing/monitoring."""
        success = [r for r in self.records if r.success]
        return {
            "total_calls": len(self.records),
            "successful_calls": len(success),
            "failed_calls": len(self.records) - len(success),
            "total_prompt_tokens": sum(r.prompt_tokens for r in self.records),
            "total_completion_tokens": sum(r.completion_tokens for r in self.records),
            "total_tokens": sum(r.total_tokens for r in self.records),
            "total_cost_usd": round(sum(r.estimated_cost_usd for r in self.records), 6),
            "avg_latency_ms": round(
                sum(r.latency_ms for r in success) / len(success), 1
            ) if success else 0,
            "by_caller": self._stats_by_caller(),
        }

    def _stats_by_caller(self) -> dict[str, dict[str, Any]]:
        callers: dict[str, list[LLMCallRecord]] = {}
        for r in self.records:
            callers.setdefault(r.caller, []).append(r)
        return {
            caller: {
                "calls": len(recs),
                "tokens": sum(r.total_tokens for r in recs),
                "cost_usd": round(sum(r.estimated_cost_usd for r in recs), 6),
            }
            for caller, recs in callers.items()
        }
```

### Step 4: Run tests to verify they pass

Run: `cd rag_engine && python -m pytest tests/test_llm_middleware.py -v`
Expected: ALL PASS

### Step 5: Commit

```bash
git add rag_engine/llm_middleware.py rag_engine/tests/test_llm_middleware.py
git commit -m "feat(rag): add LLM middleware for logging, token tracking, error standardization"
```

---

## Task 2: Self-Correction Loop — Proposal RAG

**Files:**
- Modify: `rag_engine/section_writer.py` (add `rewrite_section`)
- Modify: `rag_engine/proposal_orchestrator.py` (add per-section quality check + rewrite)
- Modify: `rag_engine/proposal_orchestrator.py:ProposalResult` (add `residual_issues` field)
- Test: `rag_engine/tests/test_self_correction.py`

### Step 1: Write the failing tests

```python
# rag_engine/tests/test_self_correction.py
"""Self-Correction Loop tests — quality check → rewrite → residual tagging."""
from unittest.mock import patch, MagicMock

import pytest

from section_writer import rewrite_section
from knowledge_models import ProposalSection, KnowledgeUnit, KnowledgeCategory, SourceType
from quality_checker import QualityIssue


class TestRewriteSection:
    def test_rewrite_injects_issues_into_prompt(self):
        section = ProposalSection(
            name="기술적 접근방안",
            evaluation_item="시스템 구축",
            max_score=20,
            weight=0.3,
        )
        issues = [
            QualityIssue(
                category="blind_violation",
                severity="critical",
                detail="회사명 '삼성전자' 이 제안서 본문에 노출됨",
                suggestion="'삼성전자'를 '당사'로 교체",
            )
        ]
        original_text = "삼성전자는 이 사업을 수행할 능력이 있습니다."

        with patch("section_writer._call_llm_for_section") as mock_llm:
            mock_llm.return_value = "당사는 이 사업을 수행할 능력이 있습니다."
            result = rewrite_section(
                section=section,
                rfp_context="테스트 RFP",
                knowledge=[],
                company_context="",
                original_text=original_text,
                issues=issues,
            )
            assert result == "당사는 이 사업을 수행할 능력이 있습니다."
            # Verify issues were included in prompt
            call_args = mock_llm.call_args[0][0]
            assert "blind_violation" in call_args
            assert "삼성전자" in call_args


class TestOrchestratorSelfCorrection:
    @patch("proposal_orchestrator.write_section")
    @patch("proposal_orchestrator.check_quality")
    @patch("proposal_orchestrator.rewrite_section")
    def test_critical_triggers_rewrite(self, mock_rewrite, mock_check, mock_write):
        from proposal_orchestrator import _write_and_check_section
        from knowledge_models import ProposalSection

        section = ProposalSection(
            name="테스트", evaluation_item="테스트", max_score=10, weight=0.1
        )
        mock_write.return_value = "bad text with 회사명"
        mock_check.return_value = [
            QualityIssue(
                category="blind_violation", severity="critical",
                detail="회사명 노출", suggestion="교체 필요",
            )
        ]
        mock_rewrite.return_value = "fixed text"

        name, text, residuals = _write_and_check_section(
            section=section, rfp_context="", knowledge=[], company_context="",
            api_key=None, profile_md="", company_name="테스트회사",
        )
        assert text == "fixed text"
        mock_rewrite.assert_called_once()

    @patch("proposal_orchestrator.write_section")
    @patch("proposal_orchestrator.check_quality")
    def test_warning_skips_rewrite(self, mock_check, mock_write):
        from proposal_orchestrator import _write_and_check_section
        from knowledge_models import ProposalSection

        section = ProposalSection(
            name="테스트", evaluation_item="테스트", max_score=10, weight=0.1
        )
        mock_write.return_value = "최고 수준의 기술력"
        mock_check.return_value = [
            QualityIssue(
                category="vague_claim", severity="warning",
                detail="근거 없는 추상 표현", suggestion="수치 추가",
            )
        ]

        name, text, residuals = _write_and_check_section(
            section=section, rfp_context="", knowledge=[], company_context="",
            api_key=None, profile_md="", company_name=None,
        )
        assert text == "최고 수준의 기술력"  # No rewrite
        assert len(residuals) == 0  # warnings not in residuals

    @patch("proposal_orchestrator.write_section")
    @patch("proposal_orchestrator.check_quality")
    @patch("proposal_orchestrator.rewrite_section")
    def test_residual_critical_after_rewrite(self, mock_rewrite, mock_check, mock_write):
        from proposal_orchestrator import _write_and_check_section
        from knowledge_models import ProposalSection

        section = ProposalSection(
            name="테스트", evaluation_item="테스트", max_score=10, weight=0.1
        )
        mock_write.return_value = "bad text"
        # First check: critical
        # Second check (after rewrite): still critical
        mock_check.side_effect = [
            [QualityIssue(category="blind_violation", severity="critical",
                          detail="회사명 노출", suggestion="교체")],
            [QualityIssue(category="blind_violation", severity="critical",
                          detail="회사명 여전히 노출", suggestion="교체")],
        ]
        mock_rewrite.return_value = "still bad text"

        name, text, residuals = _write_and_check_section(
            section=section, rfp_context="", knowledge=[], company_context="",
            api_key=None, profile_md="", company_name="회사명",
        )
        assert text == "still bad text"
        assert len(residuals) == 1  # Residual tagged
        assert residuals[0].category == "blind_violation"
```

### Step 2: Run tests to verify they fail

Run: `cd rag_engine && python -m pytest tests/test_self_correction.py -v`
Expected: FAIL with `ImportError: cannot import name 'rewrite_section'`

### Step 3: Implement rewrite_section in section_writer.py

Add to `rag_engine/section_writer.py` after `write_section()`:

```python
def rewrite_section(
    section: ProposalSection,
    rfp_context: str,
    knowledge: list[KnowledgeUnit],
    company_context: str = "",
    api_key: Optional[str] = None,
    profile_md: str = "",
    original_text: str = "",
    issues: Optional[list] = None,
) -> str:
    """Rewrite a section incorporating quality checker feedback.

    Builds the same prompt as write_section but appends the original text
    and specific issues to fix.
    """
    base_prompt = _assemble_prompt(section, knowledge, rfp_context, company_context, profile_md)

    fix_instructions = []
    for issue in (issues or []):
        fix_instructions.append(
            f"- [{issue.category}] {issue.detail}"
            + (f" → 수정방법: {issue.suggestion}" if issue.suggestion else "")
        )

    rewrite_prompt = (
        base_prompt
        + "\n\n## 이전 생성 결과 (수정 필요):\n"
        + original_text
        + "\n\n## 발견된 문제점 — 반드시 수정하세요:\n"
        + "\n".join(fix_instructions)
        + "\n\n위 문제점을 모두 수정한 새 버전을 작성하세요. 전체 섹션을 다시 작성합니다."
    )

    return _call_llm_for_section(rewrite_prompt, api_key)
```

### Step 4: Implement _write_and_check_section in proposal_orchestrator.py

Add to `rag_engine/proposal_orchestrator.py` before `generate_proposal()`:

```python
from section_writer import write_section, rewrite_section

def _write_and_check_section(
    *,
    section,
    rfp_context: str,
    knowledge: list,
    company_context: str,
    api_key,
    profile_md: str,
    company_name: str | None,
) -> tuple[str, str, list[QualityIssue]]:
    """Write section, quality check, rewrite if critical issues found.

    Returns (section_name, text, residual_critical_issues).
    """
    text = write_section(
        section=section,
        rfp_context=rfp_context,
        knowledge=knowledge,
        company_context=company_context,
        api_key=api_key,
        profile_md=profile_md,
    )

    issues = check_quality(text, company_name=company_name)
    critical = [i for i in issues if i.severity == "critical"]

    if not critical:
        return section.name, text, []

    # One rewrite attempt for critical issues
    text = rewrite_section(
        section=section,
        rfp_context=rfp_context,
        knowledge=knowledge,
        company_context=company_context,
        api_key=api_key,
        profile_md=profile_md,
        original_text=text,
        issues=critical,
    )

    # Check again — residuals are logged but don't block
    remaining = check_quality(text, company_name=company_name)
    residuals = [i for i in remaining if i.severity == "critical"]

    return section.name, text, residuals
```

Update `generate_proposal()` to use `_write_and_check_section` in the parallel loop and add `residual_issues` to ProposalResult:

```python
@dataclass
class ProposalResult:
    docx_path: str = ""
    hwpx_path: str = ""
    sections: list[tuple[str, str]] = field(default_factory=list)
    outline: Optional[ProposalOutline] = None
    quality_issues: list[QualityIssue] = field(default_factory=list)
    residual_issues: list[QualityIssue] = field(default_factory=list)  # NEW
    generation_time_sec: float = 0.0
```

In `generate_proposal()`, replace `_write_one` with:

```python
    def _write_one(section):
        knowledge = kb.search(f"{section.name} {section.evaluation_item}", top_k=10)
        name, text, residuals = _write_and_check_section(
            section=section,
            rfp_context=rfp_context,
            knowledge=knowledge,
            company_context=company_context,
            api_key=api_key,
            profile_md=profile_md,
            company_name=company_name,
        )
        return name, text, residuals

    results_map: dict[str, str] = {}
    all_residuals: list[QualityIssue] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_write_one, s): s for s in outline.sections}
        for future in as_completed(futures):
            name, text, residuals = future.result()
            results_map[name] = text
            all_residuals.extend(residuals)
```

And in the return:

```python
    return ProposalResult(
        ...
        quality_issues=quality_issues,
        residual_issues=all_residuals,
        ...
    )
```

### Step 5: Run tests to verify they pass

Run: `cd rag_engine && python -m pytest tests/test_self_correction.py -v`
Expected: ALL PASS

### Step 6: Run existing tests to check no regressions

Run: `cd rag_engine && python -m pytest -q`
Expected: All existing tests pass

### Step 7: Commit

```bash
git add rag_engine/section_writer.py rag_engine/proposal_orchestrator.py rag_engine/tests/test_self_correction.py
git commit -m "feat(rag): add self-correction loop — quality check → 1x rewrite for critical issues"
```

---

## Task 3: Planning Agent — Proposal RAG

**Files:**
- Create: `rag_engine/proposal_agent.py`
- Modify: `rag_engine/knowledge_models.py` (add StrategyMemo, ProposalStrategy)
- Modify: `rag_engine/section_writer.py` (add strategy_memo parameter)
- Modify: `rag_engine/proposal_orchestrator.py` (integrate agent)
- Test: `rag_engine/tests/test_proposal_agent.py`

### Step 1: Add data models to knowledge_models.py

Add at end of `rag_engine/knowledge_models.py`:

```python
@dataclass
class StrategyMemo:
    """Per-section strategy generated by ProposalPlanningAgent."""
    section_name: str
    emphasis_points: list[str] = field(default_factory=list)
    differentiators: list[str] = field(default_factory=list)
    risk_notes: list[str] = field(default_factory=list)
    knowledge_hints: list[str] = field(default_factory=list)


@dataclass
class ProposalStrategy:
    """Complete proposal strategy from Planning Agent."""
    overall_approach: str = ""
    strengths_mapping: dict = field(default_factory=dict)
    section_strategies: list[StrategyMemo] = field(default_factory=list)

    def get_memo_for(self, section_name: str) -> StrategyMemo | None:
        for memo in self.section_strategies:
            if memo.section_name == section_name:
                return memo
        return None
```

### Step 2: Write the failing tests

```python
# rag_engine/tests/test_proposal_agent.py
"""Planning Agent tests — strategy generation, JSON parsing, fallback."""
import json
from unittest.mock import patch, MagicMock

import pytest

from proposal_agent import ProposalPlanningAgent
from knowledge_models import ProposalStrategy, StrategyMemo, ProposalOutline, ProposalSection


SAMPLE_RFX = {
    "title": "XX 교통관제시스템 구축",
    "issuing_org": "국토교통부",
    "evaluation_criteria": [
        {"category": "기술적 접근방안", "max_score": 30, "description": "시스템 구축"},
        {"category": "수행관리", "max_score": 20, "description": "프로젝트 관리"},
    ],
}


class TestPlanningAgent:
    def test_generate_strategy_parses_json(self):
        agent = ProposalPlanningAgent()
        mock_json = json.dumps({
            "overall_approach": "교통 전문성 강조",
            "strengths_mapping": {"ITS 경험": "기술적 접근방안"},
            "section_strategies": [
                {
                    "section_name": "기술적 접근방안",
                    "emphasis_points": ["ITS 특허 3건"],
                    "differentiators": ["유지보수 인력 2배"],
                    "risk_notes": ["예산 초과 주의"],
                    "knowledge_hints": ["교통신호제어"],
                },
            ],
        })

        with patch.object(agent, "_call_llm", return_value=mock_json):
            outline = ProposalOutline(
                title="테스트", issuing_org="테스트",
                sections=[
                    ProposalSection(name="기술적 접근방안", evaluation_item="시스템 구축",
                                    max_score=30, weight=0.6),
                ],
            )
            strategy = agent.generate_strategy(
                rfx_result=SAMPLE_RFX,
                outline=outline,
                company_context="ITS 10년 경력",
            )
            assert strategy.overall_approach == "교통 전문성 강조"
            memo = strategy.get_memo_for("기술적 접근방안")
            assert memo is not None
            assert "ITS 특허 3건" in memo.emphasis_points

    def test_generate_strategy_json_parse_error_fallback(self):
        agent = ProposalPlanningAgent()

        with patch.object(agent, "_call_llm", return_value="not valid json {{{"):
            outline = ProposalOutline(
                title="테스트", issuing_org="테스트",
                sections=[
                    ProposalSection(name="테스트섹션", evaluation_item="테스트",
                                    max_score=10, weight=0.5),
                ],
            )
            strategy = agent.generate_strategy(
                rfx_result=SAMPLE_RFX,
                outline=outline,
                company_context="",
            )
            # Fallback: empty strategy (no crash)
            assert strategy.overall_approach == ""
            assert len(strategy.section_strategies) == 0

    def test_get_memo_for_missing_section(self):
        strategy = ProposalStrategy(
            overall_approach="test",
            section_strategies=[
                StrategyMemo(section_name="A", emphasis_points=["x"]),
            ],
        )
        assert strategy.get_memo_for("B") is None
```

### Step 3: Run tests to verify they fail

Run: `cd rag_engine && python -m pytest tests/test_proposal_agent.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'proposal_agent'`

### Step 4: Write implementation

```python
# rag_engine/proposal_agent.py
"""Proposal Planning Agent — strategic analysis before section writing.

Generates ProposalStrategy with per-section StrategyMemos via single LLM call.
Falls back to empty strategy on parse failure (graceful degradation).
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from openai import OpenAI

from knowledge_models import (
    ProposalOutline,
    ProposalStrategy,
    StrategyMemo,
)
from llm_utils import call_with_retry, LLM_DEFAULT_TIMEOUT

logger = logging.getLogger(__name__)

STRATEGY_SYSTEM_PROMPT = """당신은 대한민국 공공조달 입찰 전략 수립 전문가입니다.
RFP 분석 결과와 회사 역량을 바탕으로 제안서 전략을 수립합니다.

반드시 아래 JSON 형식으로만 응답하세요. 설명이나 마크다운 없이 JSON만:

{
  "overall_approach": "전체 제안 전략 요약 (1-2문장)",
  "strengths_mapping": {"회사강점1": "매핑될 평가항목", ...},
  "section_strategies": [
    {
      "section_name": "정확한 섹션 이름",
      "emphasis_points": ["이 섹션에서 강조할 포인트"],
      "differentiators": ["경쟁 차별화 요소"],
      "risk_notes": ["주의사항"],
      "knowledge_hints": ["Layer1 검색 키워드 힌트"]
    }
  ]
}"""

FEW_SHOT_EXAMPLE = """예시 응답:
{
  "overall_approach": "스마트시티 특화 기술력과 10년 ITS 실적을 앞세워 기술점수 극대화",
  "strengths_mapping": {
    "ITS 구축 실적 50건": "기술적 접근방안",
    "PM 자격 보유 인력 3명": "수행관리"
  },
  "section_strategies": [
    {
      "section_name": "기술적 접근방안",
      "emphasis_points": ["자체 특허 3건 활용 방안", "유사 사업 성공 사례 제시"],
      "differentiators": ["경쟁사 대비 유지보수 인력 2배"],
      "risk_notes": ["예산 범위 내 기술 제안 필수"],
      "knowledge_hints": ["교통신호제어", "ITS 아키텍처"]
    }
  ]
}"""


class ProposalPlanningAgent:
    """Strategic planning agent for proposal generation.

    Phase 1+2 combined: single LLM call generates full ProposalStrategy JSON.
    Falls back to empty strategy on parse failure.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")

    def generate_strategy(
        self,
        rfx_result: dict[str, Any],
        outline: ProposalOutline,
        company_context: str = "",
    ) -> ProposalStrategy:
        """Generate complete proposal strategy in one LLM call."""
        section_names = [s.name for s in outline.sections]
        section_info = "\n".join(
            f"- {s.name} (배점 {s.max_score}점, 비중 {s.weight:.0%}): {s.evaluation_item}"
            for s in outline.sections
        )

        user_prompt = (
            f"## RFP 정보\n"
            f"공고명: {rfx_result.get('title', '')}\n"
            f"발주기관: {rfx_result.get('issuing_org', '')}\n"
            f"예산: {rfx_result.get('budget', '미정')}\n"
            f"사업기간: {rfx_result.get('project_period', '미정')}\n\n"
            f"## 평가항목\n{section_info}\n\n"
            f"## 회사 역량\n{company_context or '정보 없음'}\n\n"
            f"{FEW_SHOT_EXAMPLE}\n\n"
            f"위 정보를 바탕으로 제안서 전략을 수립하세요. "
            f"section_strategies의 section_name은 반드시 다음 목록에서 선택: {section_names}"
        )

        raw = self._call_llm(user_prompt)
        return self._parse_strategy(raw)

    def _call_llm(self, user_prompt: str) -> str:
        client = OpenAI(api_key=self.api_key, timeout=LLM_DEFAULT_TIMEOUT)

        def _do_call():
            return client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": STRATEGY_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=3000,
            )

        resp = call_with_retry(_do_call)
        return resp.choices[0].message.content or ""

    def _parse_strategy(self, raw: str) -> ProposalStrategy:
        """Parse JSON response into ProposalStrategy. Fallback to empty on failure."""
        try:
            # Strip markdown code fences if present
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()

            data = json.loads(cleaned)

            sections = []
            for s in data.get("section_strategies", []):
                sections.append(StrategyMemo(
                    section_name=s.get("section_name", ""),
                    emphasis_points=s.get("emphasis_points", []),
                    differentiators=s.get("differentiators", []),
                    risk_notes=s.get("risk_notes", []),
                    knowledge_hints=s.get("knowledge_hints", []),
                ))

            return ProposalStrategy(
                overall_approach=data.get("overall_approach", ""),
                strengths_mapping=data.get("strengths_mapping", {}),
                section_strategies=sections,
            )

        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.warning("Strategy JSON parse failed, using empty strategy: %s", exc)
            return ProposalStrategy()
```

### Step 5: Update section_writer.py — add strategy_memo parameter

Add `strategy_memo` to both `_assemble_prompt` and `write_section`:

In `_assemble_prompt`, after the profile block and before RFP context:

```python
    # Strategy memo (from Planning Agent)
    if strategy_memo:
        memo_parts = []
        if strategy_memo.emphasis_points:
            memo_parts.append("강조 포인트: " + ", ".join(strategy_memo.emphasis_points))
        if strategy_memo.differentiators:
            memo_parts.append("차별화 요소: " + ", ".join(strategy_memo.differentiators))
        if strategy_memo.risk_notes:
            memo_parts.append("주의사항: " + ", ".join(strategy_memo.risk_notes))
        parts.append("## 이 섹션의 전략 (반드시 반영):\n" + "\n".join(memo_parts))
```

Update `write_section` signature:

```python
def write_section(
    section: ProposalSection,
    rfp_context: str,
    knowledge: list[KnowledgeUnit],
    company_context: str = "",
    api_key: Optional[str] = None,
    profile_md: str = "",
    strategy_memo: Optional[StrategyMemo] = None,  # NEW
) -> str:
```

### Step 6: Integrate agent into proposal_orchestrator.py

In `generate_proposal()`, after building outline (step 1) and before writing sections:

```python
    # 1.5. Planning Agent — generate strategy
    strategy = ProposalStrategy()
    try:
        from proposal_agent import ProposalPlanningAgent
        agent = ProposalPlanningAgent(api_key=api_key)
        strategy = agent.generate_strategy(
            rfx_result=rfx_result,
            outline=outline,
            company_context=company_context,
        )
        if strategy.overall_approach:
            import logging
            logging.getLogger(__name__).info("Strategy: %s", strategy.overall_approach)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Planning agent skipped: %s", exc)
```

Update `_write_and_check_section` and `_write_one` to accept and pass `strategy_memo`:

```python
    def _write_one(section):
        knowledge = kb.search(f"{section.name} {section.evaluation_item}", top_k=10)
        memo = strategy.get_memo_for(section.name)
        name, text, residuals = _write_and_check_section(
            section=section,
            rfp_context=rfp_context,
            knowledge=knowledge,
            company_context=company_context,
            api_key=api_key,
            profile_md=profile_md,
            company_name=company_name,
            strategy_memo=memo,
        )
        return name, text, residuals
```

### Step 7: Run tests

Run: `cd rag_engine && python -m pytest tests/test_proposal_agent.py tests/test_self_correction.py -v`
Expected: ALL PASS

### Step 8: Run full test suite

Run: `cd rag_engine && python -m pytest -q`
Expected: All tests pass

### Step 9: Commit

```bash
git add rag_engine/proposal_agent.py rag_engine/knowledge_models.py rag_engine/section_writer.py rag_engine/proposal_orchestrator.py rag_engine/tests/test_proposal_agent.py
git commit -m "feat(rag): add Planning Agent — strategic proposal planning with per-section memos"
```

---

## Task 4: ReAct Pattern — Chat RAG

**Files:**
- Create: `services/web_app/react_chat.py`
- Modify: `chat_tools.py` (add `need_more_context` tool)
- Modify: `services/web_app/main.py` (delegate to react loop)
- Test: `tests/test_react_chat.py`

### Step 1: Add need_more_context tool to chat_tools.py

Append to `CHAT_TOOLS` list in `chat_tools.py`:

```python
    {
        "type": "function",
        "function": {
            "name": "need_more_context",
            "description": (
                "현재 컨텍스트로 충분한 답변이 불가능할 때 사용. "
                "다른 검색어나 문서 범위로 재검색 요청."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "왜 현재 컨텍스트가 불충분한지 설명",
                    },
                    "suggested_query": {
                        "type": "string",
                        "description": "재검색할 쿼리 (더 구체적이거나 다른 각도)",
                    },
                    "search_scope": {
                        "type": "string",
                        "enum": ["company", "rfx", "both"],
                        "description": "재검색 대상 (회사문서/RFx/둘다)",
                    },
                },
                "required": ["reason", "suggested_query", "search_scope"],
            },
        },
    },
```

Update `parse_tool_call_result` to handle `need_more_context`:

```python
    if tool_name == "need_more_context":
        reason = str(args.get("reason", ""))
        suggested_query = str(args.get("suggested_query", ""))
        search_scope = str(args.get("search_scope", "both"))
        # Return as special marker — caller (react loop) will handle
        return tool_name, suggested_query, [{"reason": reason, "scope": search_scope}]
```

### Step 2: Write the failing tests

```python
# tests/test_react_chat.py
"""ReAct Chat Loop tests — early exit, re-search, max turns."""
from unittest.mock import patch, MagicMock, AsyncMock

import pytest


class TestReActLoop:
    def test_early_exit_on_document_qa(self):
        """Turn 1 returns document_qa → immediate return, no loop."""
        from services.web_app.react_chat import react_chat_loop

        with patch("services.web_app.react_chat._single_turn") as mock_turn:
            mock_turn.return_value = ("document_qa", "답변입니다.", [{"page": 1, "text": "ref"}])

            tool, answer, refs = react_chat_loop(
                api_key="test",
                message="자격요건 알려줘",
                company_context_text="회사 정보",
                rfx_context_text="RFx 내용",
                session=MagicMock(),
            )
            assert tool == "document_qa"
            assert answer == "답변입니다."
            assert mock_turn.call_count == 1  # Only 1 turn

    def test_react_loop_on_need_more_context(self):
        """Turn 1 returns need_more_context → Turn 2 with new query."""
        from services.web_app.react_chat import react_chat_loop

        with patch("services.web_app.react_chat._single_turn") as mock_turn, \
             patch("services.web_app.react_chat._rebuild_context") as mock_rebuild:
            # Turn 1: need more context
            # Turn 2: successful answer
            mock_turn.side_effect = [
                ("need_more_context", "자격요건 상세", [{"reason": "불충분", "scope": "rfx"}]),
                ("document_qa", "상세 답변", [{"page": 5, "text": "상세 ref"}]),
            ]
            mock_rebuild.return_value = ("회사ctx", "새RFx ctx")

            tool, answer, refs = react_chat_loop(
                api_key="test",
                message="복합 질문",
                company_context_text="",
                rfx_context_text="",
                session=MagicMock(),
            )
            assert tool == "document_qa"
            assert answer == "상세 답변"
            assert mock_turn.call_count == 2

    def test_max_3_turns_forced_exit(self):
        """After 3 turns of need_more_context, force final answer."""
        from services.web_app.react_chat import react_chat_loop

        with patch("services.web_app.react_chat._single_turn") as mock_turn, \
             patch("services.web_app.react_chat._rebuild_context") as mock_rebuild, \
             patch("services.web_app.react_chat._force_final_answer") as mock_force:
            mock_turn.side_effect = [
                ("need_more_context", "q1", [{"reason": "r1", "scope": "rfx"}]),
                ("need_more_context", "q2", [{"reason": "r2", "scope": "both"}]),
            ]
            mock_rebuild.return_value = ("", "")
            mock_force.return_value = ("document_qa", "강제 답변", [])

            tool, answer, refs = react_chat_loop(
                api_key="test",
                message="매우 복합적 질문",
                company_context_text="",
                rfx_context_text="",
                session=MagicMock(),
                max_turns=3,
            )
            assert answer == "강제 답변"
            assert mock_force.call_count == 1
```

### Step 3: Run tests to verify they fail

Run: `cd /Users/min-kyungwook/Desktop/MS_SOLUTIONS && python -m pytest tests/test_react_chat.py -v`
Expected: FAIL with `ModuleNotFoundError`

### Step 4: Write implementation

```python
# services/web_app/react_chat.py
"""ReAct Chat Loop — Reasoning + Acting pattern for Chat RAG.

Wraps the existing Tool Use call with a max-3-turn loop.
Early exit when LLM provides a direct answer (document_qa, general_response, etc.).
Re-search with LLM-generated query when need_more_context is triggered.
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Tools without need_more_context (for forced final turn)
FINAL_TURN_TOOLS: list[str] = ["document_qa", "general_response", "bid_search", "bid_analyze"]


def react_chat_loop(
    *,
    api_key: str,
    message: str,
    company_context_text: str,
    rfx_context_text: str,
    session: Any,
    max_turns: int = 3,
) -> tuple[str, str, list[dict[str, Any]]]:
    """ReAct loop: Reason → Act → Observe → Repeat (max 3 turns).

    Returns (tool_name, answer, references).
    Most queries resolve in Turn 1 (early exit).
    """
    current_company_ctx = company_context_text
    current_rfx_ctx = rfx_context_text
    current_message = message

    for turn in range(max_turns - 1):  # Reserve last turn for forced answer
        tool_name, answer, refs = _single_turn(
            api_key=api_key,
            message=current_message,
            company_context_text=current_company_ctx,
            rfx_context_text=current_rfx_ctx,
            session=session,
            include_need_more=True,
        )

        if tool_name != "need_more_context":
            logger.info("ReAct resolved in turn %d: %s", turn + 1, tool_name)
            return tool_name, answer, refs

        # Observation: need more context
        suggested_query = answer  # answer field carries suggested_query
        scope = refs[0].get("scope", "both") if refs else "both"
        reason = refs[0].get("reason", "") if refs else ""
        logger.info(
            "ReAct turn %d: need_more_context (reason=%s, query=%s, scope=%s)",
            turn + 1, reason, suggested_query, scope,
        )

        # Re-search with suggested query
        current_company_ctx, current_rfx_ctx = _rebuild_context(
            session=session,
            query=suggested_query,
            scope=scope,
        )
        current_message = f"{message}\n\n[이전 검색에서 불충분했던 이유: {reason}]"

    # Final turn: forced answer (no need_more_context tool)
    return _force_final_answer(
        api_key=api_key,
        message=current_message,
        company_context_text=current_company_ctx,
        rfx_context_text=current_rfx_ctx,
        session=session,
    )


def _single_turn(
    *,
    api_key: str,
    message: str,
    company_context_text: str,
    rfx_context_text: str,
    session: Any,
    include_need_more: bool = True,
) -> tuple[str, str, list[dict[str, Any]]]:
    """Execute one Tool Use call. Delegates to existing logic."""
    from chat_tools import CHAT_TOOLS, TOOL_USE_SYSTEM_PROMPT, parse_tool_call_result
    from openai import OpenAI

    tools = CHAT_TOOLS if include_need_more else [
        t for t in CHAT_TOOLS if t["function"]["name"] != "need_more_context"
    ]

    # Build system prompt (same as _generate_chat_answer_with_tools)
    matching_context = ""
    if hasattr(session, "latest_matching_result") and session.latest_matching_result:
        m = session.latest_matching_result
        matching_context = (
            f"적합도: {m.overall_score:.0f}%, 추천: {m.recommendation}, "
            f"충족/부분/미충족: {m.met_count}/{m.partially_met_count}/{m.not_met_count}"
        )

    rfx_meta = ""
    if hasattr(session, "latest_rfx_analysis") and session.latest_rfx_analysis:
        a = session.latest_rfx_analysis
        rfx_meta = f"공고명: {a.title}, 발주기관: {a.issuing_org}, 마감일: {a.deadline}"

    ctx_parts: list[str] = []
    if company_context_text:
        ctx_parts.append(f"\n### 회사 정보\n{company_context_text}")
    if rfx_context_text:
        ctx_parts.append(f"\n### RFx 원문\n{rfx_context_text}")
    if rfx_meta:
        ctx_parts.append(f"\n### RFx 메타\n{rfx_meta}")
    if matching_context:
        ctx_parts.append(f"\n### 매칭 요약\n{matching_context}")
    if not ctx_parts:
        ctx_parts.append("\n### 문서 컨텍스트: 없음")

    full_system = TOOL_USE_SYSTEM_PROMPT + "\n".join(ctx_parts)

    model = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        max_tokens=4096,
        temperature=0.3,
        tools=tools,
        tool_choice="required",
        messages=[
            {"role": "system", "content": full_system},
            {"role": "user", "content": message},
        ],
    )
    return parse_tool_call_result(response.choices[0].message)


def _rebuild_context(
    session: Any,
    query: str,
    scope: str,
) -> tuple[str, str]:
    """Re-search RAG with the suggested query."""
    company_text = ""
    rfx_text = ""

    try:
        if scope in ("company", "both") and hasattr(session, "rag_engine"):
            results = session.rag_engine.search(query, top_k=12)
            if results:
                chunks = []
                for doc, meta in results:
                    src = meta.get("source_file", "unknown")
                    page = meta.get("page_number", "?")
                    chunks.append(f"[{src}, 페이지 {page}]\n{doc}")
                company_text = "\n---\n".join(chunks)

        if scope in ("rfx", "both") and hasattr(session, "rfx_rag_engine"):
            results = session.rfx_rag_engine.search(query, top_k=12)
            if results:
                chunks = []
                for doc, meta in results:
                    src = meta.get("source_file", "unknown")
                    page = meta.get("page_number", "?")
                    chunks.append(f"[{src}, 페이지 {page}]\n{doc}")
                rfx_text = "\n---\n".join(chunks)
    except Exception as exc:
        logger.warning("ReAct rebuild_context error: %s", exc)

    return company_text, rfx_text


def _force_final_answer(
    *,
    api_key: str,
    message: str,
    company_context_text: str,
    rfx_context_text: str,
    session: Any,
) -> tuple[str, str, list[dict[str, Any]]]:
    """Final turn without need_more_context tool — must give an answer."""
    return _single_turn(
        api_key=api_key,
        message=message,
        company_context_text=company_context_text,
        rfx_context_text=rfx_context_text,
        session=session,
        include_need_more=False,
    )
```

### Step 5: Update main.py to delegate to react loop

Replace `_generate_chat_answer_with_tools` call in `/api/chat` endpoint with `react_chat_loop`:

In `services/web_app/main.py`, at the point where `_generate_chat_answer_with_tools` is called (around the chat endpoint), add import and replace:

```python
from services.web_app.react_chat import react_chat_loop

# Replace:
# tool_name, answer, references = _generate_chat_answer_with_tools(...)
# With:
tool_name, answer, references = react_chat_loop(
    api_key=api_key,
    message=message,
    company_context_text=company_context_text,
    rfx_context_text=rfx_context_text,
    session=session,
)
```

Keep `_generate_chat_answer_with_tools` as-is for backward compatibility.

### Step 6: Run tests

Run: `cd /Users/min-kyungwook/Desktop/MS_SOLUTIONS && python -m pytest tests/test_react_chat.py -v`
Expected: ALL PASS

### Step 7: Run full test suite

Run: `cd /Users/min-kyungwook/Desktop/MS_SOLUTIONS && python -m pytest -q && cd rag_engine && python -m pytest -q`
Expected: All tests pass

### Step 8: Commit

```bash
git add services/web_app/react_chat.py chat_tools.py services/web_app/main.py tests/test_react_chat.py
git commit -m "feat(chat): add ReAct pattern — multi-turn reasoning with re-search capability"
```

---

## Task 5: Integration — Middleware 연결

**Files:**
- Modify: `rag_engine/section_writer.py` (wrap LLM call with middleware)
- Modify: `rag_engine/proposal_agent.py` (wrap LLM call with middleware)
- Modify: `rag_engine/proposal_orchestrator.py` (create middleware instance, pass to writers)

### Step 1: Wire middleware into section_writer

In `section_writer.py`, update `_call_llm_for_section` to accept optional middleware:

```python
def _call_llm_for_section(prompt: str, api_key: Optional[str] = None, middleware=None) -> str:
    client = OpenAI(
        api_key=api_key or os.environ.get("OPENAI_API_KEY"),
        timeout=LLM_DEFAULT_TIMEOUT,
    )

    def _do_call():
        return client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=4000,
        )

    fn = _do_call
    if middleware:
        fn = middleware.wrap(_do_call, caller_name="section_writer")
    resp = call_with_retry(fn)
    return resp.choices[0].message.content or ""
```

### Step 2: Wire middleware into proposal_orchestrator

In `generate_proposal()`, create middleware at start and pass through:

```python
    # 0.5. Initialize middleware
    from llm_middleware import LLMMiddleware
    middleware = LLMMiddleware()
```

Pass `middleware` through `_write_one` → `_write_and_check_section` → `write_section`/`rewrite_section`.

At the end, log stats:

```python
    stats = middleware.get_session_stats()
    import logging
    logging.getLogger(__name__).info("LLM stats: %s", stats)
```

### Step 3: Run full test suite

Run: `cd rag_engine && python -m pytest -q`
Expected: All tests pass

### Step 4: Commit

```bash
git add rag_engine/section_writer.py rag_engine/proposal_agent.py rag_engine/proposal_orchestrator.py
git commit -m "feat(rag): wire LLM middleware into proposal pipeline for observability"
```

---

## Task 6: Code Review + Flow Review

**Both RAG systems — user perspective review.**

### Step 1: Run full test suite

```bash
cd /Users/min-kyungwook/Desktop/MS_SOLUTIONS
python -m pytest -q
cd rag_engine && python -m pytest -q
```

Expected: All tests pass

### Step 2: Dispatch code-reviewer subagent

Use superpowers:code-reviewer to review all changes since the design docs commit.

Focus areas:
- Self-correction loop: does 1-rewrite actually fix issues?
- Planning Agent: does JSON parsing handle edge cases?
- Middleware: is token tracking accurate?
- ReAct: does early exit work correctly?
- Thread safety: any new shared state?
- Import cycles: any circular dependencies?

### Step 3: Fix any issues found

### Step 4: Commit fixes

---

## Task 7: RAG Architecture Documentation Update

**Files:**
- Modify: `docs/plans/2026-03-01-kira-rag-architecture.md` (add implementation results)

### Step 1: Update architecture doc with actual implementation details

- Add section: "구현 결과" with actual test counts, file paths, code examples
- Update any diagrams that changed during implementation

### Step 2: Commit

```bash
git add docs/plans/2026-03-01-kira-rag-architecture.md
git commit -m "docs: update RAG architecture doc with implementation results"
```
