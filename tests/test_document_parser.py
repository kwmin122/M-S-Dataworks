"""PDF 표 파싱 + 마크다운 변환 테스트."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from document_parser import DocumentParser


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
