# Keep the local report server running and restart it if it exits.
#
# Recommended Task Scheduler action:
#   powershell.exe -ExecutionPolicy Bypass -File C:\guptakanak\AI_Agents\Marketing\Research\scripts\run_site_24x7.ps1

$ErrorActionPreference = 'Stop'
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}

$root = 'C:\guptakanak\AI_Agents\Marketing\Research'
Set-Location $root

$venvPython = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPython)) {
    throw "Virtual environment Python not found: $venvPython"
}

$logDir = Join-Path $root 'logs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

$currentLog = Join-Path $logDir 'site_24x7_current.log'

while ($true) {
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    "[$stamp] starting site server" | Tee-Object -FilePath $currentLog -Append
    & $venvPython scripts/Build_open_site.py --host 127.0.0.1 --port 8888 --page index.html --no-browser *>&1 |
        Tee-Object -FilePath $currentLog -Append
    $code = $LASTEXITCODE
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    "[$stamp] site server exited with code $code; restarting in 10 seconds" | Tee-Object -FilePath $currentLog -Append
    Start-Sleep -Seconds 10
}