# Daily refresh for IoT Wireless Intel report.
# Trigger from Windows Task Scheduler before 6:00 AM Pacific.
$ErrorActionPreference = 'Stop'
# In PowerShell 7+, avoid converting native stderr lines into terminating errors.
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}
$root = 'C:\guptakanak\AI_Agents\Marketing\Research'
Set-Location $root

$venvPython = Join-Path $root '.venv\Scripts\python.exe'
$pythonCmd = if (Test-Path $venvPython) { $venvPython } else { 'python' }

$logDir = Join-Path $root 'logs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$log = Join-Path $logDir ("daily_{0}.log" -f (Get-Date -Format 'yyyyMMdd_HHmmss'))

"=== Daily refresh started $(Get-Date -Format o) ===" | Tee-Object -FilePath $log

# Rebuild the multi-tab report with fresh news/customers/competitors/research
# pulled from the web (default mode = with --external + --enrich).
"--- step 1/1: regenerate report (web pull) ---" | Tee-Object -FilePath $log -Append
& $pythonCmd run.py *>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) {
    throw "step 1 failed (exit $LASTEXITCODE): $pythonCmd run.py"
}

"=== Finished $(Get-Date -Format o) ===" | Tee-Object -FilePath $log -Append

# Keep only the last 14 daily logs
Get-ChildItem $logDir -Filter 'daily_*.log' |
    Sort-Object LastWriteTime -Descending |
    Select-Object -Skip 14 |
    Remove-Item -Force -ErrorAction SilentlyContinue
