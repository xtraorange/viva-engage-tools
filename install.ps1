# jampy-engage Installer for Windows
# One-line install (copy and paste into PowerShell):
# irm https://raw.githubusercontent.com/xtraorange/jampy-engage/main/install.ps1 | iex

param(
    [string]$TargetDir = "$env:USERPROFILE\jampy-engage"
)

Write-Host "========================================" -ForegroundColor Green
Write-Host "    jampy-engage Installer for Windows" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# Check for Python
Write-Host "Checking for Python installation..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✓ $pythonVersion found" -ForegroundColor Green
} catch {
    Write-Host "✗ Python is required but not installed." -ForegroundColor Red
    Write-Host "Please install Python from https://www.python.org/" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Important: Make sure to check 'Add Python to PATH' during installation"
    exit 1
}

Write-Host ""
Write-Host "Installing to: $TargetDir" -ForegroundColor Yellow

# Clone or pull repo
if (Test-Path $TargetDir) {
    Write-Host "Directory exists, pulling latest changes..." -ForegroundColor Yellow
    Set-Location $TargetDir
    git pull
} else {
    Write-Host "Cloning repository..." -ForegroundColor Yellow
    git clone https://github.com/xtraorange/jampy-engage.git $TargetDir
    Set-Location $TargetDir
}

# Check for git
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "✗ Git is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Git from https://git-scm.com/" -ForegroundColor Yellow
    exit 1
}

# Create virtual environment
Write-Host ""
Write-Host "Creating virtual environment..." -ForegroundColor Yellow
python -m venv .venv

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& ".\.venv\Scripts\Activate.ps1"

# Install requirements
Write-Host "Installing dependencies..." -ForegroundColor Yellow
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "    Installation Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "To start the application, run:" -ForegroundColor White
Write-Host "  cd $TargetDir" -ForegroundColor Yellow
Write-Host "  .\.venv\Scripts\Activate.ps1" -ForegroundColor Yellow
Write-Host "  python run_reports.py" -ForegroundColor Yellow
Write-Host ""
Write-Host "Then open your browser to: http://localhost:5000" -ForegroundColor Yellow
Write-Host ""
