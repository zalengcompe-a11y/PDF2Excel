"""
gui.py — tkinter frontend for PDF to Excel Converter.
Run directly:  python gui.py
Or via:        launch.bat  (handles Python install + dependencies first)
"""

import queue
import subprocess
import sys
import threading
import traceback
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


# ── Theme helpers ─────────────────────────────────────────────────────────────

_BG        = "#F5F5F5"
_ACCENT    = "#2E75B6"
_BTN_FG    = "#FFFFFF"
_DONE_CLR  = "#217346"   # Excel green
_ERR_CLR   = "#C00000"

_THAI_FONTS = ["Leelawadee UI", "Leelawadee", "Tahoma", "TH Sarabun New"]

def _thai_font(size: int = 10, bold: bool = False) -> tuple:
    """Return the first available Thai-capable font on this system."""
    import tkinter.font as tkfont
    available = tkfont.families()
    for name in _THAI_FONTS:
        if name in available:
            weight = "bold" if bold else "normal"
            return (name, size, weight)
    return ("TkDefaultFont", size, "bold" if bold else "normal")


# ── Main window ───────────────────────────────────────────────────────────────

class App(tk.Tk):

    def __init__(self) -> None:
        super().__init__()
        self.title("PDF to Excel Converter")
        self.resizable(False, False)
        self.configure(bg=_BG)

        self._q: queue.Queue = queue.Queue()
        self._running = False
        self._output_path: str | None = None

        self._apply_styles()
        self._build_ui()
        self._poll()

    # ── Styles ────────────────────────────────────────────────────────────────

    def _apply_styles(self) -> None:
        s = ttk.Style(self)
        s.theme_use("clam")
        font_n = _thai_font(10)
        font_b = _thai_font(10, bold=True)
        font_h = _thai_font(13, bold=True)

        s.configure(".",            background=_BG, font=font_n)
        s.configure("TLabel",       background=_BG, font=font_n)
        s.configure("TFrame",       background=_BG)
        s.configure("TLabelframe",  background=_BG, font=font_b)
        s.configure("TLabelframe.Label", background=_BG, font=font_b, foreground=_ACCENT)
        s.configure("TEntry",       font=font_n, fieldbackground="white")
        s.configure("TSpinbox",     font=font_n, fieldbackground="white")
        s.configure("Header.TLabel", font=font_h, foreground=_ACCENT, background=_BG)

        # Primary convert button
        s.configure("Primary.TButton",
                    font=_thai_font(11, bold=True),
                    background=_ACCENT,
                    foreground=_BTN_FG,
                    borderwidth=0,
                    focusthickness=0,
                    padding=(0, 8))
        s.map("Primary.TButton",
              background=[("active", "#1A5C9A"), ("disabled", "#AAAAAA")],
              foreground=[("disabled", "#DDDDDD")])

        # Open-file button
        s.configure("Open.TButton",
                    font=_thai_font(10, bold=True),
                    background=_DONE_CLR,
                    foreground=_BTN_FG,
                    borderwidth=0,
                    padding=(0, 6))
        s.map("Open.TButton", background=[("active", "#145A32")])

        s.configure("TProgressbar",
                    troughcolor="#DDDDDD",
                    background=_ACCENT,
                    thickness=14)

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        pad = {"padx": 18, "pady": 6}

        # ── Header ────────────────────────────────────────────────────────────
        hdr = ttk.Frame(self)
        hdr.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 4))
        ttk.Label(hdr, text="PDF to Excel Converter", style="Header.TLabel").pack(side="left")

        # ── File picker ───────────────────────────────────────────────────────
        f_file = ttk.LabelFrame(self, text=" PDF File ")
        f_file.grid(row=1, column=0, sticky="ew", **pad)
        f_file.columnconfigure(0, weight=1)

        self._file_var = tk.StringVar()
        ttk.Entry(f_file, textvariable=self._file_var, state="readonly", width=52) \
            .grid(row=0, column=0, padx=(8, 6), pady=8, sticky="ew")
        ttk.Button(f_file, text="Browse...", command=self._browse) \
            .grid(row=0, column=1, padx=(0, 8), pady=8)

        # ── Options ───────────────────────────────────────────────────────────
        f_opt = ttk.LabelFrame(self, text=" Options ")
        f_opt.grid(row=2, column=0, sticky="ew", **pad)

        # Row 0 — page range
        ttk.Label(f_opt, text="Start page:").grid(row=0, column=0, sticky="w", padx=(8,4), pady=(8,4))
        self._start_var = tk.StringVar(value="1")
        ttk.Spinbox(f_opt, from_=1, to=9999, textvariable=self._start_var, width=7) \
            .grid(row=0, column=1, sticky="w", padx=(0,16), pady=(8,4))

        ttk.Label(f_opt, text="End page:").grid(row=0, column=2, sticky="w", padx=(0,4))
        self._end_var = tk.StringVar(value="")
        ttk.Entry(f_opt, textvariable=self._end_var, width=7) \
            .grid(row=0, column=3, sticky="w", padx=(0,8))
        ttk.Label(f_opt, text="(blank = last page)", foreground="#888888") \
            .grid(row=0, column=4, sticky="w", padx=(0, 8))

        # Row 1 — skip rows + sheet name
        ttk.Label(f_opt, text="Skip rows:").grid(row=1, column=0, sticky="w", padx=(8,4), pady=(4,8))
        self._skip_var = tk.StringVar(value="0")
        ttk.Spinbox(f_opt, from_=0, to=99, textvariable=self._skip_var, width=7) \
            .grid(row=1, column=1, sticky="w", padx=(0,16), pady=(4,8))

        ttk.Label(f_opt, text="Sheet name:").grid(row=1, column=2, sticky="w", padx=(0,4))
        self._sheet_var = tk.StringVar(value="Data")
        ttk.Entry(f_opt, textvariable=self._sheet_var, width=18) \
            .grid(row=1, column=3, columnspan=2, sticky="w", pady=(4,8))

        # ── Convert button ────────────────────────────────────────────────────
        self._btn = ttk.Button(
            self, text="Convert to Excel",
            style="Primary.TButton",
            command=self._start_conversion,
        )
        self._btn.grid(row=3, column=0, sticky="ew", padx=18, pady=(10, 4), ipady=2)

        # ── Progress bar ──────────────────────────────────────────────────────
        self._progress = ttk.Progressbar(self, orient="horizontal", mode="determinate")
        self._progress.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 2))

        # ── Status label ──────────────────────────────────────────────────────
        self._status_var = tk.StringVar(value="Ready — click Browse to select a PDF file")
        self._status_lbl = ttk.Label(
            self, textvariable=self._status_var,
            wraplength=560, anchor="w",
        )
        self._status_lbl.grid(row=5, column=0, sticky="ew", padx=20, pady=(2, 4))

        # ── Open output button (hidden until conversion succeeds) ─────────────
        self._open_btn = ttk.Button(
            self, text="Open Excel File",
            style="Open.TButton",
            command=self._open_output,
        )

        self.columnconfigure(0, weight=1)
        self.update_idletasks()
        # Centre on screen
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")

    # ── Event handlers ────────────────────────────────────────────────────────

    def _browse(self) -> None:
        path = filedialog.askopenfilename(
            title="Select PDF file",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
        )
        if path:
            self._file_var.set(path)
            self._set_status(f"Selected: {Path(path).name}", color="#333333")
            self._open_btn.grid_remove()
            self._progress["value"] = 0

    def _start_conversion(self) -> None:
        if not self._file_var.get():
            messagebox.showwarning("No file selected", "Please select a PDF file first.")
            return
        if self._running:
            return

        # Validate numeric inputs
        try:
            start = int(self._start_var.get() or 1)
            end_str = self._end_var.get().strip()
            end = int(end_str) if end_str else None
            skip = int(self._skip_var.get() or 0)
        except ValueError:
            messagebox.showerror("Invalid input", "Start page, end page and skip rows must be numbers.")
            return

        if end and start > end:
            messagebox.showerror("Invalid range", f"Start page ({start}) cannot be greater than end page ({end}).")
            return

        self._running = True
        self._open_btn.grid_remove()
        self._progress.configure(mode="indeterminate")
        self._progress.start(10)
        self._btn.state(["disabled"])
        self._set_status("Starting conversion...", color=_ACCENT)

        thread = threading.Thread(
            target=self._run_conversion,
            args=(Path(self._file_var.get()), start, end, skip,
                  self._sheet_var.get() or "Data"),
            daemon=True,
        )
        thread.start()

    def _run_conversion(self, input_path: Path, start: int, end, skip: int, sheet: str) -> None:
        """Runs in background thread — communicates via self._q."""
        try:
            from extractor import PDFExtractor
            from formatter import ExcelFormatter

            output_path = input_path.with_suffix(".xlsx")

            def on_progress(current: int, total: int) -> None:
                self._q.put(("progress", current, total))

            extractor = PDFExtractor(
                pdf_path=input_path,
                start_page=start,
                end_page=end,
                skip_rows=skip,
                skip_duplicate_headers=True,
                on_progress=on_progress,
            )
            rows = extractor.extract()

            if not rows:
                self._q.put(("error", "No data extracted.\nPlease check that the PDF contains selectable (non-scanned) text."))
                return

            self._q.put(("status", f"Writing {len(rows):,} rows to Excel..."))
            formatter = ExcelFormatter(sheet_name=sheet)
            formatter.write(rows)
            formatter.save(output_path)

            self._q.put(("done", str(output_path), len(rows)))

        except Exception as exc:
            self._q.put(("error", traceback.format_exc()))

    # ── Queue polling (thread-safe GUI updates) ───────────────────────────────

    def _poll(self) -> None:
        try:
            while True:
                msg = self._q.get_nowait()
                kind = msg[0]

                if kind == "progress":
                    _, current, total = msg
                    self._progress.stop()
                    self._progress.configure(mode="determinate", maximum=total, value=current)
                    self._set_status(f"Processing page {current} / {total}...", color=_ACCENT)

                elif kind == "status":
                    self._set_status(msg[1], color=_ACCENT)

                elif kind == "done":
                    _, out_path, row_count = msg
                    self._output_path = out_path
                    self._progress.stop()
                    self._progress.configure(mode="determinate", maximum=100, value=100)
                    self._btn.state(["!disabled"])
                    self._running = False
                    name = Path(out_path).name
                    self._set_status(
                        f"Done!  {row_count:,} rows saved to  {name}",
                        color=_DONE_CLR,
                    )
                    self._open_btn.grid(row=6, column=0, sticky="ew",
                                        padx=18, pady=(0, 16), ipady=2)

                elif kind == "error":
                    self._progress.stop()
                    self._progress.configure(mode="determinate", maximum=100, value=0)
                    self._btn.state(["!disabled"])
                    self._running = False
                    self._set_status("Conversion failed — see error dialog.", color=_ERR_CLR)
                    messagebox.showerror("Error", msg[1])

        except queue.Empty:
            pass

        self.after(80, self._poll)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_status(self, text: str, color: str = "#333333") -> None:
        self._status_var.set(text)
        self._status_lbl.configure(foreground=color)

    def _open_output(self) -> None:
        if self._output_path:
            subprocess.Popen(["explorer", "/select,", self._output_path])


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()
