# CloakChat - Start Script
# Starts backend (foreground) and frontend (background), cleans up on exit

$ErrorActionPreference = "Stop"
$ProjectDir = $PSScriptRoot
$BackendPort = 8012
$FrontendPort = 5173

Write-Host "`nStarting CloakChat" -ForegroundColor Cyan
Write-Host "========================"

# --- Prerequisites ---
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python not found. Install Python 3.12+" -ForegroundColor Red; exit 1
}
if (-not (Test-Path "$ProjectDir\.venv")) {
    Write-Host ".venv not found. Run: python -m venv .venv" -ForegroundColor Red; exit 1
}
if (-not (Get-Command bun -ErrorAction SilentlyContinue)) {
    Write-Host "Bun not found. Install from https://bun.sh" -ForegroundColor Red; exit 1
}

# --- Kill anything on our ports ---
function Kill-Port($Port) {
    $killed = $false
    $lines = netstat -ano | Select-String "`:$Port\s+.*LISTENING"
    foreach ($line in $lines) {
        $procId = ($line -split '\s+')[-1]
        if ($procId -and $procId -ne "0") {
            $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
            if ($proc) {
                Write-Host "  Killed $($proc.ProcessName) (PID: $procId) on port $Port" -ForegroundColor DarkYellow
                Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
                $killed = $true
            }
        }
    }
    if (-not $killed) {
        Write-Host "  Port $Port is free" -ForegroundColor DarkGray
    }
}

Write-Host "`nStopping previous instances..."
Kill-Port $BackendPort
Kill-Port $FrontendPort
Start-Sleep -Seconds 2

# --- Start Frontend (background process) ---
Write-Host "`nStarting frontend..."
$frontend = Start-Process -FilePath "bun" -ArgumentList "run dev" `
    -WorkingDirectory "$ProjectDir\frontend" `
    -WindowStyle Hidden -PassThru

# Wait for frontend to be listening
$ready = $false
for ($i = 0; $i -lt 10; $i++) {
    Start-Sleep -Milliseconds 500
    $check = netstat -ano | Select-String "`:$FrontendPort\s+.*LISTENING"
    if ($check) { $ready = $true; break }
}

if ($ready) {
    Write-Host "  Frontend running (PID: $($frontend.Id))" -ForegroundColor Green
    Write-Host "  App: http://localhost:$FrontendPort"
} else {
    Write-Host "  Frontend may not have started - check manually" -ForegroundColor Yellow
}

# --- Start Backend (foreground, logs visible) ---
Write-Host "`n========================"
Write-Host "BACKEND LOGS" -ForegroundColor Yellow
Write-Host "========================"
Write-Host "Press Ctrl+C to stop both servers.`n"

try {
    $env:PYTHONPATH = "$ProjectDir;$env:PYTHONPATH"
    & "$ProjectDir\.venv\Scripts\activate.ps1"
    & python "$ProjectDir\backend\main.py"
} finally {
    # Always runs - even on Ctrl+C
    Write-Host "`nShutting down..." -ForegroundColor Yellow
    if ($frontend -and -not $frontend.HasExited) {
        Stop-Process -Id $frontend.Id -Force -ErrorAction SilentlyContinue
    }
    Kill-Port $FrontendPort
    Kill-Port $BackendPort
    Write-Host "All servers stopped." -ForegroundColor Green
}
