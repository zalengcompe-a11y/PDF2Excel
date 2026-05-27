# -*- mode: python ; coding: utf-8 -*-
# PDF2Excel_mac.spec  —  PyInstaller build spec for macOS
#
# ต้องรันบนเครื่อง Mac เท่านั้น:
#   python -m PyInstaller PDF2Excel_mac.spec --clean --noconfirm
#
# หรือใช้:  ./build_mac.sh
# ─────────────────────────────────────────────────────────────

from PyInstaller.utils.hooks import collect_all

datas        = []
binaries     = []
hiddenimports = []

for _pkg in ('fitz', 'pymupdf'):
    _d, _b, _h = collect_all(_pkg)
    datas += _d; binaries += _b; hiddenimports += _h

for _pkg in ('pdfplumber', 'pdfminer'):
    _d, _b, _h = collect_all(_pkg)
    datas += _d; binaries += _b; hiddenimports += _h

for _pkg in ('openpyxl', 'et_xmlfile'):
    _d, _b, _h = collect_all(_pkg)
    datas += _d; binaries += _b; hiddenimports += _h

try:
    _d, _b, _h = collect_all('cryptography')
    datas += _d; binaries += _b; hiddenimports += _h
except Exception:
    pass


a = Analysis(
    ['gui.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + [
        'extractor', 'formatter', 'thai_utils',
        'tkinter', 'tkinter.ttk', 'tkinter.filedialog',
        'tkinter.messagebox', 'tkinter.font',
        'openpyxl', 'openpyxl.cell._writer',
        'openpyxl.drawing.spreadsheet_drawing',
        'openpyxl.styles', 'openpyxl.utils',
        'tqdm',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'numpy', 'pandas', 'scipy',
        'PIL', 'Pillow',
        'IPython', 'jupyter',
        'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
        'tensorflow', 'torch',
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
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='PDF2Excel',
)

# ── Mac .app bundle ───────────────────────────────────────────
app = BUNDLE(
    coll,
    name='PDF2Excel.app',
    icon=None,              # เพิ่ม icon.icns ถ้ามี
    bundle_identifier='com.pdf2excel.converter',
    info_plist={
        'CFBundleName':             'PDF2Excel',
        'CFBundleDisplayName':      'PDF to Excel Converter',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleVersion':          '1.0.0',
        'NSHighResolutionCapable':  True,
        'LSMinimumSystemVersion':   '10.13.0',
    },
)
