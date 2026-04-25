# Nail Salon - Flask App Launcher
# Right-click and choose "Run with PowerShell"

Set-Location $PSScriptRoot

Write-Host ""
Write-Host "Starting Nail Salon app..." -ForegroundColor Green
Write-Host ">> Open your browser to: http://127.0.0.1:5000" -ForegroundColor Yellow
Write-Host ">> Login: admin / admin123" -ForegroundColor Yellow
Write-Host ">> Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""

python app.py

Read-Host "Press Enter to exit"
