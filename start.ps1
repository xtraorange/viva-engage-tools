# Jampy Engage Application Launcher
# This script activates the virtual environment and starts the web application

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "   Jampy Engage Application" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""

# Change to the script directory (in case it's run from elsewhere)
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# Activate the virtual environment
Write-Host "Activating virtual environment..."
$venvPath = Join-Path $scriptDir ".venv\Scripts\Activate.ps1"
if (Test-Path $venvPath) {
    & $venvPath
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "[ERROR] Could not activate virtual environment" -ForegroundColor Red
        Write-Host "Make sure the .venv folder exists and contains the virtual environment" -ForegroundColor Yellow
        Write-Host ""
        Read-Host "Press Enter to exit"
        exit 1
    }
} else {
    Write-Host ""
    Write-Host "[ERROR] Virtual environment not found at $venvPath" -ForegroundColor Red
    Write-Host "Make sure the .venv folder exists and contains the virtual environment" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Virtual environment activated successfully." -ForegroundColor Green
Write-Host ""
Write-Host "Starting Flask application..." -ForegroundColor Green
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "   Jampy Engage is starting..." -ForegroundColor Cyan
Write-Host "   Opening the configured app URL in your browser" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C to stop the server." -ForegroundColor Yellow
Write-Host ""

# Start the Flask application (this will also open the browser automatically)
python -m src.ui

# Show that the app has closed
Write-Host ""
Write-Host "Application has stopped." -ForegroundColor Yellow
Write-Host ""
Read-Host "Press Enter to exit"