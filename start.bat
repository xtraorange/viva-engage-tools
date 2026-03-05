@echo off
REM Jampy Engage Application Launcher
REM This script activates the virtual environment and starts the web application

echo.
echo ============================================
echo   Jampy Engage Application
echo ============================================
echo.

REM Change to the script directory (in case it's run from elsewhere)
cd /d "%~dp0"

REM Activate the virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate.bat

REM Check if activation was successful
if errorlevel 1 (
    echo.
    echo [ERROR] Could not activate virtual environment
    echo Make sure the .venv folder exists and contains the virtual environment
    echo.
    pause
    exit /b 1
)

echo Virtual environment activated successfully.
echo.
echo Starting Flask application...
echo.
REM Start the Flask application in a new window
echo Starting Flask application...
start "Jampy Engage Server" cmd /k "python -m src.ui"

REM Wait a moment for the server to start
timeout /t 2 /nobreak

REM Open the browser
echo.
echo Opening browser to http://localhost:5000...
start http://localhost:5000

REM Give feedback
echo.
echo Application started! Check the "Jampy Engage Server" window for server logs.
echo.
pause