Set WshShell = CreateObject("WScript.Shell")
' 0 means hide window
WshShell.Run "cmd.exe /c """ & "C:\Users\trist\gemini-voice-assistant\start_jester.bat" & """", 0, False
Set WshShell = Nothing
