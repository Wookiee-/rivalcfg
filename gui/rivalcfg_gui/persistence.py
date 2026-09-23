"""Persistence: re-apply last settings on login / device plug (reboot-safe).

rivalcfg already persists to onboard memory when you call mouse.save().
This module adds a second layer so the GUI state survives even when:
- the mouse has no save_command, or user used --no-save,
- the device was unplugged, or the machine rebooted.

Flow:
  Apply/Save in GUI -> persistence.record(vid, pid, values)
  Login/boot        -> `python -m rivalcfg_gui.apply_last` (systemd user unit
                       + XDG autostart .desktop) re-applies the recorded values.
"""

import json
import os

APP_DIR = os.path.join(os.path.expanduser("~"), ".config", "rivalcfg-gui")
LAST_DIR = os.path.join(APP_DIR, "last-applied")


def _ensure():
    os.makedirs(LAST_DIR, exist_ok=True)


def _path(vendor_id, product_id):
    _ensure()
    return os.path.join(LAST_DIR, f"{vendor_id:04x}_{product_id:04x}.json")


def record(vendor_id, product_id, values, persist_onboard=True):
    """Remember what was applied so it can be re-applied after reboot."""
    path = _path(vendor_id, product_id)
    with open(path, "w") as f:
        json.dump(
            {
                "vendor_id": vendor_id,
                "product_id": product_id,
                "values": values,
                "persist_onboard": persist_onboard,
            },
            f,
            indent=2,
        )
    return path


def load(vendor_id, product_id):
    path = _path(vendor_id, product_id)
    if not os.path.isfile(path):
        return None
    with open(path) as f:
        return json.load(f)


def load_all():
    _ensure()
    out = []
    for fn in sorted(os.listdir(LAST_DIR)):
        if fn.endswith(".json"):
            with open(os.path.join(LAST_DIR, fn)) as f:
                out.append(json.load(f))
    return out
