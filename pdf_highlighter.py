"""
RFx AI Assistant - PDF 하이라이트 엔진

PDF 문서에서 텍스트를 검색하고,
해당 위치를 노란색 하이라이트 어노테이션으로 변환.

📌 핵심 역할:
   챗봇이 답변할 때 참조한 텍스트의 정확한 위치를 찾아서
   PDF 뷰어에 노란색 형광펜으로 표시해줌.

🔍 참조 및 설계 근거:
   - Adobe Acrobat AI: 답변에 번호 매긴 참조 링크 → 클릭 시 원문 하이라이트
   - ChatPDF: side-by-side 레이아웃 + 클릭 가능한 소스 인용
   - LightPDF: 각주/참조 번호 → 원문 위치 네비게이션
   - streamlit-pdf-viewer: Grobid 좌표 기반 어노테이션 오버레이 지원
   - PyMuPDF(fitz): page.search_for()로 텍스트의 정확한 바운딩 박스 획득

Example:
    >>> highlighter = PDFHighlighter("rfp_document.pdf")
    >>> annotations = highlighter.find_and_highlight("ISO 9001 인증")
    >>> # → [{"page": 3, "x": 120, "y": 340, "width": 200, "height": 15, "color": "#FFEB3B80"}]
"""

import os
import re
from difflib import SequenceMatcher
from typing import Optional
from dataclasses import dataclass, field


# ============================================================
# STEP 1: 하이라이트 결과 데이터 클래스
# ============================================================

@dataclass
class HighlightResult:
    """하이라이트 검색 결과"""
    page: int              # 페이지 번호 (1-based)
    x: float               # 좌상단 X 좌표
    y: float               # 좌상단 Y 좌표
    width: float           # 너비
    height: float          # 높이
    text: str = ""         # 매칭된 텍스트
    color: str = "#FFEB3B80"  # 노란색 형광펜 (반투명)

    def to_annotation(self) -> dict:
        """streamlit-pdf-viewer 어노테이션 포맷으로 변환

        왜 이 포맷인가:
        streamlit-pdf-viewer는 Grobid 좌표계를 사용.
        page, x, y, width, height, color 6개 필드 딕셔너리.
        color는 HTML CSS 컨벤션 따름 → 반투명 노랑 사용.
        """
        return {
            "page": self.page,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "color": self.color
        }


@dataclass
class SourceReference:
    """AI 답변의 출처 참조 정보

    ChatPDF/Adobe 스타일의 [📄 p.3] 같은 인라인 참조를
    데이터로 관리하기 위한 구조.
    """
    page: int              # 페이지 번호
    text_snippet: str      # 참조된 텍스트 조각
    highlights: list[HighlightResult] = field(default_factory=list)
    ref_id: int = 0        # 참조 번호 [1], [2], ...


# ============================================================
# STEP 2: PDF 하이라이트 엔진
# ============================================================

class PDFHighlighter:
    """
    PDF 문서에서 텍스트를 검색하고 하이라이트 어노테이션을 생성.

    왜 PyMuPDF(fitz)를 사용하는가:
    ─────────────────────────────
    1. page.search_for(text)가 텍스트의 정확한 바운딩 박스(Rect)를 반환
    2. 한국어 검색 지원 (UTF-8 네이티브)
    3. 좌표계가 PDF 표준(pt 단위)이라 streamlit-pdf-viewer와 호환
    4. 부분 매칭, 정규식 검색 가능
    5. 페이지별 처리로 대용량 PDF도 효율적

    왜 streamlit-pdf-viewer 어노테이션 방식인가:
    ─────────────────────────────────────────
    1. PDF.js 위에 오버레이로 그려지므로 원본 PDF 변경 없음
    2. scroll_to_page / scroll_to_annotation으로 자동 네비게이션
    3. 반투명 색상 지원 → 형광펜 효과 구현
    4. 어노테이션 클릭 이벤트 콜백 지원
    """

    # 노란색 형광펜 색상 (반투명)
    HIGHLIGHT_YELLOW = "rgba(255, 235, 59, 0.35)"
    # 주황색 (중요 참조용)
    HIGHLIGHT_ORANGE = "rgba(255, 152, 0, 0.35)"
    # 연한 파랑 (보조 참조용)
    HIGHLIGHT_BLUE = "rgba(100, 181, 246, 0.35)"

    def __init__(self, pdf_path: Optional[str] = None, pdf_bytes: Optional[bytes] = None):
        """
        Args:
            pdf_path: PDF 파일 경로
            pdf_bytes: PDF 바이너리 데이터 (Streamlit file_uploader에서 받은 것)
        """
        self.pdf_path = pdf_path
        self.pdf_bytes = pdf_bytes
        self._doc = None
        self._page_dimensions = {}

        if pdf_path or pdf_bytes:
            self._load_document()

    def _load_document(self):
        """PDF 문서 로드 및 페이지 크기 캐싱"""
        try:
            import fitz  # PyMuPDF

            if self.pdf_bytes:
                self._doc = fitz.open(stream=self.pdf_bytes, filetype="pdf")
            elif self.pdf_path:
                self._doc = fitz.open(self.pdf_path)

            # 페이지별 크기 캐싱 (좌표 변환에 필요)
            for i in range(len(self._doc)):
                page = self._doc[i]
                rect = page.rect
                self._page_dimensions[i] = {
                    "width": rect.width,
                    "height": rect.height
                }

        except ImportError:
            print("⚠️ PyMuPDF 미설치. pip install pymupdf")
        except Exception as e:
            print(f"⚠️ PDF 로드 실패: {e}")

    @property
    def page_count(self) -> int:
        """총 페이지 수"""
        return len(self._doc) if self._doc else 0

    def close(self):
        """문서 닫기"""
        if self._doc:
            self._doc.close()

    # ============================================================
    # STEP 3: 텍스트 검색 → 하이라이트 좌표 변환
    # ============================================================

    def find_text(
        self,
        search_text: str,
        pages: Optional[list[int]] = None,
        color: Optional[str] = None
    ) -> list[HighlightResult]:
        """
        PDF에서 텍스트를 검색하고 하이라이트 좌표를 반환.

        왜 이렇게 구현했는가:
        ───────────────────
        PyMuPDF의 search_for()는 fitz.Rect 객체 리스트를 반환.
        이 Rect는 (x0, y0, x1, y1) 형태의 PDF 좌표계.
        streamlit-pdf-viewer는 (page, x, y, width, height) 형태를 요구.
        따라서 Rect → 어노테이션 포맷 변환이 필요.

        Args:
            search_text: 검색할 텍스트 (부분 일치 지원)
            pages: 검색할 페이지 목록 (None이면 전체)
            color: 하이라이트 색상 (None이면 노란색)

        Returns:
            list[HighlightResult]: 하이라이트 좌표 리스트
        """
        if not self._doc:
            return []

        highlights = []
        highlight_color = color or self.HIGHLIGHT_YELLOW

        # 검색할 페이지 범위 결정
        page_range = pages if pages else range(len(self._doc))

        for page_idx in page_range:
            if isinstance(page_idx, int) and 0 <= page_idx < len(self._doc):
                page = self._doc[page_idx]
                # PyMuPDF search_for → Rect 리스트 반환
                rects = page.search_for(search_text) or []

                for rect in rects:
                    highlights.append(HighlightResult(
                        page=page_idx + 1,  # 1-based (streamlit-pdf-viewer 규격)
                        x=rect.x0,
                        y=rect.y0,
                        width=rect.width,
                        height=rect.height,
                        text=search_text,
                        color=highlight_color
                    ))

        return highlights

    def find_multiple_texts(
        self,
        search_texts: list[str],
        color: Optional[str] = None
    ) -> list[HighlightResult]:
        """
        여러 텍스트를 한번에 검색.
        AI 답변에서 여러 근거 텍스트를 추출했을 때 사용.
        """
        all_highlights = []
        for text in search_texts:
            results = self.find_text(text, color=color)
            all_highlights.extend(results)
        return all_highlights

    # ============================================================
    # STEP 4: 스마트 검색 (긴 문장 → 키워드 분할)
    # ============================================================

    def smart_find(
        self,
        text: str,
        pages: Optional[list[int]] = None,
        min_length: int = 4,
        color: Optional[str] = None
    ) -> list[HighlightResult]:
        """
        긴 문장이 정확히 매칭되지 않을 때,
        핵심 구절로 분할하여 검색하는 스마트 검색.

        왜 이 기능이 필요한가:
        ─────────────────────
        LLM이 반환하는 "근거 텍스트"가 PDF 원문과 100% 일치하지 않을 수 있음.
        (줄바꿈, 공백, 하이픈 차이 등)
        따라서:
        1. 먼저 전체 텍스트로 검색 시도
        2. 실패하면 문장을 구절 단위로 분할하여 재검색
        3. 최소 min_length 이상의 구절만 검색 (노이즈 방지)

        Args:
            text: 검색할 텍스트 (문장 또는 구절)
            pages: 검색할 페이지 목록 (None이면 전체)
            min_length: 최소 검색 문자열 길이
            color: 하이라이트 색상

        Returns:
            list[HighlightResult]: 하이라이트 좌표 리스트
        """
        # 1차: 전체 텍스트 검색
        results = self.find_text(text, pages=pages, color=color)
        if results:
            return results

        # 2차: 텍스트 정리 후 재검색
        cleaned = re.sub(r'\s+', ' ', text).strip()
        if cleaned != text:
            results = self.find_text(cleaned, pages=pages, color=color)
            if results:
                return results

        # 3차: 구절 단위로 분할 검색
        #   "ISO 9001 인증을 보유하고 있어야 합니다"
        #   → ["ISO 9001 인증", "보유하고 있어야"]
        phrases = self._split_into_phrases(text, min_length)
        for phrase in phrases:
            phrase_results = self.find_text(phrase, pages=pages, color=color)
            results.extend(phrase_results)
        if results:
            return results

        # 4차: 퍼지 매칭 (키워드 + 문자열 유사도)
        fuzzy_results = self._fuzzy_find_by_lines(text, pages=pages, color=color)
        if fuzzy_results:
            return fuzzy_results

        # 특정 페이지 지정이 실패하면 전체 페이지로 1회 확장 탐색
        if pages:
            fuzzy_results = self._fuzzy_find_by_lines(text, pages=None, color=color)
            if fuzzy_results:
                return fuzzy_results

        return []

    @staticmethod
    def _normalize_for_match(text: str) -> str:
        """비교용 정규화: 공백/특수문자 차이를 줄여 검색 내성을 높임"""
        lowered = (text or "").lower()
        lowered = re.sub(r"[\u2010-\u2015]", "-", lowered)
        lowered = re.sub(r"[^0-9a-zA-Z가-힣\s-]", " ", lowered)
        lowered = re.sub(r"\s+", " ", lowered).strip()
        return lowered

    @classmethod
    def _extract_keywords(cls, text: str) -> list[str]:
        """참조 문장에서 핵심 키워드(명사/숫자 중심) 추출"""
        normalized = cls._normalize_for_match(text)
        if not normalized:
            return []

        stop_words = {
            "및", "또는", "대한", "관련", "사항", "내용", "기준", "조건",
            "the", "and", "for", "with", "from", "this", "that",
        }
        raw_tokens = normalized.split()
        keywords = []
        for token in raw_tokens:
            if len(token) < 2:
                continue
            if token in stop_words:
                continue
            if token not in keywords:
                keywords.append(token)
        return keywords[:8]

    def _fuzzy_find_by_lines(
        self,
        text: str,
        pages: Optional[list[int]] = None,
        color: Optional[str] = None
    ) -> list[HighlightResult]:
        """페이지별 라인 단위 퍼지 매칭으로 하이라이트 좌표를 찾는다."""
        if not self._doc:
            return []

        query_norm = self._normalize_for_match(text)
        if not query_norm:
            return []
        keywords = self._extract_keywords(text)
        if not keywords:
            return []

        highlight_color = color or self.HIGHLIGHT_YELLOW
        page_range = pages if pages else range(len(self._doc))
        candidates: list[tuple[float, int, float, float, float, float, str]] = []

        for page_idx in page_range:
            if not isinstance(page_idx, int) or not (0 <= page_idx < len(self._doc)):
                continue
            page = self._doc[page_idx]
            words = page.get_text("words")
            if not words:
                continue

            grouped_lines: dict[tuple[int, int], dict] = {}
            grouped_blocks: dict[int, dict] = {}
            for word in words:
                if len(word) < 8:
                    continue
                x0, y0, x1, y1, token, block_no, line_no, _ = word[:8]
                block_no = int(block_no)
                line_no = int(line_no)

                line_key = (block_no, line_no)
                if line_key not in grouped_lines:
                    grouped_lines[line_key] = {
                        "tokens": [],
                        "x0": float(x0),
                        "y0": float(y0),
                        "x1": float(x1),
                        "y1": float(y1),
                    }
                line = grouped_lines[line_key]
                line["tokens"].append(str(token))
                line["x0"] = min(line["x0"], float(x0))
                line["y0"] = min(line["y0"], float(y0))
                line["x1"] = max(line["x1"], float(x1))
                line["y1"] = max(line["y1"], float(y1))

                if block_no not in grouped_blocks:
                    grouped_blocks[block_no] = {
                        "tokens": [],
                        "x0": float(x0),
                        "y0": float(y0),
                        "x1": float(x1),
                        "y1": float(y1),
                    }
                block = grouped_blocks[block_no]
                block["tokens"].append(str(token))
                block["x0"] = min(block["x0"], float(x0))
                block["y0"] = min(block["y0"], float(y0))
                block["x1"] = max(block["x1"], float(x1))
                block["y1"] = max(block["y1"], float(y1))

            def collect_candidates(
                grouped: dict,
                min_score: float,
                min_coverage: float,
                min_similarity: float
            ) -> None:
                for item in grouped.values():
                    item_text = " ".join(item["tokens"]).strip()
                    item_norm = self._normalize_for_match(item_text)
                    if len(item_norm) < 3:
                        continue

                    keyword_hits = sum(1 for kw in keywords if kw in item_norm)
                    keyword_coverage = keyword_hits / len(keywords)
                    similarity = SequenceMatcher(None, query_norm, item_norm).ratio()

                    if query_norm in item_norm:
                        similarity = max(similarity, 0.95)
                    elif item_norm in query_norm:
                        similarity = max(similarity, 0.70)

                    score = (0.65 * keyword_coverage) + (0.35 * similarity)
                    if score < min_score and not (
                        keyword_coverage >= min_coverage and similarity >= min_similarity
                    ):
                        continue

                    candidates.append(
                        (
                            score,
                            page_idx + 1,
                            item["x0"],
                            item["y0"],
                            max(2.0, item["x1"] - item["x0"]),
                            max(2.0, item["y1"] - item["y0"]),
                            item_text,
                        )
                    )

            # 1차: 라인 단위 정밀 매칭
            collect_candidates(
                grouped=grouped_lines,
                min_score=0.58,
                min_coverage=0.5,
                min_similarity=0.33,
            )
            # 2차: 블록 단위 확장 매칭 (표 셀/줄바꿈 분리 대응)
            collect_candidates(
                grouped=grouped_blocks,
                min_score=0.52,
                min_coverage=0.4,
                min_similarity=0.28,
            )

        candidates.sort(key=lambda item: item[0], reverse=True)
        top_candidates = candidates[:3]
        highlights: list[HighlightResult] = []
        for _, page_num, x, y, width, height, matched_text in top_candidates:
            highlights.append(
                HighlightResult(
                    page=page_num,
                    x=x,
                    y=y,
                    width=width,
                    height=height,
                    text=matched_text,
                    color=highlight_color,
                )
            )
        return highlights

    def _split_into_phrases(self, text: str, min_length: int = 4) -> list[str]:
        """텍스트를 의미 있는 구절로 분할"""
        # 쉼표, 마침표, 세미콜론 등으로 분할
        parts = re.split(r'[,;.·•\n]', text)
        phrases = []

        for part in parts:
            part = part.strip()
            if len(part) >= min_length:
                phrases.append(part)
                # 긴 구절은 추가 분할
                if len(part) > 30:
                    words = part.split()
                    if len(words) > 4:
                        # 앞쪽 절반, 뒤쪽 절반
                        mid = len(words) // 2
                        front = " ".join(words[:mid])
                        back = " ".join(words[mid:])
                        if len(front) >= min_length:
                            phrases.append(front)
                        if len(back) >= min_length:
                            phrases.append(back)

        return phrases

    # ============================================================
    # STEP 5: 페이지 텍스트 추출 (RAG 연동용)
    # ============================================================

    def get_page_text(self, page_number: int) -> str:
        """특정 페이지의 텍스트 추출 (1-based)"""
        if not self._doc or page_number < 1 or page_number > len(self._doc):
            return ""
        page = self._doc[page_number - 1]
        return page.get_text("text")

    def get_all_text_with_pages(self) -> list[dict]:
        """
        전체 텍스트를 페이지 정보와 함께 추출.
        RAG 청킹 시 페이지 번호를 메타데이터로 보존하기 위함.

        Returns:
            list[dict]: [{"page": 1, "text": "..."}, ...]
        """
        if not self._doc:
            return []

        result = []
        for i in range(len(self._doc)):
            text = self._doc[i].get_text("text").strip()
            if text:
                result.append({
                    "page": i + 1,
                    "text": text
                })
        return result

    # ============================================================
    # STEP 6: 어노테이션 변환 유틸리티
    # ============================================================

    @staticmethod
    def highlights_to_annotations(highlights: list[HighlightResult]) -> list[dict]:
        """
        HighlightResult 리스트 → streamlit-pdf-viewer annotations 리스트

        이것이 PyMuPDF 좌표 → streamlit-pdf-viewer 좌표 변환의 핵심.

        왜 직접 변환이 되는가:
        ────────────────────
        PyMuPDF의 Rect와 streamlit-pdf-viewer 모두 PDF 포인트 단위를 사용.
        streamlit-pdf-viewer 내부에서 pdf.js가 렌더링할 때
        자동으로 뷰포트 스케일링을 처리함.
        따라서 PyMuPDF의 좌표를 그대로 사용해도 정확히 매칭됨.
        """
        return [h.to_annotation() for h in highlights]

    @staticmethod
    def get_first_highlight_page(highlights: list[HighlightResult]) -> Optional[int]:
        """첫 번째 하이라이트의 페이지 번호 반환 (자동 스크롤용)"""
        if highlights:
            return highlights[0].page
        return None

    @staticmethod
    def group_by_page(highlights: list[HighlightResult]) -> dict[int, list[HighlightResult]]:
        """하이라이트를 페이지별로 그룹핑"""
        grouped = {}
        for h in highlights:
            if h.page not in grouped:
                grouped[h.page] = []
            grouped[h.page].append(h)
        return grouped


# ============================================================
# STEP 7: AI 응답에서 참조 텍스트 추출
# ============================================================

class ReferenceExtractor:
    """
    AI(LLM) 응답에서 출처 참조 정보를 추출하는 유틸리티.

    왜 이 클래스가 필요한가:
    ─────────────────────
    Adobe Acrobat AI 방식: 답변에 [1], [2] 같은 참조 번호가 포함됨.
    사용자가 클릭하면 PDF의 해당 위치로 이동 + 하이라이트.

    우리 시스템에서는:
    1. LLM에게 답변 시 "근거 텍스트"와 "페이지 번호"를 함께 반환하도록 프롬프트
    2. 이 클래스가 응답을 파싱하여 참조 정보 추출
    3. PDFHighlighter로 실제 좌표 검색
    4. streamlit-pdf-viewer에 어노테이션으로 전달
    """

    @staticmethod
    def parse_references_from_response(response_text: str) -> list[dict]:
        """
        AI 응답에서 [📄 p.X "인용텍스트"] 형태의 참조를 추출.

        Returns:
            list[dict]: [{"page": 3, "text": "인용 텍스트"}, ...]
        """
        references = []

        # 패턴: [📄 p.숫자 "텍스트"] 또는 [📄 p.숫자]
        pattern = r'\[📄\s*p\.(\d+)(?:\s*"([^"]*)")?\]'
        matches = re.finditer(pattern, response_text)

        for i, match in enumerate(matches):
            page = int(match.group(1))
            text = match.group(2) or ""
            references.append({
                "ref_id": i + 1,
                "page": page,
                "text": text
            })

        return references

    @staticmethod
    def parse_structured_references(ref_data: list[dict]) -> list[dict]:
        """
        구조화된 참조 데이터를 파싱.
        (LLM이 JSON 형태로 참조를 반환할 때 사용)

        Input format:
        [
            {"page": 3, "text": "ISO 9001 인증", "relevance": "high"},
            {"page": 5, "text": "유사 실적", "relevance": "medium"}
        ]
        """
        references = []
        for i, ref in enumerate(ref_data):
            references.append({
                "ref_id": i + 1,
                "page": ref.get("page", 1),
                "text": ref.get("text", ""),
                "relevance": ref.get("relevance", "medium")
            })
        return references


# ============================================================
# STEP 8: 통합 하이라이트 매니저
# ============================================================

class HighlightManager:
    """
    PDF 하이라이트의 전체 생명주기를 관리.

    Streamlit 세션 상태에서 사용:
    1. PDF 로드 시 초기화
    2. AI 답변마다 하이라이트 업데이트
    3. 사용자가 참조 클릭 시 해당 위치로 스크롤

    사용 흐름:
    ─────────
    manager = HighlightManager(pdf_bytes)
    manager.add_highlights_from_response(ai_response, references)
    annotations = manager.get_annotations()     # → pdf_viewer에 전달
    scroll_page = manager.get_scroll_target()   # → scroll_to_page에 전달
    """

    def __init__(self, pdf_path: str = None, pdf_bytes: bytes = None):
        self.highlighter = PDFHighlighter(pdf_path=pdf_path, pdf_bytes=pdf_bytes)
        self.current_highlights: list[HighlightResult] = []
        self.reference_history: list[SourceReference] = []
        self._scroll_target_page: Optional[int] = None
        self._scroll_target_annotation: Optional[int] = None

    def clear_highlights(self):
        """현재 하이라이트 초기화"""
        self.current_highlights = []
        self._scroll_target_page = None
        self._scroll_target_annotation = None

    def add_highlights_from_references(
        self,
        references: list[dict],
        color: str = None
    ) -> list[HighlightResult]:
        """
        참조 정보로부터 하이라이트를 생성하고 추가.

        Args:
            references: [{"page": 3, "text": "검색할 텍스트"}, ...]
            color: 하이라이트 색상

        Returns:
            list[HighlightResult]: 새로 추가된 하이라이트
        """
        new_highlights = []
        highlight_color = color or PDFHighlighter.HIGHLIGHT_YELLOW

        for ref in references:
            page = ref.get("page")
            text = ref.get("text", "")

            if text:
                # 텍스트 기반 검색 (특정 페이지 우선)
                if page:
                    # 해당 페이지에서 먼저 검색
                    results = self.highlighter.find_text(
                        text, pages=[page - 1], color=highlight_color
                    )
                    # 못 찾으면 스마트 검색
                    if not results:
                        results = self.highlighter.smart_find(
                            text, pages=[page - 1], color=highlight_color
                        )
                else:
                    results = self.highlighter.smart_find(
                        text, color=highlight_color
                    )

                new_highlights.extend(results)

            elif page:
                # 텍스트 없이 페이지만 지정된 경우
                # 페이지 상단에 얇은 하이라이트 바 추가
                new_highlights.append(HighlightResult(
                    page=page,
                    x=0,
                    y=0,
                    width=595,  # A4 width in points
                    height=5,
                    text="[page reference]",
                    color=highlight_color
                ))

        self.current_highlights.extend(new_highlights)

        # 첫 번째 하이라이트로 스크롤 타겟 설정
        if new_highlights:
            self._scroll_target_page = new_highlights[0].page
            # 새로 추가된 하이라이트 중 첫 번째의 인덱스
            first_new_idx = len(self.current_highlights) - len(new_highlights)
            self._scroll_target_annotation = first_new_idx + 1  # 1-based

        return new_highlights

    def get_annotations(self) -> list[dict]:
        """현재 하이라이트를 streamlit-pdf-viewer 어노테이션으로 반환"""
        return PDFHighlighter.highlights_to_annotations(self.current_highlights)

    def get_scroll_target_page(self) -> Optional[int]:
        """자동 스크롤 대상 페이지"""
        return self._scroll_target_page

    def get_scroll_target_annotation(self) -> Optional[int]:
        """자동 스크롤 대상 어노테이션 인덱스 (1-based)"""
        return self._scroll_target_annotation

    @property
    def page_count(self) -> int:
        return self.highlighter.page_count

    def close(self):
        self.highlighter.close()
