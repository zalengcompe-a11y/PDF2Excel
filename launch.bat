@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

:: ============================================================
::  launch.bat  —  PDF to Excel Converter launcher
::
::  1. Checks whether Python 3 is installed
::  2. If missing, downloads & silently installs Python 3.12
::  3. Installs / updates pip dependencies (quiet)
::  4. Launches gui.py
:: ============================================================

set "PY_VERSION=3.12.10"
set "PY_INSTALLER=python-%PY_VERSION%-amd64.exe"
set "PY_URL=https://www.python.org/ftp/python/%PY_VERSION%/%PY_INSTALLER%"

:: ── 1. Find Python ───────────────────────────────────────────
echo Checking for Python...

python --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do set "PY_VER=%%v"
    echo   Found Python !PY_VER!
    goto :install_deps
)

py --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    for /f "tokens=2" %%v in ('py --version 2^>^&1') do set "PY_VER=%%v"
    echo   Found Python !PY_VER! (py launcher)
    :: Use the py launcher for the rest
    set "PYTHON=py"
    goto :install_deps
)

:: ── 2. Python not found — download & install ─────────────────
echo.
echo   Python was not found on this machine.
echo   Downloading Python %PY_VERSION% — this may take a minute...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "try { $p = '%TEMP%\%PY_INSTALLER%'; Invoke-WebRequest -Uri '%PY_URL%' -OutFile $p -UseBasicParsing; Write-Host '  Download complete.' } catch { Write-Host ('  ERROR: ' + $_.Exception.Message); exit 1 }"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo   Download failed.  Please check your internet connection and try again,
    echo   or install Python 3.12 manually from https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo   Installing Python %PY_VERSION% — please wait...
"%TEMP%\%PY_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_launcher=1

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo   Installation failed (exit code %ERRORLEVEL%).
    echo   Please install Python 3.12 manually from https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo   Python installed successfully.
echo   Restarting launcher so the new PATH takes effect...
echo.

:: Re-launch this script in a fresh shell so updated PATH is visible
start "" /wait cmd /c ""%~f0""
exit /b 0


:: ── 3. Install / upgrade pip dependencies ────────────────────
:install_deps

:: Resolve which python command to use (prefer 'python', then 'py')
if not defined PYTHON (
    python --version >nul 2>&1 && set "PYTHON=python" || set "PYTHON=py"
)

echo.
echo Installing / verifying dependencies...
%PYTHON% -m pip install --quiet --upgrade pip
%PYTHON% -m pip install --quiet -r requirements.txt

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo   Dependency installation failed.
    echo   Try running manually:  %PYTHON% -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo   Dependencies OK.
echo.

:: ── 4. Launch GUI ─────────────────────────────────────────────
echo Starting PDF to Excel Converter...
%PYTHON% gui.py

:: If gui.py exits with an error, keep the window open so the user can read it
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo   gui.py exited with error code %ERRORLEVEL%.
    pause
)

endlocal
