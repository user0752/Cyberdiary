@echo off
setlocal enabledelayedexpansion

echo ========================================
echo   CyberNote Startup Script
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

echo [INFO] Starting backend service...
cd backend

:: Check virtual environment
if not exist "venv" (
    echo [INFO] First run, creating Python virtual environment...
    python -m venv venv
    call venv\Scripts\activate.bat
    echo [INFO] Installing backend dependencies...
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

:: Start backend (background)
start "CyberNote Backend" /min cmd /c "venv\Scripts\activate.bat && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

cd ..

echo [INFO] Starting frontend service...
cd frontend

:: Check node_modules
if not exist "node_modules" (
    echo [INFO] First run, installing frontend dependencies...
    npm install
)

:: Start frontend (background)
start "CyberNote Frontend" /min cmd /c "npm run dev"

cd ..

echo.
echo ========================================
echo   Startup Complete!
echo ========================================
echo.
echo Frontend: http://localhost:5173
echo Backend:  http://localhost:8000
echo API Docs: http://localhost:8000/docs
echo.
echo Press any key to open browser...
pause >nul

:: Open browser
start http://localhost:5173

echo.
echo [TIP] Services are running in background.
echo [TIP] Close the corresponding windows or use Task Manager to stop services.
echo.
pause
