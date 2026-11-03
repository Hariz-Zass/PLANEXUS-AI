# Opt-in Windows Task Scheduler worker. PowerShell 5.1 compatible.
param([switch]$Scheduled)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root 'backend\.venv\Scripts\python.exe'
$folder = Join-Path $root 'private-backups\automatic'
if (-not (Test-Path -LiteralPath $python)) {
  Write-Error 'PLANEXUS Python .venv not found. Run START-PLANEXUS.bat once.'
  exit 1
}
if (-not (Test-Path -LiteralPath $folder)) {
  New-Item -ItemType Directory -Path $folder -Force | Out-Null
}
Push-Location (Join-Path $root 'backend')
try {
  & $python -m app.backup_scheduler once --output-dir $folder --keep 14
  if ($LASTEXITCODE -ne 0) { throw 'Automated GIS snapshot failed. Existing archives were not pruned.' }
  if (-not $Scheduled) {
    Write-Host 'Verified automatic backup created. See private-backups\automatic.' -ForegroundColor Green
    Write-Host 'Archive is NOT encrypted or offsite. Copy to protected independent storage.' -ForegroundColor Yellow
  }
} finally { Pop-Location }
