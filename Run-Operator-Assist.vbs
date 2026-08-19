Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
launcher = fso.BuildPath(scriptDir, "Run-Operator-Assist.ps1")
command = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & launcher & """"
shell.Run command, 0, False
