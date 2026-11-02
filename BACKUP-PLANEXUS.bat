@echo off
setlocal
cd /d "%~dp0"
title PLANEXUS AI - Workspace Backup
echo ============================================
echo  PLANEXUS AI - Local Projects Backup
echo ============================================
echo Stop PLANEXUS servers before backing up raster files.
echo The new ZIP file will be saved to the backups folder.
echo.
if not exist "backend\.venv\Scripts\python.exe" (
  echo [ERROR] Python virtual environment not found.
  echo Run START-PLANEXUS.bat first to set up the application.
  pause
  exit /b 1
)
cd backend
".venv\Scripts\python.exe" -m app.backup
if errorlevel 1 (
  echo.
  echo Backup did not complete. Review the error above.
  pause
  exit /b 1
)
echo.
echo Backup complete. Keep the ZIP private and store a copy elsewhere.
pause
endlocal
