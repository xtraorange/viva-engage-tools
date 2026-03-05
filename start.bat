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
echo ============================================
echo   Jampy Engage is starting...
echo   Opening http://localhost:5000 in your browser
echo ============================================
echo.
echo Press Ctrl+C to stop the server.
echo.

REM Start the Flask application inside a restart loop
:loop
python -m src.ui

REM When the server exits, check for restart flag
if exist restart.flag (
    del restart.flag
    echo Restart requested, launching again...
    goto loop
)

REM No restart requested; exit script
exit /b