"""rivalcfg GUI backend - thin wrapper over the rivalcfg Python library."""

from rivalcfg import devices
from rivalcfg.mouse import get_mouse


def list_devices():
    """Return plugged supported devices as list of dicts.

    :rtype: list[dict] [{vendor_id, product_id, name}]
    """
    try:
        seen = set()
        out = []
        for d in devices.list_plugged_devices():
            key = (d["vendor_id"], d["product_id"])
            if key in seen:
                continue
            seen.add(key)
            out.append(d)
        return out
    except Exception:
        return []


def list_all_supported():
    """Return all supported (vid, pid) -> profile name, for offline browsing."""
    out = []
    for (vid, pid), profile in sorted(devices.PROFILES.items()):
        out.append({"vendor_id": vid, "product_id": pid, "name": profile["name"]})
    return out


def get_profile(vendor_id, product_id):
    return devices.get_profile(vendor_id, product_id)


def open_mouse(vendor_id, product_id):
    """Open a Mouse instance. Caller must call mouse.close()."""
    return get_mouse(vendor_id=vendor_id, product_id=product_id)


def setting_names(profile):
    return list(profile.get("settings", {}).keys())


def apply_settings(mouse, values, persist=True):
    """Apply {setting_name: value} to an open Mouse.

    :param mouse: rivalcfg.mouse.Mouse instance
    :param values: dict of setting_name -> python value (str/int)
    :param persist: if True call mouse.save() (onboard memory)
    """
    for name, value in values.items():
        setter = getattr(mouse, f"set_{name}")
        # CLI passes everything as strings; handlers accept str or int.
        # Keep ints as ints for choice handlers with int keys.
        setter(value)
    if persist:
        mouse.save()
