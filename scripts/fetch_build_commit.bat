@echo off
setlocal

REM Launcher for scripts\fetch_build_commit.ps1
REM Usage examples:
REM   scripts\fetch_build_commit.bat
REM   scripts\fetch_build_commit.bat -CommitMessage "daily auto update"
REM   scripts\fetch_build_commit.bat -SkipGitPull

set "SCRIPT_DIR=%~dp0"
set "PS1=%SCRIPT_DIR%fetch_build_commit.ps1"
set "POWERSHELL=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"

echo [INFO] Starting fetch/build/commit pipeline...
echo [INFO] This can take several minutes depending on feed/API response times.

if not exist "%PS1%" (
  echo [ERROR] Script not found: "%PS1%"
  exit /b 1
)

if not exist "%POWERSHELL%" (
  set "POWERSHELL=pwsh"
)

"%POWERSHELL%" -NoProfile -ExecutionPolicy Bypass -File "%PS1%" %*
set "EXITCODE=%ERRORLEVEL%"

if not "%EXITCODE%"=="0" (
  echo [ERROR] fetch_build_commit.ps1 failed with exit code %EXITCODE%
  exit /b %EXITCODE%
)

echo [OK] fetch/build/commit/push completed.
exit /b 0
