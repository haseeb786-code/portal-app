@echo off
title ODOCUST Academic Monitoring Agent
echo ===================================================
echo     ODOCUST Academic Monitoring & Notification Agent
echo ===================================================
echo.

if not exist .venv (
    echo [ERROR] Virtual environment .venv not found.
    pause
    exit /b 1
)

echo Starting ODOCUST Agent Daemon & Web Dashboard...
echo Open your browser at: http://127.0.0.1:8000
echo.
.venv\Scripts\python.exe main.py
pause
