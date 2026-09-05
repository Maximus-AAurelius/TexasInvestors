"""Desktop entry point: reuse a healthy app or start it without console windows."""
import json
import os
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
URL = "http://127.0.0.1:8765"


def is_running():
    try:
        with urllib.request.urlopen(URL + "/api/health", timeout=2) as response:
            return json.load(response).get("app") == "TexasInvestors"
    except (OSError, ValueError):
        return False


def main():
    if not is_running():
        output = ROOT / "output"
        output.mkdir(exist_ok=True)
        environment = {**os.environ, "TX_APP_HOST": "127.0.0.1", "TX_APP_PORT": "8765"}
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        with (output / "launcher.log").open("ab") as log:
            subprocess.Popen([sys.executable, str(ROOT / "app.py")], cwd=ROOT, env=environment,
                             stdin=subprocess.DEVNULL, stdout=log, stderr=log, creationflags=flags)
        for _ in range(40):
            if is_running():
                break
            time.sleep(.25)
        else:
            raise RuntimeError("The app did not start. Check output/launcher.log or whether port 8765 is in use.")
    webbrowser.open(URL)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        if os.name == "nt":
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, str(exc), "Texas Investors", 0x10)
        else:
            raise
