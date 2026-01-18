@echo off
setlocal
cd /d "%~dp0"

echo ======================================================
echo       WhatsApp Bot Environment Setup Script
echo ======================================================
echo.

:: 1. Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python from https://www.python.org/
    pause
    exit /b
)

:: 2. Create Virtual Environment if it doesn't exist
if not exist venv (
    echo [*] Creating virtual environment...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b
    )
    echo [OK] Virtual environment created successfully.
) else (
    echo [!] Virtual environment already exists.
)

:: 3. Activate and Install Requirements
echo [*] Activating environment and installing requirements...
echo.

call venv\Scripts\activate.bat

:: Upgrade pip first
python -m pip install --upgrade pip

:: Install requirements
if exist requirements.txt (
    echo [*] Installing dependencies from requirements.txt...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b
    )
) else (
    echo [WARNING] requirements.txt not found!
)

echo.
echo ======================================================
echo [SUCCESS] Environment setup is complete!
echo You can now use run_bot.bat, run_dashboard.bat, etc.
echo ======================================================
echo.
pause
