# Read-only local diagnostic. Never claims a raster has been analysed.
param(
  [string]$ApiUrl = 'http://127.0.0.1:8000',
  [string]$FrontendUrl = 'http://127.0.0.1:3000'
)
$ErrorActionPreference = 'Stop'
Write-Host ''
Write-Host 'PLANEXUS AI / LOCAL SYSTEM CHECK' -ForegroundColor Cyan
Write-Host 'This does not deploy anything or modify saved projects.'
Write-Host ''
$fail = 0

function Test-Endpoint([string]$Label, [string]$Url) {
  try {
    $result = Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec 8
    if ($null -eq $result) { throw 'Empty response' }
    Write-Host ('[OK] ' + $Label) -ForegroundColor Green
    return $result
  }
  catch {
    Write-Host ('[FAIL] ' + $Label + ': ' + $_.Exception.Message) -ForegroundColor Red
    return $null
  }
}

try {
  $front = Invoke-WebRequest -Uri $FrontendUrl -Method Get -UseBasicParsing -TimeoutSec 8
  if ($front.StatusCode -ge 200 -and $front.StatusCode -lt 400) {
    Write-Host '[OK] Next.js frontend HTTP reachable' -ForegroundColor Green
  } else {
    Write-Host '[FAIL] Next.js frontend returned an unexpected HTTP status.' -ForegroundColor Red
    $fail++
  }
} catch {
  Write-Host '[FAIL] Next.js frontend offline: Start START-PLANEXUS.bat first.' -ForegroundColor Red
  $fail++
}

$health = Test-Endpoint 'FastAPI /api/health' ($ApiUrl + '/api/health')
if ($null -eq $health) {
  Write-Host 'GIS backend is OFFLINE. No DEM, slope, elevation, project save or GPP API available.' -ForegroundColor Yellow
  $fail++
} elseif ($health.status -ne 'ok') {
  Write-Host '[FAIL] Backend health is not OK.' -ForegroundColor Red
  $fail++
} else {
  Write-Host (' Storage: ' + $health.storage + ' / persistent=' + $health.persistent)
  if ($health.persistent -ne $true) {
    Write-Host ' Local writable data folder only. Cloud persistence is NOT verified.' -ForegroundColor Yellow
  }
  if ($health.public_multiuser_ready -ne $true) {
    Write-Host ' Security: private single-user build, NOT public multi-user ready.' -ForegroundColor Yellow
  }
  $projects = Test-Endpoint 'Saved project registry' ($ApiUrl + '/api/projects')
  if ($null -eq $projects) {
    $fail++
  } else {
    Write-Host (' Saved project records accessible: ' + @($projects.projects).Count)
  }
  $analyses = Test-Endpoint 'Saved GIS report registry' ($ApiUrl + '/api/analyses')
  if ($null -eq $analyses) {
    $fail++
  } else {
    Write-Host (' Saved reports indexed: ' + @($analyses.analyses).Count)
  }
  $policy = Test-Endpoint 'Official-source GPP registry API' ($ApiUrl + '/api/policy/catalog')
  if ($null -eq $policy -or @($policy.sources).Count -lt 1) {
    Write-Host '[FAIL] No indexed policy sources returned.' -ForegroundColor Red
    $fail++
  } else {
    Write-Host (' GPP reference sources indexed/catalogued: ' + @($policy.sources).Count)
  }
  $copilot = Test-Endpoint 'Copilot capabilities' ($ApiUrl + '/api/copilot/capabilities')
  if ($null -eq $copilot) { $fail++ }
}

Write-Host ''
if ($fail -eq 0) {
  Write-Host 'READ-ONLY API CHECKS PASSED.' -ForegroundColor Green
  Write-Host 'Next: test Create Project > Boundary > DEM > Slope/Elevation > Save > Reopen in browser.'
  Write-Host 'This check does NOT validate actual Copernicus availability, site data accuracy or PBT rules.'
  exit 0
}
Write-Host ('SYSTEM CHECK FAILED (' + $fail + ' problem(s)).') -ForegroundColor Red
Write-Host 'Start PLANEXUS via START-PLANEXUS.bat and keep backend/frontend terminals open.'
exit 1
