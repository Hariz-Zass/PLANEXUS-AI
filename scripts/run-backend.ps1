# Launched in a dedicated terminal by start-planexus.ps1.
$ErrorActionPreference = 'Stop'
$host.UI.RawUI.WindowTitle = 'PLANEXUS AI - GIS Backend'
$root = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $root 'backend')
Write-Host 'PLANEXUS GIS Backend: http://localhost:8000/docs' -ForegroundColor Cyan
Write-Host 'Tutup window ini untuk hentikan backend.' -ForegroundColor Yellow
$env:PYTHONUNBUFFERED = '1'
& '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
if ($LASTEXITCODE -ne 0) {
  Write-Host '[RALAT] Backend tidak berjaya berjalan. Sila ambil screenshot output ini.' -ForegroundColor Red
}
