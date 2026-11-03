@echo off
setlocal
cd /d "%~dp0"
title PLANEXUS AI - Local GIS System Check
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\check-planexus.ps1"
echo.
pause
endlocal
