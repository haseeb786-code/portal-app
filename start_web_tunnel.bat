@echo off
title ODOCUST Public Web Tunnel
echo ===================================================
echo     ODOCUST Public Cloudflare Web Tunnel
echo ===================================================
echo.
echo Creating secure public HTTPS link for your dashboard...
cloudflared.exe tunnel --url http://127.0.0.1:8000 --no-autoupdate
pause
