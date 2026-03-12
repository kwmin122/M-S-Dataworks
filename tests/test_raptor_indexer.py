"""RAPTOR 트리 인덱서 테스트."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import numpy as np


def test_raptor_node_creation():
    """RaptorNode 데이터 모델."""
    from raptor_indexer import RaptorNode
    node = RaptorNode(text="요약 텍스트", level=1, source_chunks=[0, 1, 2])
    assert node.text == "요약 텍스트"
    assert node.level == 1
    assert node.source_chunks == [0, 1, 2]


def test_cluster_texts_basic():
    """유사 텍스트를 같은 클러스터로 묶기."""
    from raptor_indexer import RaptorIndexer

    indexer = RaptorIndexer()
    # 3개의 명확히 분리된 클러스터 (클러스터당 15개 = 45개 포인트)
    # BIC가 올바르게 k=3을 선택할 수 있도록 충분한 샘플 수 확보
    rng = np.random.RandomState(42)
    cluster_a = rng.randn(15, 2) * 1.0 + [10, 0]    # (10, 0) 부근
    cluster_b = rng.randn(15, 2) * 1.0 + [0, 10]     # (0, 10) 부근
    cluster_c = rng.randn(15, 2) * 1.0 + [-10, -10]  # (-10, -10) 부근
    embeddings = np.vstack([cluster_a, cluster_b, cluster_c])
    labels = indexer._cluster_embeddings(embeddings, min_clusters=2, max_clusters=10)
    assert len(labels) == 45
    # 같은 클러스터 내 포인트들은 같은 레이블
    assert len(set(labels[:15])) == 1, "클러스터 A 포인트들이 분리됨"
    assert len(set(labels[15:30])) == 1, "클러스터 B 포인트들이 분리됨"
    assert len(set(labels[30:])) == 1, "클러스터 C 포인트들이 분리됨"
    # 서로 다른 그룹은 다른 클러스터
    assert labels[0] != labels[15]
    assert labels[0] != labels[30]


def test_skip_short_documents():
    """청크 수가 min_chunks 미만이면 빈 결과."""
    from raptor_indexer import RaptorIndexer

    indexer = RaptorIndexer(min_chunks=10)
    result = indexer.build_tree(["짧은 문서"] * 5, embed_fn=lambda x: [[0.1]*10]*len(x))
    assert result == []


def test_summarize_cluster():
    """클러스터 텍스트 요약 (mock LLM)."""
    from unittest.mock import patch
    from raptor_indexer import RaptorIndexer

    indexer = RaptorIndexer()
    texts = ["첫 번째 내용", "두 번째 내용", "세 번째 내용"]

    with patch("raptor_indexer._call_summary_llm", return_value="세 가지 내용을 요약합니다."):
        summary = indexer._summarize_texts(texts)

    assert "요약" in summary


def test_raptor_integration_with_engine():
    """engine.py와 RAPTOR 통합 — 요약 노드가 ChromaDB에 저장."""
    from unittest.mock import patch, MagicMock
    import time
    from engine import RAGEngine

    class _FakeEF:
        def is_legacy(self) -> bool:
            return True

        def __call__(self, input):
            return [[0.1] * 256 for _ in input]
        def name(self):
            return "default"

    engine = RAGEngine(
        persist_directory="/tmp/test_raptor_engine",
        collection_name=f"raptor_test_{int(time.time() * 1e6)}",
        embedding_function=_FakeEF(),
        hybrid_enabled=False,
    )
    engine._raptor_enabled = True

    # Mock the RaptorIndexer
    from raptor_indexer import RaptorIndexer, RaptorNode
    mock_indexer = MagicMock(spec=RaptorIndexer)
    mock_indexer.min_chunks = 3
    mock_indexer.build_tree.return_value = [
        RaptorNode(text="요약 노드 1", level=1, source_chunks=[0, 1]),
        RaptorNode(text="요약 노드 2", level=1, source_chunks=[2, 3]),
    ]
    engine._raptor = mock_indexer

    # Add enough chunks to trigger RAPTOR (need >= min_chunks=3)
    for i in range(5):
        engine.add_text_directly(f"청크 {i}: 테스트 내용 번호 {i}", f"source_{i}")

    # Note: add_text_directly doesn't trigger RAPTOR (only add_document does)
    # So let's test add_document with a mock
    from document_parser import TextChunk
    mock_chunks = [
        TextChunk(text=f"청크 {i}", chunk_id=i, source_file="test.pdf")
        for i in range(5)
    ]

    with patch.object(engine.parser, 'parse_and_chunk', return_value=mock_chunks):
        engine.add_document("test.pdf")

    # Verify RAPTOR build_tree was called
    mock_indexer.build_tree.assert_called_once()

    # Verify summary nodes are in collection (5 original + 2 raptor)
    count = engine.collection.count()
    # 5 from add_text_directly + 5 from add_document + 2 raptor nodes = 12
    assert count >= 12, f"Expected >= 12 docs, got {count}"
