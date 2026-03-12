"""PDF 표 파싱 + 마크다운 변환 테스트."""
import importlib.util
import sys
from pathlib import Path

import pytest

# Import the ROOT document_parser explicitly by file path to avoid
# collision with rag_engine/document_parser.py when rag_engine/ is on sys.path.
_root = Path(__file__).parent.parent
_spec = importlib.util.spec_from_file_location("document_parser", _root / "document_parser.py")
_mod = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("document_parser", _mod)
_spec.loader.exec_module(_mod)
DocumentParser = _mod.DocumentParser


class TestTableToMarkdown:
    """_table_to_markdown() 단위 테스트."""

    def test_basic_table(self):
        """기본 2x3 표 → 마크다운 변환."""
        table = [
            ["평가항목", "배점", "세부기준"],
            ["사업이해", "15", "목적 이해도"],
            ["기술방안", "25", "구현 적정성"],
        ]
        result = DocumentParser._table_to_markdown(table)
        assert "| 평가항목 | 배점 | 세부기준 |" in result
        assert "| --- | --- | --- |" in result
        assert "| 사업이해 | 15 | 목적 이해도 |" in result
        assert "| 기술방안 | 25 | 구현 적정성 |" in result

    def test_none_cells(self):
        """None 셀 → 빈 문자열 처리."""
        table = [
            ["구분", "값"],
            [None, "100"],
            ["항목", None],
        ]
        result = DocumentParser._table_to_markdown(table)
        assert "|  | 100 |" in result
        assert "| 항목 |  |" in result

    def test_single_row_returns_empty(self):
        """행 1개 → 빈 문자열 (표가 아님)."""
        table = [["헤더만"]]
        result = DocumentParser._table_to_markdown(table)
        assert result == ""

    def test_empty_table_returns_empty(self):
        """빈 테이블 → 빈 문자열."""
        assert DocumentParser._table_to_markdown([]) == ""
        assert DocumentParser._table_to_markdown(None) == ""

    def test_pipe_in_cell_escaped(self):
        """셀 내 파이프 문자 → 이스케이프."""
        table = [
            ["항목", "값"],
            ["A|B", "100"],
        ]
        result = DocumentParser._table_to_markdown(table)
        assert "A\\|B" in result

    def test_uneven_columns(self):
        """열 수가 불균일 → 부족한 열은 빈 셀로 채움."""
        table = [
            ["A", "B", "C"],
            ["1", "2"],
            ["x", "y", "z"],
        ]
        result = DocumentParser._table_to_markdown(table)
        lines = result.strip().split("\n")
        assert lines[2].count("|") == lines[0].count("|")

    def test_newline_in_cell(self):
        """셀 내 줄바꿈 → 공백으로 치환."""
        table = [
            ["항목", "설명"],
            ["A", "첫째줄\n둘째줄"],
        ]
        result = DocumentParser._table_to_markdown(table)
        assert "첫째줄 둘째줄" in result
        assert "\n" not in result.split("\n")[2]


class TestPdfTableIntegration:
    """_parse_pdf() 표 추출 통합 테스트."""

    def test_parse_pdf_with_tables_mock(self, tmp_path):
        """pdfplumber 표 추출이 page text에 포함되는지."""
        from unittest.mock import patch, MagicMock

        parser = DocumentParser()

        # parse()가 path.exists() 체크하므로 더미 파일 생성
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 dummy")

        mock_page = MagicMock()
        mock_page.extract_text.return_value = "일반 텍스트 내용"
        mock_page.extract_tables.return_value = [
            [["항목", "점수"], ["사업이해", "15"], ["기술방안", "25"]],
        ]

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = lambda s: s
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with patch("pdfplumber.open", return_value=mock_pdf):
            doc = parser.parse(str(pdf_path))

        assert "일반 텍스트 내용" in doc.text
        assert "| 항목 | 점수 |" in doc.text
        assert "| 사업이해 | 15 |" in doc.text

    def test_parse_pdf_no_tables(self, tmp_path):
        """표 없는 PDF → 기존 동작 유지."""
        from unittest.mock import patch, MagicMock

        parser = DocumentParser()

        # parse()가 path.exists() 체크하므로 더미 파일 생성
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 dummy")

        mock_page = MagicMock()
        mock_page.extract_text.return_value = "텍스트만 있는 페이지"
        mock_page.extract_tables.return_value = []

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = lambda s: s
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with patch("pdfplumber.open", return_value=mock_pdf):
            doc = parser.parse(str(pdf_path))

        assert "텍스트만 있는 페이지" in doc.text
        assert "|" not in doc.text
