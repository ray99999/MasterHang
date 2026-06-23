@echo off
echo ========================================
echo           AI Smart Agent
echo ========================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.8+
    pause
    exit /b 1
)

echo [INFO] Checking dependencies...
pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing dependencies...
    pip install -r requirements.txt
)

echo.
echo [INFO] Starting server...
echo.
echo Local access: http://127.0.0.1:8000
echo LAN access: http://[YOUR_IP]:8000 (use 'ipconfig' to find your IP)
echo.
echo Press Ctrl+C to stop
echo.
echo ========================================
echo.

uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

pause
