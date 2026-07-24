<#
    update_loop.ps1
    ------------------------------------------------------------
        Background updater for IoT Wireless Intel.

    Behavior:
      - Optional immediate cycle if data is stale (default threshold: 8 hours)
            - Then runs either:
                    * every N hours (when -IntervalHours > 0), or
                    * daily at configured Pacific hour (default: 6 AM)

    Each cycle does:
      1) Fetch/update data + rebuild local site (python run.py)
      2) Stage, commit, and push to GitHub (if changes exist)
#>
param(
    [int]$RunHourPacific = 6,
    [int]$IntervalHours = 0,
    [switch]$RunNow,
    [switch]$RunNowIfStale,
    [int]$StaleHours = 8
)

$ErrorActionPreference = 'Continue'

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { $Python = 'python' }

$StateDir = Join-Path $Root 'data'
if (-not (Test-Path $StateDir)) { New-Item -ItemType Directory -Path $StateDir | Out-Null }
$StateFile = Join-Path $StateDir 'auto_update_state.json'

function Write-Log([string]$msg) {
    $line = '[{0}] {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
    Write-Host $line
}

function Write-Fail([string]$msg) {
    $line = '[{0}] {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
    Write-Host $line -ForegroundColor Red
}

function Write-Success([string]$msg) {
    $line = '[{0}] {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
    Write-Host $line -ForegroundColor Green
}

function Invoke-LoggedCommand([string]$stepMsg, [string]$cmdText, [scriptblock]$cmdBlock) {
    Write-Log $stepMsg
    Write-Log ("CMD> " + $cmdText)
    # Capture all streams from native commands so informational stderr output
    # (for example python logging) does not get treated as a PowerShell failure.
    $output = & $cmdBlock *>&1
    $exitCode = $LASTEXITCODE

    if ($output) {
        foreach ($line in @($output)) {
            Write-Log ("OUT> " + ($line.ToString().TrimEnd()))
        }
    }

    if ($exitCode -ne 0) {
        Write-Fail "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        Write-Fail ("FAIL: Command failed with exit code $exitCode")
        Write-Fail ("FAIL: " + $cmdText)
        Write-Fail "Updater halted so the failure is visible and can be fixed."
        Write-Fail "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        throw "Command failed with exit code $exitCode"
    }
    return $exitCode
}

function Get-PacificTimeZone {
    foreach ($id in @('Pacific Standard Time', 'America/Los_Angeles')) {
        try { return [System.TimeZoneInfo]::FindSystemTimeZoneById($id) } catch { }
    }
    return $null
}

function Get-SecondsUntilNextRun([int]$hour) {
    $tz = Get-PacificTimeZone
    $nowLocal = Get-Date

    if ($null -eq $tz) {
        $target = $nowLocal.Date.AddHours($hour)
        if ($nowLocal -ge $target) { $target = $target.AddDays(1) }
        return [math]::Max(1, ($target - $nowLocal).TotalSeconds)
    }

    $nowPac = [System.TimeZoneInfo]::ConvertTime($nowLocal, $tz)
    $targetPac = $nowPac.Date.AddHours($hour)
    if ($nowPac -ge $targetPac) { $targetPac = $targetPac.AddDays(1) }

    $targetPacUnspecified = [DateTime]::SpecifyKind($targetPac, [System.DateTimeKind]::Unspecified)
    $targetLocal = [System.TimeZoneInfo]::ConvertTime($targetPacUnspecified, $tz, [System.TimeZoneInfo]::Local)
    return [math]::Max(1, ($targetLocal - $nowLocal).TotalSeconds)
}

function Write-StateSuccess {
    $state = @{
        last_success_utc   = (Get-Date).ToUniversalTime().ToString('o')
        last_success_local = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
        stale_hours        = $StaleHours
        run_hour_pacific   = $RunHourPacific
        interval_hours     = $IntervalHours
    }
    try {
        $state | ConvertTo-Json | Set-Content -Path $StateFile -Encoding UTF8
    }
    catch {
        Write-Log ('WARN: unable to write state file: ' + $_.Exception.Message)
    }
}

function Get-LastSuccessUtc {
    if (-not (Test-Path $StateFile)) { return $null }
    try {
        $obj = Get-Content -Path $StateFile -Raw | ConvertFrom-Json
        if (-not $obj.last_success_utc) { return $null }
        return [DateTime]::Parse($obj.last_success_utc).ToUniversalTime()
    }
    catch {
        Write-Log ('WARN: failed to parse state file; treating as stale. ' + $_.Exception.Message)
        return $null
    }
}

function Test-IsStale([int]$hours) {
    $last = Get-LastSuccessUtc
    if ($null -eq $last) { return $true }
    $ageH = ((Get-Date).ToUniversalTime() - $last).TotalHours
    Write-Log ('Last successful update age: {0:N2} hours (threshold {1}h)' -f $ageH, $hours)
    return ($ageH -ge $hours)
}

function Invoke-UpdateCycle {
    $cycleStart = Get-Date
    Invoke-LoggedCommand 'STEP 1/3  Fetch latest data + rebuild local site (run.py --max-age-days 10 -v)' "$Python -u run.py --max-age-days 10 -v" { & $Python -u run.py --max-age-days 10 -v } | Out-Null

    Invoke-LoggedCommand 'STEP 2/3  Stage changes (git add -A)' 'git add -A' { git add -A } | Out-Null

    Write-Log 'Checking pending changes before commit...'
    Write-Log 'CMD> git status --porcelain'
    $changes = git status --porcelain
    if (-not [string]::IsNullOrWhiteSpace($changes)) {
        $changes | ForEach-Object { Write-Log ("OUT> " + $_) }
    }

    if ([string]::IsNullOrWhiteSpace($changes)) {
        Write-Log 'No changes to push this cycle.'
    }
    else {
        $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm'
        Invoke-LoggedCommand 'STEP 3/3  Commit changes' ('git commit -m "auto update ' + $stamp + '"') { git commit -m "auto update $stamp" } | Out-Null
        Invoke-LoggedCommand 'Push changes to remote (origin/main)...' 'git push origin main' { git push origin main } | Out-Null
        Write-Log 'Pushed update to GitHub.'
    }

    Write-StateSuccess

    $elapsed = (Get-Date) - $cycleStart
    Write-Log ('Cycle finished in {0:N1} min.' -f $elapsed.TotalMinutes)
    Write-Success "============================================================"
    Write-Success "SUCCESS: Fetch/build/push cycle completed cleanly."
    Write-Success "============================================================"
}

Write-Log "update_loop started. Root=$Root Python=$Python"
if ($IntervalHours -gt 0) {
    Write-Log "Interval mode enabled: run every ${IntervalHours} hour(s)."
}
else {
    Write-Log "Schedule mode enabled: run daily at ${RunHourPacific}:00 Pacific."
}

if ($RunNow) {
    Write-Log 'RunNow requested - running one cycle immediately.'
    try {
        Invoke-UpdateCycle
    }
    catch {
        Write-Fail "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        Write-Fail ('HALT: updater stopped during startup run: ' + $_.Exception.Message)
        Write-Fail "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        exit 1
    }
}

if ($RunNowIfStale) {
    if (Test-IsStale -hours $StaleHours) {
        Write-Log "RunNowIfStale requested - data is stale (>= ${StaleHours}h). Running one cycle now."
        try {
            Invoke-UpdateCycle
        }
        catch {
            Write-Fail "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
            Write-Fail ('HALT: updater stopped during stale-start run: ' + $_.Exception.Message)
            Write-Fail "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
            exit 1
        }
    }
    else {
        Write-Log "RunNowIfStale requested - data is fresh (< ${StaleHours}h). Skipping immediate cycle."
    }
}

while ($true) {
    if ($IntervalHours -gt 0) {
        $secs = [int][math]::Max(60, $IntervalHours * 3600)
        $when = (Get-Date).AddSeconds($secs)
        Write-Log ('Next update at {0:yyyy-MM-dd HH:mm} local ({1:N1} h away, every {2}h mode).' -f $when, ($secs / 3600), $IntervalHours)
    }
    else {
        $secs = Get-SecondsUntilNextRun -hour $RunHourPacific
        $when = (Get-Date).AddSeconds($secs)
        Write-Log ('Next update at {0:yyyy-MM-dd HH:mm} local ({1:N1} h away, = {2}:00 Pacific).' -f $when, ($secs / 3600), $RunHourPacific)
    }
    Start-Sleep -Seconds $secs
    try {
        Invoke-UpdateCycle
    }
    catch {
        Write-Fail "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        Write-Fail ('HALT: updater stopped due to failure: ' + $_.Exception.Message)
        Write-Fail "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        exit 1
    }
}
