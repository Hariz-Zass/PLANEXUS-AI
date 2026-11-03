# Explicit opt-in; daily 02:00 LOCAL TIME, interactive user only.
param([switch]$Remove)
$ErrorActionPreference = 'Stop'
$name = 'PLANEXUS-GIS-Verified-Backup'
if ($Remove) {
  Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction Stop
  Write-Host ('Removed Task Scheduler entry: ' + $name) -ForegroundColor Green
  exit 0
}
$root = Split-Path -Parent $PSScriptRoot
$worker = Join-Path $PSScriptRoot 'auto-backup-planexus.ps1'
$python = Join-Path $root 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
  throw 'Run START-PLANEXUS.bat and configure Python first.'
}
$hostPowerShell = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
$action = New-ScheduledTaskAction -Execute $hostPowerShell -Argument ('-NoProfile -ExecutionPolicy Bypass -File "' + $worker + '" -Scheduled') -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Daily -At '02:00'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Principal $principal -Description 'Private PLANEXUS GIS daily verified archive; only when user is logged in' -Force | Out-Null
Write-Host 'Backup schedule installed: 02:00 daily while signed in.' -ForegroundColor Green
Write-Host 'Laptop must be on and user must be logged in. An unscheduled missed run is NOT a backup.' -ForegroundColor Yellow
Write-Host 'Verify actual backups using python -m app.backup_scheduler status.' -ForegroundColor Yellow
