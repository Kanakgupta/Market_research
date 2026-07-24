@echo on
REM ============================================================
REM  BUILD_RUN.bat
REM  1) Start background updater:
REM        - run one cycle immediately now
REM        - run once daily at 12:00 AM Pacific
REM  2) Updater keeps looping forever and does:
REM        - fetches the latest data
REM        - rebuilds the local site
REM        - pushes the updates to GitHub
REM
REM  Usage:  double-click  OR  run from any directory:
REM          "C:\guptakanak\AI_Agents\Marketing\Research\BUILD_RUN.bat"
REM ============================================================

SET ROOT=C:\guptakanak\AI_Agents\Marketing\Research
SET PYTHON=%ROOT%\.venv\Scripts\python.exe
SET POWERSHELL=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe

REM -- fall back to system python if venv does not exist
IF NOT EXIST "%PYTHON%" SET PYTHON=python

cd /d "%ROOT%"

echo.
echo ============================================================
echo  STEP 1/1  Start updater (run now, then daily at 12:00 AM Pacific)
echo ============================================================
echo Updater will run in this window. Press Ctrl+C to stop.
"%POWERSHELL%" -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\update_loop.ps1" -RunHourPacific 0 -RunNow
IF ERRORLEVEL 1 (
	echo.
	echo ============================================================
	echo  UPDATER STOPPED WITH ERROR. See red log lines above.
	echo ============================================================
	pause
)
