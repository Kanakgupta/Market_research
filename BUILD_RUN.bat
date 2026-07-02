@echo off
REM ============================================================
REM  BUILD_RUN.bat
REM  1) Start ONE local server (report + AI) on localhost:5005
REM  2) Open the UI in the browser
REM  3) Start a 6-hour loop that:
REM        - fetches the latest data
REM        - rebuilds the local site (localhost reflects updates)
REM        - pushes the updates to GitHub
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
echo  STEP 1/3  Start local server on http://localhost:5005
echo ============================================================
start "AIROC Unified Server" cmd /k "%PYTHON% run.py ai --no-open"

echo Waiting a few seconds for the server to come up...
timeout /t 4 /nobreak >nul

echo.
echo ============================================================
echo  STEP 2/3  Open the UI at http://localhost:5005
echo ============================================================
IF EXIST "%CHROME%" (
    start "" "%CHROME%" "http://localhost:5005"
) ELSE (
    echo [WARN] Chrome not found at "%CHROME%". Opening in default browser...
    start "" "http://localhost:5005"
)

echo.
echo ============================================================
echo  STEP 3/3  Start daily 4 AM Pacific update (fetch - build - push)
echo ============================================================
start "AIROC Update Loop" "%POWERSHELL%" -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\update_loop.ps1" -RunHourPacific 4

echo.
echo Done.
echo   - "AIROC Unified Server" window serves http://localhost:5005 (report + AI)
echo   - "AIROC Update Loop" window rebuilds data and pushes to GitHub once a day
echo     at 4:00 AM California time.
echo Close those two windows to stop the server / updates.
echo Press any key to exit this launcher.
pause >nul
