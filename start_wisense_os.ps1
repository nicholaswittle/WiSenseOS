# WiSense OS One-Click Desktop Launcher
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Set-Location $ScriptDir

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "         WiSense OS Launcher            " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$EnginePort = 5050

function Test-EngineFullHealth {
    try {
        $headers = @{}
        $tokenFile = Join-Path $env:LOCALAPPDATA "WiSenseOS\engine.token"
        if (Test-Path $tokenFile) {
            $token = (Get-Content $tokenFile).Trim()
            if ($token) {
                $headers["Authorization"] = "Bearer $token"
            }
        }
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:$EnginePort/api/v1/telemetry" -Headers $headers -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

# Stop stale engine if running without latest AIOS endpoints
if (-not (Test-EngineFullHealth)) {
    Get-NetTCPConnection -LocalPort $EnginePort -ErrorAction SilentlyContinue | ForEach-Object {
        Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Milliseconds 500
}

if (Test-EngineFullHealth) {
    Write-Host "[+] WiSense Engine is active on http://127.0.0.1:$EnginePort" -ForegroundColor Green
} else {
    Write-Host "[i] Starting local WiSense Engine on http://127.0.0.1:$EnginePort..." -ForegroundColor Yellow
    $VenvPython = Join-Path $ScriptDir ".venv\Scripts\python.exe"
    $RunEngine = Join-Path $ScriptDir "run_engine.py"
    
    if (-not (Test-Path $VenvPython)) {
        Write-Host "[!] Virtual environment python not found at $VenvPython" -ForegroundColor Red
        exit 1
    }
    
    Start-Process -FilePath $VenvPython -ArgumentList "$RunEngine" -WindowStyle Hidden
    Write-Host "[+] WiSense Engine background process launched." -ForegroundColor Green
}

Write-Host "[i] Waiting for Engine health..." -ForegroundColor Yellow
$deadline = (Get-Date).AddSeconds(30)
$healthy = $false
while ((Get-Date) -lt $deadline) {
    if (Test-EngineFullHealth) {
        $healthy = $true
        break
    }
    Start-Sleep -Milliseconds 500
}

if (-not $healthy) {
    Write-Host "[!] Engine did not become healthy within 30 seconds." -ForegroundColor Red
    exit 1
}
Write-Host "[+] Engine health confirmed." -ForegroundColor Green

# Launch Flutter Desktop Client
$ClientDir = Join-Path $ScriptDir "client"
Write-Host "[i] Launching WiSense OS Client..." -ForegroundColor Yellow
Set-Location $ClientDir
flutter run -d windows
