# Keep the interactive local report server running and restart it if it exits.
#
# Recommended Task Scheduler action:
#   powershell.exe -ExecutionPolicy Bypass -File C:\guptakanak\AI_Agents\Marketing\Research\scripts\run_site_24x7.ps1

$ErrorActionPreference = 'Continue'
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}

$root = 'C:\guptakanak\AI_Agents\Marketing\Research'
Set-Location $root

$venvPython = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPython)) {
    throw "Virtual environment Python not found: $venvPython"
}

while ($true) {
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Write-Host "[$stamp] starting site server"
    # Build from current local snapshot so first load has valid docs before interactive refreshes.
    & $venvPython run.py site-dev --output-dir docs
    & $venvPython run.py server --host 127.0.0.1 --port 8888 --docs-dir docs
    $code = $LASTEXITCODE
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Write-Host "[$stamp] site server exited with code $code; restarting in 10 seconds"
    Start-Sleep -Seconds 10
}