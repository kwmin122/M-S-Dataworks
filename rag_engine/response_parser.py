"""
LLM 답변 파싱 유틸리티.

지원 포맷:
1) 권장 JSON 객체
   {"answer":"...", "references":[{"page":1,"text":"..."}]}
2) 레거시 json_refs 코드블록
3) 인라인 참조 [📄 p.3 "텍스트"]
"""

from __future__ import annotations

import json
import re
from typing import Any


INLINE_REF_PATTERN = r'\[📄\s*p\.(\d+)(?:\s*"([^"]*)")?\]'


def _extract_first_json_object(raw_text: str) -> dict[str, Any] | None:
    text = (raw_text or "").strip()
    if not text:
        return None

    # 코드블록으로 감싼 경우 우선 제거
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 3:
            candidate = parts[1]
            if candidate.startswith("json"):
                candidate = candidate[4:].lstrip()
            try:
                data = json.loads(candidate)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass

    # 전체가 JSON인 경우
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    # 텍스트 내 첫 JSON 객체 추출 (brace matching)
    start = text.find("{")
    if start < 0:
        return None

    depth = 0
    in_string = False
    escape = False
    end = -1
    for idx, ch in enumerate(text[start:], start=start):
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = idx + 1
                break

    if end <= start:
        return None

    candidate = text[start:end]
    try:
        data = json.loads(candidate)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        return None
    return None


def _normalize_references(raw_references: Any) -> list[dict]:
    references: list[dict] = []
    if not isinstance(raw_references, list):
        return references

    for item in raw_references:
        if not isinstance(item, dict):
            continue
        try:
            page = int(item.get("page", 0))
        except (TypeError, ValueError):
            page = 0
        if page <= 0:
            continue
        text = str(item.get("text", "")).strip()
        references.append({"page": page, "text": text})
    return references


def _parse_inline_references(text: str) -> list[dict]:
    references: list[dict] = []
    for match in re.finditer(INLINE_REF_PATTERN, text or ""):
        page = int(match.group(1))
        snippet = (match.group(2) or "").strip()
        references.append({"page": page, "text": snippet})
    return references


def parse_chat_response(raw_text: str) -> tuple[str, list[dict]]:
    """
    LLM raw 응답을 (표시 텍스트, 참조 리스트)로 변환.
    """
    text = (raw_text or "").strip()
    if not text:
        return "", []

    payload = _extract_first_json_object(text)
    if payload:
        # 권장 포맷
        answer = str(payload.get("answer", "")).strip()
        references = _normalize_references(payload.get("references", []))
        if answer:
            if not references:
                references = _parse_inline_references(answer)
            return answer, references

    # 레거시 json_refs 블록
    display_text = text
    references: list[dict] = []
    if "```json_refs" in text:
        parts = text.split("```json_refs", 1)
        display_text = parts[0].strip()
        try:
            json_part = parts[1].split("```", 1)[0].strip()
            parsed = json.loads(json_part)
            references = _normalize_references(parsed)
        except (json.JSONDecodeError, IndexError):
            references = []

    if not references:
        references = _parse_inline_references(display_text)

    return display_text, references

