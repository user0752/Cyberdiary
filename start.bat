@echo off
setlocal enabledelayedexpansion

echo ========================================
echo   CyberNote - Interactive Launcher
echo ========================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

:: Check Node.js
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js not found. Please install Node.js 18+
    pause
    exit /b 1
)

:: Ensure backend venv + dependencies
cd backend
if not exist "venv" (
    echo [SETUP] Creating Python virtual environment...
    python -m venv venv
    call venv\Scripts\activate.bat
    echo [SETUP] Installing backend dependencies...
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
    echo [CHECK] Verifying backend dependencies...
    pip install -r requirements.txt -q 2>nul
)
cd ..

:: Ensure frontend node_modules
cd frontend
if not exist "node_modules" (
    echo [SETUP] Installing frontend dependencies...
    call npm install
)
cd ..

echo.
echo [LAUNCH] Starting interactive service dashboard...
echo.

:: Run the launcher (with venv Python for proper dependency resolution)
cd backend
venv\Scripts\python.exe ..\launcher.py
cd ..
