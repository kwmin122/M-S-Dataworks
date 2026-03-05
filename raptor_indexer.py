"""RAPTOR: Recursive Abstractive Processing for Tree-Organized Retrieval.

문서 청크를 재귀적으로 클러스터링 + 요약하여 트리 구조를 빌드.
검색 시 Collapsed Tree 방식으로 모든 레벨에서 flat 검색.

Reference: https://arxiv.org/abs/2401.18059
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np
from openai import OpenAI
from sklearn.mixture import GaussianMixture


@dataclass
class RaptorNode:
    """RAPTOR 트리의 한 노드."""
    text: str
    level: int
    source_chunks: list[int] = field(default_factory=list)
    node_id: str = ""

    def __post_init__(self):
        if not self.node_id:
            self.node_id = f"raptor_L{self.level}_{uuid.uuid4().hex[:8]}"


SUMMARY_SYSTEM_PROMPT = """당신은 한국어 문서 요약 전문가입니다.
주어진 텍스트 조각들의 핵심 내용을 하나의 요약으로 통합하세요.
- 구체적 수치, 조건, 요건은 반드시 보존
- 추상적 표현 없이 팩트 중심 요약
- 200~400자 분량"""


def _call_summary_llm(
    texts: list[str],
    api_key: Optional[str] = None,
) -> str:
    """클러스터 텍스트를 LLM으로 요약."""
    client = OpenAI(
        api_key=api_key or os.environ.get("OPENAI_API_KEY"),
        timeout=30,
    )
    combined = "\n\n---\n\n".join(texts)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": f"다음 텍스트 조각들을 요약하세요:\n\n{combined}"},
        ],
        temperature=0.3,
        max_tokens=800,
    )
    return resp.choices[0].message.content or ""


class RaptorIndexer:
    """RAPTOR 트리 빌더."""

    def __init__(
        self,
        min_chunks: int = 10,
        max_levels: int = 3,
        api_key: Optional[str] = None,
    ):
        self.min_chunks = min_chunks
        self.max_levels = max_levels
        self.api_key = api_key

    def _cluster_embeddings(
        self,
        embeddings: np.ndarray,
        min_clusters: int = 2,
        max_clusters: int = 10,
    ) -> np.ndarray:
        """UMAP 차원축소 + GMM 클러스터링 (BIC로 최적 k 결정)."""
        n = len(embeddings)
        if n <= min_clusters:
            return np.zeros(n, dtype=int)

        reduced = embeddings
        if embeddings.shape[1] > 10 and n > 10:
            try:
                import umap
                n_neighbors = min(15, n - 1)
                reducer = umap.UMAP(
                    n_components=min(10, embeddings.shape[1]),
                    n_neighbors=n_neighbors,
                    min_dist=0.0,
                    random_state=42,
                )
                reduced = reducer.fit_transform(embeddings)
            except Exception:
                reduced = embeddings

        max_k = min(max_clusters, n - 1)
        if max_k < min_clusters:
            return np.zeros(n, dtype=int)

        best_bic = float("inf")
        best_labels = np.zeros(n, dtype=int)

        for k in range(min_clusters, max_k + 1):
            try:
                gmm = GaussianMixture(n_components=k, random_state=42)
                gmm.fit(reduced)
                bic = gmm.bic(reduced)
                if bic < best_bic:
                    best_bic = bic
                    best_labels = gmm.predict(reduced)
            except Exception:
                continue

        return best_labels

    def _summarize_texts(self, texts: list[str]) -> str:
        """텍스트 리스트를 LLM으로 요약."""
        return _call_summary_llm(texts, api_key=self.api_key)

    def build_tree(
        self,
        chunks: list[str],
        embed_fn: Optional[Callable[[list[str]], list[list[float]]]] = None,
    ) -> list[RaptorNode]:
        """청크 리스트 -> RAPTOR 트리 노드 리스트 (요약 노드만)."""
        if len(chunks) < self.min_chunks:
            return []

        if embed_fn is None:
            embed_fn = self._default_embed

        all_nodes: list[RaptorNode] = []
        current_texts = list(chunks)
        level = 0

        while len(current_texts) > 1 and level < self.max_levels:
            embeddings = np.array(embed_fn(current_texts))
            labels = self._cluster_embeddings(embeddings)
            unique_labels = set(labels)

            if len(unique_labels) <= 1 and level > 0:
                break

            level += 1
            summaries = []
            for label in sorted(unique_labels):
                indices = [i for i, l in enumerate(labels) if l == label]
                cluster_texts = [current_texts[i] for i in indices]

                if len(cluster_texts) == 1:
                    summary = cluster_texts[0]
                else:
                    summary = self._summarize_texts(cluster_texts)

                node = RaptorNode(
                    text=summary,
                    level=level,
                    source_chunks=indices,
                )
                all_nodes.append(node)
                summaries.append(summary)

            current_texts = summaries

        return all_nodes

    def _default_embed(self, texts: list[str]) -> list[list[float]]:
        """OpenAI text-embedding-3-small 임베딩."""
        client = OpenAI(
            api_key=self.api_key or os.environ.get("OPENAI_API_KEY"),
            timeout=30,
        )
        resp = client.embeddings.create(
            model="text-embedding-3-small",
            input=texts,
        )
        return [d.embedding for d in resp.data]
