@echo off
REM ── FollowCursor build script ─────────────────────────────────
REM Builds a single-folder exe using PyInstaller.
REM Usage: build.bat
REM Output: dist\FollowCursor\FollowCursor.exe

REM ── Ensure virtual environment exists ─────────────────────────
if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo ✗ Failed to create virtual environment. Is Python installed and on PATH?
        exit /b 1
    )
)

echo Installing dependencies...
.venv\Scripts\python.exe -m pip install --quiet --upgrade pip
.venv\Scripts\python.exe -m pip install --quiet -r requirements.txt

echo Installing / updating PyInstaller...
.venv\Scripts\python.exe -m pip install --quiet pyinstaller

echo.
echo Building FollowCursor...
.venv\Scripts\pyinstaller.exe ^
    --name "FollowCursor" ^
    --windowed ^
    --icon "followcursor.ico" ^
    --noconfirm ^
    --clean ^
    --add-data "app;app" ^
    --hidden-import "PySide6.QtSvg" ^
    --hidden-import "mss" ^
    --hidden-import "cv2" ^
    --hidden-import "numpy" ^
    --hidden-import "imageio_ffmpeg" ^
    --hidden-import "windows_capture" ^
    --exclude-module "PySide6.QtWebEngine" ^
    --exclude-module "PySide6.QtWebEngineCore" ^
    --exclude-module "PySide6.QtWebEngineWidgets" ^
    --exclude-module "PySide6.QtWebChannel" ^
    --exclude-module "PySide6.QtNetwork" ^
    --exclude-module "PySide6.QtQml" ^
    --exclude-module "PySide6.QtQuick" ^
    --exclude-module "PySide6.QtQuickWidgets" ^
    --exclude-module "PySide6.Qt3DCore" ^
    --exclude-module "PySide6.Qt3DRender" ^
    --exclude-module "PySide6.Qt3DInput" ^
    --exclude-module "PySide6.Qt3DLogic" ^
    --exclude-module "PySide6.Qt3DExtras" ^
    --exclude-module "PySide6.Qt3DAnimation" ^
    --exclude-module "PySide6.QtMultimedia" ^
    --exclude-module "PySide6.QtMultimediaWidgets" ^
    --exclude-module "PySide6.QtBluetooth" ^
    --exclude-module "PySide6.QtNfc" ^
    --exclude-module "PySide6.QtPositioning" ^
    --exclude-module "PySide6.QtLocation" ^
    --exclude-module "PySide6.QtSensors" ^
    --exclude-module "PySide6.QtSerialPort" ^
    --exclude-module "PySide6.QtTest" ^
    --exclude-module "PySide6.QtCharts" ^
    --exclude-module "PySide6.QtDataVisualization" ^
    --exclude-module "PySide6.QtOpenGL" ^
    --exclude-module "PySide6.QtOpenGLWidgets" ^
    --exclude-module "PySide6.QtPdf" ^
    --exclude-module "PySide6.QtPdfWidgets" ^
    --exclude-module "PySide6.QtRemoteObjects" ^
    --exclude-module "PySide6.QtScxml" ^
    --exclude-module "PySide6.QtSql" ^
    --exclude-module "PySide6.QtXml" ^
    --exclude-module "PySide6.QtDesigner" ^
    --exclude-module "PySide6.QtHelp" ^
    --exclude-module "PySide6.QtUiTools" ^
    --exclude-module "PySide6.QtConcurrent" ^
    --exclude-module "PySide6.QtDBus" ^
    --exclude-module "PySide6.QtStateMachine" ^
    --exclude-module "PySide6.QtTextToSpeech" ^
    --exclude-module "PySide6.QtHttpServer" ^
    --exclude-module "PySide6.QtWebSockets" ^
    --exclude-module "PySide6.QtSpatialAudio" ^
    --exclude-module "PySide6.QtAsyncio" ^
    --exclude-module "tkinter" ^
    --exclude-module "unittest" ^
    --exclude-module "email" ^
    --exclude-module "http" ^
    --exclude-module "xml" ^
    --exclude-module "pydoc" ^
    main.py

echo.
if exist "dist\FollowCursor\FollowCursor.exe" (
    echo ✓ Build succeeded: dist\FollowCursor\FollowCursor.exe
) else (
    echo ✗ Build failed — check output above for errors.
)
pause
