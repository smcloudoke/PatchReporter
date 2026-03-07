@echo off
echo ============================================
echo  Patch Reporter - Build Script
echo ============================================
echo.

echo [1/2] Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install failed. Make sure Python is in your PATH.
    pause
    exit /b 1
)

echo.
echo [2/2] Building PatchReporter.exe...
pyinstaller ^
    --onefile ^
    --windowed ^
    --name PatchReporter ^
    --collect-data customtkinter ^
    --hidden-import win32com.client ^
    --hidden-import win32api ^
    --hidden-import win32con ^
    --hidden-import pywintypes ^
    --add-data "constants.py;." ^
    --add-data "db.py;." ^
    --add-data "msrc.py;." ^
    --add-data "report.py;." ^
    --add-data "ui.py;." ^
    --add-data "ui_customer.py;." ^
    --add-data "ui_patches.py;." ^
    --add-data "ui_servers.py;." ^
    approvalreport.py

if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Build complete!
echo  Your executable is at: dist\PatchReporter.exe
echo ============================================
pause
