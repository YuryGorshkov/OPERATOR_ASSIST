Set wsh = CreateObject("WScript.Shell")
windowTitle = WScript.Arguments(0)
pressEnter = LCase(WScript.Arguments(1))
If wsh.AppActivate(windowTitle) Then
  WScript.Sleep 350
  wsh.SendKeys "^v"
  WScript.Sleep 150
  If pressEnter = "true" Then
    wsh.SendKeys "{ENTER}"
  End If
  WScript.Quit 0
Else
  WScript.Quit 1
End If
