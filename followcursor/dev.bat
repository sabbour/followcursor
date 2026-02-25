@echo off
REM ── FollowCursor dev setup ────────────────────────────────────
REM Creates a virtual environment, installs dependencies, and
REM launches the app. Run this once to set up, or any time to
REM start the app.
REM Usage: dev.bat

cd /d "%~dp0"

REM ── Ensure virtual environment exists ─────────────────────────
if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo.
        echo ✗ Failed to create virtual environment.
        echo   Make sure Python 3.10+ is installed and on your PATH.
        echo   Download from https://www.python.org/downloads/
        exit /b 1
    )
)

REM ── Install / update dependencies ─────────────────────────────
echo Installing dependencies...
.venv\Scripts\python.exe -m pip install --quiet --upgrade pip
.venv\Scripts\python.exe -m pip install --quiet -r requirements.txt

REM ── Launch the app ────────────────────────────────────────────
echo.
echo Starting FollowCursor...
echo.
.venv\Scripts\python.exe main.py
