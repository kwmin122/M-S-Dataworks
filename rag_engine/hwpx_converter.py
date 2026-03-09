"""
HWP 변환 모듈 (pypandoc-hwpx 기반)

Markdown → HWPX 변환 기능 제공
"""

import subprocess
import os
import re
from pathlib import Path
from typing import Optional


def convert_markdown_to_hwpx(
    md_text: str,
    output_path: str,
    reference_doc: Optional[str] = None
) -> str:
    """
    Markdown 텍스트를 HWPX 파일로 변환

    Args:
        md_text: 마크다운 텍스트
        output_path: 출력 HWPX 파일 경로
        reference_doc: 참조 문서 (스타일 템플릿, 선택)

    Returns:
        생성된 HWPX 파일 경로

    Raises:
        RuntimeError: 변환 실패 시
    """
    # 1. 임시 마크다운 파일 생성
    temp_md = output_path.replace(".hwpx", "_temp.md")

    try:
        with open(temp_md, "w", encoding="utf-8") as f:
            f.write(md_text)

        # 2. pypandoc-hwpx 실행
        cmd = ["pypandoc-hwpx", temp_md, "-o", output_path]

        if reference_doc and os.path.exists(reference_doc):
            cmd.extend(["--reference-doc", reference_doc])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            raise RuntimeError(f"HWPX 변환 실패: {result.stderr}")

        if not os.path.exists(output_path):
            raise RuntimeError(f"HWPX 파일 생성 실패: {output_path}")

        return output_path

    finally:
        # 3. 임시 파일 정리
        if os.path.exists(temp_md):
            os.remove(temp_md)


def convert_docx_to_hwpx(
    docx_path: str,
    output_path: str,
    reference_doc: Optional[str] = None
) -> str:
    """
    DOCX 파일을 HWPX로 변환

    Args:
        docx_path: 입력 DOCX 파일 경로
        output_path: 출력 HWPX 파일 경로
        reference_doc: 참조 문서 (스타일 템플릿, 선택)

    Returns:
        생성된 HWPX 파일 경로
    """
    if not os.path.exists(docx_path):
        raise FileNotFoundError(f"DOCX 파일 없음: {docx_path}")

    cmd = ["pypandoc-hwpx", docx_path, "-o", output_path]

    if reference_doc and os.path.exists(reference_doc):
        cmd.extend(["--reference-doc", reference_doc])

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=60
    )

    if result.returncode != 0:
        raise RuntimeError(f"DOCX→HWPX 변환 실패: {result.stderr}")

    return output_path


def sanitize_filename(filename: str, max_length: int = 100) -> str:
    """
    파일명 안전화 (한글 지원)

    Args:
        filename: 원본 파일명
        max_length: 최대 길이

    Returns:
        안전한 파일명
    """
    # 허용: 한글, 영문, 숫자, 언더스코어, 하이픈, 점
    safe = re.sub(r'[^\w가-힣\s.\-]', '_', filename)
    safe = safe.strip()[:max_length]
    return safe
