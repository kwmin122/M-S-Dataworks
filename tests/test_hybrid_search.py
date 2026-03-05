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

    def embed_query(self, input):  # noqa: A002
        """ChromaDB 최신 버전 쿼리 임베딩 인터페이스."""
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


def test_kiwi_bm25_korean_matching():
    """Kiwi 토크나이저로 한국어 조사 차이를 극복."""
    from korean_tokenizer import tokenize_ko
    from rank_bm25 import BM25Okapi

    corpus = [
        "정보통신공사업 면허를 보유하고 있습니다",
        "건축공사업 면허 보유",
        "소프트웨어 개발 전문기업",
    ]
    tokenized = [tokenize_ko(doc) for doc in corpus]
    bm25 = BM25Okapi(tokenized)

    # "정보통신공사업을" (조사 '을' 포함) → 첫 번째 문서 매칭
    scores = bm25.get_scores(tokenize_ko("정보통신공사업을 보유한 업체"))
    best_idx = int(scores.argmax())
    assert best_idx == 0, f"Expected 0, got {best_idx}. Scores: {scores}"


def test_weighted_rrf_bm25_priority():
    """7:3 가중 RRF에서 BM25 정확 매칭이 벡터 유사 매칭보다 우선."""
    engine = _make_engine(hybrid=True)
    engine.add_text_directly("ISO 9001 품질경영시스템 인증서", "cert")
    engine.add_text_directly("품질 관리 체계 구축 방안", "plan")
    engine.add_text_directly("회사 연혁 2010년 설립", "history")

    results = engine.search("ISO 9001 인증", top_k=3)
    assert len(results) > 0
    # BM25 가중치 0.7 → 정확 키워드 매칭("ISO 9001")이 1위
    assert "ISO" in results[0].text or "9001" in results[0].text


def test_mmr_reduces_redundancy():
    """MMR 리랭킹으로 유사 청크가 연속 배치되지 않음."""
    engine = _make_engine(hybrid=True)
    # 거의 동일한 문서 3개 + 다른 문서 1개
    engine.add_text_directly("ISO 9001 품질경영시스템 인증서 보유", "cert1")
    engine.add_text_directly("ISO 9001 품질경영시스템 인증서 확인", "cert2")
    engine.add_text_directly("ISO 9001 품질경영 인증 획득 완료", "cert3")
    engine.add_text_directly("정보통신공사업 면허 등록 확인서", "license")

    results = engine.search("ISO 인증 및 면허", top_k=4)
    # MMR로 다양성 보장 → "면허" 관련 문서가 상위 3개 안에 포함
    texts = [r.text for r in results[:3]]
    has_license = any("면허" in t for t in texts)
    assert has_license, f"MMR 다양성 부족: top-3에 면허 문서 없음. got: {texts}"
