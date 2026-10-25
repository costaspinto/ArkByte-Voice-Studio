@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0STOP ARKBYTE VOICE STUDIO WEB.ps1"
pause
endlocal
