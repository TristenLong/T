$WshShell = New-Object -comObject WScript.Shell
$DesktopPath = [System.Environment]::GetFolderPath('Desktop')
$StartupPath = [System.Environment]::GetFolderPath('Startup')

# Create Desktop Shortcut
$DesktopShortcut = $WshShell.CreateShortcut("$DesktopPath\Jester Voice Assistant.lnk")
$DesktopShortcut.TargetPath = "wscript.exe"
$DesktopShortcut.Arguments = """C:\Users\trist\gemini-voice-assistant\launch_jester.vbs"""
$DesktopShortcut.WorkingDirectory = "C:\Users\trist\gemini-voice-assistant"
$DesktopShortcut.WindowStyle = 1
$DesktopShortcut.IconLocation = "shell32.dll, 13"
$DesktopShortcut.Description = "Launch Jester AI (Matrix Protocol)"
$DesktopShortcut.Save()
Write-Host "Shortcut created on Desktop successfully."

# Create Startup Shortcut
$StartupShortcut = $WshShell.CreateShortcut("$StartupPath\Jester Voice Assistant.lnk")
$StartupShortcut.TargetPath = "wscript.exe"
$StartupShortcut.Arguments = """C:\Users\trist\gemini-voice-assistant\launch_jester.vbs"""
$StartupShortcut.WorkingDirectory = "C:\Users\trist\gemini-voice-assistant"
$StartupShortcut.WindowStyle = 1
$StartupShortcut.IconLocation = "shell32.dll, 13"
$StartupShortcut.Description = "Launch Jester AI (Matrix Protocol)"
$StartupShortcut.Save()
Write-Host "Shortcut created in Startup folder successfully."
