# WiSense OS One-Click Desktop Launcher
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Set-Location $ScriptDir

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "         WiSense OS Launcher            " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Check if Engine is running on port 5050
$EnginePort = 5050
$IsEngineRunning = $false

try {
    $Tcp = New-Object System.Net.Sockets.TcpClient
    $Tcp.Connect("127.0.0.1", $EnginePort)
    $Tcp.Close()
    $IsEngineRunning = $true
} catch {
    $IsEngineRunning = $false
}

if ($IsEngineRunning) {
    Write-Host "[+] WiSense Engine is already active on http://127.0.0.1:$EnginePort" -ForegroundColor Green
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

function Test-EngineHealth {
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:$EnginePort/api/v1/health" -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

Write-Host "[i] Waiting for Engine health..." -ForegroundColor Yellow
$deadline = (Get-Date).AddSeconds(30)
$healthy = $false
while ((Get-Date) -lt $deadline) {
    if (Test-EngineHealth) {
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
