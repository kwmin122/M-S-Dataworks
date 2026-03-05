"""한국어 형태소 분석 BM25 토크나이저 테스트."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


def test_tokenize_ko_basic():
    """기본 한국어 문장을 형태소로 분리."""
    from korean_tokenizer import tokenize_ko
    tokens = tokenize_ko("정보통신공사업을 수행합니다")
    assert "정보" in tokens or "통신" in tokens or "공사" in tokens
    assert "을" not in tokens
    assert "합니다" not in tokens


def test_tokenize_ko_removes_particles():
    """조사/어미가 제거되어 동일 어근 매칭 가능."""
    from korean_tokenizer import tokenize_ko
    tokens_a = tokenize_ko("제안서를 작성했습니다")
    tokens_b = tokenize_ko("제안서 작성")
    common = set(tokens_a) & set(tokens_b)
    assert len(common) >= 2, f"공통 토큰 부족: {common}"


def test_tokenize_ko_english_passthrough():
    """영문/숫자는 그대로 토큰으로 포함."""
    from korean_tokenizer import tokenize_ko
    tokens = tokenize_ko("ISO 9001 인증")
    has_iso = any("ISO" in t or "iso" in t.lower() for t in tokens)
    assert has_iso
    assert "9001" in tokens


def test_tokenize_ko_empty():
    """빈 문자열 → 빈 리스트."""
    from korean_tokenizer import tokenize_ko
    assert tokenize_ko("") == []


def test_tokenize_ko_fallback_without_kiwi():
    """kiwipiepy 미설치 시 공백 분할 폴백."""
    from korean_tokenizer import _fallback_tokenize
    tokens = _fallback_tokenize("제안서를 작성합니다")
    assert tokens == ["제안서를", "작성합니다"]
