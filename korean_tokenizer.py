"""한국어 형태소 분석 기반 BM25 토크나이저.

Kiwi 형태소 분석기로 명사/동사/형용사 어근만 추출.
kiwipiepy 미설치 시 str.split() 폴백.
"""
from __future__ import annotations

_kiwi = None
_USE_KIWI = True

# 추출할 품사 태그 — 내용어만 (기능어 제거)
_CONTENT_POS = {"NNG", "NNP", "NNB", "VV", "VA", "XR", "SL", "SN"}

try:
    from kiwipiepy import Kiwi as _KiwiClass
except ImportError:
    _KiwiClass = None
    _USE_KIWI = False


def _get_kiwi():
    """Kiwi 싱글턴 (lazy init, ~200ms 첫 호출)."""
    global _kiwi
    if _kiwi is None and _KiwiClass is not None:
        _kiwi = _KiwiClass()
    return _kiwi


def _fallback_tokenize(text: str) -> list[str]:
    """kiwipiepy 미설치 시 공백 분할 폴백."""
    return text.split()


def tokenize_ko(text: str) -> list[str]:
    """한국어 텍스트를 BM25용 토큰으로 분해.

    Kiwi 형태소 분석기로 내용어(명사/동사/형용사/외국어/숫자)만 추출.
    조사, 어미 등 기능어는 제거하여 BM25 노이즈 감소.

    Args:
        text: 분석할 한국어 텍스트

    Returns:
        토큰 리스트 (내용어 어근)
    """
    if not text or not text.strip():
        return []

    kiwi = _get_kiwi()
    if kiwi is None:
        return _fallback_tokenize(text)

    tokens = kiwi.tokenize(text)
    return [t.form for t in tokens if t.tag in _CONTENT_POS]
