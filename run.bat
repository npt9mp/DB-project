@echo off
cd /d "%~dp0"

echo Starting Nail Salon...
echo Open browser to: http://127.0.0.1:5000
echo Login: admin / admin123
echo Press Ctrl+C to stop
echo.

python app.py

pause
