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

# ── python-docx — needs its template .docx bundled ───────────────────────────
for _pkg in ('docx',):
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
        'extractor', 'formatter', 'formatter_word', 'thai_utils',
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
        # heavy data-science packages
        'matplotlib', 'numpy', 'pandas', 'scipy',
        'PIL', 'Pillow',
        # interactive / notebook
        'IPython', 'jupyter', 'notebook', 'ipykernel',
        # GUI toolkits we don't use
        'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'wx',
        # ML frameworks
        'tensorflow', 'torch', 'keras',
        # unused stdlib
        'unittest', 'email', 'html', 'http', 'xml',
        'pydoc', 'doctest', 'difflib', 'calendar',
        'ftplib', 'imaplib', 'poplib', 'smtplib',
        'sqlite3', 'shelve', 'dbm',
        'curses', 'readline', 'rlcompleter',
        'setuptools', 'pip', 'pkg_resources',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PDF2Office',
    debug=False,
    strip=True,     # strip debug symbols on macOS → ลดขนาดได้ ~20-30%
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=True,     # strip debug symbols from all binaries
    upx=False,
    name='PDF2Office',
)

# ── Mac .app bundle ───────────────────────────────────────────
app = BUNDLE(
    coll,
    name='PDF2Office.app',
    icon=None,              # เพิ่ม icon.icns ถ้ามี
    bundle_identifier='com.pdf2office.converter',
    info_plist={
        'CFBundleName':             'PDF2Office',
        'CFBundleDisplayName':      'PDF2Office',
        'CFBundleShortVersionString': '2.0.4',
        'CFBundleVersion':          '2.0.4',
        'NSHighResolutionCapable':  True,
        'LSMinimumSystemVersion':   '10.13.0',
    },
)
