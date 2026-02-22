from __future__ import annotations
import re
from typing import Any


def extract_template_sections(template_text: str) -> dict[str, str]:
    """DOCX 텍스트에서 {{섹션명}} 플레이스홀더를 파싱한다."""
    pattern = r'\{\{([^}]+)\}\}'
    placeholders = re.findall(pattern, template_text)
    return {p: f'{{{{{p}}}}}' for p in dict.fromkeys(placeholders)}


def fill_template_sections(
    sections: dict[str, str],
    notice_text: str,
    company_info: dict[str, Any],
) -> dict[str, str]:
    """각 섹션에 대해 기본 초안 텍스트를 생성한다 (LLM 연동은 호출 측에서 처리)."""
    filled: dict[str, str] = {}
    company_name = company_info.get("name", "당사")
    for section_name in sections:
        if '개요' in section_name or '배경' in section_name:
            filled[section_name] = (
                f"본 사업은 {notice_text[:100]}에 관한 사업입니다. "
                f"{company_name}은 이 분야에서 풍부한 경험을 보유하고 있습니다."
            )
        elif '전략' in section_name:
            filled[section_name] = (
                f"{company_name}의 핵심 수행 전략은 품질 우선, 일정 준수, 고객 소통입니다."
            )
        elif '실적' in section_name:
            filled[section_name] = f"{company_name}의 최근 유사 수행 실적을 첨부합니다."
        else:
            filled[section_name] = f"[{section_name}에 대한 내용을 작성해주세요]"
    return filled
