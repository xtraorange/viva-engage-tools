@echo off
REM Jampy Engage Application Launcher
REM This script activates the virtual environment and starts the web application

cd /d "%~dp0"

REM Activate the virtual environment
call .venv\Scripts\activate.bat

REM Check if activation was successful
if errorlevel 1 (
    echo [ERROR] Could not activate virtual environment
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Jampy Engage
echo   Opening configured app URL
echo ============================================
echo.

REM Start the Flask application inside a restart loop
:loop
echo Server running...
python -m src.ui

REM When the server exits, check for restart flag
if exist restart.flag (
    del restart.flag
    cls
    echo.
    echo ============================================
    echo   Jampy Engage
    echo   Opening configured app URL
    echo ============================================
    echo.
    goto loop
)

REM No restart requested; exit script
exit /b