"""Headless re-apply used at login/boot:  python -m rivalcfg_gui.apply_last."""

import sys
import traceback

from . import backend
from . import persistence


def main():
    applied, failed = 0, 0
    # Prefer actually-plugged devices so we don't error on missing hardware
    plugged = {(d["vendor_id"], d["product_id"]) for d in backend.list_devices()}
    for entry in persistence.load_all():
        key = (entry["vendor_id"], entry["product_id"])
        if plugged and key not in plugged:
            continue
        try:
            mouse = backend.open_mouse(*key)
            try:
                backend.apply_settings(
                    mouse,
                    entry.get("values", {}),
                    persist=entry.get("persist_onboard", True),
                )
            finally:
                try:
                    mouse.close()
                except Exception:
                    pass
            applied += 1
            print(f"re-applied {entry['vendor_id']:04x}:{entry['product_id']:04x}")
        except Exception:
            failed += 1
            traceback.print_exc()
    print(f"done: applied={applied} failed={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
