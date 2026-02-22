import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from hwp_parser import extract_hwp_text_bytes, is_hwp_bytes


def test_is_hwp_bytes_false_for_empty():
    assert is_hwp_bytes(b"") is False


def test_is_hwp_bytes_false_for_pdf():
    assert is_hwp_bytes(b"%PDF-1.4") is False


def test_extract_hwp_text_bytes_returns_str():
    """비-HWP 바이트도 빈 문자열 반환 (실제 HWP 없이 기본 동작 검증)"""
    result = extract_hwp_text_bytes(b"notahwpfile")
    assert isinstance(result, str)
