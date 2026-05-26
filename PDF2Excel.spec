# -*- mode: python ; coding: utf-8 -*-
# PDF2Excel.spec  —  PyInstaller build specification
#
# Build command (run once from the project folder):
#   python -m PyInstaller PDF2Excel.spec --clean --noconfirm
#
# Or just double-click:  build.bat
# ─────────────────────────────────────────────────────────────

from PyInstaller.utils.hooks import collect_all, collect_data_files

datas     = []
binaries  = []
hiddenimports = []

# ── PyMuPDF (fitz) — includes MuPDF DLLs; must collect everything ────────────
for _pkg in ('fitz', 'pymupdf'):
    _d, _b, _h = collect_all(_pkg)
    datas += _d; binaries += _b; hiddenimports += _h

# ── pdfplumber + pdfminer ─────────────────────────────────────────────────────
for _pkg in ('pdfplumber', 'pdfminer'):
    _d, _b, _h = collect_all(_pkg)
    datas += _d; binaries += _b; hiddenimports += _h

# ── openpyxl — MUST collect data files (XML templates inside the package) ────
#    Without this, Workbook() can't load its default styles → _ws = None crash
for _pkg in ('openpyxl', 'et_xmlfile'):
    _d, _b, _h = collect_all(_pkg)
    datas += _d; binaries += _b; hiddenimports += _h

# ── cryptography (indirect dep of some pdfminer builds) ─────────────────────
try:
    _d, _b, _h = collect_all('cryptography')
    datas += _d; binaries += _b; hiddenimports += _h
except Exception:
    pass


a = Analysis(
    ['gui.py'],
    pathex=['.'],               # project root on sys.path → finds our modules
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + [
        # ── our own modules (imported lazily inside methods) ──────────────────
        'extractor',
        'formatter',
        'thai_utils',
        # ── stdlib / tkinter ─────────────────────────────────────────────────
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'tkinter.font',
        # ── third-party ──────────────────────────────────────────────────────
        'openpyxl',
        'openpyxl.cell._writer',    # openpyxl lazy-imports this
        'openpyxl.drawing.spreadsheet_drawing',
        'openpyxl.styles',
        'openpyxl.utils',
        'tqdm',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Exclude heavy packages we definitely don't use (keeps dist small)
    excludes=[
        'matplotlib', 'numpy', 'pandas', 'scipy',
        'PIL', 'Pillow',
        'IPython', 'jupyter', 'notebook',
        'wx', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
        'tensorflow', 'torch',
        'setuptools', 'pip',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PDF2Excel',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,               # UPX disabled — avoids antivirus false-positives
    console=False,           # no black terminal window
    disable_windowed_traceback=False,
    # icon='icon.ico',       # uncomment + add icon.ico to use a custom icon
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='PDF2Excel',
)
