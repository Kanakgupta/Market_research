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

Write-Host "=== Daily refresh started $(Get-Date -Format o) ==="

# Rebuild the multi-tab report with fresh news/customers/competitors/research
# pulled from the web (default mode = with --external + --enrich).
Write-Host '--- step 1/1: regenerate report (web pull) ---'
& $pythonCmd run.py --max-age-days 10
if ($LASTEXITCODE -ne 0) {
    throw "step 1 failed (exit $LASTEXITCODE): $pythonCmd run.py --max-age-days 10"
}

Write-Host '--- step 2/3: stage generated data + docs only ---'
git add -A data docs
if ($LASTEXITCODE -ne 0) {
    throw "step 2 failed (exit $LASTEXITCODE): git add -A data docs"
}

Write-Host '--- step 3/3: commit + push when changes exist ---'
$changes = git status --porcelain
if ([string]::IsNullOrWhiteSpace($changes)) {
    Write-Host 'No changes detected. Nothing to commit/push.'
}
else {
    $changes | ForEach-Object { Write-Host $_ }
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm'

    git commit -m "auto update $stamp"
    if ($LASTEXITCODE -ne 0) {
        throw "step 3 commit failed (exit $LASTEXITCODE): git commit"
    }

    git push origin main
    if ($LASTEXITCODE -ne 0) {
        throw "step 3 push failed (exit $LASTEXITCODE): git push origin main"
    }
}

Write-Host "=== Finished $(Get-Date -Format o) ==="
