@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0BUILD ARKBYTE VOICE STUDIO WEB.ps1"
if errorlevel 1 (
  echo.
  echo Production build failed. Read the error above and check the logs folder.
  pause
  exit /b 1
)
pause
endlocal
