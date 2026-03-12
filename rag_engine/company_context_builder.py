"""Company Context Builder — CompanyDB에서 회사 맞춤 컨텍스트 문자열 생성.

모든 문서 생성 오케스트레이터(제안서/PPT/WBS)가 공유하는 유틸리티.
CompanyDB + company_analyzer에서 회사 역량·스타일·유사실적을 추출하여
LLM 프롬프트에 주입할 문자열을 빌드한다.

사용 패턴:
    from company_context_builder import build_company_context
    ctx = build_company_context(rfx_result, company_db_path="./data/company_db")
    # ctx → section_writer(company_context=ctx)
    # ctx → ppt_slide_planner(company_context=ctx)
    # ctx → wbs_planner(company_context=ctx)
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def build_company_context(
    rfx_result: dict[str, Any],
    company_db_path: str = "./data/company_db",
    max_projects: int = 5,
    max_personnel: int = 5,
    company_db: Optional[Any] = None,
) -> str:
    """CompanyDB에서 RFP 맞춤 회사 컨텍스트 문자열 빌드.

    Args:
        company_db: Pre-initialized CompanyDB instance (preferred).
                    If provided, company_db_path is ignored.

    Returns:
        company_context 문자열. DB 없거나 데이터 없으면 빈 문자열.
    """
    db = company_db
    if db is None:
        try:
            from company_db import CompanyDB
        except ImportError:
            logger.warning("company_db module not available")
            return ""

        try:
            db = CompanyDB(persist_directory=company_db_path)
        except Exception as exc:
            logger.warning("CompanyDB init failed: %s", exc)
            return ""

    parts: list[str] = []

    # 1. Company profile (기본 정보 + 자격/인증)
    profile = db.load_profile()
    if profile:
        parts.append(_format_profile(profile))

    # 2. Similar projects (유사수행실적)
    title = rfx_result.get("title", "")
    requirements_text = _extract_requirements_text(rfx_result)
    query = f"{title} {requirements_text}"[:500]

    if query.strip():
        try:
            projects = db.search_similar_projects(query, top_k=max_projects)
            if projects:
                parts.append(_format_projects(projects))
        except Exception as exc:
            logger.debug("search_similar_projects failed: %s", exc)

    # 3. Matching personnel (투입 가능 인력)
    if requirements_text.strip():
        try:
            personnel = db.find_matching_personnel(requirements_text, top_k=max_personnel)
            if personnel:
                parts.append(_format_personnel(personnel))
        except Exception as exc:
            logger.debug("find_matching_personnel failed: %s", exc)

    # 4. Writing style (과거 제안서 스타일 — profile.writing_style에 저장)
    if profile and profile.writing_style:
        parts.append(_format_style(profile.writing_style))

    return "\n\n".join(parts)


def _format_profile(profile) -> str:
    """회사 기본 프로필 포맷."""
    lines = [f"회사명: {profile.name}"]
    if profile.licenses:
        lines.append(f"보유 면허: {', '.join(profile.licenses)}")
    if profile.certifications:
        lines.append(f"인증: {', '.join(profile.certifications)}")
    if profile.capital > 0:
        lines.append(f"자본금: {profile.capital}억원")
    if profile.employee_count > 0:
        lines.append(f"인력: {profile.employee_count}명")
    return "## 회사 기본 정보\n" + "\n".join(lines)


def _format_projects(projects: list[dict]) -> str:
    """유사수행실적 포맷."""
    lines = []
    for i, p in enumerate(projects, 1):
        text = p.get("text", "")
        meta = p.get("metadata", {})
        name = meta.get("project_name", "")
        client = meta.get("client", "")
        header = f"{i}. {name}" if name else f"{i}."
        if client:
            header += f" ({client})"
        lines.append(f"{header}\n{text}")
    return "## 유사수행실적\n" + "\n".join(lines)


def _format_personnel(personnel: list[dict]) -> str:
    """투입 가능 인력 포맷."""
    lines = []
    for i, p in enumerate(personnel, 1):
        text = p.get("text", "")
        meta = p.get("metadata", {})
        name = meta.get("name", "")
        role = meta.get("role", "")
        exp = meta.get("experience_years", 0)
        header = f"{i}. {name}" if name else f"{i}."
        if role:
            header += f" ({role}, {exp}년)"
        lines.append(f"{header}\n{text}")
    return "## 투입 가능 핵심 인력\n" + "\n".join(lines)


def _format_style(style: dict) -> str:
    """회사 제안서 스타일 포맷."""
    lines = []
    if style.get("tone"):
        lines.append(f"문체: {style['tone']}")
    if style.get("avg_sentence_length"):
        lines.append(f"평균 문장 길이: {style['avg_sentence_length']}자")
    if style.get("strength_keywords"):
        kws = style["strength_keywords"]
        if isinstance(kws, list):
            lines.append(f"강점 키워드: {', '.join(kws[:10])}")
    if style.get("common_phrases"):
        phrases = style["common_phrases"]
        if isinstance(phrases, list):
            lines.append(f"빈출 표현: {', '.join(phrases[:5])}")
    if not lines:
        return ""
    return "## 과거 제안서 스타일\n" + "\n".join(lines)


def _extract_requirements_text(rfx_result: dict[str, Any]) -> str:
    """RFP에서 요구사항 텍스트 추출."""
    parts = []
    for req in rfx_result.get("requirements", []):
        if isinstance(req, dict):
            desc = req.get("description", "")
            if desc:
                parts.append(desc)
        elif isinstance(req, str) and req:
            parts.append(req)
    return " ".join(parts)[:300]
