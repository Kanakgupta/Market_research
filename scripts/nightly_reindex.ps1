# Daily refresh for IoT Wireless Intel report.
# Trigger from Windows Task Scheduler before 6:00 AM Pacific.
$ErrorActionPreference = 'Continue'
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

"--- step 2/3: stage generated data + docs only ---" | Tee-Object -FilePath $log -Append
git add -A data docs *>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) {
    throw "step 2 failed (exit $LASTEXITCODE): git add -A data docs"
}

"--- step 3/3: commit + push when changes exist ---" | Tee-Object -FilePath $log -Append
$changes = git status --porcelain
if ([string]::IsNullOrWhiteSpace($changes)) {
    "No changes detected. Nothing to commit/push." | Tee-Object -FilePath $log -Append
}
else {
    $changes | Tee-Object -FilePath $log -Append | Out-Null
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm'

    git commit -m "auto update $stamp" *>&1 | Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) {
        throw "step 3 commit failed (exit $LASTEXITCODE): git commit"
    }

    git push origin main *>&1 | Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) {
        throw "step 3 push failed (exit $LASTEXITCODE): git push origin main"
    }
}

"=== Finished $(Get-Date -Format o) ===" | Tee-Object -FilePath $log -Append

# Keep only the last 14 daily logs
Get-ChildItem $logDir -Filter 'daily_*.log' |
    Sort-Object LastWriteTime -Descending |
    Select-Object -Skip 14 |
    Remove-Item -Force -ErrorAction SilentlyContinue
