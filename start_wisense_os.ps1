# WiSense OS One-Click Desktop Launcher
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Set-Location $ScriptDir

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "         WiSense OS Launcher            " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$EnginePort = 5050

function Test-EngineHealth {
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:$EnginePort/api/v1/health" -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Show-OnboardDiagnostics {
    Write-Host ""
    Write-Host "[i] Onboard diagnostics" -ForegroundColor Yellow

    # Git
    $git = Get-Command git -ErrorAction SilentlyContinue
    if ($git) {
        Write-Host "  [+] git: $($git.Source)" -ForegroundColor Green
    } else {
        Write-Host "  [!] git: not found on PATH (scoped commits will stay uncommitted)" -ForegroundColor DarkYellow
    }

    # Disk space on project drive
    try {
        $drive = (Get-Item $ScriptDir).PSDrive.Name
        $freeGb = [math]::Round((Get-PSDrive $drive).Free / 1GB, 1)
        Write-Host "  [+] disk ${drive}: ${freeGb} GB free" -ForegroundColor Green
    } catch {
        Write-Host "  [!] disk: could not read free space" -ForegroundColor DarkYellow
    }

    # Ollama loopback
    try {
        $tags = Invoke-WebRequest -Uri "http://127.0.0.1:11434/api/tags" -UseBasicParsing -TimeoutSec 2
        if ($tags.StatusCode -eq 200) {
            Write-Host "  [+] Ollama: reachable on 127.0.0.1:11434" -ForegroundColor Green
        }
    } catch {
        Write-Host "  [!] Ollama: not reachable (cloud models via Ollama will fail until it is up)" -ForegroundColor DarkYellow
    }

    # Engine diagnostics (auth if token present)
    try {
        $headers = @{}
        $tokenFile = Join-Path $env:LOCALAPPDATA "WiSenseOS\engine.token"
        if (Test-Path $tokenFile) {
            $token = (Get-Content $tokenFile -Raw).Trim()
            if ($token) { $headers["Authorization"] = "Bearer $token" }
        }
        $diag = Invoke-RestMethod -Uri "http://127.0.0.1:$EnginePort/api/v1/diagnostics" -Headers $headers -TimeoutSec 3
        Write-Host "  [+] engine: $($diag.engine.status) v$($diag.engine.version)" -ForegroundColor Green
        if ($diag.cloud_assisted_only) {
            Write-Host "  [i] cloud-assisted only — use Ask Before Changes (Autopilot/Offline locked)" -ForegroundColor Cyan
        }
    } catch {
        Write-Host "  [!] engine diagnostics unavailable yet" -ForegroundColor DarkYellow
    }
    Write-Host ""
}

# Stop stale listener only when health fails
if (-not (Test-EngineHealth)) {
    Get-NetTCPConnection -LocalPort $EnginePort -ErrorAction SilentlyContinue | ForEach-Object {
        Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Milliseconds 500
}

if (Test-EngineHealth) {
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

Show-OnboardDiagnostics

# Launch Flutter Desktop Client
$ClientDir = Join-Path $ScriptDir "client"
Write-Host "[i] Launching WiSense OS Client..." -ForegroundColor Yellow
Set-Location $ClientDir
flutter run -d windows
