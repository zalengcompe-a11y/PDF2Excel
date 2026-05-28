#!/usr/bin/env python3
"""
pdf2excel.py — Robust PDF-to-Office converter (Excel or Word).

Usage:
    python pdf2excel.py input.pdf
    python pdf2excel.py input.pdf output.xlsx
    python pdf2excel.py input.pdf output.docx  --format docx
    python pdf2excel.py input.pdf --format docx --verbose
    python pdf2excel.py input.pdf output.xlsx --sheet "Sales Data"
    python pdf2excel.py input.pdf output.xlsx --start-page 5 --end-page 50
    python pdf2excel.py input.pdf output.xlsx --skip-rows 1
    python pdf2excel.py input.pdf output.xlsx --engine pdfplumber

Dependencies:
    pip install -r requirements.txt
"""

import argparse
import logging
import sys
from pathlib import Path

from extractor import PDFExtractor
from formatter import ExcelFormatter
from formatter_word import WordFormatter


# ── Logging ──────────────────────────────────────────────────────────────────

def _setup_logging(verbose: bool) -> logging.Logger:
    logging.basicConfig(
        format="%(asctime)s  [%(levelname)-8s]  %(message)s",
        datefmt="%H:%M:%S",
        level=logging.DEBUG if verbose else logging.INFO,
        stream=sys.stderr,
    )
    return logging.getLogger("pdf2excel")


# ── CLI ───────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pdf2excel",
        description="Convert PDF tables to Excel (.xlsx) or Word (.docx).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pdf2excel.py report.pdf                           # saves as report.xlsx
  python pdf2excel.py report.pdf out.xlsx                  # saves as out.xlsx
  python pdf2excel.py report.pdf --format docx             # saves as report.docx
  python pdf2excel.py report.pdf out.docx --format docx    # named output
  python pdf2excel.py report.pdf --sheet "Q1 Data"
  python pdf2excel.py report.pdf --start-page 5 --end-page 100
  python pdf2excel.py report.pdf --skip-rows 1
  python pdf2excel.py report.pdf --engine pdfplumber --verbose
        """,
    )
    p.add_argument("input",  help="Path to the input PDF file (Thai filenames supported).")
    p.add_argument(
        "output",
        nargs="?",
        default=None,
        help="Output path (optional). Defaults to <pdf-name>.xlsx/.docx in the same folder.",
    )

    # ── Page range ────────────────────────────────────────────────────────────
    pg = p.add_argument_group("page range")
    pg.add_argument(
        "--start-page", "-sp",
        type=int,
        default=None,
        metavar="N",
        help="First page to extract, 1-based (default: 1).",
    )
    pg.add_argument(
        "--end-page", "-ep",
        type=int,
        default=None,
        metavar="N",
        help="Last page to extract, 1-based inclusive (default: last page).",
    )

    # ── Output options ────────────────────────────────────────────────────────
    out = p.add_argument_group("output options")
    out.add_argument(
        "--format", "-f",
        default="xlsx",
        choices=["xlsx", "docx"],
        help="Output format: xlsx (default) or docx.",
    )
    out.add_argument(
        "--sheet", "-s",
        default="Data",
        metavar="NAME",
        help="Worksheet name for Excel output (default: Data). Ignored for --format docx.",
    )
    out.add_argument(
        "--skip-rows",
        type=int,
        default=0,
        metavar="N",
        help="Drop the first N rows of output, e.g. --skip-rows 1 removes the header row.",
    )

    # ── Engine / behaviour ────────────────────────────────────────────────────
    eng = p.add_argument_group("engine / behaviour")
    eng.add_argument(
        "--engine", "-e",
        default="pymupdf",
        choices=["pymupdf", "pdfplumber"],
        help="Extraction engine (default: pymupdf). pymupdf handles Thai correctly.",
    )
    eng.add_argument(
        "--no-skip-headers",
        action="store_true",
        help="Keep repeated header rows instead of removing duplicates.",
    )
    eng.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug-level logging.",
    )
    return p


# ── Validation helpers ────────────────────────────────────────────────────────

def _validate_page_range(args, log: logging.Logger) -> None:
    if args.start_page is not None and args.start_page < 1:
        log.error("--start-page must be >= 1 (got %d).", args.start_page)
        sys.exit(1)
    if args.end_page is not None and args.end_page < 1:
        log.error("--end-page must be >= 1 (got %d).", args.end_page)
        sys.exit(1)
    if (args.start_page and args.end_page
            and args.start_page > args.end_page):
        log.error(
            "--start-page (%d) must be <= --end-page (%d).",
            args.start_page, args.end_page,
        )
        sys.exit(1)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    args = _build_parser().parse_args()
    log  = _setup_logging(args.verbose)

    input_path = Path(args.input)

    # Auto-name: <pdf-stem>.<ext> next to the PDF if user didn't supply output
    out_suffix = ".docx" if args.format == "docx" else ".xlsx"
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_suffix(out_suffix)

    # ── Validate ──────────────────────────────────────────────────────────────
    if not input_path.exists():
        log.error("Input file not found: %s", input_path)
        sys.exit(1)

    if input_path.suffix.lower() != ".pdf":
        log.error("Input must be a .pdf file (got: %s).", input_path.suffix)
        sys.exit(1)

    expected_ext = out_suffix
    if output_path.suffix.lower() not in (expected_ext, ""):
        log.warning(
            "Output extension '%s' doesn't match --format %s (expected %s).",
            output_path.suffix, args.format, expected_ext,
        )

    _validate_page_range(args, log)

    # ── Extract ───────────────────────────────────────────────────────────────
    log.info("Input  : %s", input_path.resolve())
    log.info("Output : %s", output_path.resolve())

    extractor = PDFExtractor(
        pdf_path=input_path,
        engine=args.engine,
        start_page=args.start_page,
        end_page=args.end_page,
        skip_rows=args.skip_rows,
        skip_duplicate_headers=not args.no_skip_headers,
        logger=log,
    )
    rows = extractor.extract()

    if not rows:
        log.error(
            "No data could be extracted. "
            "Ensure the PDF contains selectable text (not a scanned image)."
        )
        sys.exit(1)

    # ── Write output ─────────────────────────────────────────────────────────
    if args.format == "docx":
        formatter = WordFormatter(logger=log)
    else:
        formatter = ExcelFormatter(sheet_name=args.sheet, logger=log)
    formatter.write(rows)
    formatter.save(output_path)

    fmt_label = "Word (.docx)" if args.format == "docx" else "Excel (.xlsx)"
    print(f"\n  Format       : {fmt_label}")
    print(f"  Rows written : {len(rows)}")
    print(f"  Columns      : {len(rows[0]) if rows else 0}")
    print(f"  Pages        : {args.start_page or 1} – {args.end_page or 'last'}")
    print(f"  Output       : {output_path.resolve()}\n")


if __name__ == "__main__":
    main()
