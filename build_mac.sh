#!/bin/bash
# ============================================================
#  build_mac.sh  —  Build PDF2Excel.app for macOS distribution
#
#  Output:  dist/PDF2Excel.app
#           PDF2Excel_mac_vYYYYMMDD.zip  (ready to share)
#
#  ต้องรันบนเครื่อง Mac เท่านั้น
# ============================================================

set -e
cd "$(dirname "$0")"

TODAY=$(date +%Y%m%d)
ZIP_NAME="PDF2Excel_mac_v${TODAY}.zip"
DIST_NAME="PDF2Excel"

echo ""
echo "===================================================="
echo "  PDF2Excel — macOS Build Script"
echo "===================================================="
echo ""

# ── Step 1: Python ────────────────────────────────────────────
echo "[1/5] Checking Python..."
if ! command -v python3 &>/dev/null; then
    echo "  ERROR: Python not found. Run launch.sh first."
    exit 1
fi
echo "  $(python3 --version) OK"

# ── Step 2: Build tools ───────────────────────────────────────
echo ""
echo "[2/5] Installing build tools (PyInstaller)..."
python3 -m pip install --quiet --upgrade pip
python3 -m pip install --quiet pyinstaller
echo "  PyInstaller ready."

# ── Step 3: Runtime dependencies ─────────────────────────────
echo ""
echo "[3/5] Installing runtime dependencies..."
python3 -m pip install --quiet -r requirements.txt
echo "  Dependencies OK."

# ── Step 4: Build .app ────────────────────────────────────────
echo ""
echo "[4/5] Building PDF2Excel.app (this takes 2-5 minutes)..."
echo ""

# ลบ build เก่า
rm -rf build/ dist/

python3 -m PyInstaller PDF2Excel_mac.spec --noconfirm

if [ ! -d "dist/${DIST_NAME}.app" ]; then
    echo ""
    echo "  BUILD FAILED: dist/${DIST_NAME}.app not found."
    exit 1
fi

echo ""
echo "  Build successful."

# ── Step 5: Zip ───────────────────────────────────────────────
echo ""
echo "[5/5] Creating distributable zip..."

rm -f "${ZIP_NAME}"
cd dist
zip -r "../${ZIP_NAME}" "${DIST_NAME}.app" -x "*.DS_Store"
cd ..

SIZE=$(du -sh "${ZIP_NAME}" | cut -f1)
echo "  Zip created: ${ZIP_NAME} (${SIZE})"

# ── Summary ───────────────────────────────────────────────────
echo ""
echo "===================================================="
echo "  Done!"
echo ""
echo "  To share with team:"
echo "  1. ส่ง ${ZIP_NAME}"
echo "  2. แตกไฟล์ zip"
echo "  3. ลาก PDF2Excel.app ไปไว้ใน Applications"
echo "  4. ดับเบิลคลิก PDF2Excel.app"
echo ""
echo "  หรืออัปโหลดไปที่ GitHub Releases"
echo "===================================================="
echo ""
