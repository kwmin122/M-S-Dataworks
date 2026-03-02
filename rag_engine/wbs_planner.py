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

    # "1년" → 12, "2년" → 24
    m = re.search(r"(\d+)\s*년", period_str)
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
        "당신은 공공조달 IT 프로젝트 방법론 전문가입니다. "
        "RFP를 분석하여 최적 개발 방법론을 추천합니다."
    )
    user_prompt = f"""다음 RFP를 분석하여 최적 개발 방법론을 결정하세요.

[RFP 내용]
{rfp_text}

[판단 기준]
- waterfall: 요구사항이 확정되어 있고, 단계별 산출물이 명시되어 있으며, 감리/검수 기반의 전통적 개발
- agile: 반복 개발, 사용자 피드백 중심, MVP 단계별 릴리즈, 스프린트 기반
- hybrid: 분석·설계까지 waterfall + 구현부터 agile 반복 (대부분의 공공SI 프로젝트)

[참고]
- 공공조달 프로젝트는 대부분 단계별 산출물과 감리를 요구하므로 waterfall이 기본
- 명시적으로 애자일/스크럼을 언급하거나 반복 개발을 요구하면 agile
- 설계까지 단계별 + 개발은 반복적이면 hybrid"""

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

        # Determine grade based on role
        grade = "중급"
        if role in ("PM", "PD", "프로젝트매니저"):
            grade = "특급"
        elif role in ("PL", "아키텍트", "설계자"):
            grade = "고급"

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
) -> tuple[list[WbsTask], list[PersonnelAllocation], int, MethodologyType]:
    """RFP 분석 결과로 WBS 구조 생성.

    Args:
        knowledge_texts: Layer 1 knowledge rules from KnowledgeDB (optional).
        company_context: Layer 2 회사 역량 컨텍스트 (optional).
        profile_md: 회사 제안서 프로필 (문체/전략/강점 DNA).

    Returns: (tasks, personnel, total_months, methodology)
    """
    if methodology is None:
        methodology = _detect_methodology(rfx_result, api_key=api_key)

    if total_months is None:
        total_months = _extract_project_duration(rfx_result)

    template = _TEMPLATES[methodology]

    # Use LLM to customize tasks based on RFP + Layer 1 + Layer 2 knowledge
    tasks = _generate_wbs_tasks_llm(
        rfx_result, template, total_months, methodology, api_key,
        knowledge_texts=knowledge_texts,
        company_context=company_context,
        profile_md=profile_md,
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
) -> str:
    """6계층 프롬프트 조립 (section_writer 패턴).

    Layer 1: 범용 지식 (KnowledgeDB)
    Layer 1.5: 회사 역량 (CompanyDB)
    Layer 1.7: 회사 프로필 (profile.md — 문체/전략/강점 DNA)
    Layer 2: 방법론 템플릿
    Layer 3: RFP 컨텍스트
    Layer 4: 생성 지시
    """
    parts: list[str] = []

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
        f"3. responsible_role은 PM/PL/개발자/디자이너/QA/DBA 중 택일\n"
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
) -> list[WbsTask]:
    """LLM으로 RFP 맞춤 WBS 태스크 생성 (Structured Outputs + 6계층 프롬프트)."""
    import openai

    resolved_key = api_key or os.environ.get("OPENAI_API_KEY", "")
    client = openai.OpenAI(api_key=resolved_key, timeout=LLM_DEFAULT_TIMEOUT)

    prompt = _build_wbs_prompt(rfx_result, template, total_months, methodology, knowledge_texts, company_context=company_context, profile_md=profile_md)

    system_prompt = (
        "당신은 대한민국 공공조달 프로젝트 WBS 작성 전문가입니다. "
        "RFP 분석 결과와 방법론 프레임워크를 기반으로 구체적이고 실행 가능한 WBS를 생성합니다. "
        "각 태스크는 이 사업에 특화된 내용이어야 하며, 범용적 템플릿을 그대로 복사하지 마세요."
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
            return _fallback_tasks(template, total_months)
        raw = choice.message.content or "{}"
        result = json.loads(raw)
        items = result.get("tasks", [])
    except Exception as exc:
        logger.warning("LLM WBS generation failed, using template fallback: %s", exc)
        return _fallback_tasks(template, total_months)

    if not isinstance(items, list):
        return _fallback_tasks(template, total_months)

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
                responsible_role=item.get("responsible_role", "개발자"),
                man_months=max(0.1, float(item.get("man_months", 1.0))),
            ))
        except (ValueError, TypeError):
            continue

    if not tasks:
        return _fallback_tasks(template, total_months)

    return tasks


def _fallback_tasks(
    template: list[dict[str, Any]],
    total_months: int,
) -> list[WbsTask]:
    """LLM 실패 시 템플릿 기반 기본 WBS."""
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
                responsible_role="개발자",
                man_months=round(duration * 0.8, 1),
            ))
        current_month = min(current_month + duration, total_months)

    return tasks
