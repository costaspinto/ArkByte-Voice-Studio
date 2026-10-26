@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0START ARKBYTE VOICE STUDIO WEB.ps1" %*
if errorlevel 1 (
  echo.
  echo ArkByte did not start. Review the message and logs folder.
  pause
  exit /b 1
)
endlocal
