$ws = New-Object -ComObject WScript.Shell
$startupPath = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Startup)
$shortcutPath = Join-Path $startupPath "ODOCUST_Agent.lnk"
$shortcut = $ws.CreateShortcut($shortcutPath)
$shortcut.TargetPath = "C:\Users\haseeb\OneDrive\Desktop\web\start_background.vbs"
$shortcut.WorkingDirectory = "C:\Users\haseeb\OneDrive\Desktop\web"
$shortcut.Description = "ODOCUST Academic Monitor Background Service"
$shortcut.Save()
Write-Host "Shortcut created at $shortcutPath"
