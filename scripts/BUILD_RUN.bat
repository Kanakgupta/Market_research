@echo on
REM ============================================================
REM  BUILD_RUN.bat
REM  1) Start local server on http://localhost:5005
REM  2) Start background updater:
REM        - if last successful update is older than 8h, run now
REM        - then run every 6 hours
REM  3) Open local website UI in browser
REM  4) Updater keeps looping forever and does:
REM        - fetches the latest data
REM        - rebuilds the local site
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
echo  STEP 1/4  Start local server on http://localhost:5005 SKIPPED
echo ============================================================
REM start "IoT Local Server (5005)" cmd /k %PYTHON% run.py server --host 127.0.0.1 --port 5005 --docs-dir "%ROOT%\docs"

echo Waiting a few seconds for the server to come up...
timeout /t 2 /nobreak >nul

echo.
echo ============================================================
echo  STEP 2/4  Start background updater (8h stale check + every 6 hours)
echo ============================================================
start "AIROC Update Loop" "%POWERSHELL%" -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\update_loop.ps1" -IntervalHours 6 -RunNowIfStale -StaleHours 8

echo.
echo ============================================================
echo  STEP 3/4  Open local website UI at localhost SKIPPED
echo ============================================================
REM IF EXIST "%CHROME%" (
REM    start "" "%CHROME%" "http://localhost:5005"
REM ) ELSE (
REM    echo [WARN] Chrome not found at "%CHROME%". Opening in default browser...
REM    start "" "http://localhost:5005"
REM )

echo.
echo ============================================================
echo  STEP 4/4  Services running
echo ============================================================

echo.
echo Done.
echo OFF  - "IoT Local Server (5005)" serves docs on http://localhost:5005
echo   - "AIROC Update Loop" runs now only if stale ^(older than 8h^), then every 6 hours
echo   - Each update cycle: fetch/build via run.py, then git add/commit/push
echo OFF Refresh the browser tab after the updater logs "Cycle finished" to see latest HTML.
echo Close the server/update windows to stop the long-running services.
echo Press any key to exit this launcher.
pause >nul
