# Launched in a dedicated terminal by start-planexus.ps1.
$ErrorActionPreference = 'Stop'
$host.UI.RawUI.WindowTitle = 'PLANEXUS AI - Dashboard'
$root = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $root 'frontend')
Write-Host 'PLANEXUS Dashboard: http://localhost:3000' -ForegroundColor Cyan
Write-Host 'Tutup window ini untuk hentikan frontend.' -ForegroundColor Yellow
& npm.cmd run dev
if ($LASTEXITCODE -ne 0) {
  Write-Host '[RALAT] Dashboard tidak berjaya berjalan. Sila ambil screenshot output ini.' -ForegroundColor Red
}
