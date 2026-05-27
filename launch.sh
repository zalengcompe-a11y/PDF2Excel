#!/bin/bash
# ============================================================
#  launch.sh  —  PDF to Excel Converter launcher (macOS)
#
#  1. ตรวจสอบว่ามี Python 3 หรือยัง
#  2. ถ้าไม่มี — ติดตั้งผ่าน Homebrew อัตโนมัติ
#  3. ติดตั้ง dependencies
#  4. เปิด gui.py
# ============================================================

set -e
cd "$(dirname "$0")"

echo ""
echo "===================================================="
echo "  PDF to Excel Converter"
echo "===================================================="
echo ""

# ── 1. ตรวจ Python 3 ─────────────────────────────────────────
echo "Checking Python..."

if command -v python3 &>/dev/null; then
    PY_VER=$(python3 --version 2>&1)
    echo "  Found $PY_VER"
    PYTHON=python3
else
    echo "  Python not found — installing via Homebrew..."

    # ติดตั้ง Homebrew ถ้ายังไม่มี
    if ! command -v brew &>/dev/null; then
        echo "  Installing Homebrew first..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        # เพิ่ม Homebrew ลง PATH สำหรับ Apple Silicon
        eval "$(/opt/homebrew/bin/brew shellenv)" 2>/dev/null || true
        eval "$(/usr/local/bin/brew shellenv)" 2>/dev/null || true
    fi

    brew install python
    PYTHON=python3
fi

# ── 2. ตรวจ tkinter (Mac Python บางตัวไม่มี) ─────────────────
if ! $PYTHON -c "import tkinter" &>/dev/null; then
    echo ""
    echo "  tkinter not found — installing python-tk via Homebrew..."
    brew install python-tk
fi

# ── 3. ติดตั้ง dependencies ──────────────────────────────────
echo ""
echo "Installing / verifying dependencies..."
$PYTHON -m pip install --quiet --upgrade pip
$PYTHON -m pip install --quiet -r requirements.txt
echo "  Dependencies OK."

# ── 4. เปิด GUI ───────────────────────────────────────────────
echo ""
echo "Starting PDF to Excel Converter..."
$PYTHON gui.py
