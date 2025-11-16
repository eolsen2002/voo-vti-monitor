# auto_update_monitor.py
"""
auto_update_monitor.py
- Checks GitHub repo for latest voo_vti_monitor.py
- Downloads and replaces local file if newer
- Saves backup of old file
"""

import os
import requests
from datetime import datetime

# ---------------- CONFIG ----------------
GITHUB_RAW_URL = "https://raw.githubusercontent.com/eolsen2002/voo-vti-monitor/main/voo_vti_monitor.py"
LOCAL_FILE = r"C:\xampp\htdocs\vg-micro\voo_vti_monitor.py"
BACKUP_DIR = r"C:\xampp\htdocs\vg-micro\backup"

def backup_local_file():
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(BACKUP_DIR, f"voo_vti_monitor_{timestamp}.py")
    with open(LOCAL_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    with open(backup_file, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Backup saved: {backup_file}")

def download_latest_file():
    r = requests.get(GITHUB_RAW_URL)
    if r.status_code == 200:
        latest_content = r.text
        with open(LOCAL_FILE, "w", encoding="utf-8") as f:
            f.write(latest_content)
        print(f"Local file updated from GitHub at {datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')}")
    else:
        print("Failed to fetch latest file from GitHub. Status code:", r.status_code)

if __name__ == "__main__":
    try:
        backup_local_file()
        download_latest_file()
    except Exception as e:
        print("Error updating monitor:", e)
