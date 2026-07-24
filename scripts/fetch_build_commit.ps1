<#
    fetch_build_commit.ps1
    ------------------------------------------------------------
    One-shot automation for:
      1) sync latest code (fast-forward only)
      2) fetch latest data + rebuild site
      3) commit and push to GitHub

    Usage:
      powershell.exe -ExecutionPolicy Bypass -File C:\guptakanak\AI_Agents\Marketing\Research\scripts\fetch_build_commit.ps1

      powershell.exe -ExecutionPolicy Bypass -File C:\guptakanak\AI_Agents\Marketing\Research\scripts\fetch_build_commit.ps1 -CommitMessage "daily auto update"

      powershell.exe -ExecutionPolicy Bypass -File C:\guptakanak\AI_Agents\Marketing\Research\scripts\fetch_build_commit.ps1 -SkipGitPull
#>

param(
    [string]$CommitMessage,
    [switch]$SkipGitPull
)

$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) {
    throw "Virtual environment Python not found: $Python"
}

function Write-Log([string]$Message) {
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Write-Host "[$stamp] $Message"
}

function Invoke-Step([string]$Step, [scriptblock]$Command) {
    Write-Log $Step
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "Step failed (exit code $LASTEXITCODE): $Step"
    }
}

if (-not $SkipGitPull) {
    Invoke-Step 'Fetching origin/main...' { git fetch origin main }
    # Fast-forward only keeps history clean and avoids merge commits in automation.
    Invoke-Step 'Pulling latest code (fast-forward only)...' { git pull --ff-only origin main }
}
else {
    Write-Log 'SkipGitPull enabled. Proceeding with local branch state.'
}

Invoke-Step 'Running full pipeline: latest fetch + build (python run.py --max-age-days 10)...' { & $Python run.py --max-age-days 10 }

Invoke-Step 'Staging changes (git add -A)...' { git add -A }

$changes = git status --porcelain
if ([string]::IsNullOrWhiteSpace($changes)) {
    Write-Log 'No changes detected after build. Nothing to commit or push.'
    exit 0
}

if ([string]::IsNullOrWhiteSpace($CommitMessage)) {
    $CommitMessage = 'auto update ' + (Get-Date -Format 'yyyy-MM-dd HH:mm')
}

Invoke-Step ("Committing changes: $CommitMessage") { git commit -m $CommitMessage }
Invoke-Step 'Pushing to origin/main...' { git push origin main }

Write-Log 'Done. Latest data fetched, site built, committed, and pushed.'