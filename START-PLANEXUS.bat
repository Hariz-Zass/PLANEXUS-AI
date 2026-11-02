@echo off
setlocal
cd /d "%~dp0"
title PLANEXUS AI - One Click Launcher
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-planexus.ps1"
if errorlevel 1 (
  echo.
  echo PLANEXUS tidak berjaya dimulakan. Sila ambil gambar ralat di atas.
  pause
)
endlocal
