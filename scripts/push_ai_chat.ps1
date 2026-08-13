<#
    push_ai_chat.ps1
    ------------------------------------------------------------
    Commit + push the reusable HerAI chat repo (sibling AI_Chat folder) when its
    sources have changed. Safe no-op when there are no changes or the repo/remote
    is not set up. Called by the Research build/push scripts so both repos stay in
    sync ("respective gits updated based on the changes").
#>
param(
    [string]$CommitMessage
)

$ErrorActionPreference = 'Continue'
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}

# scripts -> Research -> Marketing ; the chat repo is Marketing\AI_Chat
$marketing = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$aiChat = Join-Path $marketing 'AI_Chat'

if (-not (Test-Path (Join-Path $aiChat '.git'))) {
    Write-Host "AI_Chat git repo not found at $aiChat; skipping chat push."
    return
}

Push-Location $aiChat
try {
    git add -A | Out-Null
    $changes = git status --porcelain
    if ([string]::IsNullOrWhiteSpace($changes)) {
        Write-Host 'AI_Chat: no changes to commit/push.'
        return
    }
    if ([string]::IsNullOrWhiteSpace($CommitMessage)) {
        $CommitMessage = 'auto update ' + (Get-Date -Format 'yyyy-MM-dd HH:mm')
    }
    Write-Host "AI_Chat: committing changes ($CommitMessage)"
    git commit -m $CommitMessage
    # Prefer local on conflict so automated builds never block on merges.
    git pull -X ours --no-edit origin main
    git push origin main
    Write-Host 'AI_Chat: pushed changes to HerAI.'
}
finally {
    Pop-Location
}
