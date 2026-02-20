"""
BM25+벡터 하이브리드 검색 테스트.
TDD: hybrid_enabled 플래그, dirty flag, filter 동등성, 회귀 방지.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import MagicMock, patch


class _FakeEF:
    """ChromaDB EmbeddingFunction 인터페이스 호환 mock (signature + name 검증 통과)."""
    def __call__(self, input):  # noqa: A002
        return [[0.1] * 256 for _ in input]

    def name(self) -> str:
        return "default"


def _make_engine(hybrid: bool = False) -> object:
    """테스트용 RAGEngine (임베딩 없는 mock)"""
    import time
    from engine import RAGEngine
    ef = _FakeEF()
    engine = RAGEngine(
        persist_directory="/tmp/test_bm25_engine",
        collection_name=f"test_col_{int(time.time() * 1e6)}",
        embedding_function=ef,
        hybrid_enabled=hybrid,
    )
    return engine


def test_hybrid_disabled_by_default():
    """기본값: hybrid_enabled=False → 기존 벡터 검색"""
    engine = _make_engine(hybrid=False)
    assert engine.hybrid_enabled is False


def test_hybrid_enabled_flag():
    """hybrid_enabled=True 인스턴스 설정"""
    engine = _make_engine(hybrid=True)
    assert engine.hybrid_enabled is True


def test_dirty_flag_set_after_add_text():
    """add_text_directly 호출 후 _bm25_dirty=True"""
    engine = _make_engine(hybrid=True)
    assert engine._bm25_dirty is False
    engine.add_text_directly("테스트 텍스트", "test_source")
    assert engine._bm25_dirty is True


def test_bm25_keyword_precision():
    """BM25가 정확한 키워드(코드/번호)를 다른 문서보다 잘 랭킹하는지 확인"""
    from rank_bm25 import BM25Okapi
    corpus = [
        "소프트웨어사업자 신고확인서 번호 SW-2015-034821",
        "회사 설립연도 2012년 대표이사 김철수",
        "ISO 9001 인증 유효기간 2024년까지",
    ]
    tokenized = [doc.split() for doc in corpus]
    bm25 = BM25Okapi(tokenized)

    scores = bm25.get_scores("신고확인서 번호".split())
    best_idx = int(scores.argmax())
    assert "신고확인서" in corpus[best_idx], \
        f"BM25 오류: '{corpus[best_idx]}' 가 최상위"


def test_rebuild_bm25_clears_dirty_flag():
    """_rebuild_bm25() 호출 후 _bm25_dirty=False"""
    engine = _make_engine(hybrid=True)
    engine.add_text_directly("내용 A", "source_a")
    assert engine._bm25_dirty is True
    engine._rebuild_bm25()
    assert engine._bm25_dirty is False
