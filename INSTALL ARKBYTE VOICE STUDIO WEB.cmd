@echo off
setlocal
cd /d "%~dp0"
echo =============================================
echo ARKBYTE VOICE STUDIO WEB - FULL INSTALLATION
echo =============================================
echo This installs the web app, local Python bridge and Chatterbox AI dependencies.
echo The first AI model download happens when the first narration is generated.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALL_WEB_WINDOWS.ps1" -InstallAI
if errorlevel 1 (
  echo.
  echo Installation failed. Read the recovery instructions above and check the logs folder.
  pause
  exit /b 1
)
echo.
echo Installation completed. Run START ARKBYTE VOICE STUDIO WEB.cmd to launch.
pause
endlocal
