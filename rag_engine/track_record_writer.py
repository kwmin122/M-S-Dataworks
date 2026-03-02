"""Track Record Writer — 유사수행실적/투입인력 선정 및 서술 생성.

RFP 과업 vs 실적 유사도 매칭, LLM 서술형 텍스트 생성.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

from llm_utils import call_with_retry, LLM_DEFAULT_TIMEOUT
from phase2_models import TrackRecordEntry, PersonnelEntry

logger = logging.getLogger(__name__)


def select_track_records(
    rfx_result: dict[str, Any],
    company_db: Any,
    max_records: int = 10,
) -> list[TrackRecordEntry]:
    """RFP 과업 vs 실적 유사도 매칭, 관련도 순 정렬."""
    title = rfx_result.get("title", "")
    requirements = rfx_result.get("requirements", [])
    query_parts = [title]
    for req in requirements:
        desc = req.get("description", "") if isinstance(req, dict) else str(req)
        if desc:
            query_parts.append(desc)
    query = " ".join(query_parts)[:2000]

    results = company_db.search_similar_projects(query, top_k=max_records)
    entries: list[TrackRecordEntry] = []
    for item in results:
        meta = item.get("metadata", {})
        distance = item.get("distance", 1.0)
        relevance = max(0.0, 1.0 - distance)  # cosine distance → similarity
        entries.append(TrackRecordEntry(
            project_name=meta.get("project_name", ""),
            client=meta.get("client", ""),
            amount=meta.get("amount", 0.0),
            description=item.get("text", ""),
            relevance_score=round(relevance, 3),
        ))
    entries.sort(key=lambda e: e.relevance_score, reverse=True)
    return entries[:max_records]


def select_personnel(
    rfx_result: dict[str, Any],
    company_db: Any,
    max_personnel: int = 10,
) -> list[PersonnelEntry]:
    """요구인력 기반 최적 매칭."""
    title = rfx_result.get("title", "")
    requirements = rfx_result.get("requirements", [])
    query_parts = [title]
    for req in requirements:
        desc = req.get("description", "") if isinstance(req, dict) else str(req)
        if desc:
            query_parts.append(desc)
    query = " ".join(query_parts)[:2000]

    results = company_db.find_matching_personnel(query, top_k=max_personnel)
    entries: list[PersonnelEntry] = []
    for item in results:
        meta = item.get("metadata", {})
        entries.append(PersonnelEntry(
            name=meta.get("name", ""),
            role=meta.get("role", ""),
            experience_years=int(meta.get("experience_years", 0)),
        ))
    return entries[:max_personnel]


def generate_track_record_text(
    entry: TrackRecordEntry,
    rfp_context: str,
    api_key: Optional[str] = None,
    knowledge_texts: Optional[list[str]] = None,
    profile_md: str = "",
) -> str:
    """LLM으로 단일 실적 서술형 생성 (5계층 프롬프트)."""
    import openai

    client = openai.OpenAI(
        api_key=api_key or os.environ.get("OPENAI_API_KEY", ""),
        timeout=LLM_DEFAULT_TIMEOUT,
    )

    # 5-layer prompt
    parts: list[str] = []

    # Layer 1 — universal knowledge
    if knowledge_texts:
        rules = "\n".join(f"- {t}" for t in knowledge_texts[:5])
        parts.append(f"## 유사수행실적 기술서 작성 규칙 (공공조달 지식):\n{rules}")

    # Layer 1.7 — company profile (문체, 강점 패턴 — 반드시 준수)
    if profile_md:
        parts.append(f"## 이 회사의 제안서 프로필 (반드시 준수):\n{profile_md}")

    # Layer 2 — RFP context
    if rfp_context:
        parts.append(f"## 사업 정보:\n{rfp_context[:1000]}")

    # Layer 3 — track record data
    parts.append(
        f"## 실적 정보:\n"
        f"프로젝트명: {entry.project_name}\n"
        f"발주처: {entry.client}\n"
        f"기간: {entry.period}\n"
        f"금액: {entry.amount}억원\n"
        f"설명: {entry.description}\n"
        f"기술: {', '.join(entry.technologies)}"
    )

    # Layer 4 — generation instructions
    parts.append(
        "## 작성 지시:\n"
        "위 실적 정보를 바탕으로 RFP 과업과의 연관성을 강조하는 서술형 텍스트를 작성하세요.\n\n"
        "규칙:\n"
        "1. 200~400자 분량\n"
        "2. 사업 목적, 수행 범위, 핵심 성과를 포함\n"
        "3. 현재 RFP 과업과의 유사성/연관성을 명시\n"
        "4. 구체적인 수치(규모, 사용자 수, 성능 개선 등) 포함\n"
        "5. 블라인드 평가를 고려하여 회사 고유명칭 사용 금지 (발주처명은 허용)"
    )

    prompt = "\n\n".join(parts)

    def _call():
        return client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "공공조달 유사수행실적 서술 전문가입니다. 평가위원이 높은 점수를 줄 수 있도록 실적과 RFP의 연관성을 구체적으로 서술합니다."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=1000,
        )

    try:
        resp = call_with_retry(_call)
        return resp.choices[0].message.content or ""
    except Exception as exc:
        logger.warning("generate_track_record_text LLM failed for %s: %s", entry.project_name, exc)
        return entry.description


def generate_personnel_text(
    entry: PersonnelEntry,
    rfp_context: str,
    api_key: Optional[str] = None,
    knowledge_texts: Optional[list[str]] = None,
    profile_md: str = "",
) -> str:
    """LLM으로 단일 인력 경력 서술 (5계층 프롬프트)."""
    import openai

    client = openai.OpenAI(
        api_key=api_key or os.environ.get("OPENAI_API_KEY", ""),
        timeout=LLM_DEFAULT_TIMEOUT,
    )

    # 5-layer prompt
    parts: list[str] = []

    # Layer 1 — universal knowledge
    if knowledge_texts:
        rules = "\n".join(f"- {t}" for t in knowledge_texts[:5])
        parts.append(f"## 투입인력 경력기술서 작성 규칙 (공공조달 지식):\n{rules}")

    # Layer 1.7 — company profile (문체, 강점 패턴 — 반드시 준수)
    if profile_md:
        parts.append(f"## 이 회사의 제안서 프로필 (반드시 준수):\n{profile_md}")

    # Layer 2 — RFP context
    if rfp_context:
        parts.append(f"## 사업 정보:\n{rfp_context[:1000]}")

    # Layer 3 — personnel data
    parts.append(
        f"## 인력 정보:\n"
        f"성명: {entry.name}\n"
        f"역할: {entry.role}\n"
        f"등급: {entry.grade}\n"
        f"경력: {entry.experience_years}년\n"
        f"자격증: {', '.join(entry.certifications)}\n"
        f"주요 프로젝트: {', '.join(entry.key_projects)}"
    )

    # Layer 4 — generation instructions
    parts.append(
        "## 작성 지시:\n"
        "위 인력 정보를 바탕으로 본 사업에 적합한 경력기술서를 작성하세요.\n\n"
        "규칙:\n"
        "1. 150~300자 분량\n"
        "2. 본 사업 역할과 관련된 핵심 역량 중심\n"
        "3. 주요 수행 프로젝트와 역할을 구체적으로 서술\n"
        "4. 보유 자격증/인증의 사업 연관성 명시"
    )

    prompt = "\n\n".join(parts)

    def _call():
        return client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "공공조달 투입인력 경력기술서 작성 전문가입니다. 평가위원이 높은 점수를 줄 수 있도록 인력의 역량과 RFP 요구사항의 연관성을 강조합니다."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=800,
        )

    try:
        resp = call_with_retry(_call)
        return resp.choices[0].message.content or ""
    except Exception as exc:
        logger.warning("generate_personnel_text LLM failed for %s: %s", entry.name, exc)
        return ""
