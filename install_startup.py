import os
import subprocess

def create_shortcut():
    startup_folder = os.path.expandvars(r'%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup')
    target = r"C:\Users\trist\gemini-voice-assistant\start_jester.bat"
    shortcut_path = os.path.join(startup_folder, "JesterLink.lnk")
    
    vbs_script = f"""
    Set oWS = WScript.CreateObject("WScript.Shell")
    sLinkFile = "{shortcut_path}"
    Set oLink = oWS.CreateShortcut(sLinkFile)
    oLink.TargetPath = "{target}"
    oLink.WorkingDirectory = "{os.path.dirname(target)}"
    oLink.Description = "Jester AI Auto-Start"
    oLink.Save
    """
    
    vbs_file = "make_link.vbs"
    with open(vbs_file, "w") as f:
        f.write(vbs_script)
        
    subprocess.run(["cscript", "//Nologo", vbs_file], shell=True)
    if os.path.exists(vbs_file): os.remove(vbs_file)
    print(f"INSTALLED: {shortcut_path}")

if __name__ == "__main__":
    create_shortcut()
