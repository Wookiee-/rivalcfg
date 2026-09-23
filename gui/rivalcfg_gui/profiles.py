"""Simple JSON file profiles for the rivalcfg GUI.

A profile is {setting_name: value} plus device metadata.
Stored under ~/.config/rivalcfg-gui/profiles/<name>.json
"""

import json
import os

APP_DIR = os.path.join(os.path.expanduser("~"), ".config", "rivalcfg-gui")
PROFILE_DIR = os.path.join(APP_DIR, "profiles")


def _ensure_dirs():
    os.makedirs(PROFILE_DIR, exist_ok=True)


def profile_path(name):
    _ensure_dirs()
    safe = "".join(c if c.isalnum() or c in "-_ " else "_" for c in name).strip()
    return os.path.join(PROFILE_DIR, f"{safe or 'profile'}.json")


def save_profile(name, vendor_id, product_id, values):
    path = profile_path(name)
    with open(path, "w") as f:
        json.dump(
            {
                "name": name,
                "vendor_id": vendor_id,
                "product_id": product_id,
                "values": values,
            },
            f,
            indent=2,
        )
    return path


def load_profile(path):
    with open(path) as f:
        return json.load(f)


def list_profiles():
    _ensure_dirs()
    return sorted(
        os.path.join(PROFILE_DIR, f)
        for f in os.listdir(PROFILE_DIR)
        if f.endswith(".json")
    )
