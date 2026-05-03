"""
Sollie Setup Script
Automates installation and initial configuration
"""

import subprocess
import sys
import os
import time
import traceback
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOG_PATH = BASE_DIR / "setup.log"


def log_message(message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with LOG_PATH.open("a", encoding="utf-8", errors="ignore") as log_file:
        log_file.write(f"[{timestamp}] {message}\n")


def print_header(text):
    """Print formatted header"""
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60 + "\n")


def check_python_version():
    """Ensure Python version is compatible"""
    print_header("Checking Python Version")
    
    version = sys.version_info
    print(f"Python version: {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ ERROR: Python 3.8 or higher required!")
        return False
    
    print("✓ Python version is compatible")
    return True


def install_dependencies():
    """Install required Python packages"""
    print_header("Installing Dependencies")
    
    try:
        print("Installing required packages...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
        ])
        print("✓ All dependencies installed successfully")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to install dependencies")
        return False


def test_imports():
    """Test if all required modules can be imported"""
    print_header("Testing Imports")
    
    modules = [
        "requests",
        "customtkinter",
        "psutil",
        "pyautogui"
    ]
    
    all_good = True
    for module in modules:
        try:
            __import__(module)
            print(f"✓ {module}")
        except ImportError:
            print(f"❌ {module} - FAILED")
            all_good = False
    
    return all_good


def create_desktop_shortcut():
    """Create a desktop shortcut for Sollie (Windows only)"""
    if os.name != 'nt':
        return
    
    print_header("Creating Desktop Shortcut")
    
    try:
        import win32com.client
        
        desktop = Path.home() / "Desktop"
        shortcut_path = desktop / "Sollie.lnk"
        
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(str(shortcut_path))

        python_path = Path(sys.executable)
        vbs_path = create_vbs_launcher(python_path, Path.cwd() / "sollie_launcher.py")
        wscript_path = Path(os.environ.get("WINDIR", "C:\\Windows")) / "System32" / "wscript.exe"

        shortcut.Targetpath = str(wscript_path)
        shortcut.Arguments = str(vbs_path)
        shortcut.WorkingDirectory = str(Path.cwd())

        icon_path = Path.cwd() / "assets" / "sollie.ico"
        if icon_path.exists():
            shortcut.IconLocation = str(icon_path)
        else:
            shortcut.IconLocation = sys.executable
        shortcut.save()
        
        print(f"✓ Desktop shortcut created: {shortcut_path}")
    except Exception as e:
        print(f"⚠ Could not create desktop shortcut: {e}")
        print("  You can manually run: python sollie_gui.py")


def check_lm_studio():
    """Check if LM Studio is accessible"""
    print_header("Checking LM Studio Connection")
    
    import requests
    
    try:
        response = requests.get("http://localhost:1234/v1/models", timeout=2)
        if response.status_code == 200:
            print("✓ LM Studio is running and accessible")
            return True
        else:
            print("⚠ LM Studio responded but with unexpected status")
            return False
    except requests.exceptions.RequestException:
        print("⚠ LM Studio is not running or not accessible")
        print("  Please start LM Studio and start the local server")
        print("  Then you can run Sollie")
        return False


def create_vbs_launcher(python_path, script_path):
    """Create a hidden VBS launcher to avoid console windows"""
    pythonw_path = python_path.with_name("pythonw.exe")
    launcher_path = pythonw_path if pythonw_path.exists() else python_path

    vbs_path = Path.cwd() / "sollie_launcher.vbs"
    def escape(path_value):
        return str(path_value).replace("\\", "\\\\")

    cwd = escape(Path.cwd())
    launcher = escape(launcher_path)
    script = escape(script_path)

    vbs_content = (
        "Set shell = CreateObject(\"WScript.Shell\")\n"
        f"shell.CurrentDirectory = \"{cwd}\"\n"
        "shell.Run Chr(34) & \"" + launcher + "\" & Chr(34) & _\n"
        "\" \" & Chr(34) & \"" + script + "\" & Chr(34), 0, False\n"
    )

    vbs_path.write_text(vbs_content, encoding="utf-8")
    return vbs_path


def main():
    """Main setup function"""
    os.chdir(BASE_DIR)
    print("\n" + "🤖 "*20)
    print("       SOLLIE - AI ASSISTANT SETUP")
    print("🤖 "*20 + "\n")
    
    steps = [
        ("Python Version Check", check_python_version),
        ("Install Dependencies", install_dependencies),
        ("Test Imports", test_imports),
        ("Check LM Studio", check_lm_studio)
    ]
    
    for step_name, step_func in steps:
        if not step_func():
            print(f"\n❌ Setup failed at: {step_name}")
            print("\nPlease fix the error and run setup.py again")
            return False
    
    # Optional: Create desktop shortcut
    create_desktop_shortcut()
    
    print_header("✓ SETUP COMPLETE!")
    
    print("""
╔════════════════════════════════════════════════════════════╗
║                    NEXT STEPS                              ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  1. Make sure LM Studio is running with local server ON   ║
║                                                            ║
║  2. Run Sollie with:                                       ║
║     → python sollie_launcher.py                            ║
║                                                            ║
║  3. Or use the desktop shortcut (if created)              ║
║                                                            ║
║  4. Chat with Sollie and test basic commands!             ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
    """)
    
    return True


if __name__ == "__main__":
    try:
        success = main()
    except Exception:
        success = False
        error_text = traceback.format_exc()
        log_message(error_text)
        print("Setup failed. Details were saved to setup.log")
        print(error_text)

    if os.name == "nt" and os.environ.get("SOLLIE_NO_PAUSE") != "1":
        input("\nPress Enter to exit...")

    if not success:
        sys.exit(1)
