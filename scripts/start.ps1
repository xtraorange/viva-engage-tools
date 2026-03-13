param(
    [string]$RootDir = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = 'Stop'
Set-Location $RootDir

$script:SessionStart = Get-Date
$script:RestartCount = 0
$script:StatusBase = 'Starting server'
$script:StatusColor = 'Yellow'
$script:DotFrames = @('.', '..', '...')
$script:RuntimeInfoPath = Join-Path $RootDir '.runtime\ui.json'
$script:RuntimeLogPath = Join-Path $RootDir '.runtime\server.err.log'
$script:BannerTopRow = -1
$global:CurrentServerPid = $null
$script:JobHandle = [IntPtr]::Zero

$jobTypeSource = @"
using System;
using System.Runtime.InteropServices;

public static class JobObjectNative {
    [StructLayout(LayoutKind.Sequential)]
    public struct JOBOBJECT_BASIC_LIMIT_INFORMATION {
        public long PerProcessUserTimeLimit;
        public long PerJobUserTimeLimit;
        public uint LimitFlags;
        public UIntPtr MinimumWorkingSetSize;
        public UIntPtr MaximumWorkingSetSize;
        public uint ActiveProcessLimit;
        public long Affinity;
        public uint PriorityClass;
        public uint SchedulingClass;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct IO_COUNTERS {
        public ulong ReadOperationCount;
        public ulong WriteOperationCount;
        public ulong OtherOperationCount;
        public ulong ReadTransferCount;
        public ulong WriteTransferCount;
        public ulong OtherTransferCount;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct JOBOBJECT_EXTENDED_LIMIT_INFORMATION {
        public JOBOBJECT_BASIC_LIMIT_INFORMATION BasicLimitInformation;
        public IO_COUNTERS IoInfo;
        public UIntPtr ProcessMemoryLimit;
        public UIntPtr JobMemoryLimit;
        public UIntPtr PeakProcessMemoryUsed;
        public UIntPtr PeakJobMemoryUsed;
    }

    public const int JobObjectExtendedLimitInformation = 9;
    public const uint JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000;

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
    public static extern IntPtr CreateJobObject(IntPtr lpJobAttributes, string lpName);

    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool SetInformationJobObject(IntPtr hJob, int JobObjectInfoClass, IntPtr lpJobObjectInfo, uint cbJobObjectInfoLength);

    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool AssignProcessToJobObject(IntPtr hJob, IntPtr hProcess);
}
"@

if (-not ("JobObjectNative" -as [type])) {
    Add-Type -TypeDefinition $jobTypeSource
}

function New-KillOnCloseJob {
    $job = [JobObjectNative]::CreateJobObject([IntPtr]::Zero, $null)
    if ($job -eq [IntPtr]::Zero) {
        throw 'Failed to create Windows job object for process lifetime control.'
    }

    $info = New-Object JobObjectNative+JOBOBJECT_EXTENDED_LIMIT_INFORMATION
    $info.BasicLimitInformation.LimitFlags = [JobObjectNative]::JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE

    $length = [Runtime.InteropServices.Marshal]::SizeOf([type]'JobObjectNative+JOBOBJECT_EXTENDED_LIMIT_INFORMATION')
    $ptr = [Runtime.InteropServices.Marshal]::AllocHGlobal($length)
    try {
        [Runtime.InteropServices.Marshal]::StructureToPtr($info, $ptr, $false)
        $ok = [JobObjectNative]::SetInformationJobObject($job, [JobObjectNative]::JobObjectExtendedLimitInformation, $ptr, [uint32]$length)
        if (-not $ok) {
            throw 'Failed to configure Windows job object limits.'
        }
    } finally {
        [Runtime.InteropServices.Marshal]::FreeHGlobal($ptr)
    }

    return $job
}

function Add-ProcessToJob {
    param(
        [int]$ProcessId,
        [IntPtr]$JobHandle
    )

    if ($JobHandle -eq [IntPtr]::Zero) {
        throw 'Invalid job handle.'
    }

    $proc = Get-Process -Id $ProcessId -ErrorAction Stop
    $assigned = [JobObjectNative]::AssignProcessToJobObject($JobHandle, $proc.Handle)
    if (-not $assigned) {
        throw "Failed to assign process $ProcessId to launcher job object."
    }
}

$script:JobHandle = New-KillOnCloseJob

# Best-effort shutdown hook for clean exits; hard closes are handled by the job object.
Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action {
    if ($global:CurrentServerPid) {
        Stop-Process -Id $global:CurrentServerPid -Force -ErrorAction SilentlyContinue
    }
} | Out-Null

function Ensure-RuntimeDirectory {
    $runtimeDir = Split-Path -Parent $script:RuntimeInfoPath
    if (-not (Test-Path $runtimeDir)) {
        New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
    }
}

function Get-ConfiguredUrl {
    $configPath = Join-Path $RootDir 'config\general.yaml'
    $port = '5000'
    if (Test-Path $configPath) {
        $match = Select-String -Path $configPath -Pattern '^ui_port:\s*(\d+)' | Select-Object -First 1
        if ($match -and $match.Matches.Count -gt 0) {
            $port = $match.Matches[0].Groups[1].Value
        }
    }
    return "http://127.0.0.1:$port"
}

function Get-ActiveUrl {
    if (Test-Path $script:RuntimeInfoPath) {
        try {
            $info = Get-Content $script:RuntimeInfoPath -Raw | ConvertFrom-Json
            if ($info.url) {
                return [string]$info.url
            }
        } catch {
        }
    }
    return Get-ConfiguredUrl
}

function Compress-PathForDisplay {
    param(
        [string]$Path,
        [int]$MaxLength = 52
    )

    if ([string]::IsNullOrWhiteSpace($Path) -or $Path.Length -le $MaxLength) {
        return $Path
    }

    $leaf = Split-Path $Path -Leaf
    $parent = Split-Path $Path -Parent
    if (-not $parent) {
        return $Path.Substring(0, $MaxLength - 3) + '...'
    }

    $prefix = '...' + [IO.Path]::DirectorySeparatorChar
    $tail = Split-Path $parent -Leaf
    $candidate = "$prefix$tail$([IO.Path]::DirectorySeparatorChar)$leaf"
    if ($candidate.Length -le $MaxLength) {
        return $candidate
    }

    $trimmedLeaf = if ($leaf.Length -gt ($MaxLength - 8)) { $leaf.Substring(0, $MaxLength - 11) + '...' } else { $leaf }
    return "$prefix$trimmedLeaf"
}

function Pad-Line {
    param(
        [string]$Text,
        [int]$Width = 58
    )

    $safe = [string]$Text
    if ($safe.Length -gt $Width) {
        $safe = $safe.Substring(0, $Width - 3) + '...'
    }
    return $safe.PadRight($Width)
}

# Write a single banner row: borders in Cyan, inner text in $TextColor.
function Write-BannerLine {
    param(
        [string]$Text,
        [ConsoleColor]$TextColor = [ConsoleColor]::White
    )
    $padded = Pad-Line $Text
    Write-Host '| ' -ForegroundColor Cyan -NoNewline
    Write-Host $padded -ForegroundColor $TextColor -NoNewline
    Write-Host ' |' -ForegroundColor Cyan
}

function Show-Banner {
    param(
        [string]$Dots = '.'
    )

    $uptime    = [DateTime]::Now - $script:SessionStart
    $uptimeText = "{0}:{1:00}:{2:00}" -f [int]$uptime.TotalHours, $uptime.Minutes, $uptime.Seconds
    $urlText   = Get-ActiveUrl
    $rootText  = Compress-PathForDisplay -Path $RootDir -MaxLength 50
    $logText   = Compress-PathForDisplay -Path $script:RuntimeLogPath -MaxLength 48

    # First draw: record the row so subsequent draws overwrite in place (no flicker).
    if ($script:BannerTopRow -lt 0) {
        $script:BannerTopRow = [Console]::CursorTop
    } else {
        try {
            [Console]::CursorVisible = $false
            [Console]::SetCursorPosition(0, $script:BannerTopRow)
        } catch {}
    }

    Write-Host '+------------------------------------------------------------+' -ForegroundColor Cyan
    Write-BannerLine 'Viva Engage Tools Server' White
    Write-Host '+------------------------------------------------------------+' -ForegroundColor Cyan
    Write-BannerLine "URL: $urlText"  White
    Write-BannerLine "Root: $rootText" Gray
    Write-BannerLine "Session: $($script:SessionStart.ToString('yyyy-MM-dd HH:mm:ss'))" DarkGray
    Write-BannerLine "Uptime: $uptimeText   Restarts: $script:RestartCount" DarkGray
    Write-BannerLine "Logs: $logText" DarkGray
    Write-Host '+------------------------------------------------------------+' -ForegroundColor Cyan
    Write-Host ''
    Write-Host ("Status: " + $script:StatusBase + $Dots).PadRight(70) -ForegroundColor $script:StatusColor
    [Console]::CursorVisible = $true
}

function Start-ServerProcess {
    Ensure-RuntimeDirectory

    if (Test-Path $script:RuntimeInfoPath) {
        Remove-Item $script:RuntimeInfoPath -Force -ErrorAction SilentlyContinue
    }

    $pythonExe = Join-Path $RootDir '.venv\Scripts\python.exe'
    if (-not (Test-Path $pythonExe)) {
        throw "Python executable not found at $pythonExe"
    }

    $stdoutLog = Join-Path $RootDir '.runtime\server.out.log'
    $stderrLog = $script:RuntimeLogPath

    $proc = Start-Process -FilePath $pythonExe -ArgumentList '-m', 'src.ui' -WorkingDirectory $RootDir -PassThru -WindowStyle Hidden -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog
    Add-ProcessToJob -ProcessId $proc.Id -JobHandle $script:JobHandle
    return $proc
}

Clear-Host

# Clean up any stale state from a previous session that may have been killed mid-restart.
Remove-Item (Join-Path $RootDir 'restart.flag') -Force -ErrorAction SilentlyContinue
$env:JAMPY_SKIP_BROWSER = ''

while ($true) {
    $server = Start-ServerProcess
    $global:CurrentServerPid = $server.Id
    $script:StatusBase = 'Server running'
    $script:StatusColor = 'Green'
    $frameIndex = 0

    while (-not $server.HasExited) {
        Show-Banner -Dots $script:DotFrames[$frameIndex]
        Start-Sleep -Seconds 1
        $frameIndex = ($frameIndex + 1) % $script:DotFrames.Count
        $server.Refresh()

        # restart.flag is our primary restart signal. Don't wait for HasExited —
        # kill the process ourselves if it hasn't gone away yet, then break.
        if (Test-Path (Join-Path $RootDir 'restart.flag')) {
            if (-not $server.HasExited) {
                try { $server.Kill() } catch {}
                $server.WaitForExit(3000) | Out-Null
            }
            break
        }
    }

    if (Test-Path (Join-Path $RootDir 'restart.flag')) {
        $restartMode = 'restart'
        try {
            $restartMode = (Get-Content (Join-Path $RootDir 'restart.flag') -Raw).Trim()
        } catch {
            $restartMode = 'restart'
        }
        Remove-Item (Join-Path $RootDir 'restart.flag') -Force -ErrorAction SilentlyContinue

        if ($restartMode -eq 'restart:no-browser') {
            $env:JAMPY_SKIP_BROWSER = '1'
            $script:StatusBase = 'Restarting (reconnecting current tab)'
        } else {
            $env:JAMPY_SKIP_BROWSER = ''
            $script:StatusBase = 'Restarting'
        }

        $script:StatusColor = 'Yellow'
        $script:RestartCount += 1
        Show-Banner -Dots '...'
        Start-Sleep -Milliseconds 900
        continue
    }

    $script:StatusBase = 'Server stopped'
    $script:StatusColor = 'Yellow'
    $global:CurrentServerPid = $null
    Show-Banner -Dots '.'
    break
}

Read-Host 'Press Enter to exit'