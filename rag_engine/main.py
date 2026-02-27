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

import asyncio
import logging
import os
import sys
import threading
import traceback
from contextlib import asynccontextmanager
from typing import Any

import re as _re

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator

from models import AnalyzeBidRequest, AnalyzeBidResponse
from proposal_generator import extract_template_sections, fill_template_sections
from hwp_parser import extract_hwp_text_bytes

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

    # Load auto-learner state
    auto_learn_dir = os.path.join(this_dir, "data", "auto_learning")
    try:
        from auto_learner import load_state as _al_load
        _al_load(auto_learn_dir)
        logger.info("Auto-learner state loaded from %s", auto_learn_dir)
    except Exception as exc:
        logger.warning("Auto-learner state load skipped: %s", exc)

    yield  # application runs here

    # Save auto-learner state on shutdown
    try:
        from auto_learner import save_state as _al_save
        _al_save(auto_learn_dir)
        logger.info("Auto-learner state saved to %s", auto_learn_dir)
    except Exception as exc:
        logger.warning("Auto-learner state save failed: %s", exc)


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
# Proposal generation
# ---------------------------------------------------------------------------

class GenerateProposalRequest(BaseModel):
    notice_text: str
    template_text: str = ""
    company_info: dict = {}


class GenerateProposalResponse(BaseModel):
    sections: dict[str, str]
    status: str


@app.post("/api/generate-proposal", response_model=GenerateProposalResponse)
async def generate_proposal(req: GenerateProposalRequest) -> GenerateProposalResponse:
    """Generate a proposal draft skeleton from bid notice text and company info."""
    if req.template_text:
        sections = extract_template_sections(req.template_text)
    else:
        sections = {
            "사업 개요": "{{사업 개요}}",
            "수행 전략": "{{수행 전략}}",
            "유사 실적": "{{유사 실적}}",
        }
    filled = fill_template_sections(sections, req.notice_text, req.company_info)
    return GenerateProposalResponse(sections=filled, status="done")


# ---------------------------------------------------------------------------
# Shared Pydantic input schemas for RFP analysis result
# ---------------------------------------------------------------------------

class EvaluationCriterionInput(BaseModel):
    category: str = ""
    max_score: float = 0.0
    description: str = ""


class RequirementInput(BaseModel):
    category: str = ""
    description: str = ""


class RfxResultInput(BaseModel):
    """Validated RFP analysis result — used by v2 proposal + checklist endpoints."""
    title: str = Field(min_length=1, description="사업명")
    issuing_org: str = ""
    budget: str = ""
    project_period: str = ""
    evaluation_criteria: list[EvaluationCriterionInput] = Field(default_factory=list)
    requirements: list[RequirementInput] = Field(default_factory=list)
    rfp_text_summary: str = ""

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title은 빈 문자열일 수 없습니다")
        return v.strip()


# ---------------------------------------------------------------------------
# Proposal generation v2 (Layer 1 knowledge-augmented)
# ---------------------------------------------------------------------------

class GenerateProposalV2Request(BaseModel):
    rfx_result: RfxResultInput
    company_context: str = ""
    company_name: str | None = None
    total_pages: int = Field(default=50, ge=10, le=200)


@app.post("/api/generate-proposal-v2")
async def generate_proposal_v2(req: GenerateProposalV2Request):
    """Generate a full proposal DOCX using Layer 1 knowledge + RFP analysis."""
    from proposal_orchestrator import generate_proposal as _generate

    try:
        result = await asyncio.to_thread(
            _generate,
            rfx_result=req.rfx_result.model_dump(),
            company_context=req.company_context,
            company_name=req.company_name,
            total_pages=req.total_pages,
        )
    except Exception as exc:
        logger.error("generate_proposal_v2 failed: %s\n%s", exc, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"제안서 생성 실패: {exc}") from exc

    # Return only filename, not full server path (security: C1)
    docx_filename = os.path.basename(result.docx_path) if result.docx_path else ""
    return {
        "docx_filename": docx_filename,
        "sections": [{"name": n, "preview": t[:500]} for n, t in result.sections],
        "quality_issues": [
            {"category": qi.category, "severity": qi.severity, "detail": qi.detail}
            for qi in result.quality_issues
        ],
        "generation_time_sec": result.generation_time_sec,
    }


# ---------------------------------------------------------------------------
# Proposal DOCX download
# ---------------------------------------------------------------------------

_PROPOSALS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "proposals")
_SAFE_FILENAME_RE = _re.compile(r'^[a-zA-Z0-9가-힣._\-]+\.docx$')


@app.get("/api/proposals/download/{filename}")
async def download_proposal(filename: str):
    """Serve a generated DOCX file for download.

    Security:
      - Filename must match whitelist regex (no path separators)
      - realpath must resolve within _PROPOSALS_DIR (prevents traversal)
    """
    if not _SAFE_FILENAME_RE.match(filename) or len(filename) > 150:
        raise HTTPException(status_code=400, detail="잘못된 파일명입니다.")

    filepath = os.path.join(_PROPOSALS_DIR, filename)
    real = os.path.realpath(filepath)
    base = os.path.realpath(_PROPOSALS_DIR)
    if not (real.startswith(base + os.sep) or real == base):
        raise HTTPException(status_code=400, detail="잘못된 파일 경로입니다.")

    if not os.path.isfile(real):
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")

    return FileResponse(
        real,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename,
    )


# ---------------------------------------------------------------------------
# Submission checklist
# ---------------------------------------------------------------------------

class ChecklistRequest(BaseModel):
    rfx_result: RfxResultInput
    rfp_text: str = ""


@app.post("/api/checklist")
async def extract_checklist_endpoint(req: ChecklistRequest):
    """Extract submission checklist from RFP analysis result."""
    try:
        from checklist_extractor import extract_checklist
        items = extract_checklist(req.rfx_result.model_dump(), req.rfp_text)
    except Exception as exc:
        logger.error("checklist extraction failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"체크리스트 추출 실패: {exc}") from exc
    return {
        "items": [
            {
                "document_name": it.document_name,
                "is_mandatory": it.is_mandatory,
                "format_hint": it.format_hint,
                "deadline_note": it.deadline_note,
                "status": it.status,
            }
            for it in items
        ],
        "total": len(items),
        "mandatory_count": sum(1 for it in items if it.is_mandatory),
    }


# ---------------------------------------------------------------------------
# Edit feedback (diff learning)
# ---------------------------------------------------------------------------

class EditFeedbackRequest(BaseModel):
    company_id: str = Field(min_length=1)
    section_name: str = Field(min_length=1)
    original_text: str
    edited_text: str


@app.post("/api/edit-feedback")
async def edit_feedback_endpoint(req: EditFeedbackRequest):
    """Process user edits for auto-learning pipeline."""
    try:
        from auto_learner import process_edit_feedback
        result = process_edit_feedback(
            company_id=req.company_id,
            section_name=req.section_name,
            original_text=req.original_text,
            edited_text=req.edited_text,
        )
    except Exception as exc:
        logger.error("edit feedback failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"수정 피드백 처리 실패: {exc}") from exc
    return {
        "edit_rate": result.edit_rate,
        "new_diffs": result.new_diffs,
        "promoted_patterns": [
            {
                "section_name": p.section_name,
                "description": p.description,
                "occurrence_count": p.occurrence_count,
            }
            for p in result.promoted_patterns
        ],
        "notifications": result.notifications,
    }


# ---------------------------------------------------------------------------
# Company DB CRUD
# ---------------------------------------------------------------------------

_company_db_instance = None
_company_db_init_lock = threading.Lock()
_company_db_profile_lock = asyncio.Lock()


def _get_company_db():
    global _company_db_instance
    if _company_db_instance is None:
        with _company_db_init_lock:
            if _company_db_instance is None:
                from company_db import CompanyDB
                db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "company_db")
                _company_db_instance = CompanyDB(persist_directory=db_path)
    return _company_db_instance


class TrackRecordRequest(BaseModel):
    project_name: str = Field(min_length=1)
    client: str = Field(min_length=1)
    contract_amount: str = ""
    period: str = ""
    description: str = ""
    technologies: list[str] = Field(default_factory=list)


class PersonnelRequest(BaseModel):
    name: str = Field(min_length=1)
    role: str = Field(min_length=1)
    experience_years: int = Field(default=0, ge=0)
    certifications: list[str] = Field(default_factory=list)
    description: str = ""


class CompanyProfileUpdateRequest(BaseModel):
    company_name: str = ""
    business_type: str = ""
    specializations: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    employee_count: int = 0
    capital: float = 0.0


@app.post("/api/company-db/track-records")
async def add_track_record_endpoint(req: TrackRecordRequest):
    """Add a track record to the company DB."""
    from company_db import TrackRecord as TR

    db = _get_company_db()
    amount = 0.0
    if req.contract_amount:
        try:
            amount = float(req.contract_amount.replace(",", "").replace("억", "").strip())
        except ValueError:
            pass

    record = TR(
        project_name=req.project_name,
        client=req.client,
        period=req.period,
        amount=amount,
        description=req.description,
        technologies=req.technologies,
    )
    doc_id = db.add_track_record(record)

    # Update profile under lock to prevent TOCTOU race
    async with _company_db_profile_lock:
        profile = db.load_profile()
        if profile:
            profile.track_records.append(record)
            db.save_profile(profile)

    return {"id": doc_id, "total": db.count()}


@app.post("/api/company-db/personnel")
async def add_personnel_endpoint(req: PersonnelRequest):
    """Add personnel info to the company DB."""
    from company_db import Personnel as PS

    db = _get_company_db()
    person = PS(
        name=req.name,
        role=req.role,
        experience_years=req.experience_years,
        certifications=req.certifications,
        specialties=[],
        key_projects=[],
    )
    doc_id = db.add_personnel(person)

    # Update profile under lock to prevent TOCTOU race
    async with _company_db_profile_lock:
        profile = db.load_profile()
        if profile:
            profile.personnel.append(person)
            db.save_profile(profile)

    return {"id": doc_id, "total": db.count()}


@app.get("/api/company-db/profile")
async def get_company_db_profile():
    """Get company capability profile."""
    db = _get_company_db()
    profile = db.load_profile()
    if profile is None:
        return {"profile": None}
    return {
        "profile": {
            "company_name": profile.name,
            "business_type": "",
            "specializations": profile.certifications,
            "track_record_count": len(profile.track_records),
            "personnel_count": len(profile.personnel),
        }
    }


@app.put("/api/company-db/profile")
async def update_company_db_profile(req: CompanyProfileUpdateRequest):
    """Update or create company capability profile."""
    from company_db import CompanyCapabilityProfile

    db = _get_company_db()
    profile = db.load_profile()
    if profile is None:
        profile = CompanyCapabilityProfile(name=req.company_name or "미설정")

    if req.company_name:
        profile.name = req.company_name
    if req.certifications:
        profile.certifications = req.certifications
    if req.employee_count:
        profile.employee_count = req.employee_count
    if req.capital:
        profile.capital = req.capital

    db.save_profile(profile)
    return {
        "profile": {
            "company_name": profile.name,
            "business_type": "",
            "specializations": profile.certifications,
            "track_record_count": len(profile.track_records),
            "personnel_count": len(profile.personnel),
        }
    }


@app.get("/api/company-db/stats")
async def get_company_db_stats():
    """Get company DB statistics."""
    db = _get_company_db()
    profile = db.load_profile()
    return {
        "track_record_count": len(profile.track_records) if profile else 0,
        "personnel_count": len(profile.personnel) if profile else 0,
        "total_knowledge_units": db.count(),
    }


# ---------------------------------------------------------------------------
# HWP parsing
# ---------------------------------------------------------------------------

@app.post("/api/parse-hwp")
async def parse_hwp(file: UploadFile = File(...)) -> dict:
    """Extract plain text from an HWP 5.x file."""
    data = await file.read()
    text = extract_hwp_text_bytes(data)
    if not text:
        return {"text": "", "success": False, "error": "파싱 실패 또는 HWP 형식 아님"}
    return {"text": text, "success": True, "char_count": len(text)}


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
