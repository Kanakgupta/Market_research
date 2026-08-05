# Daily refresh for IoT Wireless Intel report.
# Trigger from Windows Task Scheduler at 6:00 AM Pacific.
$ErrorActionPreference = 'Stop'
# In PowerShell 7+, avoid converting native stderr lines into terminating errors.
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}
$root = 'C:\guptakanak\AI_Agents\Marketing\Research'
Set-Location $root

$lockPath = Join-Path $root 'data\daily_update.lock'
$lockTtlHours = 6
$runStartedAt = Get-Date

if (Test-Path $lockPath) {
    try {
        $lockText = Get-Content -Path $lockPath -Raw -ErrorAction Stop
        $lockObj = $lockText | ConvertFrom-Json
        $lockTime = if ($lockObj.started_at) { [DateTime]::Parse($lockObj.started_at) } else { (Get-Item $lockPath).LastWriteTime }
        $ageHours = ((Get-Date) - $lockTime).TotalHours
        if ($ageHours -lt $lockTtlHours) {
            Write-Host ("Another daily refresh is already in progress (lock age {0:N2}h). Exiting." -f $ageHours)
            exit 0
        }
        Write-Host ("Stale lock detected (age {0:N2}h). Removing stale lock." -f $ageHours)
    }
    catch {
        Write-Host "Unable to parse existing lock file. Removing lock and continuing."
    }
    Remove-Item -Path $lockPath -Force -ErrorAction SilentlyContinue
}

@{
    started_at = $runStartedAt.ToString('o')
    machine = $env:COMPUTERNAME
    user = $env:USERNAME
    pid = $PID
} | ConvertTo-Json | Set-Content -Path $lockPath -Encoding UTF8

$venvPython = Join-Path $root '.venv\Scripts\python.exe'
$pythonCmd = if (Test-Path $venvPython) { $venvPython } else { 'python' }

Write-Host "=== Daily refresh started $(Get-Date -Format o) ==="
try {
    # Rebuild the multi-tab report with fresh news/customers/competitors/research
    # pulled from the web (default mode = with --external + --enrich).
    Write-Host '--- step 1/4: regenerate report (web pull) ---'
    & $pythonCmd run.py --max-age-days 10
    if ($LASTEXITCODE -ne 0) {
        throw "step 1 failed (exit $LASTEXITCODE): $pythonCmd run.py --max-age-days 10"
    }

    Write-Host '--- step 2/4: verify critical outputs exist ---'
    $criticalDocs = @(
        'docs\index.html',
        'docs\news.html',
        'docs\opportunity.html',
        'docs\threat.html',
        'docs\relationships.html',
        'docs\technology.html',
        'docs\applications.html',
        'docs\bt_stack.html',
        'docs\customers.html',
        'docs\competitors.html'
    )
    foreach ($relativePath in $criticalDocs) {
        $fullPath = Join-Path $root $relativePath
        if (-not (Test-Path $fullPath)) {
            throw "Missing expected output: $relativePath"
        }
    }

    Write-Host '--- step 3/4: stage generated data + docs only ---'
    git add -A data docs
    if ($LASTEXITCODE -ne 0) {
        throw "step 3 failed (exit $LASTEXITCODE): git add -A data docs"
    }

    Write-Host '--- step 4/4: commit + push when changes exist ---'
    $changes = git status --porcelain
    if ([string]::IsNullOrWhiteSpace($changes)) {
        Write-Host 'No changes detected. Nothing to commit/push.'
    }
    else {
        $changes | ForEach-Object { Write-Host $_ }
        $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm'

        git commit -m "auto update $stamp"
        if ($LASTEXITCODE -ne 0) {
            throw "step 4 commit failed (exit $LASTEXITCODE): git commit"
        }

        git push origin main
        if ($LASTEXITCODE -ne 0) {
            Write-Host 'Push failed on first attempt. Syncing with remote and retrying...'
            git pull --rebase origin main
            if ($LASTEXITCODE -ne 0) {
                throw "step 4 pull --rebase failed (exit $LASTEXITCODE): git pull --rebase origin main"
            }
            git push origin main
            if ($LASTEXITCODE -ne 0) {
                throw "step 4 push retry failed (exit $LASTEXITCODE): git push origin main"
            }
        }
    }

    Write-Host "=== Finished $(Get-Date -Format o) ==="
}
finally {
    Remove-Item -Path $lockPath -Force -ErrorAction SilentlyContinue
}
