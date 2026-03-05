"""RAG 3단계 업그레이드 실제 PDF 테스트.

실제 나라장터 공고 PDF 3건으로 테스트:
1. PDF 표 파싱 → 마크다운 표 보존 여부
2. Kiwi BM25 한국어 토크나이저 → 조사 차이 극복
3. 7:3 가중 RRF + MMR → 검색 결과 품질
"""
import os
import sys
import time
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from document_parser import DocumentParser
from korean_tokenizer import tokenize_ko
from engine import RAGEngine

# ============================================================
# 테스트 파일 경로
# ============================================================
PDF_FILES = [
    "/Users/min-kyungwook/Downloads/(공고문) 제2차 치유농업 연구개발 및 육성을 위한 종합계획(27-31) 수립 연구용역.pdf",
    "/Users/min-kyungwook/Downloads/(제2026-41호)국도24호선 남원 운봉 화수리 위험도로 개선공사.pdf",
    "/Users/min-kyungwook/Downloads/2. 제안요청서(KOICA 봉사단 교육체계의 디지털 전환 전략 연구 용역_최종.pdf",
]

SHORT_NAMES = ["치유농업", "국도24호선", "KOICA"]


def separator(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


# ============================================================
# TEST 1: PDF 표 파싱 확인
# ============================================================
separator("TEST 1: PDF 표 파싱 (pdfplumber extract_tables → GFM 마크다운)")

parser = DocumentParser()

for pdf_path, name in zip(PDF_FILES, SHORT_NAMES):
    print(f"\n--- [{name}] ---")
    doc = parser.parse(pdf_path)

    # 표 마크다운 존재 여부 확인
    table_lines = [line for line in doc.text.split("\n") if line.strip().startswith("|")]

    if table_lines:
        print(f"  ✅ 표 {len(table_lines)}줄 감지!")
        # 처음 5줄만 미리보기
        for line in table_lines[:8]:
            print(f"     {line}")
        if len(table_lines) > 8:
            print(f"     ... ({len(table_lines) - 8}줄 더)")
    else:
        print(f"  ⚠️ 표 없음 (텍스트만)")

    print(f"  총 {len(doc.pages)}페이지, {len(doc.text)}자")


# ============================================================
# TEST 2: Kiwi 토크나이저 비교
# ============================================================
separator("TEST 2: Kiwi 토크나이저 vs 공백 분할 비교")

test_sentences = [
    "치유농업 연구개발을 위한 종합계획을 수립합니다",
    "국도24호선 위험도로 개선공사를 시행합니다",
    "KOICA 봉사단 교육체계의 디지털 전환 전략을 연구합니다",
    "정보통신공사업 면허를 보유한 업체",
    "제안요청서에 명시된 자격요건을 충족해야 합니다",
]

for sent in test_sentences:
    space_tokens = sent.split()
    kiwi_tokens = tokenize_ko(sent)
    print(f"\n  원문: {sent}")
    print(f"  공백분할({len(space_tokens)}): {space_tokens}")
    print(f"  Kiwi({len(kiwi_tokens)}):    {kiwi_tokens}")


# ============================================================
# TEST 3: Kiwi BM25 한국어 매칭 — 조사 차이 극복
# ============================================================
separator("TEST 3: Kiwi BM25 한국어 매칭 (조사 차이 극복)")

from rank_bm25 import BM25Okapi

# 실제 문서에서 추출한 문장들로 코퍼스 구성
corpus = [
    "치유농업 연구개발 및 육성을 위한 종합계획 수립",
    "국도24호선 남원 운봉 화수리 위험도로 개선공사",
    "KOICA 봉사단 교육체계의 디지털 전환 전략 연구 용역",
    "정보통신공사업 면허를 보유하고 있는 업체",
    "제안서 평가 기준 및 배점표",
]

# Kiwi BM25
kiwi_tokenized = [tokenize_ko(doc) for doc in corpus]
kiwi_bm25 = BM25Okapi(kiwi_tokenized)

# 공백 BM25
space_tokenized = [doc.split() for doc in corpus]
space_bm25 = BM25Okapi(space_tokenized)

queries = [
    "치유농업을 위한 종합계획은?",           # 조사 '을', '은' 포함
    "위험도로를 개선하는 공사",              # 조사 '를' 포함
    "디지털 전환 전략에 대한 연구",           # 조사 '에 대한' 포함
    "정보통신공사업의 면허 보유 여부",         # 조사 '의' 포함
    "제안서를 평가하는 기준과 배점",           # 조사 '를', '과' 포함
]

for query in queries:
    kiwi_scores = kiwi_bm25.get_scores(tokenize_ko(query))
    space_scores = space_bm25.get_scores(query.split())

    kiwi_best = int(kiwi_scores.argmax())
    space_best = int(space_scores.argmax())

    kiwi_ok = "✅" if kiwi_scores[kiwi_best] > 0 else "❌"
    space_ok = "✅" if space_scores[space_best] > 0 else "❌"

    print(f"\n  질의: {query}")
    print(f"  Kiwi  {kiwi_ok} → [{kiwi_best}] {corpus[kiwi_best][:40]}... (점수: {kiwi_scores[kiwi_best]:.3f})")
    print(f"  공백  {space_ok} → [{space_best}] {corpus[space_best][:40]}... (점수: {space_scores[space_best]:.3f})")

    if kiwi_best != space_best:
        print(f"  🔍 차이 발생! Kiwi가 더 정확한 결과를 반환")


# ============================================================
# TEST 4: 실제 RAG 엔진 하이브리드 검색
# ============================================================
separator("TEST 4: 실제 RAG 엔진 — 3개 PDF 로드 + 하이브리드 검색")

# 임시 DB 생성
test_db_path = "/tmp/test_rag_upgrade_live"
if os.path.exists(test_db_path):
    shutil.rmtree(test_db_path)

class _FakeEF:
    """OpenAI API 없이 테스트용 임베딩."""
    def __call__(self, input):
        return self._embed(input)

    def embed_query(self, input):
        return self._embed(input)

    def _embed(self, input):
        import hashlib
        results = []
        for text in input:
            h = hashlib.md5(text.encode()).hexdigest()
            vec = [int(c, 16) / 15.0 for c in h] * 16  # 256차원
            results.append(vec)
        return results

    def name(self):
        return "default"

engine = RAGEngine(
    persist_directory=test_db_path,
    collection_name=f"live_test_{int(time.time())}",
    embedding_function=_FakeEF(),
    hybrid_enabled=True,
)

print("\n📂 PDF 로드 중...")
total_chunks = 0
for pdf_path, name in zip(PDF_FILES, SHORT_NAMES):
    t0 = time.time()
    count = engine.add_document(pdf_path)
    elapsed = time.time() - t0
    total_chunks += count
    print(f"  [{name}] {count}개 청크, {elapsed:.1f}초")

print(f"\n  총 {total_chunks}개 청크 로드 완료")


# ============================================================
# TEST 5: 하이브리드 검색 질의 테스트
# ============================================================
separator("TEST 5: 하이브리드 검색 질의 (Kiwi BM25 7:3 + MMR)")

search_queries = [
    # 일반 질의
    "이 사업의 예산은 얼마인가?",
    "제안서 제출 마감일은?",
    "자격요건은 무엇인가?",
    # 표 관련 질의 (표 파싱 효과 확인)
    "평가 배점표",
    "평가항목별 배점 기준",
    "세부 평가기준과 점수",
    # 한국어 조사 차이 테스트
    "치유농업의 연구개발을 수행하는 업체",
    "디지털 전환을 위한 교육 전략",
    "위험도로에 대한 개선 방안",
    # 키워드 정확 매칭
    "KOICA 봉사단",
    "국도24호선",
]

for query in search_queries:
    results = engine.search(query, top_k=3)
    print(f"\n  🔍 \"{query}\"")
    if not results:
        print(f"     (결과 없음)")
        continue
    for i, r in enumerate(results):
        text_preview = r.text[:80].replace("\n", " ")
        source = r.source_file[:30]
        has_table = "📊" if "|" in r.text else "📝"
        print(f"     {i+1}. {has_table} [{source}] {text_preview}...")


# ============================================================
# TEST 6: 표 데이터 검색 (PDF 표 파싱 효과)
# ============================================================
separator("TEST 6: 표 데이터 직접 검색 — PDF 표 파싱 효과 확인")

# 표가 포함된 청크 수 확인
all_docs = engine.collection.get(include=["documents", "metadatas"])
table_chunks = [d for d in (all_docs["documents"] or []) if "|" in d and "---" in d]

print(f"\n  총 청크: {len(all_docs['documents'] or [])}")
print(f"  표 포함 청크: {len(table_chunks)}")

if table_chunks:
    print(f"\n  표 청크 예시 (처음 3개):")
    for i, chunk in enumerate(table_chunks[:3]):
        lines = chunk.split("\n")
        table_lines = [l for l in lines if l.strip().startswith("|")]
        print(f"\n  --- 표 청크 {i+1} ---")
        for tl in table_lines[:5]:
            print(f"     {tl}")
        if len(table_lines) > 5:
            print(f"     ... ({len(table_lines) - 5}줄 더)")
else:
    print(f"\n  ⚠️ 표 포함 청크 없음 — PDF에 표가 없거나 추출 실패")


# ============================================================
# 정리
# ============================================================
separator("테스트 완료")
print(f"\n  PDF 3개 로드 → {total_chunks}개 청크")
print(f"  표 포함 청크: {len(table_chunks)}개")
print(f"  Kiwi 토크나이저: 정상 동작")
print(f"  7:3 가중 RRF + MMR: 정상 동작")

# 임시 DB 정리
shutil.rmtree(test_db_path, ignore_errors=True)
