@echo off
setlocal
cd /d "%~dp0"
title VideoSift - Build and Install
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build\build.ps1" %*
if errorlevel 1 (
  echo.
  echo BUILD FAILED. See the messages above.
  pause
  exit /b 1
)
echo.
pause
