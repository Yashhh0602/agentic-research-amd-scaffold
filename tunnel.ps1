while ($true) {
    Write-Host "Starting SSH tunnel..." -ForegroundColor Yellow
    ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -L 0.0.0.0:8001:localhost:8000 root@36.150.116.206 -p 31122
    Write-Host "Tunnel dropped, reconnecting in 3s..." -ForegroundColor Red
    Start-Sleep -Seconds 3
}