<#
.SYNOPSIS
    Builds a standalone FollowCursor.exe with PyInstaller.

.DESCRIPTION
    Creates/reuses a virtual environment, installs dependencies and
    PyInstaller, then produces a single-folder distribution at
    dist\FollowCursor\FollowCursor.exe.
#>

$ErrorActionPreference = "Stop"
$FollowCursorRoot = Split-Path -Parent $PSScriptRoot
Push-Location $FollowCursorRoot

try {
    # ── Ensure virtual environment exists ────────────────────────
    if (-not (Test-Path ".venv\Scripts\python.exe")) {
        Write-Host "Creating virtual environment..."
        python -m venv .venv
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Failed to create virtual environment. Is Python x64 installed and on PATH?" -ForegroundColor Red
            exit 1
        }
    }

    # ── Verify Python is x64 ────────────────────────────────────
    $archCheck = & .venv\Scripts\python.exe -c "import sys; print('ARM64' in sys.version)"
    if ($archCheck -eq "True") {
        Write-Host ""
        Write-Host "ARM64 native Python detected in .venv." -ForegroundColor Red
        Write-Host "  Several dependencies (OpenCV, dxcam) have no ARM64 wheels."
        Write-Host "  Please install Python x64 and recreate the virtual environment:"
        Write-Host ""
        Write-Host '  1. Install "Windows installer (64-bit)" from https://www.python.org/downloads/'
        Write-Host "  2. Delete .venv:  Remove-Item -Recurse -Force .venv"
        Write-Host '  3. Recreate:      & "C:\path\to\python-x64\python.exe" -m venv .venv'
        Write-Host "  4. Run Build-App.ps1 again."
        exit 1
    }

    Write-Host "Installing dependencies..."
    & .venv\Scripts\python.exe -m pip install --quiet --upgrade pip
    & .venv\Scripts\python.exe -m pip install --quiet -r requirements.txt

    Write-Host "Installing / updating PyInstaller..."
    & .venv\Scripts\python.exe -m pip install --quiet pyinstaller

    Write-Host "Clearing __pycache__..."
    Get-ChildItem -Directory -Recurse -Filter "__pycache__" | Remove-Item -Recurse -Force

    Write-Host ""
    Write-Host "Building FollowCursor..."
    & .venv\Scripts\pyinstaller.exe `
        --name "FollowCursor" `
        --windowed `
        --icon "followcursor.ico" `
        --noconfirm `
        --clean `
        --add-data "app;app" `
        --hidden-import "shiboken6" `
        --hidden-import "shiboken6.Shiboken" `
        --hidden-import "PySide6.QtSvg" `
        --hidden-import "mss" `
        --hidden-import "cv2" `
        --hidden-import "numpy" `
        --hidden-import "imageio_ffmpeg" `
        --hidden-import "windows_capture" `
        --exclude-module "PySide6.QtWebEngine" `
        --exclude-module "PySide6.QtWebEngineCore" `
        --exclude-module "PySide6.QtWebEngineWidgets" `
        --exclude-module "PySide6.QtWebChannel" `
        --exclude-module "PySide6.QtNetwork" `
        --exclude-module "PySide6.QtQml" `
        --exclude-module "PySide6.QtQuick" `
        --exclude-module "PySide6.QtQuickWidgets" `
        --exclude-module "PySide6.Qt3DCore" `
        --exclude-module "PySide6.Qt3DRender" `
        --exclude-module "PySide6.Qt3DInput" `
        --exclude-module "PySide6.Qt3DLogic" `
        --exclude-module "PySide6.Qt3DExtras" `
        --exclude-module "PySide6.Qt3DAnimation" `
        --exclude-module "PySide6.QtMultimedia" `
        --exclude-module "PySide6.QtMultimediaWidgets" `
        --exclude-module "PySide6.QtBluetooth" `
        --exclude-module "PySide6.QtNfc" `
        --exclude-module "PySide6.QtPositioning" `
        --exclude-module "PySide6.QtLocation" `
        --exclude-module "PySide6.QtSensors" `
        --exclude-module "PySide6.QtSerialPort" `
        --exclude-module "PySide6.QtTest" `
        --exclude-module "PySide6.QtCharts" `
        --exclude-module "PySide6.QtDataVisualization" `
        --exclude-module "PySide6.QtOpenGL" `
        --exclude-module "PySide6.QtOpenGLWidgets" `
        --exclude-module "PySide6.QtPdf" `
        --exclude-module "PySide6.QtPdfWidgets" `
        --exclude-module "PySide6.QtRemoteObjects" `
        --exclude-module "PySide6.QtScxml" `
        --exclude-module "PySide6.QtSql" `
        --exclude-module "PySide6.QtXml" `
        --exclude-module "PySide6.QtDesigner" `
        --exclude-module "PySide6.QtHelp" `
        --exclude-module "PySide6.QtUiTools" `
        --exclude-module "PySide6.QtConcurrent" `
        --exclude-module "PySide6.QtDBus" `
        --exclude-module "PySide6.QtStateMachine" `
        --exclude-module "PySide6.QtTextToSpeech" `
        --exclude-module "PySide6.QtHttpServer" `
        --exclude-module "PySide6.QtWebSockets" `
        --exclude-module "PySide6.QtSpatialAudio" `
        --exclude-module "PySide6.QtAsyncio" `
        --exclude-module "tkinter" `
        --exclude-module "unittest" `
        --exclude-module "pydoc" `
        main.py

    Write-Host ""
    if (Test-Path "dist\FollowCursor\FollowCursor.exe") {
        Write-Host "Build succeeded: dist\FollowCursor\FollowCursor.exe" -ForegroundColor Green
    } else {
        Write-Host "Build failed - check output above for errors." -ForegroundColor Red
    }
} finally {
    Pop-Location
}
