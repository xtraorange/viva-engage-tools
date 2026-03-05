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

Write-Host "Starting Flask application..." -ForegroundColor Green
Write-Host ""

# Start Python in a new window
$pythonPath = (Get-Command python).Source
Start-Process -FilePath $pythonPath -ArgumentList "-m", "src.ui" -WorkingDirectory $scriptDir

# Wait for server to start
Write-Host "Waiting for server to start..." -ForegroundColor Cyan
Start-Sleep -Seconds 2

# Open browser
Write-Host "Opening browser to http://localhost:5000..." -ForegroundColor Cyan
Start-Process "http://localhost:5000"

Write-Host ""
Write-Host "Application started!" -ForegroundColor Green
Write-Host "The Flask server is running in a separate window." -ForegroundColor Cyan
Write-Host "Close this window or the server window to stop the application." -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter to exit this launcher"