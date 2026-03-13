# Viva Engage Tools Installer for Windows
# One-line install:
# irm https://raw.githubusercontent.com/xtraorange/viva-engage-tools/main/scripts/install.ps1 | iex

param(
    [string]$TargetDir = "$env:USERPROFILE\viva-engage-tools",
    [switch]$SkipClone,
    [switch]$NoLaunch
)

$ErrorActionPreference = 'Stop'

function Write-Section {
    param([string]$Text)
    Write-Host ""
    Write-Host "+----------------------------------------------------------+" -ForegroundColor Cyan
    Write-Host "| $($Text.PadRight(56)) |" -ForegroundColor Cyan
    Write-Host "+----------------------------------------------------------+" -ForegroundColor Cyan
}

function Get-PythonCommand {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return @('py', '-3')
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @('python')
    }
    throw 'Python 3.10+ is required but was not found in PATH.'
}

function Invoke-PythonCommand {
    param(
        [string[]]$PythonCommand,
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Arguments
    )

    if (-not $PythonCommand -or $PythonCommand.Count -eq 0) {
        throw 'Python command was not resolved.'
    }

    $exe = $PythonCommand[0]
    $prefixArgs = @()
    if ($PythonCommand.Count -gt 1) {
        $prefixArgs = $PythonCommand[1..($PythonCommand.Count - 1)]
    }

    & $exe @prefixArgs @Arguments
}

Write-Section 'Viva Engage Tools Installer'
Write-Host "Target directory: $TargetDir" -ForegroundColor DarkGray

$pythonCmd = Get-PythonCommand
Write-Host "Using Python command: $($pythonCmd -join ' ')" -ForegroundColor Green

if (-not $SkipClone) {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw 'Git is required for one-line install but was not found in PATH.'
    }

    if (Test-Path $TargetDir) {
        Set-Location $TargetDir
        if (Test-Path '.git') {
            Write-Host 'Directory exists, pulling latest changes...' -ForegroundColor Yellow
            git pull --ff-only
        } else {
            Write-Host 'Directory exists without git metadata, using it as-is...' -ForegroundColor Yellow
        }
    } else {
        Write-Host 'Cloning repository...' -ForegroundColor Yellow
        git clone https://github.com/xtraorange/viva-engage-tools.git $TargetDir
        Set-Location $TargetDir
    }
} else {
    if (-not (Test-Path $TargetDir)) {
        throw "Target directory does not exist: $TargetDir"
    }
    Set-Location $TargetDir
}

if (-not (Test-Path 'requirements.txt')) {
    throw 'requirements.txt not found. Are you in the project root?'
}

Write-Section 'Environment Setup'
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    Write-Host 'Creating virtual environment...' -ForegroundColor Yellow
    Invoke-PythonCommand $pythonCmd -Arguments @('-m', 'venv', '.venv')
} else {
    Write-Host 'Virtual environment already exists, reusing it...' -ForegroundColor Yellow
}

$venvPython = Join-Path (Get-Location) '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPython)) {
    throw 'Virtual environment Python executable was not created successfully.'
}

Write-Host 'Installing dependencies...' -ForegroundColor Yellow
& $venvPython -m pip install --upgrade pip setuptools wheel
& $venvPython -m pip install -r requirements.txt

Write-Section 'Install Complete'
if ($NoLaunch) {
    Write-Host 'Install finished. Returning to caller without launching start.bat.' -ForegroundColor Green
} else {
    Write-Host 'Launching application...' -ForegroundColor Green

    $startBat = Join-Path (Get-Location) 'start.bat'
    if (Test-Path $startBat) {
        Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', $startBat
    } else {
        Write-Host 'start.bat not found. Navigate to the install folder and double-click start.bat to launch.' -ForegroundColor Yellow
    }
}