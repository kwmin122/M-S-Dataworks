"""
RFx AI Assistant - RAG 엔진

회사 정보를 벡터 DB에 저장하고 검색하는 RAG 파이프라인.
핵심: 회사 정보를 임베딩하여 RFx 요건과 매칭할 수 있게 준비.

Example:
    >>> engine = RAGEngine()
    >>> engine.add_company_documents("./data/company_docs/")
    >>> results = engine.search("ISO 9001 인증 보유 여부")
"""

import os
import uuid
from typing import Optional
from dataclasses import dataclass, field

from document_parser import DocumentParser, TextChunk

try:
    from rank_bm25 import BM25Okapi as _BM25Okapi
    _BM25_AVAILABLE = True
except ImportError:
    _BM25Okapi = None  # type: ignore
    _BM25_AVAILABLE = False


# ============================================================
# STEP 1: 검색 결과 데이터 클래스
# ============================================================

@dataclass
class SearchResult:
    """RAG 검색 결과"""
    text: str
    score: float
    source_file: str
    chunk_id: int
    metadata: dict = field(default_factory=dict)


# ============================================================
# STEP 2: RAG 엔진 (ChromaDB 기반)
# ============================================================

class RAGEngine:
    """
    RAG(Retrieval-Augmented Generation) 엔진.
    
    회사 문서를 벡터화하여 저장하고,
    RFx 요건에 대해 관련 정보를 검색한다.
    
    Example:
        >>> engine = RAGEngine()
        >>> engine.add_text_directly("ISO 9001 인증 보유", "company")
        >>> results = engine.search("ISO 인증")
    """
    
    def __init__(
        self,
        persist_directory: str = "./data/vectordb",
        collection_name: str = "company_knowledge",
        embedding_model: str = "text-embedding-3-small",
        embedding_function: object = None,
        hybrid_enabled: Optional[bool] = None,
    ):
        """
        Args:
            persist_directory (str): ChromaDB 저장 경로
            collection_name (str): 컬렉션 이름
            embedding_model (str): 임베딩 모델명
            embedding_function (object): 커스텀 임베딩 함수 (None이면 기본)
            
        Example:
            >>> engine = RAGEngine(persist_directory="./data/vectordb")
        """
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        # 운영 기준 임베딩 모델은 text-embedding-3-small로 고정한다.
        self.embedding_model = "text-embedding-3-small"
        self.embedding_function = embedding_function
        self.parser = DocumentParser()

        # BM25 하이브리드 설정
        self.hybrid_enabled: bool = (
            hybrid_enabled
            if hybrid_enabled is not None
            else os.getenv("RAG_HYBRID_ENABLED", "0") == "1"
        )
        self._bm25 = None
        self._bm25_entries: list = []   # {id, chunk_key, doc, metadata}
        self._bm25_dirty: bool = False

        # STEP 1: ChromaDB 초기화
        self._init_vectordb()
    
    def _init_vectordb(self) -> None:
        """ChromaDB 클라이언트 및 컬렉션 초기화
        
        Raises:
            ImportError: chromadb 미설치 시
        """
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
            from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
            
            # STEP 1-1: 영구 저장소 디렉토리 생성
            os.makedirs(self.persist_directory, exist_ok=True)
            
            # STEP 1-2: PersistentClient 생성
            self.client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=ChromaSettings(anonymized_telemetry=False)
            )
            
            # STEP 1-3: 컬렉션 생성 또는 가져오기
            # - 운영 기본은 OpenAI text-embedding-3-small 사용
            # - embedding_function이 지정되면 (테스트 목적) 우선 사용
            def _collection_kwargs(name: str) -> dict:
                kwargs = {
                    "name": name,
                    "metadata": {
                        "description": "회사 정보 Knowledge Base",
                        "embedding_model": self.embedding_model,
                    },
                }
                if self.embedding_function is not None:
                    kwargs["embedding_function"] = self.embedding_function
                else:
                    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
                    if not openai_api_key:
                        raise RuntimeError(
                            "OPENAI_API_KEY가 설정되지 않아 임베딩 엔진을 초기화할 수 없습니다."
                        )
                    kwargs["embedding_function"] = OpenAIEmbeddingFunction(
                        api_key_env_var="OPENAI_API_KEY",
                        model_name=self.embedding_model,
                    )
                return kwargs

            # STEP 1-3: 컬렉션 생성 또는 가져오기
            try:
                self.collection = self.client.get_or_create_collection(
                    **_collection_kwargs(self.collection_name)
                )
            except ValueError as exc:
                if "Embedding function conflict" not in str(exc):
                    raise
                migrated_name = f"{self.collection_name}__openai"
                print(
                    "⚠️ 기존 컬렉션 임베딩 설정과 충돌이 있어 OpenAI 전용 컬렉션으로 자동 전환합니다: "
                    f"{self.collection_name} -> {migrated_name}"
                )
                self.collection_name = migrated_name
                self.collection = self.client.get_or_create_collection(
                    **_collection_kwargs(self.collection_name)
                )
            
            print(f"✅ VectorDB 초기화 완료. 컬렉션: {self.collection_name}")
            print(f"   현재 문서 수: {self.collection.count()}")
            
        except ImportError:
            raise ImportError("chromadb 미설치. pip install chromadb")
    
    # ============================================================
    # STEP 3: 문서 추가 (임베딩 + 저장)
    # ============================================================
    
    def add_document(self, file_path: str) -> int:
        """
        단일 문서를 파싱하고 벡터 DB에 추가한다.
        
        Args:
            file_path (str): 문서 파일 경로
            
        Returns:
            int: 추가된 청크 수
        """
        # STEP 3-1: 문서 파싱 및 청킹
        chunks = self.parser.parse_and_chunk(file_path)
        
        if not chunks:
            print(f"⚠️ 청크가 생성되지 않았습니다: {file_path}")
            return 0
        
        # STEP 3-2: ChromaDB에 추가
        ids = []
        documents = []
        metadatas = []
        doc_uid = uuid.uuid4().hex[:8]
        
        for chunk in chunks:
            chunk_uid = f"{chunk.source_file}_{chunk.chunk_id}_{doc_uid}"
            ids.append(chunk_uid)
            documents.append(chunk.text)
            metadatas.append({
                "source_file": chunk.source_file,
                "chunk_id": chunk.chunk_id,
                "page_number": chunk.page_number or -1,
                "type": chunk.metadata.get("type", "text")
            })
        
        self.collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )

        self._bm25_dirty = True
        print(f"✅ 문서 추가 완료: {os.path.basename(file_path)} ({len(chunks)}개 청크)")
        return len(chunks)
    
    def add_documents_from_directory(self, directory: str) -> int:
        """
        디렉토리 내 모든 문서를 추가한다.
        
        Args:
            directory (str): 문서 디렉토리 경로
            
        Returns:
            int: 총 추가된 청크 수
        """
        total_chunks = 0
        supported_extensions = {'.pdf', '.docx', '.doc', '.txt'}
        
        for filename in os.listdir(directory):
            ext = os.path.splitext(filename)[1].lower()
            if ext in supported_extensions:
                file_path = os.path.join(directory, filename)
                try:
                    count = self.add_document(file_path)
                    total_chunks += count
                except Exception as e:
                    print(f"❌ 오류 발생 ({filename}): {e}")
        
        print(f"\n📊 총 {total_chunks}개 청크가 추가되었습니다.")
        return total_chunks
    
    # ============================================================
    # STEP 4: 검색 (Retrieval)
    # ============================================================
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: Optional[dict] = None
    ) -> list[SearchResult]:
        """
        쿼리와 관련된 문서 청크를 검색한다.
        RAG_HYBRID_ENABLED=1 또는 hybrid_enabled=True 이면 BM25+벡터 RRF 사용.
        """
        if self.hybrid_enabled:
            if self._bm25 is None or self._bm25_dirty:
                self._rebuild_bm25()
            return self._search_hybrid(query, top_k, filter_metadata)
        return self._search_vector(query, top_k, filter_metadata)

    def _search_vector(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: Optional[dict] = None
    ) -> list[SearchResult]:
        """순수 벡터 검색 (기존 search 로직)."""
        # 컬렉션이 비어있으면 빈 결과 반환
        if self.collection.count() == 0:
            print("⚠️ 벡터 DB가 비어있습니다. 먼저 문서를 추가해주세요.")
            return []

        # ChromaDB 검색
        query_params = {
            "query_texts": [query],
            "n_results": min(top_k, self.collection.count())
        }

        if filter_metadata:
            query_params["where"] = filter_metadata

        results = self.collection.query(**query_params)

        # 결과 변환
        search_results = []
        if results and results['documents']:
            for i, doc in enumerate(results['documents'][0]):
                raw_distance = results['distances'][0][i] if results['distances'] else None
                score = 0.0 if raw_distance is None else max(0.0, min(1.0, 1.0 - raw_distance))
                search_results.append(SearchResult(
                    text=doc,
                    score=score,
                    source_file=results['metadatas'][0][i].get('source_file', 'unknown'),
                    chunk_id=results['metadatas'][0][i].get('chunk_id', -1),
                    metadata=results['metadatas'][0][i]
                ))

        return search_results

    def _rebuild_bm25(self) -> None:
        """ChromaDB의 현재 문서로 BM25 인덱스 재구성.

        chunk_key = source_file + chunk_id 를 별도 저장해 RRF ID 정합.
        """
        if not _BM25_AVAILABLE:
            self._bm25_dirty = False
            return
        try:
            results = self.collection.get(include=["documents", "metadatas"])
            ids   = results.get("ids") or []
            docs  = results.get("documents") or []
            metas = results.get("metadatas") or []
            self._bm25_entries = []
            for i, (id_, doc, meta) in enumerate(zip(ids, docs, metas)):
                m = meta or {}
                # chunk_key: 벡터 결과와 동일한 키 (source_file + chunk_id)
                chunk_key = f"{m.get('source_file', '')}_{m.get('chunk_id', i)}"
                self._bm25_entries.append({
                    "id": id_,
                    "chunk_key": chunk_key,
                    "doc": doc,
                    "metadata": m,
                })
            if docs:
                self._bm25 = _BM25Okapi([d.split() for d in docs])
        except Exception as exc:
            print(f"⚠️ BM25 인덱스 재구성 실패 (벡터 검색으로 fallback): {exc}")
        self._bm25_dirty = False

    @staticmethod
    def _matches_filter(metadata: dict, filter_metadata: Optional[dict]) -> bool:
        """BM25 후보에 filter_metadata 동등 적용."""
        if not filter_metadata:
            return True
        return all(metadata.get(k) == v for k, v in filter_metadata.items())

    def _search_hybrid(
        self,
        query: str,
        top_k: int,
        filter_metadata: Optional[dict] = None
    ) -> list[SearchResult]:
        """BM25 + 벡터 RRF(Reciprocal Rank Fusion) 하이브리드 검색.

        chunk_key 통일 (source_file_chunk_id) 로 BM25/벡터 ID 정합.
        최종 결과를 전체 후보 풀에서 구성 → BM25-only hit도 반환 가능.
        """
        # 1) BM25 후보 (filter 동등 적용)
        candidates = [
            (i, e) for i, e in enumerate(self._bm25_entries)
            if self._matches_filter(e["metadata"], filter_metadata)
        ]
        if not candidates or self._bm25 is None:
            return self._search_vector(query, top_k, filter_metadata)

        # BM25 점수 (후보 인덱스만)
        full_scores = self._bm25.get_scores(query.split())
        candidate_scores = [(orig_idx, full_scores[orig_idx]) for orig_idx, _ in candidates]
        bm25_ranked = sorted(candidate_scores, key=lambda x: x[1], reverse=True)

        # 2) 벡터 검색 결과
        vector_results = self._search_vector(query, top_k * 2, filter_metadata)

        # 3) RRF 결합 (k=60 표준) — chunk_key 기준 통일
        K = 60
        rrf: dict = {}

        # BM25 기여 (chunk_key 사용)
        for rank, (orig_idx, _) in enumerate(bm25_ranked[:top_k * 2]):
            ck = self._bm25_entries[orig_idx]["chunk_key"]
            rrf[ck] = rrf.get(ck, 0.0) + 1.0 / (K + rank + 1)

        # 벡터 기여 (동일 chunk_key)
        for rank, vr in enumerate(vector_results):
            ck = f"{vr.source_file}_{vr.chunk_id}"
            rrf[ck] = rrf.get(ck, 0.0) + 1.0 / (K + rank + 1)

        # 4) 전체 후보 풀 구성: 벡터 결과 + BM25-only 엔트리
        vector_by_key = {f"{r.source_file}_{r.chunk_id}": r for r in vector_results}
        bm25_by_key   = {e["chunk_key"]: e for _, e in candidates}

        ranked_keys = sorted(rrf, key=rrf.__getitem__, reverse=True)
        final: list[SearchResult] = []
        for ck in ranked_keys:
            if len(final) >= top_k:
                break
            if ck in vector_by_key:
                final.append(vector_by_key[ck])
            elif ck in bm25_by_key:
                entry = bm25_by_key[ck]
                final.append(SearchResult(
                    text=entry["doc"],
                    score=rrf[ck],
                    source_file=entry["metadata"].get("source_file", "unknown"),
                    chunk_id=entry["metadata"].get("chunk_id", -1),
                    metadata=entry["metadata"],
                ))
        return final
    
    def search_multiple(
        self,
        queries: list[str],
        top_k: int = 3
    ) -> dict[str, list[SearchResult]]:
        """
        여러 쿼리를 동시에 검색한다.
        자격요건 각 항목별 검색에 사용.
        
        Args:
            queries (list[str]): 검색 쿼리 리스트
            top_k (int): 쿼리당 반환 결과 수
            
        Returns:
            dict: {쿼리: [검색결과]} 딕셔너리
        """
        results = {}
        for query in queries:
            results[query] = self.search(query, top_k=top_k)
        return results
    
    # ============================================================
    # STEP 5: 유틸리티
    # ============================================================
    
    def get_stats(self) -> dict:
        """벡터 DB 통계 정보"""
        return {
            "collection_name": self.collection_name,
            "total_documents": self.collection.count(),
            "persist_directory": self.persist_directory
        }
    
    def clear_collection(self) -> None:
        """컬렉션 초기화 (모든 데이터 삭제)"""
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

        self.client.delete_collection(self.collection_name)
        collection_kwargs = {
            "name": self.collection_name,
            "metadata": {
                "description": "회사 정보 Knowledge Base",
                "embedding_model": self.embedding_model,
            },
        }
        if self.embedding_function:
            collection_kwargs["embedding_function"] = self.embedding_function
        else:
            openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
            if not openai_api_key:
                raise RuntimeError("OPENAI_API_KEY가 설정되지 않아 컬렉션을 재생성할 수 없습니다.")
            collection_kwargs["embedding_function"] = OpenAIEmbeddingFunction(
                api_key_env_var="OPENAI_API_KEY",
                model_name=self.embedding_model,
            )
        self.collection = self.client.get_or_create_collection(**collection_kwargs)
        print("🗑️ 컬렉션이 초기화되었습니다.")
    
    def add_text_directly(
        self,
        text: str,
        source_name: str = "direct_input",
        base_metadata: Optional[dict] = None
    ) -> int:
        """
        텍스트를 직접 벡터 DB에 추가한다.
        (파일 없이 직접 텍스트 입력 시 사용)
        
        Args:
            text (str): 추가할 텍스트
            source_name (str): 소스 이름
            base_metadata (dict): 추가 메타데이터
            
        Returns:
            int: 추가된 청크 수
        """
        from document_parser import ParsedDocument
        
        doc = ParsedDocument(
            filename=source_name,
            text=text,
            pages=[text]
        )
        
        chunks = self.parser.chunker.chunk_document(doc)
        
        if not chunks:
            return 0
        
        add_uid = uuid.uuid4().hex[:8]
        ids = [f"{source_name}_{c.chunk_id}_{add_uid}" for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = []
        for c in chunks:
            metadata = {
                "source_file": source_name,
                "chunk_id": c.chunk_id,
                "page_number": c.page_number or -1,
                "type": "text",
            }
            if base_metadata:
                metadata.update(base_metadata)
            metadatas.append(metadata)
        
        self.collection.add(ids=ids, documents=documents, metadatas=metadatas)
        self._bm25_dirty = True

        print(f"✅ 텍스트 직접 추가 완료: {len(chunks)}개 청크")
        return len(chunks)
