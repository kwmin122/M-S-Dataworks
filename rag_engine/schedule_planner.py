"""Schedule Planner — Domain-dict-based WBS task generation.

Replaces wbs_planner.py's IT-fixed templates. Loads phases, roles,
methodologies from domain_dict.json. See spec §5 Step 4.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from openai import OpenAI

from llm_utils import call_with_retry, LLM_DEFAULT_TIMEOUT
from pack_models import DomainDict
from phase2_models import WbsTask, PersonnelAllocation

logger = logging.getLogger(__name__)


def _build_schedule_prompt(
    rfx_result: dict[str, Any],
    domain_dict: DomainDict,
    total_months: int,
    knowledge_texts: list[str] | None = None,
    company_context: str = "",
) -> str:
    """Build LLM prompt for WBS task generation using domain dict."""
    parts: list[str] = []

    # Domain context
    phases_str = ", ".join(f"{p.name}" for p in domain_dict.phases)
    roles_str = ", ".join(f"{r.name}({r.grade})" for r in domain_dict.roles)
    methods_str = ", ".join(m.name for m in domain_dict.methodologies)
    deliverables_str = ", ".join(domain_dict.deliverables_common[:10])

    parts.append(f"""## 도메인: {domain_dict.domain_type}
활용 가능한 단계: {phases_str}
활용 가능한 역할: {roles_str}
방법론 옵션: {methods_str}
일반 산출물: {deliverables_str}""")

    # Layer 1 knowledge
    if knowledge_texts:
        parts.append("## 공공조달 WBS 작성 지식:\n" + "\n".join(f"- {t}" for t in knowledge_texts[:5]))

    # Company context
    if company_context:
        parts.append(f"## 회사 역량:\n{company_context}")

    # RFP
    title = rfx_result.get("title", "")
    full_text = rfx_result.get("full_text", rfx_result.get("raw_text", ""))[:3000]
    parts.append(f"## RFP 정보:\n사업명: {title}\n{full_text}")

    # Task
    parts.append(f"""## 요청:
위 도메인의 단계와 역할을 사용하여 총 {total_months}개월 사업의 WBS 태스크를 생성하세요.

JSON 배열로 응답하세요. 각 태스크:
{{"phase": "단계명", "task_name": "태스크명", "start_month": 1, "duration_months": 2,
  "responsible_role": "역할명", "man_months": 2.0, "deliverables": ["산출물1"]}}

규칙:
- 위 '활용 가능한 단계'를 사업 특성에 맞게 선택하여 사용
- 위 '활용 가능한 역할'만 responsible_role에 사용
- 각 단계마다 최소 2개 이상 구체적 태스크
- man_months는 현실적 수치
- 모든 태스크의 start_month + duration_months가 {total_months} 이내
- 10~25개 태스크 범위""")

    return "\n\n".join(parts)


def _call_llm_schedule(
    prompt: str,
    api_key: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Call LLM for WBS task generation. Returns list of task dicts."""
    client = OpenAI(
        api_key=api_key or os.environ.get("OPENAI_API_KEY"),
        timeout=LLM_DEFAULT_TIMEOUT,
    )

    def _do_call():
        return client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 공공조달 수행계획서 WBS 전문가입니다. JSON만 응답합니다."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=4000,
            response_format={"type": "json_object"},
        )

    resp = call_with_retry(_do_call)
    content = resp.choices[0].message.content or "{}"
    parsed = json.loads(content)
    # Handle both {"tasks": [...]} and [...] formats
    if isinstance(parsed, list):
        return parsed
    # Try common key variations LLMs may use
    for key in ("tasks", "task_list", "wbs_tasks", "wbs", "data", "items"):
        if key in parsed and isinstance(parsed[key], list):
            return parsed[key]
    # Last resort: find the first list value in the dict
    for v in parsed.values():
        if isinstance(v, list):
            return v
    return []


def _allocate_personnel(
    tasks: list[WbsTask],
    total_months: int,
    domain_dict: DomainDict,
) -> list[PersonnelAllocation]:
    """Generate personnel allocation from tasks. Reuses wbs_planner pattern."""
    role_months: dict[str, float] = {}
    for t in tasks:
        role = t.responsible_role
        role_months[role] = role_months.get(role, 0) + t.man_months

    # Map roles to grades from domain_dict
    role_grades: dict[str, str] = {}
    for r in domain_dict.roles:
        role_grades[r.name] = r.grade
        for alias in r.aliases:
            role_grades[alias] = r.grade

    personnel: list[PersonnelAllocation] = []
    for role, mm in sorted(role_months.items(), key=lambda x: -x[1]):
        monthly = [0.0] * total_months
        # Distribute man-months across task periods
        for t in tasks:
            if t.responsible_role == role:
                for m in range(
                    t.start_month - 1,
                    min(t.start_month - 1 + t.duration_months, total_months),
                ):
                    monthly[m] += t.man_months / max(t.duration_months, 1)

        personnel.append(PersonnelAllocation(
            role=role,
            grade=role_grades.get(role, "중급"),
            total_man_months=round(mm, 1),
            monthly_allocation=[round(m, 1) for m in monthly],
        ))

    return personnel


def plan_schedule(
    rfx_result: dict[str, Any],
    domain_dict: DomainDict,
    total_months: int = 12,
    api_key: Optional[str] = None,
    knowledge_texts: list[str] | None = None,
    company_context: str = "",
) -> tuple[list[WbsTask], list[PersonnelAllocation], int]:
    """Plan WBS schedule using domain dict.

    Returns: (tasks, personnel, total_months)
    """
    # Detect total_months from RFP if not provided
    if not total_months:
        duration = rfx_result.get("duration_months")
        total_months = int(duration) if duration else 12

    prompt = _build_schedule_prompt(
        rfx_result, domain_dict, total_months, knowledge_texts, company_context
    )
    raw_tasks = _call_llm_schedule(prompt, api_key)

    tasks: list[WbsTask] = []
    for t in raw_tasks:
        try:
            tasks.append(WbsTask(
                phase=t.get("phase", ""),
                task_name=t.get("task_name", ""),
                start_month=int(t.get("start_month", 1)),
                duration_months=int(t.get("duration_months", 1)),
                responsible_role=t.get("responsible_role", ""),
                man_months=float(t.get("man_months", 1.0)),
                deliverables=t.get("deliverables", []),
            ))
        except (ValueError, TypeError) as e:
            logger.warning("Skipping invalid task: %s — %s", t, e)

    personnel = _allocate_personnel(tasks, total_months, domain_dict)
    return tasks, personnel, total_months
