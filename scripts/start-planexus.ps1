# PLANEXUS AI - Windows localhost launcher (PowerShell 5.1 compatible).
# Runs only on this computer. Never changes machine-wide execution policies.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$venv = Join-Path $backend '.venv'
$venvPython = Join-Path $venv 'Scripts\python.exe'

function Step([string]$message) {
  Write-Host "`n[PLANEXUS] $message" -ForegroundColor Cyan
}
function Check-Exit([string]$message) {
  if ($LASTEXITCODE -ne 0) { throw $message }
}
function Test-Http([string]$url) {
  try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 3
    return [int]$response.StatusCode -ge 200 -and [int]$response.StatusCode -lt 400
  } catch {
    return $false
  }
}
function Port-IsBusy([int]$port) {
  return @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue).Count -gt 0
}

try {
  Write-Host ''
  Write-Host '======================================' -ForegroundColor Green
  Write-Host ' PLANEXUS AI - TERRAIN INTELLIGENCE V1' -ForegroundColor Green
  Write-Host '======================================' -ForegroundColor Green
  Write-Host 'Local only | Backend 8000 | Dashboard 3000'

  Step '1/4 - Semak Node.js dan Python'
  if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    throw 'Node.js belum dipasang. Install Node.js 22+ daripada https://nodejs.org/ dan jalankan fail ini semula.'
  }
  if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    throw 'npm tidak dijumpai. Install semula Node.js daripada https://nodejs.org/.'
  }
  $nodeVersion = (& node --version).Trim()
  Check-Exit 'Tidak dapat menyemak versi Node.js.'
  $nodeMajor = [int](($nodeVersion.TrimStart('v')).Split('.')[0])
  if ($nodeMajor -lt 22) { throw "Node.js $nodeVersion terlalu lama. Install Node.js 22 atau lebih baharu." }

  $pythonCommand = $null
  $pythonSelector = $null
  if (Get-Command py -ErrorAction SilentlyContinue) {
    foreach ($candidate in @('3.12', '3.11')) {
      try {
        $version = & py "-$candidate" --version 2>$null
        if ($LASTEXITCODE -eq 0 -and ("$version" -match '^Python 3\.(11|12)\.')) {
          $pythonCommand = 'py'
          $pythonSelector = "-$candidate"
          break
        }
      } catch { }
    }
  }
  if (-not $pythonCommand -and (Get-Command python -ErrorAction SilentlyContinue)) {
    try {
      $version = & python --version 2>$null
      if ($LASTEXITCODE -eq 0 -and ("$version" -match '^Python 3\.(11|12)\.')) { $pythonCommand = 'python' }
    } catch { }
  }
  if (-not $pythonCommand) {
    throw 'Python 3.11 atau 3.12 belum dijumpai. Install dari https://www.python.org/downloads/ (pilih Add Python to PATH), kemudian cuba lagi.'
  }
  Write-Host "Node.js: $nodeVersion | Python: $version" -ForegroundColor Green

  if ((Port-IsBusy 8000) -or (Port-IsBusy 3000)) {
    throw 'Port 8000 atau 3000 sudah digunakan. Tutup terminal app lama dahulu, kemudian double-click START-PLANEXUS.bat semula.'
  }

  Step '2/4 - Sediakan backend GIS (Python)'
  if (-not (Test-Path $venvPython)) {
    if ($pythonSelector) {
      & $pythonCommand $pythonSelector -m venv $venv
    } else {
      & $pythonCommand -m venv $venv
    }
    Check-Exit 'Gagal membina Python virtual environment. Pastikan Python mempunyai pakej venv.'
  }
  $backendReady = $false
  try {
    & $venvPython -c 'import fastapi, uvicorn, rasterio, numpy, shapely, pyproj, httpx, openai, multipart' 2>$null
    $backendReady = $LASTEXITCODE -eq 0
  } catch { }
  if (-not $backendReady) {
    Push-Location $backend
    try {
      & $venvPython -m pip install --disable-pip-version-check -r requirements.txt
      Check-Exit 'Gagal install Python dependencies. Semak internet dan ralat pip di atas.'
    } finally { Pop-Location }
  }

  Step '3/4 - Sediakan dashboard (Next.js)'
  if (-not (Test-Path (Join-Path $frontend '.env.local'))) {
    Copy-Item (Join-Path $frontend '.env.example') (Join-Path $frontend '.env.local')
  }
  if (-not (Test-Path (Join-Path $frontend 'node_modules\next\package.json'))) {
    Push-Location $frontend
    try {
      & npm.cmd install --no-audit --no-fund
      Check-Exit 'Gagal install frontend dependencies. Semak sambungan internet dan ralat npm di atas.'
    } finally { Pop-Location }
  }

  Step '4/4 - Jalankan API dan dashboard'
  $powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
  $backendScript = Join-Path $PSScriptRoot 'run-backend.ps1'
  $frontendScript = Join-Path $PSScriptRoot 'run-frontend.ps1'
  $backendProc = Start-Process -FilePath $powershell -ArgumentList ('-NoProfile -NoExit -ExecutionPolicy Bypass -File "{0}"' -f $backendScript) -WorkingDirectory $root -PassThru
  $frontendProc = Start-Process -FilePath $powershell -ArgumentList ('-NoProfile -NoExit -ExecutionPolicy Bypass -File "{0}"' -f $frontendScript) -WorkingDirectory $root -PassThru

  Write-Host 'Memeriksa backend dan frontend. Jangan tutup dua terminal server yang baru dibuka.'
  $ready = $false
  for ($attempt = 1; $attempt -le 60; $attempt++) {
    if ($backendProc.HasExited -or $frontendProc.HasExited) { break }
    if ((Test-Http 'http://127.0.0.1:8000/api/health') -and (Test-Http 'http://127.0.0.1:3000')) {
      $ready = $true
      break
    }
    Start-Sleep -Seconds 2
  }
  if (-not $ready) {
    throw 'Server belum bersedia. Lihat mesej ralat dalam dua terminal PLANEXUS yang baru dibuka; jangan anggap analisis sudah berfungsi.'
  }
  Write-Host 'PLANEXUS berjalan! Membuka http://localhost:3000' -ForegroundColor Green
  Start-Process 'http://localhost:3000'
  Write-Host 'Untuk berhenti: tutup dua terminal server PLANEXUS.' -ForegroundColor Yellow
} catch {
  Write-Host "`n[RALAT] $($_.Exception.Message)" -ForegroundColor Red
  Write-Host 'Ambil screenshot mesej ini untuk diagnosis.' -ForegroundColor Yellow
  exit 1
}
