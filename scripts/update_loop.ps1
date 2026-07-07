<#
    update_loop.ps1
    ------------------------------------------------------------
    Daily background updater for IoT Wireless Intel.

    Behavior:
      - Optional immediate cycle if data is stale (default threshold: 8 hours)
      - Then runs one cycle daily at configured Pacific hour (default: 6 AM)

    Each cycle does:
      1) Fetch/update data + rebuild local site (python run.py)
      2) Stage, commit, and push to GitHub (if changes exist)
#>
param(
    [int]$RunHourPacific = 6,
    [switch]$RunNow,
    [switch]$RunNowIfStale,
    [int]$StaleHours = 8
)

$ErrorActionPreference = 'Continue'

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { $Python = 'python' }

$LogDir = Join-Path $Root 'logs'
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }
$Log = Join-Path $LogDir 'update_loop.log'

$StateDir = Join-Path $Root 'data'
if (-not (Test-Path $StateDir)) { New-Item -ItemType Directory -Path $StateDir | Out-Null }
$StateFile = Join-Path $StateDir 'auto_update_state.json'

function Write-Log([string]$msg) {
    $line = '[{0}] {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
    Write-Host $line
    Add-Content -Path $Log -Value $line
}

function Invoke-LoggedCommand([string]$stepMsg, [string]$cmdText, [scriptblock]$cmdBlock) {
    Write-Log $stepMsg
    Write-Log ("CMD> " + $cmdText)
    & $cmdBlock 2>&1 | Tee-Object -FilePath $Log -Append
    if ($LASTEXITCODE -ne 0) {
        Write-Log ("Command failed with exit code $LASTEXITCODE")
    }
    return $LASTEXITCODE
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
    try {
        Invoke-LoggedCommand 'STEP 1/3  Fetch latest data + rebuild local site (run.py)' "$Python run.py" { & $Python run.py } | Out-Null

        Invoke-LoggedCommand 'STEP 2/3  Stage changes (git add -A)' 'git add -A' { git add -A } | Out-Null

        Write-Log 'Checking pending changes before commit...'
        Write-Log 'CMD> git status --porcelain'
        $changes = git status --porcelain
        if (-not [string]::IsNullOrWhiteSpace($changes)) {
            $changes | Tee-Object -FilePath $Log -Append | Out-Null
        }

        if ([string]::IsNullOrWhiteSpace($changes)) {
            Write-Log 'No changes to push this cycle.'
        }
        else {
            $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm'
            Invoke-LoggedCommand 'STEP 3/3  Commit changes' ('git commit -m "auto update ' + $stamp + '"') { git commit -m "auto update $stamp" } | Out-Null
            Invoke-LoggedCommand 'Push changes to remote (origin/main)...' 'git push origin main' { git push origin main } | Out-Null

            if ($LASTEXITCODE -eq 0) {
                Write-Log 'Pushed update to GitHub.'
            }
            else {
                Write-Log "git push failed (exit $LASTEXITCODE) - check credentials. Will retry next cycle."
            }
        }

        if ($LASTEXITCODE -eq 0) {
            Write-StateSuccess
        }
    }
    catch {
        Write-Log ('ERROR: ' + $_.Exception.Message)
    }

    $elapsed = (Get-Date) - $cycleStart
    Write-Log ('Cycle finished in {0:N1} min.' -f $elapsed.TotalMinutes)
}

Write-Log "update_loop started (daily at ${RunHourPacific}:00 Pacific). Root=$Root Python=$Python"

if ($RunNow) {
    Write-Log 'RunNow requested - running one cycle immediately.'
    Invoke-UpdateCycle
}

if ($RunNowIfStale) {
    if (Test-IsStale -hours $StaleHours) {
        Write-Log "RunNowIfStale requested - data is stale (>= ${StaleHours}h). Running one cycle now."
        Invoke-UpdateCycle
    }
    else {
        Write-Log "RunNowIfStale requested - data is fresh (< ${StaleHours}h). Skipping immediate cycle."
    }
}

while ($true) {
    $secs = Get-SecondsUntilNextRun -hour $RunHourPacific
    $when = (Get-Date).AddSeconds($secs)
    Write-Log ('Next update at {0:yyyy-MM-dd HH:mm} local ({1:N1} h away, = {2}:00 Pacific).' -f $when, ($secs / 3600), $RunHourPacific)
    Start-Sleep -Seconds $secs
    Invoke-UpdateCycle
}
