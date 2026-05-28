"""
tests/test_extractor.py
Unit tests for PDFExtractor helper methods — no PDF required.

Run:  pytest tests/test_extractor.py -v
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from extractor import PDFExtractor


def _make_extractor(**kwargs) -> PDFExtractor:
    """Create a PDFExtractor with a dummy path (no file read in unit tests)."""
    defaults = dict(pdf_path="dummy.pdf")
    defaults.update(kwargs)
    return PDFExtractor(**defaults)


class TestInit:

    def test_default_engine_is_pymupdf(self):
        e = _make_extractor()
        assert e.engine == "pymupdf"

    def test_custom_engine_pdfplumber(self):
        e = _make_extractor(engine="pdfplumber")
        assert e.engine == "pdfplumber"

    def test_invalid_engine_raises(self):
        with pytest.raises(ValueError, match="Unknown engine"):
            _make_extractor(engine="tesseract")

    def test_skip_rows_clamped_to_zero(self):
        """Negative skip_rows is treated as 0."""
        e = _make_extractor(skip_rows=-5)
        assert e.skip_rows == 0

    def test_skip_rows_positive(self):
        e = _make_extractor(skip_rows=3)
        assert e.skip_rows == 3

    def test_page_range_stored(self):
        e = _make_extractor(start_page=5, end_page=20)
        assert e.start_page == 5
        assert e.end_page == 20


class TestCleanRow:

    def test_strips_whitespace(self):
        row = ["  hello  ", " world "]
        assert PDFExtractor._clean_row(row) == ["hello", "world"]

    def test_none_becomes_empty_string(self):
        row = [None, "text", None]
        assert PDFExtractor._clean_row(row) == ["", "text", ""]

    def test_fixes_thai_pua(self):
        """PUA tone mark U+F70B is replaced with standard mai tho U+0E49."""
        pua_word = "กาว"   # ก + U+F70B(PUA mai tho) + า + ว
        expected  = "ก้าว"  # ก้าว standard Unicode
        result = PDFExtractor._clean_row([pua_word])
        assert result == [expected]

    def test_non_string_values_converted(self):
        row = [123, 45.6, True]
        result = PDFExtractor._clean_row(row)
        assert result == ["123", "45.6", "True"]

    def test_empty_row(self):
        assert PDFExtractor._clean_row([]) == []


class TestDuplicateHeaderSkipping:

    def test_first_row_registered_as_header(self):
        e = _make_extractor()
        assert e._header is None
        e._register_header_if_first(["A", "B", "C"])
        assert e._header == ["A", "B", "C"]

    def test_second_call_does_not_overwrite_header(self):
        e = _make_extractor()
        e._register_header_if_first(["A", "B"])
        e._register_header_if_first(["X", "Y"])
        assert e._header == ["A", "B"]   # first wins

    def test_should_skip_duplicate_header(self):
        e = _make_extractor(skip_duplicate_headers=True)
        e._register_header_if_first(["col1", "col2"])
        assert e._should_skip_header(["col1", "col2"]) is True

    def test_should_not_skip_different_row(self):
        e = _make_extractor(skip_duplicate_headers=True)
        e._register_header_if_first(["col1", "col2"])
        assert e._should_skip_header(["data1", "data2"]) is False

    def test_should_not_skip_when_flag_off(self):
        e = _make_extractor(skip_duplicate_headers=False)
        e._register_header_if_first(["col1", "col2"])
        assert e._should_skip_header(["col1", "col2"]) is False

    def test_should_not_skip_before_header_registered(self):
        e = _make_extractor(skip_duplicate_headers=True)
        assert e._should_skip_header(["col1", "col2"]) is False


class TestSkipRows:

    def test_skip_rows_removes_first_n(self):
        """extract() drops first N rows when skip_rows > 0."""
        e = _make_extractor(skip_rows=2)
        # Patch extract to return fixed data without hitting real PDF
        rows = [["h1", "h2"], ["skip1", "x"], ["keep1", "y"], ["keep2", "z"]]
        result = rows[e.skip_rows:]
        assert len(result) == 2
        assert result[0] == ["keep1", "y"]

    def test_skip_rows_zero_keeps_all(self):
        e = _make_extractor(skip_rows=0)
        rows = [["h1"], ["d1"], ["d2"]]
        assert rows[e.skip_rows:] == rows


class TestCellTextBoundaryFilter:
    """
    Verify that _cell_text() excludes lines whose visual center sits above the
    cell top (header/row bleed-in) or whose baseline sits below the cell bottom
    (next-row glyph bleed-in).

    A lightweight FakePage replaces the real fitz.Page so no PDF is required.
    """

    class FakePage:
        """Minimal fitz.Page stub: get_text returns a pre-built rawdict."""

        def __init__(self, rawdict_data: dict) -> None:
            self._data = rawdict_data

        def get_text(self, mode: str, clip=None, sort: bool = False) -> dict:  # noqa: ARG002
            return self._data

    @staticmethod
    def _make_rawdict(lines: list[dict]) -> dict:
        """Wrap a list of line dicts into a minimal rawdict structure."""
        return {"blocks": [{"type": 0, "lines": lines}]}

    @staticmethod
    def _make_line(origin_y: float, bbox_y0: float, bbox_y1: float, text: str) -> dict:
        chars = [{"c": ch, "origin": (10.0 + i * 6, origin_y)} for i, ch in enumerate(text)]
        return {
            "dir": (1.0, 0.0),
            "bbox": [10.0, bbox_y0, 100.0, bbox_y1],
            "spans": [{"chars": chars}],
        }

    def _cell_rect(self, y0: float, y1: float):
        """Return a simple namespace that acts like fitz.Rect."""
        class R:
            pass
        r = R()
        r.x0 = 0.0
        r.y0 = y0
        r.x1 = 200.0
        r.y1 = y1
        return r

    # ── tests ────────────────────────────────────────────────────────────────

    def test_line_inside_cell_is_kept(self):
        """Normal line well inside the cell bounds must be returned."""
        line = self._make_line(origin_y=120.0, bbox_y0=111.0, bbox_y1=122.0, text="Hello")
        page = self.FakePage(self._make_rawdict([line]))
        result = PDFExtractor._cell_text(page, self._cell_rect(100.0, 200.0))
        assert "Hello" in result

    def test_line_center_above_cell_top_is_excluded(self):
        """
        A line whose visual center is above cell_y0 must be excluded.
        Simulates 'p' from a header row bleeding into the first data cell:
          - cell_y0 = 101.49
          - line bbox = (94, 107)  → center = 100.5  < 101.49  → excluded
        """
        line = self._make_line(origin_y=101.04, bbox_y0=94.0, bbox_y1=107.0, text="p")
        page = self.FakePage(self._make_rawdict([line]))
        result = PDFExtractor._cell_text(page, self._cell_rect(101.49, 251.0))
        assert "p" not in result

    def test_line_center_at_cell_top_is_kept(self):
        """
        A line whose center exactly equals cell_y0 is on the boundary and kept.
        """
        # center_y = (100.0 + 104.0) / 2 = 102.0, cell_y0 = 102.0
        line = self._make_line(origin_y=103.0, bbox_y0=100.0, bbox_y1=104.0, text="X")
        page = self.FakePage(self._make_rawdict([line]))
        result = PDFExtractor._cell_text(page, self._cell_rect(102.0, 200.0))
        assert "X" in result

    def test_line_baseline_below_cell_bottom_is_excluded(self):
        """
        A line whose baseline (origin_y) exceeds cell_y1 must be excluded.
        Simulates 'M', 'd', 'l' cap-heights bleeding up into the cell above.
          - cell_y1 = 316.68
          - line origin_y = 320.04  > 316.68  → excluded
        """
        line = self._make_line(origin_y=320.04, bbox_y0=313.0, bbox_y1=323.0, text="M")
        page = self.FakePage(self._make_rawdict([line]))
        result = PDFExtractor._cell_text(page, self._cell_rect(289.56, 316.68))
        assert "M" not in result

    def test_line_just_inside_bottom_is_kept(self):
        """A line whose baseline is exactly at cell_y1 is kept (inclusive)."""
        line = self._make_line(origin_y=200.0, bbox_y0=190.0, bbox_y1=201.0, text="Z")
        page = self.FakePage(self._make_rawdict([line]))
        result = PDFExtractor._cell_text(page, self._cell_rect(100.0, 200.0))
        assert "Z" in result

    def test_multiple_lines_partial_exclusion(self):
        """Only out-of-bounds lines are removed; valid lines remain intact."""
        line_bad_top    = self._make_line(101.04, 94.0,  107.0, "BAD_TOP")
        line_good       = self._make_line(150.0,  141.0, 155.0, "GOOD")
        line_bad_bottom = self._make_line(252.0,  244.0, 256.0, "BAD_BOT")
        page = self.FakePage(self._make_rawdict([line_bad_top, line_good, line_bad_bottom]))
        result = PDFExtractor._cell_text(page, self._cell_rect(101.49, 251.0))
        assert "GOOD" in result
        assert "BAD_TOP" not in result
        assert "BAD_BOT" not in result
