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
import re
import sys
from pathlib import Path

from tqdm import tqdm

from thai_utils import fix_thai_order

# Watermark detection: spans rotated more than this angle (degrees) are skipped.
# Content text is 0°; diagonal watermarks are typically 30°–60°.
_WATERMARK_ANGLE_THRESHOLD = 5.0

# Thai diacritics (sara i, mai tho, mai taikhu, etc.) are positioned ABOVE their
# base consonant baseline.  When a cell's top boundary cuts right through the
# diacritic zone, a hard clip excludes those glyph bboxes and the characters are
# lost entirely from the rawdict — leaving just bare consonants.
# Solution: expand the rawdict clip UPWARD by this many points before fetching,
# so diacritics of the first data line in a cell are always captured; the
# line-level boundary filter (center_y / origin_y) still excludes actual lines
# from the row above.  15 pt covers the tallest stacked diacritic in TH Sarabun
# at typical document font sizes (10–14 pt).
_DIACRITIC_CLIP_MARGIN = 15.0

# Bullet/list markers: lines starting with these get \n separation in Excel cells.
_BULLET_MARKERS: tuple[str, ...] = ("•", "◦", "○", "●", "▪", "▸", "►", "–", "—", "-")

# Numbered list pattern: matches "1. ", "2. ", "1.1 ", "2.3 ", "1.1.1 " etc.
# Requires a digit, at least one dot, optional trailing digits, then whitespace.
# Does NOT match bare numbers like "2566" (no dot) or mid-sentence numbers.
_NUMBERED_ITEM_RE = re.compile(r"^\d+\.\d*\s")


def _is_list_item(line: str) -> bool:
    """Return True if this line starts a new bullet or numbered list item."""
    return (
        any(line.startswith(m) for m in _BULLET_MARKERS)
        or bool(_NUMBERED_ITEM_RE.match(line))
    )


def _smart_sep(left: str, right: str) -> str:
    """
    Return the correct separator when concatenating two text fragments.

    Thai script has no word-boundary spaces; inserting a space between two Thai
    characters that were split by a PDF line-wrap produces unnatural output.
    When both the trailing char of *left* and the leading char of *right* are in
    the Thai Unicode block (U+0E00–U+0E7F), join with an empty string.
    Otherwise use a regular space.
    """
    if (
        left and right
        and "฀" <= left[-1] <= "๿"
        and "฀" <= right[0] <= "๿"
    ):
        return ""
    return " "


def _join_cell_lines(lines: list[str]) -> str:
    """
    Join text lines extracted from a single PDF cell into a cell string.

    Strategy:
    - Detect list items: lines starting with a bullet marker (•, –, etc.)
      OR a numbered prefix (1. / 2. / 1.1 / 2.3 / 1.1.1 …).
    - Each list item becomes a separate \\n-delimited group (→ Alt+Enter in Excel).
    - Lines that do NOT start a new item are treated as wrapped continuations
      of the preceding group and are joined using _smart_sep (no space between
      Thai characters, space otherwise).
    - If no list markers are detected at all, fall back to smart-joining all lines.

    Examples:
      Bullet list  → "• item A\\n• item B"
      Numbered list→ "intro sentence\\n1. first item\\n1.1 sub-item\\n2. second"
      Plain Thai   → "เพื่อกำหนดแนวทางการดำเนินการโครงการตั้งแต่..." (no inserted spaces)
      Plain Latin  → "word1 word2 word3" (space-joined)
    """
    if not lines:
        return ""

    if not any(_is_list_item(ln) for ln in lines):
        # Plain text — smart-join consecutive lines
        result = lines[0]
        for ln in lines[1:]:
            result += _smart_sep(result, ln) + ln
        return result

    groups: list[str] = []
    current: str = ""
    for ln in lines:
        if _is_list_item(ln):
            if current:
                groups.append(current.strip())
            current = ln
        else:
            # Wrapped continuation of the current group
            if current:
                current = current + _smart_sep(current, ln) + ln
            else:
                current = ln
    if current:
        groups.append(current.strip())

    return "\n".join(groups)


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

        # Merge continuation rows produced by cells that span page boundaries.
        # find_tables() splits such cells into a normal row on page N and a
        # "continuation row" on page N+1 with all identifying columns empty.
        rows = self._merge_continuation_rows(rows)

        if self.skip_rows and rows:
            self.log.info("Skipping first %d row(s) as requested.", self.skip_rows)
            rows = rows[self.skip_rows:]

        return rows

    @staticmethod
    def _merge_continuation_rows(rows: list[list[str]]) -> list[list[str]]:
        """
        Merge cross-page continuation rows into their preceding row.

        When a table cell spans two pages, find_tables() returns:
          - Page N  : a normal row with all columns populated
          - Page N+1: a "continuation row" whose first two identifying columns
                      are empty but whose value columns carry the overflow text

        Detection heuristic: if col[0] and col[1] are both empty and at least
        one other column has content, treat the row as a continuation.
        The overflow content is appended to the matching column of the
        preceding row, separated by \\n so bullets stay on distinct lines.
        """
        if not rows:
            return rows

        merged: list[list[str]] = []
        for row in rows:
            if not row:
                continue
            is_continuation = (
                merged                            # there is a preceding row
                and len(row) >= 2
                and row[0] == ""                  # key col 1 (e.g. row number) empty
                and row[1] == ""                  # key col 2 (e.g. name) empty
                and any(c for c in row)           # but some column has content
            )
            if is_continuation:
                prev = merged[-1]
                # Extend prev row width if needed
                while len(prev) < len(row):
                    prev.append("")
                for col_idx, cell in enumerate(row):
                    if cell:
                        if prev[col_idx]:
                            prev[col_idx] = prev[col_idx] + "\n" + cell
                        else:
                            prev[col_idx] = cell
            else:
                merged.append(list(row))

        return merged

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
            tqdm(doc.pages(start_0, end_0), desc="Extracting", unit="page", total=page_total,
                 disable=sys.stdout is None),
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
                # Recover hyperlink columns missed by find_tables() when URL
                # text overflows the table boundary (stored as PDF annotations)
                table_rows = self._enrich_rows_with_links(page, table, table_rows)
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

        Boundary filter (prevents cross-row glyph bleed):
        - PyMuPDF's clip= uses glyph bounding-box overlap, so glyphs from the
          adjacent row can appear if their visual extent crosses the cell border.
        - Two conditions must BOTH hold to keep a line:
          1. line_center_y >= cell_y0  — excludes lines whose visual center is
             above the cell top (e.g. descender of the last header word bleeds
             into the first data row, or a line sits just above the boundary).
          2. line_origin_y <= cell_y1  — excludes lines whose text baseline
             falls below the cell bottom (glyphs from the next row whose cap
             height overlaps the current cell).
        """
        # Cell bounds — support fitz.Rect (attrs), plain tuple, or any rect-like.
        def _f(obj, attr: str, idx: int) -> float:
            if hasattr(obj, attr):
                return float(getattr(obj, attr))
            try:
                return float(obj[idx])
            except (TypeError, IndexError):
                return 0.0

        cell_x0: float = _f(cell_rect, "x0", 0)
        cell_y0: float = _f(cell_rect, "y0", 1)
        cell_x1: float = _f(cell_rect, "x1", 2)
        cell_y1: float = _f(cell_rect, "y1", 3)

        # Expand the rawdict clip upward so Thai diacritics (sara i, mai tho,
        # etc.) positioned ABOVE the cell's top boundary are still captured.
        # Without this, a hard clip at cell_y0 truncates diacritic glyph bboxes
        # that sit in the zone above the baseline, stripping them from the result
        # and leaving bare consonants (e.g. "เงนได" instead of "เงินได้").
        # The line-level boundary filter below still discards entire lines from
        # the row above, so accuracy is preserved.
        try:
            import fitz as _fitz
            expanded_clip = _fitz.Rect(cell_x0, cell_y0 - _DIACRITIC_CLIP_MARGIN,
                                       cell_x1, cell_y1)
        except Exception:
            expanded_clip = cell_rect  # fall back to original clip on any error

        data = page.get_text("rawdict", clip=expanded_clip, sort=True)
        lines_out: list[str] = []

        for block in data.get("blocks", []):
            if block.get("type") != 0:          # 0 = text block
                continue
            for line in block.get("lines", []):
                dx, dy = line.get("dir", (1.0, 0.0))
                angle  = abs(math.degrees(math.atan2(-dy, dx)))
                if angle > _WATERMARK_ANGLE_THRESHOLD:
                    continue                     # ← skip watermark

                # ── boundary filter ──────────────────────────────────────────
                lbbox    = line.get("bbox", [0.0, 0.0, 0.0, 0.0])
                center_y = (lbbox[1] + lbbox[3]) / 2.0

                # Baseline (origin y) of the first character in the line
                all_chars = [
                    ch
                    for span in line.get("spans", [])
                    for ch in span.get("chars", [])
                ]
                if not all_chars:
                    continue
                origin_y = all_chars[0].get("origin", (0.0, 0.0))[1]

                if center_y < cell_y0 or origin_y > cell_y1:
                    continue                     # ← outside cell boundaries
                # ─────────────────────────────────────────────────────────────

                span_texts: list[str] = []
                for span in line.get("spans", []):
                    span_texts.append(
                        "".join(ch.get("c", "") for ch in span.get("chars", []))
                    )
                line_text = "".join(span_texts).strip()
                if line_text:
                    lines_out.append(line_text)

        return _join_cell_lines(lines_out)

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

    @staticmethod
    def _enrich_rows_with_links(
        page: "fitz.Page",
        table: "fitz.table.Table",
        rows: list[list[str]],
    ) -> list[list[str]]:
        """
        Append hyperlink URIs that fall within each table row but are NOT
        captured in any existing cell text.

        Root cause this solves:
          find_tables() detects columns from visible borders/lines.  When a
          column's content is a long URL stored as a PDF hyperlink annotation,
          its text overflows the page width so find_tables() never sees a
          column separator — the column is silently dropped.
          page.get_links() always exposes those annotations regardless of
          overflow, so we use it as a supplementary source.

        Algorithm:
          1. Collect all external-URL links on the page.
          2. For each table row compute its Y extent from the cell rects.
          3. Find links whose rect overlaps that Y extent AND whose URI is
             not already present in any cell of that row.
          4. Append the URI(s) as a new cell at the end of the row.
          5. For the first row (header), try to find extra header text in
             the area beyond the table's right edge at the same Y position.
        """
        try:
            import fitz  # already imported wherever caller runs, but keep local
        except ImportError:
            return rows

        url_links = [
            lnk for lnk in page.get_links()
            if lnk.get("kind") == 2 and lnk.get("uri")
        ]
        if not url_links or not rows:
            return rows

        # --- Y-extent per row ---
        # row_obj.cells yields fitz.Rect objects or (x0,y0,x1,y1) tuples
        # depending on PyMuPDF version — normalise to plain floats.
        def _cell_y(r: "fitz.Rect | tuple") -> tuple[float, float]:
            if hasattr(r, "y0"):
                return float(r.y0), float(r.y1)
            return float(r[1]), float(r[3])  # tuple: (x0,y0,x1,y1)

        def _cell_x1(r: "fitz.Rect | tuple") -> float:
            if hasattr(r, "x1"):
                return float(r.x1)
            return float(r[2])

        row_y: list[tuple[float, float] | None] = []
        for row_obj in table.rows:
            rects = [r for r in row_obj.cells if r is not None]
            if rects:
                ys = [_cell_y(r) for r in rects]
                row_y.append((min(y0 for y0, _ in ys), max(y1 for _, y1 in ys)))
            else:
                row_y.append(None)

        # --- Collect extra URIs per row ---
        extra: list[str] = []
        any_found = False
        for idx, yrange in enumerate(row_y):
            if idx >= len(rows) or yrange is None:
                extra.append("")
                continue
            y0, y1 = yrange
            existing_text = " ".join(rows[idx])
            seen: set[str] = set()
            uris: list[str] = []
            for lnk in url_links:
                lr = lnk.get("from")
                if lr is None:
                    continue
                uri = lnk["uri"]
                if uri in seen:
                    continue
                if lr.y0 < y1 and lr.y1 > y0 and uri not in existing_text:
                    seen.add(uri)
                    uris.append(uri)
            cell_val = " | ".join(uris) if uris else ""
            if cell_val:
                any_found = True
            extra.append(cell_val)

        if not any_found:
            return rows

        # --- Attempt to recover header text for the extra column ---
        # Look for text beyond the table's right edge at the header row Y.
        if row_y and row_y[0] is not None and not extra[0]:
            try:
                table_max_x = max(
                    _cell_x1(r)
                    for row_obj in table.rows
                    for r in row_obj.cells
                    if r is not None
                )
                y0_hdr, y1_hdr = row_y[0]
                clip = fitz.Rect(table_max_x, y0_hdr - 5, page.rect.width, y1_hdr + 5)
                extra_header = page.get_textbox(clip).strip()
                if extra_header:
                    extra[0] = extra_header
            except Exception:
                pass  # silently skip — header name is cosmetic

        return [row + [e] for row, e in zip(rows, extra)]

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
            for i, page in enumerate(tqdm(pages, desc="Extracting", unit="page",
                                          disable=sys.stdout is None), start=1):
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
