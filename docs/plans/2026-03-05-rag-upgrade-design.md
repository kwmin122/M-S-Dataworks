# RAG 엔진 3단계 업그레이드 설계

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Kira RAG 검색 품질을 3가지 축으로 업그레이드 — (1) 한국어 형태소 BM25 앙상블, (2) RAPTOR 트리 인덱싱, (3) PDF 표 파싱 강화.

**Architecture:** 기존 `engine.py` + `document_parser.py` 파이프라인 위에 3개 독립 모듈을 플러그인. 기존 동작 100% 하위호환 유지.

---

## 배경 및 동기

### 현재 한계
1. **BM25 공백 분할**: `engine.py:327`에서 `d.split()` — 한국어 조사/어미 때문에 "정보통신공사업을" ≠ "정보통신공사업" 매칭 실패. 벤치마크에서 공백 토크나이저는 최하위 성능.
2. **긴 문서 맥락 부재**: 50페이지 RFP를 900자 청크 55개로 분할 → "사업 전체 목표?" 같은 상위 맥락 질문에 답변 불가. RAPTOR 논문에서 20% 정확도 향상 입증.
3. **PDF 표 정보 손실**: `document_parser.py`에서 `pdfplumber.extract_text()` 사용 → 평가기준표, 배점표 등 표 구조가 평문으로 풀어져 행/열 관계 소실.

### 근거 자료
- [한국어 BM25 토크나이저 벤치마크](https://velog.io/@autorag): ko_okt NDCG@10=0.9005 1위, space 최하위
- [RAPTOR 논문 (ICLR 2024)](https://arxiv.org/abs/2401.18059): QuALITY 벤치마크 20% 정확도 향상
- [OCR Quality vs RAG Performance](https://www.mixedbread.com/blog/the-hidden-ceiling): 표 구조 보존이 검색 정확도에 직접 영향

---

## 1. Kiwi BM25 + Vector 앙상블 (7:3 가중 RRF + MMR 리랭킹)

### 문제
```python
# engine.py:327 — 현재
self._bm25 = _BM25Okapi([d.split() for d in docs])
# engine.py:359 — 검색 시
full_scores = self._bm25.get_scores(query.split())
```
공백 분할은 한국어에서 치명적. "제안서를 작성했습니다" vs "제안서 작성" → 매칭 안 됨.

### 설계

**새 파일: `korean_tokenizer.py`**
```python
"""한국어 형태소 분석 기반 BM25 토크나이저.

Kiwi 형태소 분석기로 명사/동사/형용사 어근만 추출.
kiwipiepy 미설치 시 str.split() 폴백.
"""
from kiwipiepy import Kiwi

_kiwi = None  # lazy singleton

# 추출할 품사 태그 (명사, 동사, 형용사 어근)
_CONTENT_POS = {'NNG', 'NNP', 'NNB', 'VV', 'VA', 'XR', 'SL', 'SN'}

def tokenize_ko(text: str) -> list[str]:
    """한국어 텍스트를 BM25용 토큰으로 분해."""
    global _kiwi
    if _kiwi is None:
        _kiwi = Kiwi()
    tokens = _kiwi.tokenize(text)
    return [t.form for t in tokens if t.tag in _CONTENT_POS]
```

- `_CONTENT_POS`: 기능어(조사 JKS/JKO, 어미 EP/EF 등) 제거 → BM25 노이즈 감소
- Kiwi 싱글턴: 초기화 ~200ms → 1회만. 이후 토크나이징 ~1ms/문장
- 폴백: `try/except ImportError` → `str.split()` 사용 (기존 동작 유지)

**engine.py 변경: 가중 RRF (7:3)**
```python
# _rebuild_bm25() — 변경
from korean_tokenizer import tokenize_ko
self._bm25 = _BM25Okapi([tokenize_ko(d) for d in docs])

# _search_hybrid() — 변경
full_scores = self._bm25.get_scores(tokenize_ko(query))

# RRF 가중치 적용
BM25_WEIGHT = 0.7
VECTOR_WEIGHT = 0.3

# BM25 기여
rrf[ck] += BM25_WEIGHT * (1.0 / (K + rank + 1))

# 벡터 기여
rrf[ck] += VECTOR_WEIGHT * (1.0 / (K + rank + 1))
```

**MMR(Maximal Marginal Relevance) 리랭킹:**
- LangChain `EnsembleRetriever(search_type="mmr")` 패턴을 LangChain 없이 직접 구현
- 가중 RRF 후 MMR 리랭킹 → 관련성(λ=0.7) + 다양성(1-λ=0.3)
- `difflib.SequenceMatcher`로 텍스트 유사도 계산 → 중복 청크 페널티
- 효과: 같은 섹션의 유사한 청크가 연속 배치되는 것을 방지, 검색 결과의 정보 커버리지 향상

**왜 FAISS 별도 추가 안 하는가:**
- ChromaDB 내부가 이미 HNSW (≈ FAISS IVF) — 동일 dense retrieval 성능
- FAISS 추가 시 이중 벡터 인덱스 유지 → 스토리지/동기화 복잡도만 증가
- 핵심 개선은 토크나이저(Kiwi)와 가중치(7:3)

**왜 Kiwi인가 (OKT 아닌 이유):**
- OKT가 NDCG 0.9005로 1위이지만 JVM 필수 (Java 의존성)
- Kiwi는 C++ 네이티브 → 5~10배 빠른 속도, `pip install kiwipiepy`로 즉시 설치
- BM25 인덱스 재빌드 시 수천 문서 토크나이징 → 속도가 중요
- 정확도 차이 ~2%는 속도/배포 편의성으로 상쇄

### 적용 범위
- `engine.py`만 (BM25가 사용되는 유일한 곳)
- `knowledge_db.py`는 순수 벡터 검색 — BM25 없음, 변경 불필요

---

## 2. RAPTOR 트리 인덱싱

### 문제
50페이지 RFP → 900자 청크 55개로 쪼개면 전체 맥락 소실.
"이 사업의 전체 목표는?" 같은 질문에 개별 청크로는 답변 불가.

### 설계

**새 파일: `raptor_indexer.py`**

```
RFP 문서 업로드
  ↓
document_parser.py → 원본 청크 (리프 노드, Level 0)
  ↓
raptor_indexer.py:
  ┌─────────────────────────────────────────────┐
  │ Level 0: 원본 청크 55개 (900자)               │
  │     ↓ UMAP 차원축소 + GMM 클러스터링          │
  │ Level 1: 클러스터별 LLM 요약 (~10개 노드)      │
  │     ↓ 재클러스터링 + 재요약                    │
  │ Level 2: 상위 요약 (~3개 노드)                 │
  │     ↓ 최종 요약                               │
  │ Level 3: 전체 문서 요약 (1개 노드)             │
  └─────────────────────────────────────────────┘
  ↓
모든 레벨 노드를 ChromaDB에 저장
  metadata: { raptor_level: 0~3, parent_cluster: "..." }
  ↓
검색 시: Collapsed Tree — 모든 레벨에서 flat 검색
```

**핵심 모듈:**

```python
class RaptorIndexer:
    """RAPTOR 트리 빌드 — 청크 → 클러스터링 → 요약 → 재귀."""

    def __init__(self, api_key=None, min_chunks=10, max_levels=3):
        self.min_chunks = min_chunks  # 이 이하면 RAPTOR 스킵
        self.max_levels = max_levels

    def build_tree(self, chunks: list[str]) -> list[RaptorNode]:
        """청크 리스트 → 트리 노드 리스트 (모든 레벨 포함)."""
        if len(chunks) < self.min_chunks:
            return []  # 짧은 문서는 스킵

        all_nodes = []
        current_texts = chunks
        level = 0

        while len(current_texts) > 1 and level < self.max_levels:
            # 1. 임베딩 생성
            embeddings = self._embed(current_texts)
            # 2. UMAP 차원축소
            reduced = self._reduce_dims(embeddings)
            # 3. GMM 클러스터링 (BIC로 최적 k)
            clusters = self._cluster(reduced)
            # 4. 클러스터별 LLM 요약
            summaries = self._summarize_clusters(current_texts, clusters)

            level += 1
            for summary in summaries:
                all_nodes.append(RaptorNode(
                    text=summary, level=level, ...
                ))
            current_texts = summaries

        return all_nodes
```

**설계 결정:**

| 결정 | 선택 | 근거 |
|------|------|------|
| 검색 전략 | Collapsed Tree | 논문에서 Tree Traversal보다 성능 우수. 구현 단순 — 모든 노드를 flat 검색 |
| 클러스터링 | UMAP + GMM | 논문 공식 방법. GMM의 확률적 할당이 소프트 클러스터링 지원 |
| 최적 k 결정 | BIC (Bayesian Information Criterion) | 자동 클러스터 수 결정. 수동 튜닝 불필요 |
| 요약 모델 | gpt-4o-mini | 비용 효율 ($0.03/50페이지). 요약 품질 충분 |
| 최소 청크 수 | 10개 미만이면 스킵 | 짧은 문서에는 RAPTOR 오버헤드만 추가 |
| 빌드 시점 | 동기 (문서 추가 시 즉시) | 비동기 복잡도 회피. 50페이지 빌드 ~10초 |
| 최대 레벨 | 3 | 논문 기본값. 대부분 문서에서 2~3레벨이면 충분 |

**engine.py 통합:**
```python
def add_document(self, file_path):
    chunks = self.parser.parse_and_chunk(file_path)
    # ... 기존 ChromaDB 저장 ...

    # RAPTOR 트리 빌드 + 저장
    if self._raptor_enabled:
        texts = [c.text for c in chunks]
        tree_nodes = self._raptor.build_tree(texts)
        for node in tree_nodes:
            self.collection.add(
                ids=[node.id],
                documents=[node.text],
                metadatas=[{..., "raptor_level": node.level}],
            )
        self._bm25_dirty = True  # BM25도 요약 노드 포함하도록 재빌드
```

**검색 시**: 기존 `search()` 변경 없음. ChromaDB에 모든 레벨이 저장되므로 자연스럽게 상위 요약도 검색됨 (Collapsed Tree).

### 비용 분석
- 50페이지 RFP, 55개 청크 기준:
  - UMAP+GMM: CPU ~2초
  - LLM 요약: ~15회 × gpt-4o-mini ≈ **$0.03~0.05**
  - 스토리지: 원본 대비 ~30% 추가 (~15개 요약 노드)
- 전체 빌드 시간: **~10초** (LLM 호출 포함)

---

## 3. PDF 표 파싱 강화

### 문제
`document_parser.py`의 `_parse_pdf()`에서 `pdfplumber.extract_text()` → 표가 평문으로 풀어짐.

```
# 원본 PDF 표:
| 평가항목 | 배점 | 세부기준 |
| 사업이해 | 15  | 목적 이해도 |
| 기술방안 | 25  | 구현 적정성 |

# 현재 파싱 결과:
"평가항목 배점 세부기준 사업이해 15 목적 이해도 기술방안 25 구현 적정성"
→ 행/열 관계 완전 소실
```

### 설계

**`document_parser.py` `_parse_pdf()` 수정:**

```python
def _parse_pdf(self, path):
    pages = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            parts = []

            # 1) 표 추출 (마크다운 변환)
            tables = page.extract_tables() or []
            table_texts = []
            for table in tables:
                md = self._table_to_markdown(table)
                if md:
                    table_texts.append(md)

            # 2) 전체 텍스트 (표 포함)
            page_text = page.extract_text() or ""

            # 3) 결합: 텍스트 + 표 (마크다운)
            combined = page_text
            if table_texts:
                combined += "\n\n" + "\n\n".join(table_texts)

            pages.append(self.chunker._normalize_text(combined))
    ...
```

**`_table_to_markdown()` 헬퍼:**

```python
@staticmethod
def _table_to_markdown(table: list[list]) -> str:
    """pdfplumber 표 데이터 → 마크다운 테이블 변환."""
    if not table or len(table) < 2:
        return ""

    def _cell(v):
        return str(v or "").strip().replace("|", "\\|").replace("\n", " ")

    # 헤더
    header = [_cell(c) for c in table[0]]
    lines = ["| " + " | ".join(header) + " |"]
    lines.append("| " + " | ".join(["---"] * len(header)) + " |")

    # 데이터 행
    for row in table[1:]:
        cells = [_cell(c) for c in row]
        # 열 수 맞추기
        while len(cells) < len(header):
            cells.append("")
        lines.append("| " + " | ".join(cells[:len(header)]) + " |")

    return "\n".join(lines)
```

**설계 결정:**

| 결정 | 선택 | 근거 |
|------|------|------|
| 표+텍스트 중복 | 허용 (둘 다 포함) | 텍스트에서 표 영역만 정확히 제거하기 어려움. 중복이 검색 정확도 감소보다 정보 손실 방지가 중요 |
| 마크다운 형식 | GFM 테이블 | 이미 `section_writer.py`와 `document_assembler.py`가 마크다운 처리. 일관성 |
| 병합 셀 처리 | None → 빈 문자열 | pdfplumber가 병합 셀을 None으로 반환. 단순 처리 |
| PyMuPDF 폴백 | 표 파싱 없이 기존 동작 | PyMuPDF에는 `extract_tables()` 없음. 텍스트만 추출 |

### 적용 범위
- `_parse_pdf()` 내 pdfplumber 경로만 변경
- PyMuPDF 폴백 경로는 기존 동작 유지
- HWP/HWPX/DOCX 파싱은 변경 없음

---

## 의존성

```
# requirements.txt에 추가
kiwipiepy>=0.18.0      # 한국어 형태소 분석 (Upgrade 1)
umap-learn>=0.5.0      # RAPTOR 차원축소 (Upgrade 2)
# scikit-learn은 이미 설치됨 (GMM용)
# pdfplumber는 이미 설치됨 (표 추출은 기존 API 활용)
```

---

## 파일 변경 요약

| 파일 | 유형 | 내용 |
|------|------|------|
| `korean_tokenizer.py` | 신규 | Kiwi 싱글턴 + `tokenize_ko()` + 폴백 |
| `raptor_indexer.py` | 신규 | RAPTOR 트리 빌드 (UMAP+GMM+LLM 요약) |
| `engine.py` | 수정 | BM25→Kiwi, RRF 가중 7:3, RAPTOR 통합 |
| `document_parser.py` | 수정 | `_parse_pdf()` 표 추출 + `_table_to_markdown()` |
| `tests/test_korean_tokenizer.py` | 신규 | Kiwi 토크나이저 단위 테스트 |
| `tests/test_raptor_indexer.py` | 신규 | RAPTOR 빌드+검색 테스트 |
| `tests/test_document_parser.py` | 수정 | PDF 표 파싱 테스트 케이스 추가 |
| `tests/test_hybrid_search.py` | 수정 | 가중 RRF 7:3 테스트 |

---

## 검증 계획

1. **Kiwi BM25**: "정보통신공사업을" 검색 → "정보통신공사업" 문서 매칭 확인
2. **7:3 가중 RRF**: BM25 정확 매칭 결과가 벡터 유사 매칭보다 상위 랭킹
3. **RAPTOR**: 50페이지 문서 트리 빌드 → "전체 사업 목표?" 질문 → 상위 레벨 노드 반환
4. **PDF 표**: 나라장터 RFP PDF의 평가기준표 → 마크다운 테이블로 정확 변환
5. **하위호환**: 기존 테스트 전체 통과 (Kiwi 미설치 시 폴백, RAPTOR 비활성화 시 기존 동작)
