Set WshShell = CreateObject("WScript.Shell")
' Run pythonw silently in background with no terminal window
WshShell.CurrentDirectory = "C:\Users\haseeb\OneDrive\Desktop\web"
WshShell.Run """C:\Users\haseeb\OneDrive\Desktop\web\.venv\Scripts\pythonw.exe"" main.py", 0, False
