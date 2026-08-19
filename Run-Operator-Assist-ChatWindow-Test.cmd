@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%Run-Operator-Assist-ChatWindow-Test.ps1"
exit /b %errorlevel%
