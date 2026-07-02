# Daily refresh for AIROC AI assistant + IoT Wireless Intel report.
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

# Pull persisted user env vars (set during one-time setup)
$gem = [Environment]::GetEnvironmentVariable('GEMINI_API_KEY','User')
$paths = [Environment]::GetEnvironmentVariable('AI_EXTRA_DOC_PATHS','User')
if ($gem)   { $env:GEMINI_API_KEY     = $gem }
if ($paths) { $env:AI_EXTRA_DOC_PATHS = $paths }

# Full coverage for nightly run (no PDF page cap, larger files allowed)
$env:AI_MAX_PDF_PAGES = '100000'
$env:AI_MAX_FILE_MB   = '200'
$env:AI_INDEX_WORKERS = '8'

$logDir = Join-Path $root 'logs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$log = Join-Path $logDir ("daily_{0}.log" -f (Get-Date -Format 'yyyyMMdd_HHmmss'))

"=== Daily refresh started $(Get-Date -Format o) ===" | Tee-Object -FilePath $log

# 1) Reindex local docs + enrich AI knowledge base from the web
"--- step 1/2: AI index + web enrichment ---" | Tee-Object -FilePath $log -Append
& $pythonCmd run.py ai-nightly *>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) {
    throw "step 1 failed (exit $LASTEXITCODE): $pythonCmd run.py ai-nightly"
}

# 2) Rebuild the multi-tab report with fresh news/customers/competitors/research
#    pulled from the web (default mode = with --external + --enrich).
"--- step 2/2: regenerate report (web pull) ---" | Tee-Object -FilePath $log -Append
& $pythonCmd run.py *>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) {
    throw "step 2 failed (exit $LASTEXITCODE): $pythonCmd run.py"
}

# Prune older site_* report folders, keep most recent 5
Get-ChildItem (Join-Path $root 'output') -Directory -Filter 'site_*' |
    Sort-Object LastWriteTime -Descending |
    Select-Object -Skip 5 |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

"=== Finished $(Get-Date -Format o) ===" | Tee-Object -FilePath $log -Append

# Keep only the last 14 daily logs
Get-ChildItem $logDir -Filter 'daily_*.log' |
    Sort-Object LastWriteTime -Descending |
    Select-Object -Skip 14 |
    Remove-Item -Force -ErrorAction SilentlyContinue
# Also clean up any old reindex_*.log left from the previous schedule
Get-ChildItem $logDir -Filter 'reindex_*.log' -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -Skip 5 |
    Remove-Item -Force -ErrorAction SilentlyContinue
