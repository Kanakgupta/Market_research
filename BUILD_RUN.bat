@echo off
REM ============================================================
REM  BUILD_RUN.bat
REM  Start one local server for report + AI on localhost:5005,
REM  then trigger background refresh (non-blocking).
REM
REM  Usage:  double-click  OR  run from any directory:
REM          "C:\guptakanak\AI_Agents\Marketing\Research\BUILD_RUN.bat"
REM ============================================================

SET ROOT=C:\guptakanak\AI_Agents\Marketing\Research
SET PYTHON=%ROOT%\.venv\Scripts\python.exe
SET CHROME=C:\Program Files\Google\Chrome\Application\chrome.exe
SET POWERSHELL=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe

REM -- fall back to system python if venv does not exist
IF NOT EXIST "%PYTHON%" SET PYTHON=python

cd /d "%ROOT%"

echo.
echo ============================================================
echo  STEP 0/3  Ensure daily refresh schedule (4:45 AM Pacific)
echo ============================================================
"%POWERSHELL%" -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\setup_daily_task.ps1" -StartTime 04:45
IF ERRORLEVEL 1 (
    echo [WARN] Could not ensure daily Task Scheduler job - continuing anyway...
)

echo.
echo ============================================================
echo  STEP 1/3  Start single local server on http://localhost:5005
echo ============================================================
start "AIROC Unified Server" cmd /k "%PYTHON% run.py ai --no-open"

echo.
echo ============================================================
echo  STEP 2/3  Trigger background full refresh (non-blocking)
echo ============================================================
timeout /t 3 /nobreak >nul
"%POWERSHELL%" -NoProfile -Command "try { Invoke-WebRequest -Uri 'http://localhost:5005/api/refresh-full' -Method POST -UseBasicParsing | Out-Null; Write-Host '[OK] Background refresh started.' } catch { Write-Host '[WARN] Could not trigger background refresh now.' }"

echo.
echo ============================================================
echo  STEP 3/3  Open unified UI at http://localhost:5005
echo ============================================================
IF EXIST "%CHROME%" (
    start "" "%CHROME%" "http://localhost:5005"
) ELSE (
    echo [WARN] Chrome not found at "%CHROME%". Opening in default browser...
    start "" "http://localhost:5005"
)

echo.
echo Done. Use http://localhost:5005 for report and AI chat.
echo The server keeps running in its own window.
echo Press any key to exit this launcher.
pause >nul
