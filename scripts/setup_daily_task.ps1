# Ensure a Windows Task Scheduler job exists for daily data refresh.
# Default schedule: 04:45 local time (set machine timezone to Pacific for 6:00 AM PST readiness).

[CmdletBinding()]
param(
    [string]$TaskName = 'AIROC_Daily_Refresh',
    [string]$StartTime = '04:45'
)

$ErrorActionPreference = 'Stop'

$root = 'C:\guptakanak\AI_Agents\Marketing\Research'
$scriptPath = Join-Path $root 'scripts\nightly_reindex.ps1'
if (-not (Test-Path $scriptPath)) {
    throw "Missing script: $scriptPath"
}

if ($StartTime -notmatch '^(?:[01]\d|2[0-3]):[0-5]\d$') {
    throw "Invalid -StartTime '$StartTime'. Use HH:mm (24-hour), for example 04:45"
}

$tz = Get-TimeZone
if ($tz.Id -ne 'Pacific Standard Time') {
    Write-Warning "Current machine timezone is '$($tz.Id)'. For strict 6:00 AM Pacific behavior, set timezone to Pacific Standard Time."
}

$psExe = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
$taskCommand = '"{0}" -NoProfile -ExecutionPolicy Bypass -File "{1}"' -f $psExe, $scriptPath

$createArgs = @(
    '/Create',
    '/F',
    '/TN', $TaskName,
    '/SC', 'DAILY',
    '/ST', $StartTime,
    '/RL', 'LIMITED',
    '/TR', $taskCommand
)

& schtasks.exe @createArgs | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create/update task '$TaskName'"
}

Write-Host "Task '$TaskName' ensured at $StartTime daily."
Write-Host "Action: $taskCommand"
