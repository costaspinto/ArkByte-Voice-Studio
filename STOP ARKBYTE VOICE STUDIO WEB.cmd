@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0STOP ARKBYTE VOICE STUDIO WEB.ps1" %*
if errorlevel 1 (
  echo.
  echo ArkByte could not be fully stopped. Review the message above.
  pause
  exit /b 1
)
endlocal
