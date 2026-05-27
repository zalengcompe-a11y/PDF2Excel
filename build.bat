@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title PDF2Excel -- Build

:: ============================================================
::  build.bat  --  Build a self-contained PDF2Excel.exe package
::
::  Output:  dist\PDF2Excel\PDF2Excel.exe  (+ support files)
::           PDF2Excel_v<date>.zip          (ready to share)
::
::  Run this script once on your developer machine.
::  The resulting zip needs NO Python on team members' PCs.
:: ============================================================

set "DIST_NAME=PDF2Excel"
:: Use PowerShell for locale-independent date (works on Thai Windows too)
for /f "tokens=*" %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set "TODAY=%%d"
set "ZIP_NAME=%DIST_NAME%_v!TODAY!.zip"

echo.
echo ====================================================
echo   PDF2Excel -- Build Script
echo ====================================================
echo.

:: ── Step 1: Python ────────────────────────────────────────────────────────────
echo [1/5] Checking Python...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   ERROR: Python not found. Run launch.bat first to install Python.
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set "PY_VER=%%v"
echo   Python !PY_VER! OK

:: ── Step 2: Install / update build tools ─────────────────────────────────────
echo.
echo [2/5] Installing build tools (PyInstaller)...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet pyinstaller

if %ERRORLEVEL% NEQ 0 (
    echo   ERROR: Failed to install PyInstaller.
    pause
    exit /b 1
)
echo   PyInstaller ready.

:: ── Step 3: Install runtime dependencies (needed at build time too) ───────────
echo.
echo [3/5] Installing runtime dependencies...
python -m pip install --quiet -r requirements.txt

if %ERRORLEVEL% NEQ 0 (
    echo   ERROR: Failed to install dependencies from requirements.txt.
    pause
    exit /b 1
)
echo   Dependencies OK.

:: ── Step 4: PyInstaller build ─────────────────────────────────────────────────
::
::  Work dir is placed in %TEMP% (outside OneDrive) to avoid the
::  PermissionError: [WinError 5] that OneDrive causes when PyInstaller
::  tries to delete the build\ folder with --clean.
::
set "WORK_DIR=%TEMP%\PDF2Excel_build"
set "DIST_DIR=%~dp0dist"

echo.
echo [4/5] Building executable (this takes 1-3 minutes)...
echo   Work dir : %WORK_DIR%
echo   Dist dir : %DIST_DIR%
echo.

:: Clean previous work dir (in TEMP — no OneDrive lock)
if exist "%WORK_DIR%" rd /s /q "%WORK_DIR%"

:: Clean previous dist in project folder (best-effort, ignore errors)
if exist "%DIST_DIR%\%DIST_NAME%" rd /s /q "%DIST_DIR%\%DIST_NAME%" 2>nul

python -m PyInstaller PDF2Excel.spec --noconfirm ^
    --workpath "%WORK_DIR%\work" ^
    --distpath "%DIST_DIR%"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo   BUILD FAILED. Check the output above for errors.
    pause
    exit /b 1
)

if not exist "%DIST_DIR%\%DIST_NAME%\%DIST_NAME%.exe" (
    echo.
    echo   ERROR: Expected dist\%DIST_NAME%\%DIST_NAME%.exe not found.
    pause
    exit /b 1
)

echo.
echo   Build successful.

:: ── Step 5: Create distributable zip ─────────────────────────────────────────
echo.
echo [5/5] Creating distributable zip...

if exist "%ZIP_NAME%" del /f /q "%ZIP_NAME%"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Compress-Archive -Path 'dist\%DIST_NAME%' -DestinationPath '%ZIP_NAME%' -Force; $mb = [math]::Round((Get-Item '%ZIP_NAME%').Length / 1MB, 1); Write-Host \"  Zip: $mb MB\""

if %ERRORLEVEL% NEQ 0 (
    echo   WARNING: Could not create zip. The dist\ folder is still usable.
) else (
    echo   Zip created: %ZIP_NAME%
)

:: ── Summary ───────────────────────────────────────────────────────────────────
echo.
echo ====================================================
echo   Done!
echo.
echo   To share with team:
echo     1. Send  %ZIP_NAME%
echo     2. Team unzips and double-clicks  PDF2Excel.exe
echo     3. No Python install needed on their PCs
echo.
echo   Folder: %~dp0dist\%DIST_NAME%\
echo ====================================================
echo.
pause
endlocal
