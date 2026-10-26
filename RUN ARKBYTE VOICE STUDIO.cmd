@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0RUN ARKBYTE VOICE STUDIO.ps1" %*
if errorlevel 1 (
  echo.
  echo ArkByte checks or startup failed. Review the logs folder.
  pause
  exit /b 1
)
endlocal
