"""Create local phone credentials/certificate. Restart the app afterward."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from phone_access import create_config

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ip", required=True)
    args = parser.parse_args()
    config = create_config(Path(__file__).resolve().parent.parent, args.ip)
    print(f"Configured HTTPS phone access at https://{config['ip']}:{config['port']}.")
    print("Restart the desktop app, then open Help > Phone access on this computer for the password.")
