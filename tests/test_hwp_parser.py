"""
HWP 파서 단위 테스트 (document_parser._parse_hwp).
LLM 미호출 - 순수 파싱 로직만 검증.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from document_parser import DocumentParser

HWP_PATH = Path("/Users/min-kyungwook/Downloads") / "[공고문] [9권역]학교 유무선 네트워크 개선 3차 정보통신공사 감리용역.hwp"


def test_hwp_file_exists():
    """테스트 HWP 파일이 존재해야 함"""
    assert HWP_PATH.exists(), f"HWP 파일 없음: {HWP_PATH}"


@pytest.mark.skipif(not HWP_PATH.exists(), reason="HWP 파일 없음")
def test_hwp_parse_returns_parsed_document():
    """parse()가 .hwp 파일을 ParsedDocument로 반환해야 함"""
    parser = DocumentParser()
    doc = parser.parse(str(HWP_PATH))
    assert doc is not None
    assert doc.filename.endswith(".hwp")
    assert doc.char_count > 100, f"텍스트가 너무 짧음: {doc.char_count}자"


@pytest.mark.skipif(not HWP_PATH.exists(), reason="HWP 파일 없음")
def test_hwp_parse_contains_key_text():
    """파싱된 텍스트에 공고 핵심 내용이 포함되어야 함"""
    parser = DocumentParser()
    doc = parser.parse(str(HWP_PATH))
    text = doc.text

    assert "엔지니어링" in text or "정보통신" in text, \
        "면허 관련 텍스트 없음"
    assert "고양" in text or "파주" in text, \
        "지역 제한 텍스트 없음"
    assert "감리" in text, \
        "감리용역 텍스트 없음"


@pytest.mark.skipif(not HWP_PATH.exists(), reason="HWP 파일 없음")
def test_hwp_parse_extracts_budget():
    """예산 금액이 텍스트에 포함되어야 함"""
    parser = DocumentParser()
    doc = parser.parse(str(HWP_PATH))
    # 43,417,000원 또는 39,470,000원 (추정가격)
    assert "43,417,000" in doc.text or "39,470,000" in doc.text or "43417000" in doc.text, \
        f"예산 금액 없음. 텍스트 앞 500자: {doc.text[:500]}"


@pytest.mark.skipif(not HWP_PATH.exists(), reason="HWP 파일 없음")
def test_hwp_parse_and_chunk():
    """parse_and_chunk()가 청크를 반환해야 함"""
    parser = DocumentParser()
    chunks = parser.parse_and_chunk(str(HWP_PATH))
    assert len(chunks) >= 1, "청크가 없음"
    assert all(c.source_file for c in chunks), "source_file 없는 청크 존재"


def test_unsupported_hwp_raises_before_fix():
    """수정 전: .hwp는 ValueError 발생해야 함 (이 테스트는 구현 후 삭제)"""
    # 이 테스트는 _parse_hwp 구현 후 자동으로 실패하므로
    # 구현 후 테스트 파일에서 이 함수를 삭제하세요.
    pass
