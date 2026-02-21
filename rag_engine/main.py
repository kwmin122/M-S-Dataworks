"""
rag_engine/main.py

FastAPI microservice wrapping the Kira Bot RAG pipeline.

Endpoints:
  GET  /health            → {"status": "ok"}
  POST /api/analyze-bid   → AnalyzeBidResponse

The RAG stack (ChromaDB, OpenAI, rank_bm25) is loaded lazily.
If any dependency is missing at startup the service still boots and
returns HTTP 503 on /api/analyze-bid with a descriptive error.
"""

import logging
import os
import sys
import traceback
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from models import AnalyzeBidRequest, AnalyzeBidResponse

logger = logging.getLogger("rag_engine")
logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------------------------------
# Engine state — populated during lifespan startup
# ---------------------------------------------------------------------------

_engine_error: str | None = None       # set if import/init fails
_rfx_analyzer_cls = None               # RFxAnalyzer class
_rag_engine_cls = None                 # RAGEngine class
_qualification_matcher_cls = None      # QualificationMatcher class
_matching_result_cls = None            # MatchingResult (for type hints only)


# ---------------------------------------------------------------------------
# Lifespan: attempt to import the RAG stack once at boot
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _engine_error, _rfx_analyzer_cls, _rag_engine_cls, _qualification_matcher_cls

    # rag_engine/ is the working directory inside Docker; the copied source
    # files (engine.py, matcher.py, rfx_analyzer.py …) live in the same dir.
    this_dir = os.path.dirname(os.path.abspath(__file__))
    if this_dir not in sys.path:
        sys.path.insert(0, this_dir)

    try:
        from rfx_analyzer import RFxAnalyzer          # noqa: F401
        from engine import RAGEngine                   # noqa: F401
        from matcher import QualificationMatcher       # noqa: F401

        _rfx_analyzer_cls = RFxAnalyzer
        _rag_engine_cls = RAGEngine
        _qualification_matcher_cls = QualificationMatcher
        logger.info("RAG engine stack imported successfully.")
    except ImportError as exc:
        _engine_error = f"ImportError during startup: {exc}"
        logger.warning(_engine_error)
    except Exception as exc:
        _engine_error = f"Unexpected error during startup: {exc}"
        logger.error(_engine_error)

    yield  # application runs here


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Kira RAG Engine",
    description="Bid qualification analysis microservice",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe. Always returns 200 while the process is alive."""
    return {"status": "ok"}


@app.post("/api/analyze-bid", response_model=AnalyzeBidResponse)
async def analyze_bid(request: AnalyzeBidRequest) -> AnalyzeBidResponse:
    """
    Analyze bid eligibility for a given company.

    Flow:
    1. Use RFxAnalyzer.analyze_text() to extract constraints from attachment_text.
    2. Build a temporary in-memory RAGEngine and inject company_facts as text.
    3. Run QualificationMatcher.match() against the extracted RFxAnalysisResult.
    4. Return is_eligible, structured details, and an action_plan.

    Returns HTTP 503 if the RAG stack failed to load at startup.
    """
    if _engine_error:
        raise HTTPException(
            status_code=503,
            detail=f"RAG engine unavailable: {_engine_error}",
        )

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY environment variable is not set.",
        )

    try:
        # ------------------------------------------------------------------
        # Step 1: Extract qualification constraints from the bid attachment
        # ------------------------------------------------------------------
        analyzer: Any = _rfx_analyzer_cls(api_key=api_key)
        rfx_result = analyzer.analyze_text(request.attachment_text)

        # ------------------------------------------------------------------
        # Step 2: Build an in-memory RAG engine and populate with company facts
        # ------------------------------------------------------------------
        # Use a temp collection per request so evaluations are isolated.
        collection_name = f"bid_{request.bid_notice_id}_{request.organization_id}"
        rag: Any = _rag_engine_cls(
            persist_directory="",          # empty → in-memory only
            collection_name=collection_name,
            hybrid_enabled=False,          # BM25 not needed for single-bid eval
        )

        # Serialize company_facts dict into a plain text blob and index it.
        facts_text = _company_facts_to_text(request.company_facts)
        rag.add_text_directly(facts_text, source="company_facts")

        # ------------------------------------------------------------------
        # Step 3: Run the qualification matcher
        # ------------------------------------------------------------------
        matcher: Any = _qualification_matcher_cls(
            rag_engine=rag,
            api_key=api_key,
        )
        matching_result = matcher.match(rfx_result)

        # ------------------------------------------------------------------
        # Step 4: Map MatchingResult → AnalyzeBidResponse
        # ------------------------------------------------------------------
        is_eligible = matching_result.recommendation == "GO"

        details: dict[str, Any] = {
            "recommendation": matching_result.recommendation,
            "overall_score": matching_result.overall_score,
            "met_count": matching_result.met_count,
            "not_met_count": matching_result.not_met_count,
            "partially_met_count": matching_result.partially_met_count,
            "unknown_count": matching_result.unknown_count,
            "mandatory_gaps": [
                {
                    "category": m.requirement.category,
                    "description": m.requirement.description,
                    "status": m.status.value if hasattr(m.status, "value") else str(m.status),
                    "evidence": m.evidence,
                }
                for m in matching_result.mandatory_gaps
            ],
            "rfx_title": matching_result.rfx_title,
            "rfx_org": matching_result.rfx_org,
        }

        action_plan = matching_result.summary or _build_fallback_action_plan(matching_result)

        return AnalyzeBidResponse(
            is_eligible=is_eligible,
            details=details,
            action_plan=action_plan,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("analyze_bid failed: %s\n%s", exc, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _company_facts_to_text(facts: dict[str, Any]) -> str:
    """
    Convert the company_facts dictionary into a human-readable text block
    that the RAG engine can index and the LLM can reason about.
    """
    lines: list[str] = ["[회사 기본 정보]"]
    for key, value in facts.items():
        # Pretty-print nested structures
        if isinstance(value, list):
            lines.append(f"{key}: {', '.join(str(v) for v in value)}")
        elif isinstance(value, dict):
            lines.append(f"{key}:")
            for k2, v2 in value.items():
                lines.append(f"  {k2}: {v2}")
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def _build_fallback_action_plan(result: Any) -> str:
    """
    Generate a minimal action plan string when MatchingResult.summary is empty.
    """
    if result.recommendation == "GO":
        return "자격요건을 모두 충족합니다. 입찰을 진행하십시오."
    if result.recommendation == "NO-GO":
        gaps = [f"- {m.requirement.description}" for m in result.mandatory_gaps]
        gap_text = "\n".join(gaps) if gaps else "세부 내용을 확인하십시오."
        return f"필수 자격요건 미충족으로 입찰이 어렵습니다.\n미충족 항목:\n{gap_text}"
    # CONDITIONAL or UNKNOWN
    return "조건부 입찰 가능. 부족한 요건을 보완한 후 검토하십시오."
