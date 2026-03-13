@echo off
setlocal EnableDelayedExpansion
REM Viva Engage Tools Server Launcher

cd /d "%~dp0"

set "ROOT_DIR=%CD%"
set "INSTALL_SCRIPT=%ROOT_DIR%\scripts\install.ps1"
set "START_SCRIPT=%ROOT_DIR%\scripts\start.ps1"
set "VENV_PYTHON=%ROOT_DIR%\.venv\Scripts\python.exe"

if not exist "%INSTALL_SCRIPT%" (
    echo [ERROR] Install script not found: %INSTALL_SCRIPT%
    pause
    exit /b 1
)

if not exist "%START_SCRIPT%" (
    echo [ERROR] Start script not found: %START_SCRIPT%
    pause
    exit /b 1
)

call :ensureInstalled
if errorlevel 1 exit /b 1

powershell -NoProfile -ExecutionPolicy Bypass -File "%START_SCRIPT%" -RootDir "%ROOT_DIR%"
exit /b %errorlevel%

:ensureInstalled
if exist "%VENV_PYTHON%" goto :eof

echo [INFO] First run detected. Installing dependencies...
powershell -NoProfile -ExecutionPolicy Bypass -File "%INSTALL_SCRIPT%" -TargetDir "%ROOT_DIR%" -SkipClone -NoLaunch
if errorlevel 1 (
    echo [ERROR] Automatic setup failed.
    pause
    exit /b 1
)

if not exist "%VENV_PYTHON%" (
    echo [ERROR] Expected virtual environment was not created.
    pause
    exit /b 1
)

goto :eof
