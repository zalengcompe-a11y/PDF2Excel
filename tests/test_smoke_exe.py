"""
tests/test_smoke_exe.py
Smoke test — verifies PDF2Excel.exe launches without crashing.

Requirements:
  - Build the .exe first:  build.bat
  - Run:  pytest tests/test_smoke_exe.py -v

Skipped automatically if the .exe has not been built yet.
"""

import subprocess
import sys
import time
from pathlib import Path

import pytest

# ── Path to the built .exe ────────────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).parent.parent
_EXE_PATH     = _PROJECT_ROOT / "dist" / "PDF2Excel" / "PDF2Excel.exe"


@pytest.fixture(scope="module", autouse=True)
def require_exe():
    """Skip all smoke tests if .exe has not been built."""
    if not _EXE_PATH.exists():
        pytest.skip(
            f".exe not found at {_EXE_PATH}\n"
            "Run build.bat first, then re-run tests."
        )


class TestExeSmoke:

    def test_exe_file_exists(self):
        """dist/PDF2Excel/PDF2Excel.exe must be present after build."""
        assert _EXE_PATH.exists(), f"Missing: {_EXE_PATH}"

    def test_exe_file_size(self):
        """Sanity-check: .exe must be at least 1 MB (not empty/truncated)."""
        size_mb = _EXE_PATH.stat().st_size / (1024 * 1024)
        assert size_mb >= 1.0, f".exe is suspiciously small: {size_mb:.1f} MB"

    def test_exe_launches_without_crash(self):
        """
        Launch PDF2Excel.exe and confirm it stays alive for 3 seconds.
        A GUI app that crashes on startup exits immediately (returncode != None).
        """
        proc = subprocess.Popen(
            [str(_EXE_PATH)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            time.sleep(3)
            still_running = proc.poll() is None
            assert still_running, (
                f"EXE exited immediately with code {proc.returncode} — "
                "likely a crash on startup (missing DLL or import error)"
            )
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    def test_exe_terminates_cleanly(self):
        """
        After receiving terminate signal, process must exit within 5 seconds.
        Hangs indicate a deadlock or uncleaned thread.
        """
        proc = subprocess.Popen(
            [str(_EXE_PATH)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(2)
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            pytest.fail("EXE did not terminate within 5 seconds after SIGTERM")

    def test_dist_folder_has_required_files(self):
        """
        Confirm essential support files are present in the dist folder.
        Missing files indicate an incomplete build.
        """
        dist_dir = _EXE_PATH.parent
        required = ["PDF2Excel.exe"]
        for name in required:
            assert (dist_dir / name).exists(), f"Missing from dist: {name}"
