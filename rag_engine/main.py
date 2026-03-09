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

from dotenv import load_dotenv

load_dotenv()  # Load .env (OPENAI_API_KEY, etc.) before anything else
import threading
import traceback
from contextlib import asynccontextmanager
from typing import Any

import re as _re

from fastapi import FastAPI, File, HTTPException, Query, UploadFile, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

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

    # Verify OPENAI_API_KEY is available (required for all LLM calls)
    if not os.environ.get("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY not found in environment. Check .env file.")
    else:
        logger.info("OPENAI_API_KEY loaded successfully.")

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

    # Ensure proposals directory exists
    proposals_dir = os.path.join(this_dir, "data", "proposals")
    os.makedirs(proposals_dir, exist_ok=True)
    logger.info("Proposals directory ready at %s", proposals_dir)

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

# Rate limiting
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Kira RAG Engine",
    description="Bid qualification analysis microservice",
    version="1.0.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe. Always returns 200 while the process is alive."""
    return {"status": "ok"}


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    """
    Readiness probe. Checks if RAG stack is loaded.
    Returns 503 if RAG engine failed to initialize.
    """
    if _engine_error or _rag_engine_cls is None:
        raise HTTPException(
            status_code=503,
            detail=f"RAG engine unavailable: {_engine_error or 'stack not loaded'}",
        )
    return {"status": "ready"}


@app.get("/api/debug/env")
async def debug_env() -> dict[str, Any]:
    """Debug endpoint to check Railway environment and file paths."""
    import os
    import sys

    # Paths are defined later in this file, access via globals
    proposals_dir = globals().get("_PROPOSALS_DIR", "NOT_DEFINED")
    knowledge_db_dir = globals().get("_KNOWLEDGE_DB_DIR", "NOT_DEFINED")
    company_db_dir = globals().get("_COMPANY_DB_DIR", "NOT_DEFINED")

    return {
        "cwd": os.getcwd(),
        "python_version": sys.version,
        "proposals_dir": proposals_dir,
        "knowledge_db_dir": knowledge_db_dir,
        "company_db_dir": company_db_dir,
        "proposals_dir_exists": os.path.exists(proposals_dir) if proposals_dir != "NOT_DEFINED" else False,
        "proposals_dir_writable": os.access(proposals_dir, os.W_OK) if proposals_dir != "NOT_DEFINED" and os.path.exists(proposals_dir) else False,
        "knowledge_db_exists": os.path.exists(knowledge_db_dir) if knowledge_db_dir != "NOT_DEFINED" else False,
        "knowledge_db_contents": os.listdir(knowledge_db_dir) if knowledge_db_dir != "NOT_DEFINED" and os.path.exists(knowledge_db_dir) else [],
        "company_db_exists": os.path.exists(company_db_dir) if company_db_dir != "NOT_DEFINED" else False,
        "company_db_writable": os.access(company_db_dir, os.W_OK) if company_db_dir != "NOT_DEFINED" and os.path.exists(company_db_dir) else False,
        "env_openai_key_set": bool(os.getenv("OPENAI_API_KEY")),
        "env_port": os.getenv("PORT", "NOT_SET"),
        "user": os.getenv("USER", "unknown"),
    }


@app.get("/warmup")
async def warmup() -> dict[str, str]:
    """
    Warmup endpoint to initialize ChromaDB on startup.
    Creates a RAGEngine instance to trigger ChromaDB collection loading.
    """
    if _engine_error or _rag_engine_cls is None:
        raise HTTPException(
            status_code=503,
            detail=f"RAG engine unavailable: {_engine_error or 'stack not loaded'}",
        )

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY environment variable is not set.",
        )

    try:
        # Create RAGEngine instance to trigger ChromaDB initialization
        this_dir = os.path.dirname(os.path.abspath(__file__))
        persist_dir = os.path.join(this_dir, "data", "vectordb")
        _ = _rag_engine_cls(persist_directory=persist_dir)
        return {"status": "warmed_up", "message": "ChromaDB initialized successfully"}
    except Exception as exc:
        logger.error("Warmup failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=f"Warmup failed: {exc}",
        )


@app.post("/api/analyze-bid", response_model=AnalyzeBidResponse)
@limiter.limit("10/minute")
async def analyze_bid(req: AnalyzeBidRequest, request: Request) -> AnalyzeBidResponse:
    """
    Analyze bid eligibility for a given company.

    Flow:
    1. Use RFxAnalyzer.analyze_text() to extract constraints from attachment_text.
    2. Build a temporary in-memory RAGEngine and inject company_facts as text.
    3. Run QualificationMatcher.match() against the extracted RFxAnalysisResult.
    4. Return is_eligible, structured details, and an action_plan.

    Returns HTTP 503 if the RAG stack failed to load at startup.
    """
    if _engine_error or _rfx_analyzer_cls is None:
        raise HTTPException(
            status_code=503,
            detail=f"RAG engine unavailable: {_engine_error or 'stack not loaded'}",
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
        rfx_result = analyzer.analyze_text(req.attachment_text)

        # ------------------------------------------------------------------
        # Step 2: Build an in-memory RAG engine and populate with company facts
        # ------------------------------------------------------------------
        # Use a temp collection per request so evaluations are isolated.
        _safe_id = _re.sub(r"[^a-zA-Z0-9_\-]", "_", f"{req.bid_notice_id}_{req.organization_id}")[:60]
        collection_name = f"bid_{_safe_id}"
        rag: Any = _rag_engine_cls(
            persist_directory="",          # empty → in-memory only
            collection_name=collection_name,
            hybrid_enabled=False,          # BM25 not needed for single-bid eval
        )

        # Serialize company_facts dict into a plain text blob and index it.
        facts_text = _company_facts_to_text(req.company_facts)
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
        raise HTTPException(status_code=500, detail="분석 실패") from exc


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
    output_format: str = Field(default="docx", pattern="^(docx|hwpx)$")


@app.post("/api/generate-proposal-v2")
@limiter.limit("5/minute")
async def generate_proposal_v2(req: GenerateProposalV2Request, request: Request):
    """Generate a full proposal DOCX using Layer 1 knowledge + RFP analysis."""
    from proposal_orchestrator import generate_proposal as _generate

    try:
        result = await asyncio.to_thread(
            _generate,
            rfx_result=req.rfx_result.model_dump(),
            company_context=req.company_context,
            company_name=req.company_name,
            company_db_path=_COMPANY_DB_DIR,
            knowledge_db_path=_KNOWLEDGE_DB_DIR,
            company_skills_dir=_get_company_skills_dir(),
            total_pages=req.total_pages,
            output_format=req.output_format,
        )
    except Exception as exc:
        logger.error("generate_proposal_v2 failed: %s\n%s", exc, traceback.format_exc())
        raise HTTPException(status_code=500, detail="제안서 생성 실패") from exc

    # Return only filename, not full server path (security: C1)
    docx_filename = os.path.basename(result.docx_path) if result.docx_path else ""
    hwpx_filename = os.path.basename(result.hwpx_path) if result.hwpx_path else ""
    output_filename = hwpx_filename or docx_filename

    # Persist full section markdown alongside output for later editing
    if output_filename and result.sections:
        try:
            base_name = output_filename.rsplit(".", 1)[0]
            sections_path = os.path.join(_PROPOSALS_DIR, f"{base_name}_sections.json")
            import json as _json
            import tempfile as _tmpfile
            payload = {
                "title": req.rfx_result.title,
                "sections": [{"name": n, "text": t} for n, t in result.sections],
            }
            with _tmpfile.NamedTemporaryFile(
                "w", dir=_PROPOSALS_DIR, suffix=".json",
                delete=False, encoding="utf-8",
            ) as tmp:
                _json.dump(payload, tmp, ensure_ascii=False)
                tmp_name = tmp.name
            try:
                os.replace(tmp_name, sections_path)
            except OSError:
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
                raise
        except Exception as exc:
            logger.warning("Failed to save proposal sections JSON: %s", exc)

    return {
        "docx_filename": docx_filename,
        "hwpx_filename": hwpx_filename,
        "output_filename": output_filename,
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
_COMPANY_DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "company_db")
# Layer 1 지식 DB는 프로젝트 루트의 data/knowledge_db (495 유닛 위치)
_KNOWLEDGE_DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "knowledge_db")
_SAFE_FILENAME_RE = _re.compile(r'^[a-zA-Z0-9가-힣._\-]+\.(docx|hwpx|xlsx|pptx|png)$')

_MIME_TYPES: dict[str, str] = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".hwpx": "application/x-hwpml",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".png": "image/png",
}


@app.get("/api/proposals/download/{filename}")
async def download_proposal(filename: str):
    """Serve a generated file for download.

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

    ext = os.path.splitext(filename)[1].lower()
    media_type = _MIME_TYPES.get(ext, "application/octet-stream")

    return FileResponse(
        real,
        media_type=media_type,
        filename=filename,
    )


# ---------------------------------------------------------------------------
# Proposal sections CRUD (for DocumentWorkspace editing)
# ---------------------------------------------------------------------------

_SAFE_DOCX_NAME_RE = _re.compile(r'^[a-zA-Z0-9가-힣._\-]+$')

# Per-file lock to prevent concurrent read-modify-write race conditions
import threading as _threading
_sections_locks: dict[str, _threading.Lock] = {}
_sections_locks_guard = _threading.Lock()


_MAX_SECTION_LOCKS = 500


def _get_sections_lock(path: str) -> _threading.Lock:
    """Get or create a per-file lock for section JSON files (bounded)."""
    with _sections_locks_guard:
        if path not in _sections_locks:
            if len(_sections_locks) >= _MAX_SECTION_LOCKS:
                # Evict oldest entries (FIFO — Python 3.7+ dict is insertion-ordered)
                excess = len(_sections_locks) - _MAX_SECTION_LOCKS + 1
                for _ in range(excess):
                    _sections_locks.pop(next(iter(_sections_locks)))
            _sections_locks[path] = _threading.Lock()
        return _sections_locks[path]


def _resolve_sections_path(docx_filename: str) -> str:
    """Resolve and validate sections JSON path for a given DOCX filename."""
    # Strip extension if present
    base = docx_filename.rsplit(".", 1)[0] if "." in docx_filename else docx_filename
    if not _SAFE_DOCX_NAME_RE.match(base) or len(base) > 150:
        raise HTTPException(status_code=400, detail="잘못된 파일명입니다.")

    path = os.path.join(_PROPOSALS_DIR, f"{base}_sections.json")
    real = os.path.realpath(path)
    proposals_base = os.path.realpath(_PROPOSALS_DIR)
    if not real.startswith(proposals_base + os.sep):
        raise HTTPException(status_code=400, detail="잘못된 파일 경로입니다.")
    return real


@app.get("/api/proposal-sections")
def get_proposal_sections(docx_filename: str):
    """Load saved proposal sections for editing in DocumentWorkspace."""
    path = _resolve_sections_path(docx_filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="섹션 파일을 찾을 수 없습니다.")
    import json as _json
    with open(path, encoding="utf-8") as f:
        return _json.load(f)


class UpdateProposalSectionRequest(BaseModel):
    docx_filename: str = Field(min_length=1, max_length=200)
    section_name: str = Field(min_length=1, max_length=512)
    text: str = Field(max_length=50_000)


@app.put("/api/proposal-sections")
def update_proposal_section(req: UpdateProposalSectionRequest):
    """Update a single section's markdown text."""
    path = _resolve_sections_path(req.docx_filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="섹션 파일을 찾을 수 없습니다.")

    import json as _json
    import tempfile

    lock = _get_sections_lock(path)
    with lock:
        with open(path, encoding="utf-8") as f:
            data = _json.load(f)

        found = False
        for section in data.get("sections", []):
            if section["name"] == req.section_name:
                section["text"] = req.text
                found = True
                break

        if not found:
            raise HTTPException(status_code=404, detail=f"섹션 '{req.section_name}'을 찾을 수 없습니다.")

        # Atomic write: temp file → os.replace
        with tempfile.NamedTemporaryFile(
            "w", dir=os.path.dirname(path), suffix=".json",
            delete=False, encoding="utf-8",
        ) as tmp:
            _json.dump(data, tmp, ensure_ascii=False)
            tmp_name = tmp.name
        try:
            os.replace(tmp_name, path)
        except OSError:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    return {"success": True}


class ReassembleProposalRequest(BaseModel):
    docx_filename: str = Field(min_length=1, max_length=200)


@app.post("/api/proposal-sections/reassemble")
def reassemble_proposal(req: ReassembleProposalRequest):
    """Reassemble DOCX from current (possibly edited) sections."""
    sections_path = _resolve_sections_path(req.docx_filename)
    if not os.path.isfile(sections_path):
        raise HTTPException(status_code=404, detail="섹션 파일을 찾을 수 없습니다.")

    import json as _json
    with open(sections_path, encoding="utf-8") as f:
        data = _json.load(f)

    sections = [(s["name"], s["text"]) for s in data.get("sections", [])]
    if not sections:
        raise HTTPException(status_code=400, detail="섹션이 비어있습니다.")

    title = data.get("title", "제안서")

    # Determine output DOCX path
    base = req.docx_filename.rsplit(".", 1)[0] if "." in req.docx_filename else req.docx_filename
    docx_path = os.path.join(_PROPOSALS_DIR, f"{base}.docx")

    try:
        from document_assembler import assemble_docx
        assemble_docx(title, sections, docx_path)
    except Exception as exc:
        logger.error("Reassemble failed: %s", exc)
        raise HTTPException(status_code=500, detail="DOCX 재생성 실패") from exc

    return {"success": True, "docx_filename": f"{base}.docx"}


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
        raise HTTPException(status_code=500, detail="체크리스트 추출 실패") from exc
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
# Phase 2: WBS generation
# ---------------------------------------------------------------------------

class GenerateWbsRequest(BaseModel):
    rfx_result: RfxResultInput
    methodology: str = ""  # "waterfall" | "agile" | "hybrid" or empty for auto


@app.post("/api/generate-wbs")
@limiter.limit("5/minute")
async def generate_wbs_endpoint(req: GenerateWbsRequest, request: Request):
    """Generate WBS (XLSX + Gantt + DOCX) from RFP analysis."""
    from wbs_orchestrator import generate_wbs as _generate_wbs
    from phase2_models import MethodologyType

    methodology = None
    if req.methodology:
        try:
            methodology = MethodologyType(req.methodology)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"잘못된 방법론: {req.methodology}. waterfall/agile/hybrid 중 택일",
            )

    try:
        result = await asyncio.to_thread(
            _generate_wbs,
            rfx_result=req.rfx_result.model_dump(),
            output_dir=_PROPOSALS_DIR,
            methodology=methodology,
            knowledge_db_path=_KNOWLEDGE_DB_DIR,
            company_db_path=_COMPANY_DB_DIR,
            company_skills_dir=_get_company_skills_dir(),
        )
    except Exception as exc:
        logger.error("generate_wbs failed: %s\n%s", exc, traceback.format_exc())
        raise HTTPException(status_code=500, detail="WBS 생성 실패") from exc

    return {
        "xlsx_filename": os.path.basename(result.xlsx_path) if result.xlsx_path else "",
        "gantt_filename": os.path.basename(result.gantt_path) if result.gantt_path else "",
        "docx_filename": os.path.basename(result.docx_path) if result.docx_path else "",
        "tasks_count": len(result.tasks),
        "total_months": result.total_months,
        "generation_time_sec": result.generation_time_sec,
    }


# ---------------------------------------------------------------------------
# Phase 2: PPT generation
# ---------------------------------------------------------------------------

class ProposalSectionInput(BaseModel):
    name: str = ""
    text: str = ""


class GeneratePptRequest(BaseModel):
    rfx_result: RfxResultInput
    proposal_sections: list[ProposalSectionInput] = Field(default_factory=list)
    duration_min: int = Field(default=30, ge=10, le=60)
    qna_count: int = Field(default=10, ge=0, le=20)
    company_name: str = ""


@app.post("/api/generate-ppt")
@limiter.limit("5/minute")
async def generate_ppt_endpoint(req: GeneratePptRequest, request: Request):
    """Generate PPT presentation (PPTX + QnA) from RFP analysis."""
    from ppt_orchestrator import generate_ppt as _generate_ppt

    sections = None
    if req.proposal_sections:
        sections = [{"name": s.name, "text": s.text} for s in req.proposal_sections]

    try:
        result = await asyncio.to_thread(
            _generate_ppt,
            rfx_result=req.rfx_result.model_dump(),
            output_dir=_PROPOSALS_DIR,
            proposal_sections=sections,
            duration_min=req.duration_min,
            qna_count=req.qna_count,
            company_name=req.company_name,
            knowledge_db_path=_KNOWLEDGE_DB_DIR,
            company_db_path=_COMPANY_DB_DIR,
            company_skills_dir=_get_company_skills_dir(),
        )
    except Exception as exc:
        logger.error("generate_ppt failed: %s\n%s", exc, traceback.format_exc())
        raise HTTPException(status_code=500, detail="PPT 생성 실패") from exc

    return {
        "pptx_filename": os.path.basename(result.pptx_path) if result.pptx_path else "",
        "slide_count": result.slide_count,
        "qna_pairs": [
            {"question": q.question, "answer": q.answer, "category": q.category}
            for q in result.qna_pairs
        ],
        "total_duration_min": result.total_duration_min,
        "generation_time_sec": result.generation_time_sec,
    }


# ---------------------------------------------------------------------------
# Phase 2: Track record document generation
# ---------------------------------------------------------------------------

class GenerateTrackRecordRequest(BaseModel):
    rfx_result: RfxResultInput
    max_records: int = Field(default=10, ge=1, le=20)
    max_personnel: int = Field(default=10, ge=1, le=20)
    company_name: str = ""


@app.post("/api/generate-track-record")
@limiter.limit("5/minute")
async def generate_track_record_endpoint(req: GenerateTrackRecordRequest, request: Request):
    """Generate track record / personnel document (DOCX)."""
    from track_record_orchestrator import generate_track_record_doc as _generate

    try:
        result = await asyncio.to_thread(
            _generate,
            rfx_result=req.rfx_result.model_dump(),
            output_dir=_PROPOSALS_DIR,
            company_db_path=_COMPANY_DB_DIR,
            knowledge_db_path=_KNOWLEDGE_DB_DIR,
            max_records=req.max_records,
            max_personnel=req.max_personnel,
            company_name=req.company_name or None,
            company_skills_dir=_get_company_skills_dir(),
        )
    except Exception as exc:
        logger.error("generate_track_record failed: %s\n%s", exc, traceback.format_exc())
        raise HTTPException(status_code=500, detail="실적기술서 생성 실패") from exc

    return {
        "docx_filename": os.path.basename(result.docx_path) if result.docx_path else "",
        "track_record_count": result.track_record_count,
        "personnel_count": result.personnel_count,
        "generation_time_sec": result.generation_time_sec,
    }


# ---------------------------------------------------------------------------
# Edit feedback (diff learning)
# ---------------------------------------------------------------------------

class EditFeedbackRequest(BaseModel):
    company_id: str = Field(min_length=1, max_length=256)
    section_name: str = Field(min_length=1, max_length=512)
    original_text: str = Field(max_length=50_000)
    edited_text: str = Field(max_length=50_000)
    doc_type: str = Field(default="proposal", pattern=r"^(proposal|wbs|ppt|track_record)$")


@app.post("/api/edit-feedback")
async def edit_feedback_endpoint(req: EditFeedbackRequest):
    """Process user edits for auto-learning pipeline."""
    try:
        from auto_learner import process_edit_feedback

        def _on_pattern_promoted(company_id, patterns):
            """Auto-learner pattern promotion → profile.md update."""
            try:
                from company_profile_updater import update_profile_section
                skills_dir = _get_company_skills_dir(company_id)
                for pattern in patterns:
                    update_profile_section(
                        company_dir=skills_dir,
                        section_name=pattern.section_name,
                        new_content=f"- 학습된 패턴: {pattern.description}",
                    )
            except Exception as exc:
                logger.debug("Profile update from callback skipped: %s", exc)

        result = await asyncio.to_thread(
            process_edit_feedback,
            company_id=req.company_id,
            section_name=req.section_name,
            original_text=req.original_text,
            edited_text=req.edited_text,
            doc_type=req.doc_type,
            on_pattern_promoted=_on_pattern_promoted,
        )
    except Exception as exc:
        logger.error("edit feedback failed: %s", exc)
        raise HTTPException(status_code=500, detail="수정 피드백 처리 실패") from exc
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


@app.get("/api/pending-knowledge")
async def get_pending_knowledge_endpoint(
    company_id: str = Query(min_length=1, max_length=256),
    doc_type: str = Query(default="proposal", pattern=r"^(proposal|wbs|ppt|track_record)$"),
):
    """Get pending patterns awaiting user approval."""
    try:
        from auto_learner import get_pending_patterns
        patterns = await asyncio.to_thread(get_pending_patterns, company_id, doc_type)
        return {
            "patterns": [
                {
                    "pattern_key": p.pattern_key,
                    "diff_type": p.diff_type,
                    "section_name": p.section_name,
                    "original_example": p.original_example,
                    "edited_example": p.edited_example,
                    "occurrence_count": p.occurrence_count,
                    "description": p.description,
                    "status": p.status,
                }
                for p in patterns
            ]
        }
    except Exception as exc:
        logger.error("get pending knowledge failed: %s", exc)
        raise HTTPException(status_code=500, detail="대기 중인 학습 조회 실패") from exc


class ApproveKnowledgeRequest(BaseModel):
    company_id: str = Field(min_length=1, max_length=256)
    pattern_key: str = Field(min_length=1)
    doc_type: str = Field(default="proposal", pattern=r"^(proposal|wbs|ppt|track_record)$")


@app.post("/api/approve-knowledge")
async def approve_knowledge_endpoint(req: ApproveKnowledgeRequest):
    """Approve a pending pattern → confirmed."""
    try:
        from auto_learner import approve_pattern
        success = await asyncio.to_thread(approve_pattern, req.company_id, req.pattern_key, req.doc_type)
        if not success:
            raise HTTPException(status_code=404, detail="패턴을 찾을 수 없거나 이미 승인되었습니다")
        return {"success": True, "message": "학습 패턴이 승인되었습니다"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("approve knowledge failed: %s", exc)
        raise HTTPException(status_code=500, detail="학습 승인 실패") from exc


class RejectKnowledgeRequest(BaseModel):
    company_id: str = Field(min_length=1, max_length=256)
    pattern_key: str = Field(min_length=1)
    doc_type: str = Field(default="proposal", pattern=r"^(proposal|wbs|ppt|track_record)$")


@app.delete("/api/reject-knowledge")
async def reject_knowledge_endpoint(req: RejectKnowledgeRequest):
    """Reject (remove) a pending pattern."""
    try:
        from auto_learner import reject_pattern
        success = await asyncio.to_thread(reject_pattern, req.company_id, req.pattern_key, req.doc_type)
        if not success:
            raise HTTPException(status_code=404, detail="패턴을 찾을 수 없거나 이미 삭제되었습니다")
        return {"success": True, "message": "학습 패턴이 거부되었습니다"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("reject knowledge failed: %s", exc)
        raise HTTPException(status_code=500, detail="학습 거부 실패") from exc


# ---------------------------------------------------------------------------
# Company DB CRUD
# ---------------------------------------------------------------------------

_company_db_instance = None
_company_db_init_lock = threading.Lock()
_company_db_profile_lock: asyncio.Lock | None = None


def _get_profile_lock() -> asyncio.Lock:
    """Lazy-init asyncio.Lock to avoid binding to wrong event loop at import time."""
    global _company_db_profile_lock
    if _company_db_profile_lock is None:
        _company_db_profile_lock = asyncio.Lock()
    return _company_db_profile_lock


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
            raw = req.contract_amount.replace(",", "").strip()
            if "억" in raw:
                amount = float(raw.replace("억", "").strip()) * 1e8
            else:
                amount = float(raw)
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
    async with _get_profile_lock():
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
    async with _get_profile_lock():
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


class AnalyzeStyleRequest(BaseModel):
    documents: list[str] = Field(
        min_length=1,
        max_length=20,
        description="과거 제안서 텍스트 목록 (최대 20개, 각 100,000자 이내)",
    )


_MAX_DOC_CHARS = 100_000


@app.post("/api/company-db/analyze-style")
async def analyze_company_style_endpoint(req: AnalyzeStyleRequest):
    """Analyze writing style from past proposal texts and save to profile."""
    from company_analyzer import analyze_company_style
    from dataclasses import asdict

    # Per-document size validation
    truncated = [doc[:_MAX_DOC_CHARS] for doc in req.documents]
    style = await asyncio.to_thread(analyze_company_style, truncated)
    style_dict = asdict(style)

    # Save to CompanyDB profile
    db = _get_company_db()
    async with _get_profile_lock():
        from company_db import CompanyCapabilityProfile
        profile = db.load_profile()
        if profile is None:
            profile = CompanyCapabilityProfile(name="미설정")
        profile.writing_style = style_dict
        db.save_profile(profile)

    return {"ok": True, "writing_style": style_dict}


# ---------------------------------------------------------------------------
# Company profile.md CRUD
# ---------------------------------------------------------------------------

_SAFE_COMPANY_ID_RE = _re.compile(r"^[a-zA-Z0-9가-힣._\-]+$")


def _get_company_skills_dir(company_id: str = "default") -> str:
    """Get company skills directory path (with path-traversal protection)."""
    if not _SAFE_COMPANY_ID_RE.match(company_id):
        raise HTTPException(status_code=400, detail="Invalid company_id")
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "company_skills")
    resolved = os.path.realpath(os.path.join(base, company_id))
    if not resolved.startswith(os.path.realpath(base) + os.sep) and resolved != os.path.realpath(base):
        raise HTTPException(status_code=400, detail="Invalid company_id")
    return resolved


class GenerateProfileRequest(BaseModel):
    company_name: str = Field(min_length=1, max_length=100)
    documents: list[str] = Field(min_length=1, max_length=20)


class UpdateProfileRequest(BaseModel):
    profile_md: str = Field(min_length=1, max_length=50_000)


@app.post("/api/company-profile/generate")
async def generate_company_profile(req: GenerateProfileRequest):
    """Generate profile.md from past proposal documents via style analysis."""
    from company_analyzer import analyze_company_style
    import company_profile_builder

    truncated = [doc[:_MAX_DOC_CHARS] for doc in req.documents]

    try:
        style = await asyncio.to_thread(analyze_company_style, truncated)
    except Exception as exc:
        logger.error("analyze_company_style failed: %s", exc)
        raise HTTPException(status_code=500, detail="스타일 분석 실패") from exc

    try:
        profile_md = company_profile_builder.build_profile_md(
            company_name=req.company_name,
            style=style,
        )
        skills_dir = _get_company_skills_dir()
        company_profile_builder.save_profile_md(skills_dir, profile_md)
    except Exception as exc:
        logger.error("build/save profile.md failed: %s", exc)
        raise HTTPException(status_code=500, detail="프로필 저장 실패") from exc

    return {"ok": True, "profile_md": profile_md}


@app.get("/api/company-profile")
async def get_company_profile():
    """Load the current company profile.md content."""
    import company_profile_builder

    skills_dir = _get_company_skills_dir()
    content = company_profile_builder.load_profile_md(skills_dir)
    return {"profile_md": content}


@app.put("/api/company-profile")
async def update_company_profile(req: UpdateProfileRequest):
    """Overwrite company profile.md with user-edited content."""
    import company_profile_builder

    skills_dir = _get_company_skills_dir()
    try:
        company_profile_builder.save_profile_md(skills_dir, req.profile_md)
    except Exception as exc:
        logger.error("save profile.md failed: %s", exc)
        raise HTTPException(status_code=500, detail="프로필 저장 실패") from exc

    return {"ok": True}


@app.post("/api/company-profile/upload-template")
async def upload_hwpx_template(file: UploadFile = File(...)):
    """Upload HWPX template and auto-enrich profile.md with extracted styles."""
    from hwpx_parser import is_hwpx_file, extract_hwpx_styles
    import company_profile_builder

    if not file.filename or not file.filename.endswith(".hwpx"):
        raise HTTPException(status_code=400, detail="HWPX 파일만 업로드 가능합니다.")

    skills_dir = _get_company_skills_dir()
    templates_dir = os.path.join(skills_dir, "templates")
    os.makedirs(templates_dir, exist_ok=True)

    # Read and validate size in memory first
    _MAX_TEMPLATE_BYTES = 10 * 1024 * 1024  # 10MB
    content = await file.read()
    if len(content) > _MAX_TEMPLATE_BYTES:
        raise HTTPException(status_code=413, detail="템플릿 파일은 10MB를 초과할 수 없습니다.")

    # Validate HWPX magic bytes in memory (ZIP PK header)
    if not content[:4].startswith(b"PK"):
        raise HTTPException(status_code=400, detail="유효하지 않은 HWPX 파일입니다.")

    # Save template with sanitized filename
    safe_name = _re.sub(r"[^a-zA-Z0-9가-힣._\-]", "_", file.filename)[:100]
    template_path = os.path.join(templates_dir, safe_name)
    with open(template_path, "wb") as f:
        f.write(content)

    # Full HWPX structure validation on disk
    if not is_hwpx_file(template_path):
        try:
            os.unlink(template_path)
        except OSError:
            pass
        raise HTTPException(status_code=400, detail="유효하지 않은 HWPX 파일입니다.")

    # Extract styles from template
    hwpx_styles = await asyncio.to_thread(extract_hwpx_styles, template_path)

    # Load existing profile or create a new one enriched with HWPX styles
    existing_md = company_profile_builder.load_profile_md(skills_dir)
    if not existing_md:
        profile_md = company_profile_builder.build_profile_md(
            "미설정", hwpx_styles=hwpx_styles,
        )
    else:
        # Re-generate with hwpx_styles merged
        profile_md = company_profile_builder.build_profile_md(
            "미설정", hwpx_styles=hwpx_styles,
        )

    company_profile_builder.save_profile_md(skills_dir, profile_md)

    return {
        "ok": True,
        "template_path": safe_name,
        "extracted_styles": hwpx_styles,
    }


# ---------------------------------------------------------------------------
# Profile.md section-level CRUD
# ---------------------------------------------------------------------------

class UpdateProfileSectionRequest(BaseModel):
    company_id: str = Field(default="default", min_length=1, max_length=256)
    section_name: str = Field(min_length=1, max_length=256)
    content: str = Field(max_length=50_000)


class RollbackProfileRequest(BaseModel):
    company_id: str = Field(default="default", min_length=1, max_length=256)
    target_version: int = Field(ge=1)


_NON_EDITABLE_SECTIONS = {"학습 이력"}


def _parse_profile_sections(content: str) -> list[dict]:
    """Parse profile.md into sections [{name, content, editable}].

    Splits on ``## `` headings.  The 학습 이력 section is marked as
    non-editable; all others are editable.
    """
    if not content or not content.strip():
        return []

    # Split on ## headings, keeping the heading text
    parts = _re.split(r"(?:^|\n)(## .+)\n", content)
    # parts[0] is the preamble (title, date), then alternating heading / body
    sections: list[dict] = []
    i = 1  # skip preamble
    while i < len(parts) - 1:
        heading = parts[i].strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        # Extract section name from "## SectionName"
        name = heading.removeprefix("## ").strip()
        # Trim trailing whitespace but keep internal structure
        body_clean = body.strip()
        sections.append({
            "name": name,
            "content": body_clean,
            "editable": name not in _NON_EDITABLE_SECTIONS,
        })
        i += 2

    return sections


@app.get("/api/company-profile/md")
async def get_profile_md_sections(company_id: str = "default"):
    """Parse profile.md into an array of named sections."""
    import company_profile_builder

    skills_dir = _get_company_skills_dir(company_id)
    content = await asyncio.to_thread(
        company_profile_builder.load_profile_md, skills_dir
    )
    sections = _parse_profile_sections(content)
    from company_profile_updater import load_changelog
    changelog = await asyncio.to_thread(load_changelog, skills_dir)
    version = len(changelog.get("versions", []))
    return {"sections": sections, "metadata": {"version": version, "company_id": company_id}}


@app.put("/api/company-profile/md/section")
async def update_profile_md_section(req: UpdateProfileSectionRequest):
    """Update a single section inside profile.md (with automatic backup)."""
    import company_profile_builder
    from company_profile_updater import update_profile_section

    skills_dir = _get_company_skills_dir(req.company_id)

    # Block edits to read-only sections
    if req.section_name in _NON_EDITABLE_SECTIONS:
        raise HTTPException(
            status_code=403,
            detail=f"섹션 '{req.section_name}'은(는) 편집할 수 없습니다 (read-only).",
        )

    async with _get_profile_lock():
        # Check profile exists (inside lock to avoid TOCTOU)
        content = await asyncio.to_thread(
            company_profile_builder.load_profile_md, skills_dir
        )
        if not content:
            raise HTTPException(status_code=404, detail="profile.md가 존재하지 않습니다.")
        ok = await asyncio.to_thread(
            update_profile_section,
            skills_dir,
            req.section_name,
            req.content,
            True,  # backup=True
        )

    if not ok:
        raise HTTPException(
            status_code=400,
            detail=f"섹션 '{req.section_name}'을(를) 찾을 수 없습니다 (section not found).",
        )

    from company_profile_updater import load_changelog
    changelog = await asyncio.to_thread(load_changelog, skills_dir)
    version = len(changelog.get("versions", []))
    return {"success": True, "version": version}


@app.get("/api/company-profile/md/history")
async def get_profile_md_history(company_id: str = "default"):
    """Return the version history (changelog) for profile.md."""
    from company_profile_updater import load_changelog

    skills_dir = _get_company_skills_dir(company_id)
    changelog = await asyncio.to_thread(load_changelog, skills_dir)
    versions = changelog.get("versions", [])
    return {"versions": versions, "current_version": len(versions)}


@app.post("/api/company-profile/md/rollback")
async def rollback_profile_md(req: RollbackProfileRequest):
    """Rollback profile.md to a specific version from profile_history/."""
    from company_profile_updater import backup_profile_version, load_changelog
    import company_profile_builder

    skills_dir = _get_company_skills_dir(req.company_id)
    history_dir = os.path.join(skills_dir, "profile_history")
    backup_file = os.path.join(
        history_dir, f"profile_v{req.target_version:03d}.md"
    )

    if not os.path.isfile(backup_file):
        raise HTTPException(
            status_code=404,
            detail=f"버전 {req.target_version}의 백업 파일이 존재하지 않습니다.",
        )

    async with _get_profile_lock():
        # Backup current state before overwriting
        profile_path = os.path.join(skills_dir, "profile.md")
        if os.path.isfile(profile_path):
            await asyncio.to_thread(
                backup_profile_version,
                skills_dir,
                f"v{req.target_version} 롤백 전 백업",
            )

        # Read the target version and restore it
        def _restore():
            with open(backup_file, "r", encoding="utf-8") as f:
                old_content = f.read()
            company_profile_builder.save_profile_md(skills_dir, old_content)

        await asyncio.to_thread(_restore)

    return {"success": True, "restored_version": req.target_version}


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
