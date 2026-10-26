@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALL VOXCPM MODELS.ps1"
if errorlevel 1 (
  echo.
  echo Optional VoxCPM setup was not completed. Review the message above.
  pause
  exit /b 1
)
pause
endlocal
