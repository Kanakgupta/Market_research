@echo off
REM ============================================================
REM  BUILD_RUN.bat
REM  Fetch latest data, build the HTML research site, start the
REM  AI chat server, then open both in Chrome.
REM
REM  Usage:  double-click  OR  run from any directory:
REM          "C:\guptakanak\AI_Agents\Marketing\Research\BUILD_RUN.bat"
REM ============================================================

SET ROOT=C:\guptakanak\AI_Agents\Marketing\Research
SET PYTHON=%ROOT%\.venv\Scripts\python.exe
SET CHROME="C:\Program Files\Google\Chrome\Application\chrome.exe"
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
echo  STEP 1/3  Rebuild AI index (local docs + web enrichment)
echo ============================================================
"%PYTHON%" run.py ai-nightly
IF ERRORLEVEL 1 (
    echo [WARN] ai-nightly step had errors - continuing anyway...
)

echo.
echo ============================================================
echo  STEP 2/3  Start AI chat server on http://localhost:5005
echo ============================================================
start "AIROC AI Server" cmd /k "%PYTHON% run.py ai --no-open"

REM Give the AI server a moment to bind its port
timeout /t 3 /nobreak >nul

echo.
echo ============================================================
echo  STEP 3/3  Build HTML site and serve on http://127.0.0.1:8888/index.html
echo            (Chrome will open automatically)
echo ============================================================

REM Open AI chat in Chrome now (site server starts next)
start "" %CHROME% "http://localhost:5005"

REM Build site + serve + open index.html in default browser
"%PYTHON%" scripts\Build_open_site.py --host 127.0.0.1 --port 8888 --page index.html

echo.
echo Done. Press any key to exit.
pause >nul
