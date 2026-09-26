@echo off
echo =======================================================
echo Setting up ODOCUST Monitor to run automatically on boot
echo =======================================================

set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT_VBS=%TEMP%\CreateShortcut.vbs"

echo Set oWS = WScript.CreateObject("WScript.Shell") > "%SHORTCUT_VBS%"
echo sLinkFile = "%STARTUP_DIR%\ODOCUST_Agent.lnk" >> "%SHORTCUT_VBS%"
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> "%SHORTCUT_VBS%"
echo oLink.TargetPath = "C:\Users\haseeb\OneDrive\Desktop\web\start_background.vbs" >> "%SHORTCUT_VBS%"
echo oLink.WorkingDirectory = "C:\Users\haseeb\OneDrive\Desktop\web" >> "%SHORTCUT_VBS%"
echo oLink.Description = "ODOCUST Academic Monitor Background Service" >> "%SHORTCUT_VBS%"
echo oLink.Save >> "%SHORTCUT_VBS%"

cscript /nologo "%SHORTCUT_VBS%"
del "%SHORTCUT_VBS%"

echo.
echo [SUCCESS] Auto-start configured!
echo The agent and dashboard (http://localhost:8000) will now start automatically whenever your laptop powers on.
echo.
pause
