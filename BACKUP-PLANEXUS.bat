@echo off
setlocal
cd /d "%~dp0"
title PLANEXUS AI - Private GIS Backup
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\backup-planexus.ps1"
echo.
pause
endlocal
