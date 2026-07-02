<#
    update_loop.ps1
    ------------------------------------------------------------
    Daily background updater for IoT Wireless Intel.

    Once per day at 04:00 America/Los_Angeles (California) it:
      1. Fetches latest data + rebuilds the AI index   (run.py ai-nightly)
      2. Rebuilds the local site so localhost reflects  (run.py)
      3. Commits tracked changes and pushes to GitHub   (git push origin main)

    It waits until the next 4 AM Pacific, runs one cycle, then waits for the
    following 4 AM Pacific, and so on.

    Started automatically by BUILD_RUN.bat; can also be run manually:
      powershell -NoProfile -ExecutionPolicy Bypass -File scripts\update_loop.ps1
    Optional: -RunNow  runs one cycle immediately before entering the daily wait.
#>
param(
    [int]$RunHourPacific = 4,
    [switch]$RunNow
)

$ErrorActionPreference = 'Continue'

# Repo root = parent of this script's folder
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { $Python = 'python' }

$LogDir = Join-Path $Root 'logs'
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }
$Log = Join-Path $LogDir 'update_loop.log'

function Write-Log([string]$msg) {
    $line = '[{0}] {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
    Write-Host $line
    Add-Content -Path $Log -Value $line
}

function Get-PacificTimeZone {
    foreach ($id in @('Pacific Standard Time', 'America/Los_Angeles')) {
        try { return [System.TimeZoneInfo]::FindSystemTimeZoneById($id) } catch { }
    }
    return $null
}

function Get-SecondsUntilNextRun([int]$hour) {
    $tz = Get-PacificTimeZone
    $nowLocal = Get-Date
    if ($null -eq $tz) {
        # Fallback: treat the hour as local time if Pacific zone is unavailable.
        $target = $nowLocal.Date.AddHours($hour)
        if ($nowLocal -ge $target) { $target = $target.AddDays(1) }
        return [math]::Max(1, ($target - $nowLocal).TotalSeconds)
    }
    $nowPac = [System.TimeZoneInfo]::ConvertTime($nowLocal, $tz)
    $targetPac = $nowPac.Date.AddHours($hour)
    if ($nowPac -ge $targetPac) { $targetPac = $targetPac.AddDays(1) }
    $targetPacUnspecified = [DateTime]::SpecifyKind($targetPac, [System.DateTimeKind]::Unspecified)
    $targetLocal = [System.TimeZoneInfo]::ConvertTime($targetPacUnspecified, $tz, [System.TimeZoneInfo]::Local)
    return [math]::Max(1, ($targetLocal - $nowLocal).TotalSeconds)
}

function Invoke-UpdateCycle {
    $cycleStart = Get-Date
    try {
        Write-Log 'STEP 1/3  Fetch latest data + rebuild AI index (run.py ai-nightly)'
        & $Python run.py ai-nightly *>&1 | Add-Content -Path $Log

        Write-Log 'STEP 2/3  Rebuild local site so localhost reflects updates (run.py)'
        & $Python run.py *>&1 | Add-Content -Path $Log

        Write-Log 'STEP 3/3  Commit + push updates to GitHub'
        git add -A *>&1 | Out-Null
        $changes = git status --porcelain
        if ([string]::IsNullOrWhiteSpace($changes)) {
            Write-Log 'No changes to push this cycle.'
        }
        else {
            $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm'
            git commit -m "auto update $stamp" *>&1 | Add-Content -Path $Log
            git push origin main *>&1 | Add-Content -Path $Log
            if ($LASTEXITCODE -eq 0) { Write-Log 'Pushed update to GitHub.' }
            else { Write-Log "git push failed (exit $LASTEXITCODE) - check credentials. Will retry next day." }
        }
    }
    catch {
        Write-Log ('ERROR: ' + $_.Exception.Message)
    }
    $elapsed = (Get-Date) - $cycleStart
    Write-Log ('Cycle finished in {0:N1} min.' -f $elapsed.TotalMinutes)
}

Write-Log "update_loop started (daily at ${RunHourPacific}:00 Pacific). Root=$Root Python=$Python"

if ($RunNow) {
    Write-Log 'RunNow requested - running one cycle immediately.'
    Invoke-UpdateCycle
}

while ($true) {
    $secs = Get-SecondsUntilNextRun -hour $RunHourPacific
    $when = (Get-Date).AddSeconds($secs)
    Write-Log ('Next update at {0:yyyy-MM-dd HH:mm} local ({1:N1} h away, = {2}:00 Pacific).' -f $when, ($secs / 3600), $RunHourPacific)
    Start-Sleep -Seconds $secs
    Invoke-UpdateCycle
}
