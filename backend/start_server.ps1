# start_server.ps1
# Automatically frees port 8000, then starts the backend cleanly.

Write-Host "Checking for processes on port 8000..." -ForegroundColor Cyan

$connections = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue

if ($connections) {
    foreach ($conn in $connections) {
        Write-Host "Killing PID $($conn.OwningProcess)..." -ForegroundColor Yellow
        Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
    Write-Host "Port 8000 cleared." -ForegroundColor Green
} else {
    Write-Host "Port 8000 was already free." -ForegroundColor Green
}

Write-Host "Starting uvicorn..." -ForegroundColor Cyan
uvicorn main:app --port 8000