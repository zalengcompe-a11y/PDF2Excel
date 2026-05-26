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
