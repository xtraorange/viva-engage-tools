# Jampy Engage Application Launcher
# This script activates the virtual environment and starts the web application

function Show-BannerAndStatus {
    param(
        [string]$Status,
        [string]$StatusColor = "Green"
    )

    Clear-Host
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host "   Viva Engage Tools Server" -ForegroundColor Cyan
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host "   Workspace: $scriptDir" -ForegroundColor DarkGray
    Write-Host "   UI restart behavior: reconnect current tab" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "Status: $Status" -ForegroundColor $StatusColor
    Write-Host ""
}

# Change to the script directory (in case it's run from elsewhere)
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# Activate the virtual environment
Show-BannerAndStatus -Status "Activating virtual environment..." -StatusColor "Yellow"
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

# Start the Flask application inside a restart loop
$env:JAMPY_SKIP_BROWSER = ""
while ($true) {
    Show-BannerAndStatus -Status "Server Running..." -StatusColor "Green"
    python -m src.ui

    if (Test-Path "restart.flag") {
        $restartMode = "restart"
        try {
            $restartMode = (Get-Content "restart.flag" -Raw).Trim()
        } catch {
            $restartMode = "restart"
        }
        Remove-Item "restart.flag" -Force -ErrorAction SilentlyContinue

        if ($restartMode -eq "restart:no-browser") {
            $env:JAMPY_SKIP_BROWSER = "1"
        } else {
            $env:JAMPY_SKIP_BROWSER = ""
        }

        if ($env:JAMPY_SKIP_BROWSER -eq "1") {
            Show-BannerAndStatus -Status "Restarting... (keeping browser in current tab)" -StatusColor "Yellow"
        } else {
            Show-BannerAndStatus -Status "Restarting... (launcher will open browser)" -StatusColor "Yellow"
        }
        Start-Sleep -Milliseconds 900
        continue
    }

    break
}

# Show that the app has closed
Show-BannerAndStatus -Status "Server stopped" -StatusColor "Yellow"
Read-Host "Press Enter to exit"