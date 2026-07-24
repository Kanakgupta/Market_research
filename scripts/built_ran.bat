@echo off
setlocal
REM Compatibility launcher for older/typo command name.
call "%~dp0BUILD_RUN.bat" %*
exit /b %ERRORLEVEL%
