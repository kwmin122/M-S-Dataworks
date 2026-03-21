"""Relevance Scorer -- RFP-based semantic matching for track records and personnel.

Scores track records and personnel against RFP requirements using multi-signal
keyword-based scoring (no LLM calls). Signals:

Track Records:
  - Semantic similarity (from ChromaDB cosine distance)
  - Domain/keyword overlap with RFP requirements
  - Scale match (budget similarity)
  - Technology overlap
  - Recency bonus

Personnel:
  - Semantic similarity (from ChromaDB cosine distance)
  - Role match against RFP required roles
  - Domain keyword overlap
  - Certification match
  - Experience level bonus
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RelevanceResult:
    """Relevance scoring result with explanation."""
    score: float  # 0.0 ~ 1.0
    match_reason: str
    signal_details: dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_KO_STOPWORDS = frozenset(
    "의 를 을 이 가 에 에서 로 으로 와 과 은 는 도 만 까지 부터 "
    "및 등 위 한 할 수 있 것 대한 통한 위한 관한 따른 대해 "
    "해당 기반 활용 사업 구축 개발 운영 관리 "
    "프로젝트 수행 지원".split()
)

# Domain keyword clusters -- maps a domain label to representative keywords.
# Used for domain matching between RFP and track records.
_DOMAIN_CLUSTERS: dict[str, set[str]] = {
    "스마트시티": {"스마트시티", "스마트도시", "관제", "IoT", "iot", "센서", "CCTV", "cctv", "교통", "도시"},
    "클라우드": {"클라우드", "cloud", "AWS", "aws", "GCP", "gcp", "Azure", "azure", "IaaS", "PaaS", "SaaS", "컨테이너", "쿠버네티스", "kubernetes", "docker"},
    "AI/빅데이터": {"AI", "ai", "인공지능", "머신러닝", "딥러닝", "빅데이터", "데이터", "분석", "ML", "ml", "NLP", "nlp", "자연어처리", "GPT"},
    "정보보안": {"보안", "정보보호", "ISMS", "isms", "개인정보", "암호화", "방화벽", "침입탐지", "취약점", "SOC"},
    "SI/개발": {"SI", "si", "개발", "소프트웨어", "웹", "앱", "모바일", "프론트엔드", "백엔드", "API", "Java", "Python"},
    "GIS/공간정보": {"GIS", "gis", "공간정보", "지리정보", "지도", "측량", "3D", "BIM", "드론"},
    "전자정부": {"전자정부", "행정", "민원", "공공", "공통기반", "표준프레임워크", "eGovFrame"},
    "교육/연구": {"교육", "학습", "LMS", "lms", "연구", "R&D", "훈련"},
    "의료/헬스케어": {"의료", "건강", "병원", "EMR", "진료", "헬스케어", "PHR"},
    "국방/안보": {"국방", "군", "안보", "방위", "무기체계", "C4I"},
}


def _tokenize(text: str) -> set[str]:
    """Split Korean/English text into a set of meaningful tokens."""
    # Split on whitespace and common punctuation
    raw = re.split(r"[\s,./·()（）\[\]<>《》「」:;\-_+|]+", text)
    tokens: set[str] = set()
    for tok in raw:
        tok = tok.strip()
        if len(tok) < 2:
            continue
        if tok.lower() in _KO_STOPWORDS:
            continue
        tokens.add(tok.lower())
    return tokens


def _extract_rfp_signals(rfx_result: dict[str, Any]) -> dict[str, Any]:
    """Extract structured signals from RFP analysis result.

    Returns dict with:
      keywords: set[str] -- all meaningful tokens from title + requirements
      budget_억: float | None -- parsed budget in 억원
      technologies: set[str] -- tech keywords mentioned
      required_roles: set[str] -- role keywords from requirements
      required_certs: set[str] -- certification keywords
      domains: set[str] -- matched domain labels
    """
    title = rfx_result.get("title", "")
    requirements = rfx_result.get("requirements", [])
    budget_str = str(rfx_result.get("budget", ""))

    # Build keyword set from title + all requirement descriptions
    all_text_parts = [title]
    role_keywords: set[str] = set()
    cert_keywords: set[str] = set()

    for req in requirements:
        if isinstance(req, dict):
            desc = req.get("description", "")
            cat = req.get("category", "").lower()
            if desc:
                all_text_parts.append(desc)
            # Detect role requirements
            if cat in ("인력", "인원", "조직", "투입인력"):
                role_keywords.update(_tokenize(desc))
            # Detect certification requirements
            if cat in ("자격", "인증", "자격증"):
                cert_keywords.update(_tokenize(desc))
        else:
            all_text_parts.append(str(req))

    full_text = " ".join(all_text_parts)
    keywords = _tokenize(full_text)

    # Parse budget
    budget = _parse_budget(budget_str)

    # Extract tech keywords -- overlap with all text
    tech_keywords: set[str] = set()
    for tok in keywords:
        # Check if token appears in any domain cluster's tech terms
        for _label, cluster in _DOMAIN_CLUSTERS.items():
            if tok in {c.lower() for c in cluster}:
                tech_keywords.add(tok)

    # Detect domains
    matched_domains: set[str] = set()
    for label, cluster in _DOMAIN_CLUSTERS.items():
        cluster_lower = {c.lower() for c in cluster}
        if keywords & cluster_lower:
            matched_domains.add(label)

    return {
        "keywords": keywords,
        "budget_억": budget,
        "technologies": tech_keywords,
        "required_roles": role_keywords,
        "required_certs": cert_keywords,
        "domains": matched_domains,
        "full_text": full_text,
    }


def _parse_budget(budget_str: str) -> float | None:
    """Parse a budget string like '50억' or '5,000만원' into 억원 float."""
    if not budget_str:
        return None
    budget_str = budget_str.replace(",", "").replace(" ", "")

    # Try 억원 pattern
    m = re.search(r"([\d.]+)\s*억", budget_str)
    if m:
        return float(m.group(1))

    # Try 만원 pattern
    m = re.search(r"([\d.]+)\s*만", budget_str)
    if m:
        return float(m.group(1)) / 10000.0

    # Try 원 pattern (plain number)
    m = re.search(r"([\d.]+)\s*원", budget_str)
    if m:
        return float(m.group(1)) / 100000000.0

    # Try plain number
    m = re.search(r"([\d.]+)", budget_str)
    if m:
        val = float(m.group(1))
        # Heuristic: if > 1000, assume 만원; if > 10, assume 억원 as-is
        if val > 10000:
            return val / 10000.0
        return val

    return None


def _parse_period_year(period_str: str) -> int | None:
    """Extract the most recent year from a period string like '2024.03 ~ 2024.12'."""
    years = re.findall(r"20\d{2}", period_str)
    if years:
        return max(int(y) for y in years)
    return None


def _keyword_overlap_score(set_a: set[str], set_b: set[str]) -> float:
    """Jaccard-like overlap score between two keyword sets."""
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    # Use min-denominator (coverage) rather than Jaccard for better signal
    # when one set is much larger (RFP keywords >> record keywords)
    denominator = min(len(set_a), len(set_b))
    if denominator == 0:
        return 0.0
    return len(intersection) / denominator


# ---------------------------------------------------------------------------
# Public scoring functions
# ---------------------------------------------------------------------------

def score_track_record_relevance(
    rfx_result: dict[str, Any],
    record_text: str,
    record_metadata: dict[str, Any],
    embedding_distance: float,
    *,
    rfp_signals: dict[str, Any] | None = None,
    current_year: int = 2026,
) -> RelevanceResult:
    """Score a single track record against the RFP.

    Args:
        rfx_result: Parsed RFP analysis result.
        record_text: Full text of the track record from ChromaDB.
        record_metadata: Metadata dict from ChromaDB (project_name, client, amount, ...).
        embedding_distance: Cosine distance from ChromaDB (lower = more similar).
        rfp_signals: Pre-computed RFP signals (optional, for batch efficiency).
        current_year: Reference year for recency calculation.

    Returns:
        RelevanceResult with score (0.0-1.0) and match_reason string.
    """
    if rfp_signals is None:
        rfp_signals = _extract_rfp_signals(rfx_result)

    signals: dict[str, float] = {}
    reasons: list[str] = []

    # --- Signal 1: Semantic similarity (weight 0.35) ---
    semantic_score = max(0.0, min(1.0, 1.0 - embedding_distance))
    signals["semantic"] = semantic_score

    # --- Signal 2: Domain/keyword overlap (weight 0.25) ---
    record_keywords = _tokenize(record_text)
    keyword_score = _keyword_overlap_score(rfp_signals["keywords"], record_keywords)
    signals["keyword_overlap"] = keyword_score

    # Detect matching domains
    record_domains: set[str] = set()
    for label, cluster in _DOMAIN_CLUSTERS.items():
        cluster_lower = {c.lower() for c in cluster}
        if record_keywords & cluster_lower:
            record_domains.add(label)
    common_domains = rfp_signals["domains"] & record_domains
    if common_domains:
        reasons.append(f"도메인 일치: {', '.join(sorted(common_domains))}")

    # --- Signal 3: Scale match (weight 0.15) ---
    rfp_budget = rfp_signals.get("budget_억")
    record_amount = record_metadata.get("amount", 0.0)
    if rfp_budget and rfp_budget > 0 and record_amount and record_amount > 0:
        ratio = min(rfp_budget, record_amount) / max(rfp_budget, record_amount)
        scale_score = ratio  # 1.0 when equal, approaches 0 when very different
        signals["scale"] = scale_score
        if ratio >= 0.5:
            reasons.append(f"규모 유사 ({record_amount:.0f}억/{rfp_budget:.0f}억)")
    else:
        signals["scale"] = 0.3  # neutral when budget info unavailable

    # --- Signal 4: Technology overlap (weight 0.15) ---
    rfp_techs = rfp_signals.get("technologies", set())
    record_techs = {t.lower() for t in record_keywords}
    tech_overlap = rfp_techs & record_techs
    if rfp_techs:
        tech_score = len(tech_overlap) / len(rfp_techs)
        signals["technology"] = tech_score
        if tech_overlap:
            # Show original case from record for readability
            display_techs = sorted(tech_overlap)[:5]
            reasons.append(f"기술 일치: {', '.join(display_techs)}")
    else:
        signals["technology"] = 0.3  # neutral

    # --- Signal 5: Recency bonus (weight 0.10) ---
    period_str = ""
    # Try to extract period from record text
    period_match = re.search(r"기간:\s*(.+)", record_text)
    if period_match:
        period_str = period_match.group(1).strip()
    record_year = _parse_period_year(period_str)
    if record_year:
        years_ago = current_year - record_year
        if years_ago <= 1:
            recency_score = 1.0
        elif years_ago <= 3:
            recency_score = 0.7
        elif years_ago <= 5:
            recency_score = 0.4
        else:
            recency_score = 0.1
        signals["recency"] = recency_score
        if years_ago <= 2:
            reasons.append(f"최근 실적 ({record_year}년)")
    else:
        signals["recency"] = 0.3  # neutral

    # --- Weighted combination ---
    weights = {
        "semantic": 0.35,
        "keyword_overlap": 0.25,
        "scale": 0.15,
        "technology": 0.15,
        "recency": 0.10,
    }
    final_score = sum(signals[k] * weights[k] for k in weights)
    final_score = round(min(1.0, max(0.0, final_score)), 3)

    # Build match reason
    project_name = record_metadata.get("project_name", "")
    if not reasons:
        if semantic_score > 0.5:
            reasons.append("RFP 과업 내용과 의미적 유사성 높음")
        else:
            reasons.append("기본 유사도 매칭")

    match_reason = f"[{final_score:.2f}] {project_name}: {'; '.join(reasons)}"

    return RelevanceResult(
        score=final_score,
        match_reason=match_reason,
        signal_details=signals,
    )


def score_personnel_relevance(
    rfx_result: dict[str, Any],
    person_text: str,
    person_metadata: dict[str, Any],
    embedding_distance: float,
    *,
    rfp_signals: dict[str, Any] | None = None,
) -> RelevanceResult:
    """Score a single personnel entry against the RFP.

    Args:
        rfx_result: Parsed RFP analysis result.
        person_text: Full text of the personnel record from ChromaDB.
        person_metadata: Metadata dict (name, role, experience_years, ...).
        embedding_distance: Cosine distance from ChromaDB.
        rfp_signals: Pre-computed RFP signals (optional, for batch efficiency).

    Returns:
        RelevanceResult with score (0.0-1.0) and match_reason string.
    """
    if rfp_signals is None:
        rfp_signals = _extract_rfp_signals(rfx_result)

    signals: dict[str, float] = {}
    reasons: list[str] = []

    # --- Signal 1: Semantic similarity (weight 0.30) ---
    semantic_score = max(0.0, min(1.0, 1.0 - embedding_distance))
    signals["semantic"] = semantic_score

    # --- Signal 2: Role match (weight 0.25) ---
    person_role = person_metadata.get("role", "").lower()
    person_keywords = _tokenize(person_text)
    role_keywords = rfp_signals.get("required_roles", set())

    # Direct role match
    role_score = 0.0
    if role_keywords:
        if person_role and any(person_role in rk or rk in person_role for rk in role_keywords):
            role_score = 1.0
            reasons.append(f"요구 역할 일치: {person_role.upper()}")
        else:
            # Partial match through keywords
            role_overlap = role_keywords & person_keywords
            role_score = min(1.0, len(role_overlap) / max(1, len(role_keywords)) * 1.5)
    else:
        role_score = 0.3  # neutral when no role requirements specified
    signals["role"] = role_score

    # --- Signal 3: Domain keyword overlap (weight 0.20) ---
    keyword_score = _keyword_overlap_score(rfp_signals["keywords"], person_keywords)
    signals["keyword_overlap"] = keyword_score

    # Check domain match
    person_domains: set[str] = set()
    for label, cluster in _DOMAIN_CLUSTERS.items():
        cluster_lower = {c.lower() for c in cluster}
        if person_keywords & cluster_lower:
            person_domains.add(label)
    common_domains = rfp_signals["domains"] & person_domains
    if common_domains:
        reasons.append(f"도메인 경험: {', '.join(sorted(common_domains))}")

    # --- Signal 4: Certification match (weight 0.15) ---
    cert_keywords = rfp_signals.get("required_certs", set())
    # Also extract certs from person text
    cert_match = re.search(r"자격증:\s*(.+)", person_text)
    person_certs = set()
    if cert_match:
        person_certs = _tokenize(cert_match.group(1))

    if cert_keywords:
        cert_overlap = cert_keywords & person_certs
        cert_score = min(1.0, len(cert_overlap) / max(1, len(cert_keywords)) * 1.5)
        if cert_overlap:
            reasons.append(f"자격증 일치: {', '.join(sorted(cert_overlap))}")
    elif person_certs:
        # No specific cert required, but having certs is a bonus
        cert_score = min(1.0, len(person_certs) * 0.2)
    else:
        cert_score = 0.2  # neutral
    signals["certification"] = cert_score

    # --- Signal 5: Experience level (weight 0.10) ---
    exp_years = int(person_metadata.get("experience_years", 0))
    if exp_years >= 15:
        exp_score = 1.0
        reasons.append(f"경력 {exp_years}년 (특급)")
    elif exp_years >= 10:
        exp_score = 0.8
        reasons.append(f"경력 {exp_years}년 (고급)")
    elif exp_years >= 5:
        exp_score = 0.5
    elif exp_years >= 1:
        exp_score = 0.3
    else:
        exp_score = 0.2
    signals["experience"] = exp_score

    # --- Weighted combination ---
    weights = {
        "semantic": 0.30,
        "role": 0.25,
        "keyword_overlap": 0.20,
        "certification": 0.15,
        "experience": 0.10,
    }
    final_score = sum(signals[k] * weights[k] for k in weights)
    final_score = round(min(1.0, max(0.0, final_score)), 3)

    # Build match reason
    person_name = person_metadata.get("name", "")
    if not reasons:
        if semantic_score > 0.5:
            reasons.append("RFP 요구사항과 의미적 유사성 높음")
        else:
            reasons.append("기본 유사도 매칭")

    match_reason = f"[{final_score:.2f}] {person_name} ({person_role}): {'; '.join(reasons)}"

    return RelevanceResult(
        score=final_score,
        match_reason=match_reason,
        signal_details=signals,
    )


def extract_rfp_signals(rfx_result: dict[str, Any]) -> dict[str, Any]:
    """Public wrapper for RFP signal extraction (batch efficiency).

    Call once per RFP, then pass the result to score_track_record_relevance()
    and score_personnel_relevance() as rfp_signals kwarg.
    """
    return _extract_rfp_signals(rfx_result)
