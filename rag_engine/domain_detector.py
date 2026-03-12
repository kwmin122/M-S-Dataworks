"""Domain Detector — RFP text → DomainType classification.

Uses LLM with keyword fallback. See spec §5 Step 1.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Optional

from openai import OpenAI

from llm_utils import call_with_retry, LLM_DEFAULT_TIMEOUT
from phase2_models import DomainType

logger = logging.getLogger(__name__)

# Keyword scoring: domain → (keyword, weight) pairs
_KEYWORD_SCORES: dict[DomainType, list[tuple[str, int]]] = {
    DomainType.IT_BUILD: [
        ("시스템 구축", 3), ("정보시스템", 3), ("SW 개발", 3), ("소프트웨어", 2),
        ("클라우드", 2), ("데이터베이스", 2), ("아키텍처", 2), ("프로그램 개발", 3),
        ("통합테스트", 2), ("데이터 이관", 2), ("ISP", 2), ("UI/UX", 1),
        ("인프라", 2), ("네트워크", 1), ("보안", 1), ("운영", 1),
    ],
    DomainType.RESEARCH: [
        ("연구", 3), ("연구용역", 4), ("선행연구", 3), ("문헌조사", 3),
        ("설문조사", 2), ("통계분석", 2), ("정책제언", 3), ("연구방법", 3),
        ("델파이", 3), ("FGI", 2), ("실증분석", 2), ("논문", 1),
        ("IRB", 3), ("연구윤리", 2), ("학술", 2), ("조사", 1),
    ],
    DomainType.CONSULTING: [
        ("컨설팅", 4), ("진단", 3), ("GAP분석", 3), ("전략 수립", 3),
        ("ISP", 2), ("현황진단", 3), ("PMO", 3), ("변화관리", 2),
        ("목표모델", 2), ("로드맵", 2), ("BPR", 3), ("PI", 2),
        ("마스터플랜", 2), ("아키텍처", 1),
    ],
    DomainType.EDUCATION_ODA: [
        ("교육", 2), ("ODA", 4), ("KOICA", 4), ("개도국", 3),
        ("역량강화", 3), ("교육과정", 2), ("교재", 2), ("콘텐츠 개발", 2),
        ("시범교육", 3), ("현지이관", 3), ("봉사단", 3), ("글로벌연수", 3),
        ("교원", 2), ("연수", 2), ("국제협력", 2),
    ],
}


def _keyword_fallback(text: str) -> DomainType:
    """Score-based keyword matching for domain classification."""
    if not text.strip():
        return DomainType.GENERAL

    scores: dict[DomainType, int] = {dt: 0 for dt in DomainType if dt != DomainType.GENERAL}
    text_lower = text.lower()

    for domain, keywords in _KEYWORD_SCORES.items():
        for kw, weight in keywords:
            if kw.lower() in text_lower:
                scores[domain] += weight

    best = max(scores, key=scores.get)
    if scores[best] < 3:  # minimum threshold
        return DomainType.GENERAL
    return best


def _call_llm_detect(
    rfp_text: str,
    api_key: Optional[str] = None,
) -> dict[str, Any]:
    """Call LLM for domain classification. Returns {"domain_type": str, "confidence": float}."""
    client = OpenAI(
        api_key=api_key or os.environ.get("OPENAI_API_KEY"),
        timeout=LLM_DEFAULT_TIMEOUT,
    )

    prompt = f"""다음 RFP(제안요청서) 텍스트를 읽고 도메인을 분류하세요.

도메인 옵션:
- it_build: IT 시스템 구축/개발/운영 사업
- research: 연구용역/정책연구/학술연구
- consulting: 컨설팅/PMO/ISP/전략수립
- education_oda: 교육/ODA/국제협력/역량강화
- general: 위 4가지에 해당하지 않는 경우

RFP 텍스트:
{rfp_text[:3000]}

JSON으로 응답하세요:
{{"domain_type": "...", "confidence": 0.0~1.0}}"""

    def _do_call():
        return client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "공공조달 RFP 도메인 분류 전문가입니다. JSON만 응답합니다."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=100,
            response_format={"type": "json_object"},
        )

    resp = call_with_retry(_do_call)
    return json.loads(resp.choices[0].message.content or "{}")


def detect_domain(
    rfx_result: dict[str, Any],
    api_key: Optional[str] = None,
) -> DomainType:
    """Detect domain type from RFP analysis result.

    Strategy: LLM first → keyword fallback if LLM fails or low confidence.
    """
    title = rfx_result.get("title", "")
    full_text = rfx_result.get("full_text", rfx_result.get("raw_text", ""))
    combined = f"{title}\n{full_text}"[:4000]

    # Try LLM
    try:
        llm_result = _call_llm_detect(combined, api_key)
        domain_str = llm_result.get("domain_type", "")
        try:
            confidence = float(llm_result.get("confidence", 0))
        except (TypeError, ValueError):
            confidence = 0.0

        if confidence >= 0.6:
            try:
                return DomainType(domain_str)
            except ValueError:
                logger.warning("LLM returned invalid domain: %s", domain_str)
    except Exception as exc:
        logger.warning("LLM domain detection failed, using keyword fallback: %s", exc)

    # Keyword fallback
    return _keyword_fallback(combined)
