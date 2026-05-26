"""
extractor.py — PDF table extraction with dual-engine support.

Engine "pymupdf"  (default) — uses MuPDF via PyMuPDF; correct Unicode handling
                               for Thai and other non-Latin scripts.
Engine "pdfplumber"          — original engine; good for Latin PDFs with clear
                               grid lines, but may mis-encode Thai characters.
"""

import io
import logging
import math
from pathlib import Path

from tqdm import tqdm

from thai_utils import fix_thai_order

# Watermark detection: spans rotated more than this angle (degrees) are skipped.
# Content text is 0°; diagonal watermarks are typically 30°–60°.
_WATERMARK_ANGLE_THRESHOLD = 5.0


# pdfplumber strategies, ordered from most precise to most lenient
_PLUMBER_STRATEGIES = [
    {"vertical_strategy": "lines",        "horizontal_strategy": "lines"},
    {"vertical_strategy": "lines_strict", "horizontal_strategy": "lines_strict"},
    {"vertical_strategy": "text",         "horizontal_strategy": "text"},
    {"vertical_strategy": "lines",        "horizontal_strategy": "text"},
]


class PDFExtractor:
    """
    Extracts table rows from a native (text-selectable) PDF.

    Parameters
    ----------
    engine : "pymupdf" | "pdfplumber"
        "pymupdf" (default) — recommended for Thai / non-Latin PDFs.
        "pdfplumber"        — fallback for Latin PDFs with clear grid lines.
    start_page : int | None
        First page to extract (1-based, inclusive). Default: first page.
    end_page : int | None
        Last page to extract (1-based, inclusive). Default: last page.
    skip_rows : int
        Drop the first N rows of the final output (e.g. 1 = skip the header).
    skip_duplicate_headers : bool
        Remove repeated header rows that appear on every page (default True).
    """

    def __init__(
        self,
        pdf_path: str | Path,
        engine: str = "pymupdf",
        start_page: int | None = None,
        end_page: int | None = None,
        skip_rows: int = 0,
        skip_duplicate_headers: bool = True,
        on_progress: "callable[[int, int], None] | None" = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.pdf_path = Path(pdf_path)
        self.engine = engine.lower()
        self.start_page = start_page        # 1-based
        self.end_page = end_page            # 1-based, inclusive
        self.skip_rows = max(0, skip_rows)
        self.skip_duplicate_headers = skip_duplicate_headers
        self.on_progress = on_progress      # fn(current_page, total_pages)
        self.log = logger or logging.getLogger(__name__)
        self._header: list[str] | None = None

        if self.engine not in ("pymupdf", "pdfplumber"):
            raise ValueError(f"Unknown engine '{engine}'. Choose 'pymupdf' or 'pdfplumber'.")

    # ── public ───────────────────────────────────────────────────────────────

    def extract(self) -> list[list[str]]:
        """Return all rows from the selected page range as a flat list."""
        if self.engine == "pymupdf":
            rows = self._extract_with_pymupdf()
        else:
            rows = self._extract_with_pdfplumber()

        if self.skip_rows and rows:
            self.log.info("Skipping first %d row(s) as requested.", self.skip_rows)
            rows = rows[self.skip_rows:]

        return rows

    # ── PyMuPDF engine ───────────────────────────────────────────────────────

    def _extract_with_pymupdf(self) -> list[list[str]]:
        try:
            import fitz  # pymupdf
        except ImportError:
            self.log.warning(
                "pymupdf not installed — falling back to pdfplumber. "
                "Run: pip install pymupdf"
            )
            return self._extract_with_pdfplumber()

        all_rows: list[list[str]] = []
        failed_pages: list[int] = []

        # Read via pathlib so Windows handles Thai filenames correctly
        doc = fitz.open(stream=self.pdf_path.read_bytes(), filetype="pdf")
        total = doc.page_count

        start_0 = (self.start_page - 1) if self.start_page else 0
        end_0   = self.end_page if self.end_page else total   # exclusive upper bound for fitz

        start_0 = max(0, min(start_0, total - 1))
        end_0   = max(start_0 + 1, min(end_0, total))

        self.log.info(
            "Engine: pymupdf  |  Pages %d–%d of %d.",
            start_0 + 1, end_0, total,
        )

        page_total = end_0 - start_0
        for i, page in enumerate(
            tqdm(doc.pages(start_0, end_0), desc="Extracting", unit="page", total=page_total),
            start=1,
        ):
            rows = self._pymupdf_page(page)
            if rows:
                all_rows.extend(rows)
            else:
                failed_pages.append(page.number + 1)
            if self.on_progress:
                self.on_progress(i, page_total)

        doc.close()
        self._report_failures(failed_pages)
        self.log.info("Total rows extracted: %d", len(all_rows))
        return all_rows

    def _pymupdf_page(self, page) -> list[list[str]]:
        finder = page.find_tables()

        if finder.tables:
            rows = []
            for table in finder.tables:
                table_rows = self._extract_table_sorted(page, table)
                for raw_row in table_rows:
                    cleaned = self._clean_row(raw_row)
                    if not any(cleaned):
                        continue
                    if self._should_skip_header(cleaned):
                        continue
                    self._register_header_if_first(cleaned)
                    rows.append(cleaned)

            if rows:
                self.log.debug(
                    "Page %d: %d rows via pymupdf (position-sorted).",
                    page.number + 1, len(rows),
                )
                return rows

        return self._pymupdf_text_fallback(page)

    @staticmethod
    def _cell_text(page, cell_rect: "fitz.Rect") -> str:
        """
        Extract text from a single table cell, filtering out watermark spans.

        Strategy:
        - Use rawdict mode to access per-span rotation (direction vector).
        - Skip any span where |rotation angle| > _WATERMARK_ANGLE_THRESHOLD.
          Content text is always 0°; diagonal watermarks are typically 30°–60°.
        - Assemble text from chars (not span['text']) so PUA/custom-encoded
          Thai characters are included as decoded by PyMuPDF.
        - sort=True orders characters by X position so Thai leading vowels
          (visually left of their consonant) come first → correct Unicode order.
        """
        data = page.get_text("rawdict", clip=cell_rect, sort=True)
        lines_out: list[str] = []

        for block in data.get("blocks", []):
            if block.get("type") != 0:          # 0 = text block
                continue
            for line in block.get("lines", []):
                dx, dy = line.get("dir", (1.0, 0.0))
                angle  = abs(math.degrees(math.atan2(-dy, dx)))
                if angle > _WATERMARK_ANGLE_THRESHOLD:
                    continue                     # ← skip watermark
                span_texts: list[str] = []
                for span in line.get("spans", []):
                    span_texts.append(
                        "".join(ch.get("c", "") for ch in span.get("chars", []))
                    )
                line_text = "".join(span_texts).strip()
                if line_text:
                    lines_out.append(line_text)

        return " ".join(lines_out)

    @staticmethod
    def _extract_table_sorted(page, table) -> list[list[str]]:
        """
        Extract table row/cell text:
        - Position-sorted (sort=True) for correct Thai leading-vowel order.
        - Watermark-filtered (rotation > threshold → skipped).
        Falls back to table.extract() if the rows/cells API is unavailable.
        """
        try:
            result = []
            for row in table.rows:
                row_data = []
                for cell_rect in row.cells:
                    if cell_rect is None:
                        row_data.append("")
                    else:
                        row_data.append(PDFExtractor._cell_text(page, cell_rect))
                result.append(row_data)
            return result
        except AttributeError:
            # Older PyMuPDF: fall back to default table.extract()
            return table.extract()

    def _pymupdf_text_fallback(self, page) -> list[list[str]]:
        """Text fallback: assemble from rawdict, filtering rotated watermark spans."""
        data = page.get_text("rawdict", sort=True)
        lines_out: list[str] = []

        for block in data.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                dx, dy = line.get("dir", (1.0, 0.0))
                angle  = abs(math.degrees(math.atan2(-dy, dx)))
                if angle > _WATERMARK_ANGLE_THRESHOLD:
                    continue
                span_texts = [
                    "".join(ch.get("c", "") for ch in span.get("chars", []))
                    for span in line.get("spans", [])
                ]
                line_text = "".join(span_texts).strip()
                if line_text:
                    lines_out.append(line_text)

        if not lines_out:
            self.log.warning("Page %d: no content found.", page.number + 1)
            return []

        self.log.warning(
            "Page %d: no table detected — using text fallback.", page.number + 1
        )
        return [[line] for line in lines_out]

    # ── pdfplumber engine ────────────────────────────────────────────────────

    def _extract_with_pdfplumber(self) -> list[list[str]]:
        import pdfplumber

        all_rows: list[list[str]] = []
        failed_pages: list[int] = []

        # Read via pathlib so Windows handles Thai filenames correctly
        raw_bytes = io.BytesIO(self.pdf_path.read_bytes())

        with pdfplumber.open(raw_bytes) as pdf:
            total = len(pdf.pages)

            start_0 = (self.start_page - 1) if self.start_page else 0
            end_0   = self.end_page if self.end_page else total

            start_0 = max(0, min(start_0, total - 1))
            end_0   = max(start_0 + 1, min(end_0, total))

            pages = pdf.pages[start_0:end_0]
            self.log.info(
                "Engine: pdfplumber  |  Pages %d–%d of %d.",
                start_0 + 1, end_0, total,
            )

            page_total = len(pages)
            for i, page in enumerate(tqdm(pages, desc="Extracting", unit="page"), start=1):
                rows = self._pdfplumber_page(page)
                if rows:
                    all_rows.extend(rows)
                else:
                    failed_pages.append(page.page_number)
                if self.on_progress:
                    self.on_progress(i, page_total)

        self._report_failures(failed_pages)
        self.log.info("Total rows extracted: %d", len(all_rows))
        return all_rows

    def _pdfplumber_page(self, page) -> list[list[str]]:
        for strategy in _PLUMBER_STRATEGIES:
            tables = page.extract_tables(table_settings=strategy)
            if not tables:
                continue

            rows = []
            for table in tables:
                for raw_row in table:
                    cleaned = self._clean_row(raw_row)
                    if not any(cleaned):
                        continue
                    if self._should_skip_header(cleaned):
                        continue
                    self._register_header_if_first(cleaned)
                    rows.append(cleaned)

            if rows:
                self.log.debug(
                    "Page %d: %d rows via '%s' strategy.",
                    page.page_number, len(rows), strategy["vertical_strategy"],
                )
                return rows

        return self._pdfplumber_text_fallback(page)

    def _pdfplumber_text_fallback(self, page) -> list[list[str]]:
        text = page.extract_text()
        if not text:
            self.log.warning("Page %d: no content found.", page.page_number)
            return []

        self.log.warning(
            "Page %d: no table detected — using text fallback.", page.page_number
        )
        return [[line] for line in text.splitlines() if line.strip()]

    # ── shared helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _clean_row(raw: list) -> list[str]:
        """Clean + fix Thai character ordering for every cell in a row."""
        return [
            fix_thai_order(str(cell).strip()) if cell is not None else ""
            for cell in raw
        ]

    def _register_header_if_first(self, row: list[str]) -> None:
        if self._header is None:
            self._header = row

    def _should_skip_header(self, row: list[str]) -> bool:
        return (
            self.skip_duplicate_headers
            and self._header is not None
            and row == self._header
        )

    def _report_failures(self, failed_pages: list[int]) -> None:
        if failed_pages:
            self.log.warning(
                "%d page(s) yielded no data: %s", len(failed_pages), failed_pages
            )
