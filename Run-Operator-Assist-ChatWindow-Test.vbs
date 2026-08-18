Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
pythonw = "C:\Users\79615\AppData\Local\Programs\Python\Python310\pythonw.exe"
shell.Run """" & pythonw & """ """ & scriptDir & "\operator_assist_chat_window_test.py""", 0, False
