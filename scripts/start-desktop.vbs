Set shell = CreateObject("WScript.Shell")
projectRoot = "D:\MyProject\extention summary meeting"
shell.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & projectRoot & "\scripts\start-desktop.ps1"""", 0, False
