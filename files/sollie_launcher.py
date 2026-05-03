"""
Sollie Launcher
Starts LM Studio (optional) and then runs the GUI
"""

import json
import os
import subprocess
import time
from pathlib import Path
import traceback
import threading

import requests

from sollie_gui import SollieGUI

BASE_DIR = Path(__file__).resolve().parent
LOG_PATH = BASE_DIR / "launcher.log"


def log_message(message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with LOG_PATH.open("a", encoding="utf-8", errors="ignore") as log_file:
        log_file.write(f"[{timestamp}] {message}\n")


def load_config(config_path="config.json"):
    path = Path(config_path)
    if not path.is_absolute():
        path = BASE_DIR / path
    with open(path, "r") as f:
        return json.load(f)


def find_lm_studio_path(config):
    app_path = config.get("lm_studio", {}).get("app_path")
    if app_path:
        candidate = Path(app_path).expanduser()
        if candidate.is_file():
            return candidate

    candidates = []

    local_appdata = os.environ.get("LOCALAPPDATA", "")
    program_files = os.environ.get("PROGRAMFILES", "")
    program_files_x86 = os.environ.get("PROGRAMFILES(X86)", "")

    if local_appdata:
        candidates.append(Path(local_appdata) / "Programs" / "LM Studio" / "LM Studio.exe")
    if program_files:
        candidates.append(Path(program_files) / "LM Studio" / "LM Studio.exe")
    if program_files_x86:
        candidates.append(Path(program_files_x86) / "LM Studio" / "LM Studio.exe")

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    return None


def start_lm_studio(config):
    if os.name != "nt":
        return False

    if not config.get("lm_studio", {}).get("auto_start", False):
        return False

    lm_studio_path = find_lm_studio_path(config)
    if not lm_studio_path:
        return False

    subprocess.Popen([str(lm_studio_path)])
    return True


def wait_for_lm_studio(api_url, timeout_sec=45, poll_interval=2):
    deadline = time.monotonic() + timeout_sec
    status_url = f"{api_url}/models"

    while time.monotonic() < deadline:
        try:
            response = requests.get(status_url, timeout=2)
            if response.status_code == 200:
                return True
        except requests.RequestException:
            pass

        time.sleep(poll_interval)

    return False


def wait_for_server_and_notify(app, api_url, timeout_sec):
    if not timeout_sec or timeout_sec <= 0:
        return

    app.set_status("● Waiting for LM Studio...", "orange")
    ready = wait_for_lm_studio(api_url, timeout_sec=timeout_sec)
    if ready:
        app.set_status("● Ready", "green")
    else:
        app.add_message(
            "System",
            "LM Studio is not ready. Start the Local Server in LM Studio, then try again.",
            "system",
        )
        app.set_status("● LM Studio not ready", "red")


def main():
    os.chdir(BASE_DIR)
    config = load_config()
    api_url = config.get("lm_studio", {}).get("api_url", "http://localhost:1234/v1")
    timeout_sec = config.get("lm_studio", {}).get("startup_timeout_sec", 45)

    start_lm_studio(config)
    app = SollieGUI()
    waiter = threading.Thread(
        target=wait_for_server_and_notify,
        args=(app, api_url, timeout_sec),
        daemon=True,
    )
    waiter.start()
    app.run()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        error_text = traceback.format_exc()
        log_message(error_text)
        print("Launcher failed. Details were saved to launcher.log")
        print(error_text)
        try:
            if sys.stdin and hasattr(sys.stdin, "isatty") and sys.stdin.isatty():
                input("\nPress Enter to exit...")
        except Exception:
            pass
