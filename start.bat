@echo off
setlocal EnableDelayedExpansion
REM Jampy Engage Application Launcher
REM This script activates the virtual environment and starts the web application

cd /d "%~dp0"

REM Activate the virtual environment
call :renderStatus "Activating virtual environment..."
call .venv\Scripts\activate.bat

REM Check if activation was successful
if errorlevel 1 (
    call :renderStatus "Activation failed"
    echo [ERROR] Could not activate virtual environment
    pause
    exit /b 1
)

set "JAMPY_SKIP_BROWSER="

REM Start the Flask application inside a restart loop
:loop
call :renderStatus "Server Running..."
python -m src.ui

REM When the server exits, check for restart flag
if exist restart.flag (
    set "RESTART_MODE=restart"
    set /p RESTART_MODE=<restart.flag
    if "!RESTART_MODE!"=="" set "RESTART_MODE=restart"
    del restart.flag
    if /I "!RESTART_MODE!"=="restart:no-browser" (
        set "JAMPY_SKIP_BROWSER=1"
    ) else (
        set "JAMPY_SKIP_BROWSER="
    )

    if "!JAMPY_SKIP_BROWSER!"=="1" (
        call :renderStatus "Restarting... (keeping browser in current tab)"
    ) else (
        call :renderStatus "Restarting... (launcher will open browser)"
    )

    timeout /t 1 /nobreak >nul
    goto loop
)

REM No restart requested; exit script
call :renderStatus "Server stopped"
exit /b

:renderStatus
cls
echo ============================================
echo   Viva Engage Tools Server
echo ============================================
echo   Workspace: %CD%
echo   UI restart behavior: reconnect current tab
echo.
echo Status: %~1
echo.
goto :eof