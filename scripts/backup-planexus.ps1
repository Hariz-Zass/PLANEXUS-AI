# PLANEXUS backup launcher; PowerShell 5.1, private single-user workflow.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root 'backend'
$python = Join-Path $backend '.venv\Scripts\python.exe'
$archiveDir = Join-Path $root 'private-backups'
try {
  Write-Host 'PLANEXUS - GIS PRIVATE BACKUP' -ForegroundColor Cyan
  if (-not (Test-Path $python)) {
    throw 'Python .venv not available. Run START-PLANEXUS.bat once and stop its server terminals.'
  }
  $apiListeners = @(Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue)
  if ($apiListeners.Count -gt 0) {
    throw 'Backend port 8000 still listening. Stop PLANEXUS backend before archiving raster files.'
  }
  New-Item -ItemType Directory -Path $archiveDir -Force | Out-Null
  Push-Location $backend
  try {
    & $python -m app.backup --output-dir $archiveDir
    if ($LASTEXITCODE -ne 0) { throw 'Backup creation/validation failed.' }
  } finally { Pop-Location }
  $latest = Get-ChildItem -LiteralPath $archiveDir -Filter 'PLANEXUS-backup-*.zip' -File |
    Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
  if ($null -eq $latest) { throw 'No backup archive generated.' }
  Write-Host ('VERIFIED: ' + $latest.FullName) -ForegroundColor Green
  Write-Host 'PRIVATE archive: copy off this PC into protected storage. No encryption/signature.' -ForegroundColor Yellow
} catch {
  Write-Host ('BACKUP FAILED: ' + $_.Exception.Message) -ForegroundColor Red
  exit 1
}
