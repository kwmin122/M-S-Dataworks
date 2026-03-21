"""WBS Planner — RFP 분석 결과 → WBS 구조 + 인력 배치 계획.

RFP에서 사업기간, 과업내용을 추출하고 방법론 템플릿 기반 WBS를 생성.
proposal_planner.py 패턴 재사용.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Optional

from llm_utils import call_with_retry, LLM_DEFAULT_TIMEOUT
from phase2_models import MethodologyType, WbsTask, PersonnelAllocation

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 방법론별 표준 WBS 템플릿
# ---------------------------------------------------------------------------

WATERFALL_TEMPLATE: list[dict[str, Any]] = [
    {"phase": "착수", "ratio": 0.05, "tasks": ["사업 착수 보고", "현황 분석", "요구사항 수집"]},
    {"phase": "분석", "ratio": 0.15, "tasks": ["현행시스템 분석", "요구사항 정의", "분석서 작성"]},
    {"phase": "설계", "ratio": 0.20, "tasks": ["아키텍처 설계", "UI/UX 설계", "DB 설계", "인터페이스 설계"]},
    {"phase": "구현", "ratio": 0.35, "tasks": ["기능 개발", "단위 테스트", "코드 리뷰"]},
    {"phase": "시험", "ratio": 0.15, "tasks": ["통합 테스트", "성능 테스트", "보안 점검", "사용자 수용 테스트"]},
    {"phase": "이행/종료", "ratio": 0.10, "tasks": ["데이터 이관", "시스템 전환", "운영자 교육", "완료 보고"]},
]

AGILE_TEMPLATE: list[dict[str, Any]] = [
    {"phase": "착수/백로그", "ratio": 0.10, "tasks": ["사업 착수", "백로그 정의", "스프린트 계획"]},
    {"phase": "스프린트 1~N", "ratio": 0.65, "tasks": ["스프린트 개발", "스프린트 리뷰", "회고"]},
    {"phase": "릴리스/안정화", "ratio": 0.15, "tasks": ["릴리스 테스트", "성능 최적화", "보안 점검"]},
    {"phase": "이행/종료", "ratio": 0.10, "tasks": ["데이터 이관", "운영 교육", "완료 보고"]},
]

HYBRID_TEMPLATE: list[dict[str, Any]] = [
    {"phase": "착수", "ratio": 0.05, "tasks": ["사업 착수 보고", "현황 분석"]},
    {"phase": "분석/설계", "ratio": 0.20, "tasks": ["요구사항 분석", "아키텍처 설계", "UI/UX 설계"]},
    {"phase": "반복 개발", "ratio": 0.45, "tasks": ["스프린트 개발", "코드 리뷰", "통합 테스트"]},
    {"phase": "시험/안정화", "ratio": 0.20, "tasks": ["시스템 테스트", "성능/보안 검증", "사용자 수용"]},
    {"phase": "이행/종료", "ratio": 0.10, "tasks": ["데이터 이관", "교육", "완료 보고"]},
]

_TEMPLATES: dict[MethodologyType, list[dict[str, Any]]] = {
    MethodologyType.WATERFALL: WATERFALL_TEMPLATE,
    MethodologyType.AGILE: AGILE_TEMPLATE,
    MethodologyType.HYBRID: HYBRID_TEMPLATE,
}

# ---------------------------------------------------------------------------
# 도메인별 WBS 템플릿 (비-IT 사업 지원)
# ---------------------------------------------------------------------------

DOMAIN_TEMPLATES: dict[str, dict[str, list[dict[str, Any]]]] = {
    "it_build": {
        "waterfall": [
            {"phase": "착수", "ratio": 0.05, "tasks": ["사업착수 회의", "수행계획서 작성", "착수보고"]},
            {"phase": "분석", "ratio": 0.15, "tasks": ["현황 분석", "요구사항 분석", "요구사항 명세"]},
            {"phase": "설계", "ratio": 0.20, "tasks": ["아키텍처 설계", "상세 설계", "UI/UX 설계", "DB 설계"]},
            {"phase": "구현", "ratio": 0.35, "tasks": ["기능 개발", "단위 테스트", "통합 테스트"]},
            {"phase": "시험", "ratio": 0.15, "tasks": ["성능 테스트", "보안 점검", "사용자 수용 테스트"]},
            {"phase": "이행/종료", "ratio": 0.10, "tasks": ["데이터 이관", "시스템 전환", "교육", "종료보고"]},
        ],
    },
    "construction": {
        "waterfall": [
            {"phase": "착수", "ratio": 0.05, "tasks": ["착수 준비", "시공계획서 작성", "착수보고"]},
            {"phase": "설계검토", "ratio": 0.10, "tasks": ["설계도서 검토", "시방서 분석", "물량 검증"]},
            {"phase": "시공", "ratio": 0.50, "tasks": ["가설공사", "토공사", "구조물 공사", "설비 공사", "마감 공사"]},
            {"phase": "품질/안전", "ratio": 0.15, "tasks": ["품질시험", "안전관리", "환경관리", "자재 검수"]},
            {"phase": "준공", "ratio": 0.10, "tasks": ["준공검사", "시운전", "하자보수 계획"]},
            {"phase": "종료", "ratio": 0.10, "tasks": ["준공보고", "인수인계", "유지관리 계획"]},
        ],
    },
    "consulting": {
        "waterfall": [
            {"phase": "착수", "ratio": 0.05, "tasks": ["착수보고", "수행계획 수립"]},
            {"phase": "현황분석", "ratio": 0.20, "tasks": ["현황 조사", "이해관계자 인터뷰", "벤치마킹", "문제점 도출"]},
            {"phase": "전략수립", "ratio": 0.25, "tasks": ["목표 설정", "전략 대안 도출", "최적안 선정"]},
            {"phase": "실행계획", "ratio": 0.25, "tasks": ["실행 로드맵", "과제 정의", "추진체계 설계"]},
            {"phase": "보고/이행", "ratio": 0.15, "tasks": ["최종보고서 작성", "이행 지원", "교육/확산"]},
            {"phase": "종료", "ratio": 0.10, "tasks": ["종료보고", "산출물 납품"]},
        ],
    },
    "research": {
        "waterfall": [
            {"phase": "착수", "ratio": 0.05, "tasks": ["연구착수", "연구계획서 확정"]},
            {"phase": "문헌조사", "ratio": 0.15, "tasks": ["선행연구 분석", "국내외 사례 조사", "법제도 분석"]},
            {"phase": "연구수행", "ratio": 0.40, "tasks": ["연구방법론 적용", "데이터 수집", "분석/실험", "결과 도출"]},
            {"phase": "보고서", "ratio": 0.25, "tasks": ["중간보고", "최종보고서 작성", "정책 제언"]},
            {"phase": "종료", "ratio": 0.15, "tasks": ["전문가 자문", "성과 발표", "산출물 납품"]},
        ],
    },
    "goods": {
        "waterfall": [
            {"phase": "착수", "ratio": 0.05, "tasks": ["계약 확정", "납품계획 수립"]},
            {"phase": "제작/조달", "ratio": 0.40, "tasks": ["원자재 조달", "제조/생산", "품질검사"]},
            {"phase": "납품", "ratio": 0.20, "tasks": ["포장/운송", "납품검수", "설치/시운전"]},
            {"phase": "교육/인수", "ratio": 0.20, "tasks": ["사용자 교육", "운영 매뉴얼", "인수인계"]},
            {"phase": "하자보증", "ratio": 0.15, "tasks": ["하자보수 체계", "유지관리 지원", "종료보고"]},
        ],
    },
    "supervision": {
        "waterfall": [
            {"phase": "착수", "ratio": 0.05, "tasks": ["감리착수", "감리계획서 작성", "착수보고"]},
            {"phase": "분석단계 감리", "ratio": 0.20, "tasks": ["요구사항 검증", "분석 산출물 검토", "감리조서 작성"]},
            {"phase": "설계단계 감리", "ratio": 0.25, "tasks": ["설계 적정성 검증", "아키텍처 검토", "감리조서 작성"]},
            {"phase": "구현단계 감리", "ratio": 0.25, "tasks": ["소스코드 품질검증", "테스트 충분성 검토", "감리조서 작성"]},
            {"phase": "종료단계 감리", "ratio": 0.15, "tasks": ["산출물 완전성 검증", "이관 적정성 검토"]},
            {"phase": "종료", "ratio": 0.10, "tasks": ["최종 감리보고서", "감리 종료보고"]},
        ],
    },
}

# ---------------------------------------------------------------------------
# 도메인 감지 (키워드 기반)
# ---------------------------------------------------------------------------

DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "construction": ["공사", "시공", "토목", "건축", "설비", "건설"],
    "supervision": ["감리", "PMO", "검수", "감리원"],
    "consulting": ["컨설팅", "ISP", "BPR", "전략수립", "정보화전략"],
    "research": ["연구", "R&D", "학술", "논문", "실험"],
    "goods": ["물품", "납품", "제조", "장비", "기자재", "설치"],
    "it_build": ["정보시스템", "소프트웨어", "SW", "개발", "구축", "홈페이지", "앱", "플랫폼"],
}


def _detect_domain(rfp_text: str) -> str:
    """RFP 텍스트에서 사업 도메인을 키워드 기반으로 감지.

    Returns one of: it_build, construction, consulting, research, goods, supervision.
    Falls back to 'it_build' if no clear signal.
    """
    text = rfp_text.lower()
    scores: dict[str, int] = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        scores[domain] = sum(1 for kw in keywords if kw.lower() in text)

    if not any(scores.values()):
        return "it_build"

    best = max(scores, key=lambda d: scores[d])
    if scores[best] == 0:
        return "it_build"
    return best


def _get_domain_template(domain: str, methodology: MethodologyType) -> list[dict[str, Any]]:
    """도메인 + 방법론에 맞는 WBS 템플릿 반환.

    비-IT 도메인은 waterfall만 지원. agile/hybrid 요청 시 IT 템플릿 사용.
    """
    if domain != "it_build" and methodology != MethodologyType.WATERFALL:
        # Non-IT domains only have waterfall templates; fall back to IT methodology template
        logger.info(
            "Domain '%s' has no %s template, using IT %s template",
            domain, methodology.value, methodology.value,
        )
        return _TEMPLATES[methodology]

    domain_entry = DOMAIN_TEMPLATES.get(domain, DOMAIN_TEMPLATES["it_build"])
    meth_key = methodology.value  # "waterfall" / "agile" / "hybrid"
    if meth_key in domain_entry:
        return domain_entry[meth_key]

    # IT agile/hybrid — use the original _TEMPLATES
    return _TEMPLATES[methodology]


# ---------------------------------------------------------------------------
# 역할-등급 매핑 (도메인 확장)
# ---------------------------------------------------------------------------

ROLE_GRADES: dict[str, str] = {
    # IT
    "PM": "특급", "PD": "특급", "프로젝트매니저": "특급",
    "PL": "고급", "아키텍트": "고급", "설계자": "고급",
    # Construction
    "현장소장": "특급", "공사감독": "특급",
    "시공관리자": "고급", "품질관리자": "고급", "안전관리자": "고급",
    # Supervision
    "총괄감리원": "특급", "책임감리원": "특급",
    "수석감리원": "고급", "감리원": "중급",
    # Research
    "연구책임자": "특급", "책임연구원": "고급",
    "선임연구원": "고급", "연구원": "중급",
    # Consulting
    "수석컨설턴트": "특급", "선임컨설턴트": "고급",
    "컨설턴트": "중급",
}

# Default role per domain (used by _fallback_tasks when no role info)
_DOMAIN_DEFAULT_ROLE: dict[str, str] = {
    "it_build": "개발자",
    "construction": "시공관리자",
    "consulting": "컨설턴트",
    "research": "연구원",
    "goods": "조달담당자",
    "supervision": "감리원",
}


# ---------------------------------------------------------------------------
# 사업기간 추출
# ---------------------------------------------------------------------------

def _extract_project_duration(rfx_result: dict[str, Any]) -> int:
    """RFP에서 사업기간(개월) 추출. 기본값 6."""
    period_str = rfx_result.get("project_period", "")
    if not period_str:
        return 6

    # "8개월" → 8
    m = re.search(r"(\d+)\s*개월", period_str)
    if m:
        return max(1, int(m.group(1)))

    # "12 months" → 12
    m = re.search(r"(\d+)\s*month", period_str, re.IGNORECASE)
    if m:
        return max(1, int(m.group(1)))

    # 날짜 범위: "2026년 4월 ~ 2026년 9월" or "2026.04 ~ 2026.09"
    m = re.search(r"(\d{4})\D*(\d{1,2})\D*~\D*(\d{4})\D*(\d{1,2})", period_str)
    if m:
        y1, m1, y2, m2 = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
        months = (y2 - y1) * 12 + (m2 - m1)
        if 1 <= months <= 60:
            return months

    # "1년" → 12, "2년" → 24 (but NOT "2026년" — 4자리 연도 제외)
    m = re.search(r"(?<!\d)([1-9]|[1-4]\d)\s*년", period_str)
    if m:
        return max(1, int(m.group(1)) * 12)

    logger.warning("project_period 파싱 실패: '%s', 기본값 6개월 적용", period_str)
    return 6


METHODOLOGY_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "methodology": {
            "type": "string",
            "enum": ["waterfall", "agile", "hybrid"],
            "description": "감지된 최적 개발 방법론",
        },
        "confidence": {
            "type": "number",
            "description": "방법론 판단 신뢰도 (0.0~1.0)",
        },
        "reasoning": {
            "type": "string",
            "description": "판단 근거 요약 (한국어)",
        },
    },
    "required": ["methodology", "confidence", "reasoning"],
}


def _detect_methodology_keywords(rfx_result: dict[str, Any]) -> MethodologyType:
    """키워드 기반 방법론 감지 (LLM 없이 동작하는 fallback)."""
    text = json.dumps(rfx_result, ensure_ascii=False).lower()
    agile_keywords = ["애자일", "agile", "스크럼", "scrum", "스프린트", "sprint", "칸반", "kanban"]
    waterfall_keywords = ["폭포수", "waterfall", "단계별", "v-모델"]

    agile_count = sum(1 for kw in agile_keywords if kw in text)
    waterfall_count = sum(1 for kw in waterfall_keywords if kw in text)

    if agile_count > waterfall_count:
        return MethodologyType.AGILE
    elif waterfall_count > agile_count:
        return MethodologyType.WATERFALL
    return MethodologyType.WATERFALL  # default


def _detect_methodology(
    rfx_result: dict[str, Any],
    api_key: Optional[str] = None,
) -> MethodologyType:
    """RFP 텍스트에서 방법론 자동 감지.

    api_key가 있으면 LLM Structured Outputs로 문맥 분석.
    없거나 실패 시 키워드 fallback.
    """
    resolved_key = api_key or os.environ.get("OPENAI_API_KEY", "")

    # Build context text from RFP
    rfp_text_parts = [
        rfx_result.get("title", ""),
        rfx_result.get("rfp_text_summary", ""),
    ]
    for req in rfx_result.get("requirements", []):
        desc = req.get("description", "") if isinstance(req, dict) else str(req)
        if desc:
            rfp_text_parts.append(desc)
    rfp_text = "\n".join(p for p in rfp_text_parts if p)[:3000]

    # 3000자 제한: 방법론 감지는 고수준 신호만 필요하므로 충분
    if not rfp_text.strip():
        return _detect_methodology_keywords(rfx_result)

    import openai

    client = openai.OpenAI(api_key=resolved_key, timeout=LLM_DEFAULT_TIMEOUT)

    system_prompt = (
        "당신은 대한민국 공공조달 프로젝트 방법론 전문가입니다. "
        "용역(IT/연구/컨설팅), 물품, 공사 등 모든 조달 유형의 RFP를 분석하여 "
        "최적 수행 방법론을 추천합니다."
    )
    user_prompt = f"""다음 RFP를 분석하여 최적 수행 방법론을 결정하세요.

[RFP 내용]
{rfp_text}

[판단 기준]
- waterfall: 요구사항이 확정되어 있고, 단계별 산출물이 명시되어 있으며, 감리/검수 기반의 전통적 수행
- agile: 반복 수행, 사용자 피드백 중심, MVP 단계별 릴리즈, 스프린트 기반
- hybrid: 분석·설계까지 waterfall + 수행부터 agile 반복

[참고]
- 공공조달 프로젝트는 대부분 단계별 산출물과 감리를 요구하므로 waterfall이 기본
- 명시적으로 애자일/스크럼을 언급하거나 반복 수행을 요구하면 agile
- IT 프로젝트뿐 아니라 연구용역, 컨설팅, 물품, 공사 등도 이 기준으로 판단
- 비-IT 프로젝트는 대부분 waterfall이 적절"""

    def _call():
        return client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=500,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "methodology_detection",
                    "strict": True,
                    "schema": METHODOLOGY_JSON_SCHEMA,
                },
            },
        )

    try:
        resp = call_with_retry(_call)
        choice = resp.choices[0]
        if choice.finish_reason == "length":
            logger.warning("Methodology detection truncated (finish_reason=length), using keyword fallback")
            return _detect_methodology_keywords(rfx_result)
        raw = choice.message.content or "{}"
        result = json.loads(raw)
        methodology_str = result.get("methodology", "waterfall")
        confidence = result.get("confidence", 0.0)
        reasoning = result.get("reasoning", "")

        logger.info(
            "LLM methodology detection: %s (confidence=%.2f, reason=%s)",
            methodology_str, confidence, reasoning,
        )

        mapping = {
            "waterfall": MethodologyType.WATERFALL,
            "agile": MethodologyType.AGILE,
            "hybrid": MethodologyType.HYBRID,
        }
        return mapping.get(methodology_str, MethodologyType.WATERFALL)
    except Exception as exc:
        logger.warning("LLM methodology detection failed, using keyword fallback: %s", exc)
        return _detect_methodology_keywords(rfx_result)


# ---------------------------------------------------------------------------
# WBS 생성
# ---------------------------------------------------------------------------

def _allocate_personnel(
    tasks: list[WbsTask],
    total_months: int,
) -> list[PersonnelAllocation]:
    """WBS 태스크 기반 인력 배치표 생성."""
    role_mm: dict[str, float] = {}
    for task in tasks:
        role = task.responsible_role or "개발자"
        role_mm[role] = role_mm.get(role, 0) + task.man_months

    allocations: list[PersonnelAllocation] = []
    for role, total_mm in sorted(role_mm.items(), key=lambda x: -x[1]):
        monthly = [0.0] * total_months
        # Distribute evenly across relevant months
        role_tasks = [t for t in tasks if (t.responsible_role or "개발자") == role]
        for task in role_tasks:
            for m in range(task.start_month - 1, min(task.end_month(), total_months)):
                if task.duration_months > 0:
                    monthly[m] += task.man_months / task.duration_months

        # Determine grade based on role (expanded ROLE_GRADES lookup)
        grade = ROLE_GRADES.get(role, "중급")

        allocations.append(PersonnelAllocation(
            role=role,
            grade=grade,
            total_man_months=round(total_mm, 1),
            monthly_allocation=[round(v, 2) for v in monthly],
        ))

    return allocations


def plan_wbs(
    rfx_result: dict[str, Any],
    methodology: Optional[MethodologyType] = None,
    total_months: Optional[int] = None,
    api_key: Optional[str] = None,
    knowledge_texts: Optional[list[str]] = None,
    company_context: str = "",
    profile_md: str = "",
    domain: Optional[str] = None,
) -> tuple[list[WbsTask], list[PersonnelAllocation], int, MethodologyType]:
    """RFP 분석 결과로 WBS 구조 생성.

    Args:
        knowledge_texts: Layer 1 knowledge rules from KnowledgeDB (optional).
        company_context: Layer 2 회사 역량 컨텍스트 (optional).
        profile_md: 회사 제안서 프로필 (문체/전략/강점 DNA).
        domain: 사업 도메인 (it_build/construction/consulting/research/goods/supervision).
                None이면 RFP 텍스트에서 자동 감지.

    Returns: (tasks, personnel, total_months, methodology)
    """
    if methodology is None:
        methodology = _detect_methodology(rfx_result, api_key=api_key)

    if total_months is None:
        total_months = _extract_project_duration(rfx_result)

    # Safety clamp: max 60 months (5 years) — prevents LLM hallucination crash
    total_months = max(1, min(total_months, 60))

    # Detect domain from RFP if not explicitly provided
    if domain is None:
        rfp_text_for_domain = json.dumps(rfx_result, ensure_ascii=False)
        domain = _detect_domain(rfp_text_for_domain)
    logger.info("WBS domain detected: %s", domain)

    # Select domain-aware template
    template = _get_domain_template(domain, methodology)

    # Use LLM to customize tasks based on RFP + Layer 1 + Layer 2 knowledge
    tasks = _generate_wbs_tasks_llm(
        rfx_result, template, total_months, methodology, api_key,
        knowledge_texts=knowledge_texts,
        company_context=company_context,
        profile_md=profile_md,
        domain=domain,
    )

    # Allocate personnel
    personnel = _allocate_personnel(tasks, total_months)

    return tasks, personnel, total_months, methodology


WBS_TASK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "tasks": {
            "type": "array",
            "description": "WBS 태스크 목록 (15~30개)",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "phase": {"type": "string", "description": "단계명 (착수/분석/설계/구현/시험/이행 등)"},
                    "task_name": {"type": "string", "description": "세부 작업명"},
                    "start_month": {"type": "integer", "description": "시작월 (1부터)"},
                    "duration_months": {"type": "integer", "description": "소요 기간 (월)"},
                    "deliverables": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "산출물 목록",
                    },
                    "responsible_role": {"type": "string", "description": "담당 역할 (PM/PL/개발자/디자이너/QA/DBA)"},
                    "man_months": {"type": "number", "description": "투입 M/M (0.5~5.0)"},
                },
                "required": ["phase", "task_name", "start_month", "duration_months", "deliverables", "responsible_role", "man_months"],
            },
        },
    },
    "required": ["tasks"],
}


def _build_wbs_prompt(
    rfx_result: dict[str, Any],
    template: list[dict[str, Any]],
    total_months: int,
    methodology: MethodologyType,
    knowledge_texts: Optional[list[str]] = None,
    company_context: str = "",
    profile_md: str = "",
    domain: str = "it_build",
) -> str:
    """7계층 프롬프트 조립 (section_writer 패턴).

    Layer 0: 도메인 컨텍스트
    Layer 1: 범용 지식 (KnowledgeDB)
    Layer 1.5: 회사 역량 (CompanyDB)
    Layer 1.7: 회사 프로필 (profile.md — 문체/전략/강점 DNA)
    Layer 2: 방법론 템플릿
    Layer 3: RFP 컨텍스트
    Layer 4: 생성 지시
    """
    parts: list[str] = []

    # Layer 0 — domain context
    domain_labels = {
        "it_build": "IT 시스템 구축/개발",
        "construction": "건설/시공/공사",
        "consulting": "컨설팅/ISP/BPR",
        "research": "연구/R&D/학술용역",
        "goods": "물품/장비 납품",
        "supervision": "감리/PMO",
    }
    domain_label = domain_labels.get(domain, "IT 시스템 구축/개발")
    parts.append(
        f"## 사업 도메인: {domain_label}\n"
        f"이 사업은 '{domain_label}' 유형입니다. "
        f"태스크명, 산출물, 담당 역할을 이 도메인에 맞게 작성하세요. "
        f"IT 전용 용어(아키텍처 설계, 단위 테스트 등)를 비-IT 사업에 사용하지 마세요."
    )

    # Layer 1 — retrieved universal knowledge
    if knowledge_texts:
        rules = "\n".join(f"- {t}" for t in knowledge_texts[:10])
        parts.append(f"## 수행계획서/WBS 작성 핵심 규칙 (공공조달 지식 기반):\n{rules}")

    # Layer 1.5 — company context (유사실적의 수행기간/인력 패턴 활용)
    if company_context:
        parts.append(f"## 제안사 역량 정보 (인력배치/기간 참고):\n{company_context[:2000]}")

    # Layer 1.7 — company profile (문체, 강점 패턴, 전략 — 반드시 준수)
    if profile_md:
        parts.append(f"## 이 회사의 제안서 프로필 (반드시 준수):\n{profile_md}")

    # Layer 2 — methodology template
    template_str = json.dumps(template, ensure_ascii=False, indent=2)
    parts.append(
        f"## 방법론 프레임워크: {methodology.value}\n"
        f"아래 표준 단계 구조를 참고하되, RFP 요구사항에 맞게 태스크를 구체화하세요.\n"
        f"{template_str}"
    )

    # Layer 3 — RFP context
    requirements_str = ""
    for req in rfx_result.get("requirements", []):
        desc = req.get("description", "") if isinstance(req, dict) else str(req)
        if desc:
            requirements_str += f"- {desc}\n"

    rfp_summary = rfx_result.get("rfp_text_summary", "")
    rfp_context = f"""## 이번 사업 정보:
사업명: {rfx_result.get('title', '')}
발주기관: {rfx_result.get('issuing_org', '')}
사업기간: {total_months}개월
예산: {rfx_result.get('budget', '')}"""

    if rfp_summary:
        rfp_context += f"\n\n사업 요약:\n{rfp_summary[:2000]}"
    if requirements_str:
        rfp_context += f"\n\n과업 요구사항:\n{requirements_str}"

    parts.append(rfp_context)

    # Layer 4 — generation instructions
    parts.append(
        f"## 작성 지시:\n"
        f"위 정보를 기반으로 이 사업에 최적화된 WBS 태스크를 생성하세요.\n\n"
        f"규칙:\n"
        f"1. 총 15~30개 태스크 (사업 규모에 비례)\n"
        f"2. 템플릿의 ratio에 비례한 기간 배분 (전체 {total_months}개월)\n"
        f"3. responsible_role은 사업 유형에 맞는 역할 (예: PM/PL/개발자/연구원/설계자/시공관리자/품질관리자 등)\n"
        f"4. man_months는 해당 태스크의 투입 M/M (0.5~5.0)\n"
        f"5. 시작월(1~{total_months})은 전후 태스크와 논리적으로 연결\n"
        f"6. RFP 과업 요구사항을 구체적으로 반영한 태스크명과 산출물\n"
        f"7. 단순 템플릿 복사가 아닌, 이 사업에 특화된 내용"
    )

    return "\n\n".join(parts)


def _generate_wbs_tasks_llm(
    rfx_result: dict[str, Any],
    template: list[dict[str, Any]],
    total_months: int,
    methodology: MethodologyType,
    api_key: Optional[str] = None,
    knowledge_texts: Optional[list[str]] = None,
    company_context: str = "",
    profile_md: str = "",
    domain: str = "it_build",
) -> list[WbsTask]:
    """LLM으로 RFP 맞춤 WBS 태스크 생성 (Structured Outputs + 7계층 프롬프트)."""
    import openai

    resolved_key = api_key or os.environ.get("OPENAI_API_KEY", "")
    client = openai.OpenAI(api_key=resolved_key, timeout=LLM_DEFAULT_TIMEOUT)

    prompt = _build_wbs_prompt(rfx_result, template, total_months, methodology, knowledge_texts, company_context=company_context, profile_md=profile_md, domain=domain)

    system_prompt = (
        "당신은 대한민국 공공조달 프로젝트 WBS 작성 전문가입니다. "
        "IT 구축, 건설, 컨설팅, 연구, 물품, 감리 등 모든 조달 유형의 WBS를 생성합니다. "
        "RFP 분석 결과와 방법론 프레임워크를 기반으로 구체적이고 실행 가능한 WBS를 생성합니다. "
        "각 태스크는 이 사업에 특화된 내용이어야 하며, 범용적 템플릿을 그대로 복사하지 마세요. "
        "사업 도메인에 맞는 용어와 역할을 사용하세요."
    )

    def _call():
        return client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=4000,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "wbs_tasks",
                    "strict": True,
                    "schema": WBS_TASK_SCHEMA,
                },
            },
        )

    try:
        resp = call_with_retry(_call)
        choice = resp.choices[0]
        # Unlike rfx_analyzer (which retries with doubled max_tokens),
        # WBS truncation falls back to templates directly because
        # template-based WBS is always a valid output.
        if choice.finish_reason == "length":
            logger.warning("WBS generation truncated (finish_reason=length), using fallback")
            return _fallback_tasks(template, total_months, domain=domain)
        raw = choice.message.content or "{}"
        result = json.loads(raw)
        items = result.get("tasks", [])
    except Exception as exc:
        logger.warning("LLM WBS generation failed, using template fallback: %s", exc)
        return _fallback_tasks(template, total_months, domain=domain)

    if not isinstance(items, list):
        return _fallback_tasks(template, total_months, domain=domain)

    tasks: list[WbsTask] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            start = max(1, min(int(item.get("start_month", 1)), total_months))
            dur = max(1, int(item.get("duration_months", 1)))
            dur = min(dur, total_months - start + 1)  # clamp: end_month <= total_months
            tasks.append(WbsTask(
                phase=item.get("phase", ""),
                task_name=item.get("task_name", ""),
                start_month=start,
                duration_months=dur,
                deliverables=item.get("deliverables", []),
                responsible_role=item.get("responsible_role", _DOMAIN_DEFAULT_ROLE.get(domain, "개발자")),
                man_months=max(0.1, float(item.get("man_months", 1.0))),
            ))
        except (ValueError, TypeError):
            continue

    if not tasks:
        return _fallback_tasks(template, total_months, domain=domain)

    return tasks


def _fallback_tasks(
    template: list[dict[str, Any]],
    total_months: int,
    domain: str = "it_build",
) -> list[WbsTask]:
    """LLM 실패 시 템플릿 기반 기본 WBS."""
    default_role = _DOMAIN_DEFAULT_ROLE.get(domain, "개발자")
    tasks: list[WbsTask] = []
    current_month = 1
    for phase_info in template:
        duration = max(1, round(total_months * phase_info["ratio"]))
        for task_name in phase_info["tasks"]:
            tasks.append(WbsTask(
                phase=phase_info["phase"],
                task_name=task_name,
                start_month=current_month,
                duration_months=duration,
                responsible_role=default_role,
                man_months=round(duration * 0.8, 1),
            ))
        current_month = min(current_month + duration, total_months)

    return tasks
