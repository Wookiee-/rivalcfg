"""Mouse button diagram (Piper-style) using the doc SVGs in doc/devices/images/."""

import os
import re

# Profile name (or prefix) -> svg file in doc/devices/images/
SVG_MAP = {
    "SteelSeries Aerox 3": "aerox_3_buttons.svg",
    "SteelSeries Aerox 5": "aerox_5_wireless_buttons.svg",
    "SteelSeries Aerox 9": "aerox_5_wireless_buttons.svg",  # closest existing
    "SteelSeries Kana v2": None,
    "SteelSeries Kinzu v2": None,
    "SteelSeries Prime Mini": "prime_mini_buttons.svg",
    "SteelSeries Prime+": "prime_plus_buttons.svg",
    "SteelSeries Prime Wireless": "prime_wireless_buttons.svg",
    "SteelSeries Prime": "prime_buttons.svg",
    "SteelSeries Rival 100": None,
    "SteelSeries Rival 110": None,
    "SteelSeries Rival 106": None,
    "SteelSeries Rival 3 Wireless Gen 2": "rival_3_wireless_buttons.svg",
    "SteelSeries Rival 3 Wireless": "rival_3_wireless_buttons.svg",
    "SteelSeries Rival 3 Gen 2": "rival3_gen2_buttons.svg",
    "SteelSeries Rival 3": "rival_3_buttons.svg",
    "SteelSeries Rival 300S": "rival_300_buttons.svg",
    "SteelSeries Rival 300": "rival_300_buttons.svg",
    "SteelSeries Rival 310": "rival_310_buttons.svg",
    "SteelSeries Rival 5": "rival_5_buttons.svg",
    "SteelSeries Rival 500": "rival_500_buttons.svg",
    "SteelSeries Rival 600": "rival_600_buttons.svg",
    "SteelSeries Rival 650": "rival_650_buttons.svg",
    "SteelSeries Rival 700": None,
    "SteelSeries Rival 95": None,
    "SteelSeries Sensei 310": "sensei_310_buttons.svg",
    "SteelSeries Sensei TEN": "sensei_ten_buttons.svg",
    "SteelSeries Sensei": "sensei_raw_buttons.svg",
}


def _candidate_dirs():
    here = os.path.dirname(os.path.abspath(__file__))
    return [
        os.path.join(here, "assets", "buttons"),  # bundled copies (future)
        os.path.normpath(os.path.join(here, "..", "..", "doc", "devices", "images")),
        os.path.normpath(os.path.join(here, "..", "..", "..", "doc", "devices", "images")),
        "/usr/share/rivalcfg-gui/buttons",
    ]


def get_diagram_svg(profile_name):
    """Return filesystem path to the button diagram SVG, or None."""
    filename = None
    # longest-prefix match so "Rival 3 Wireless Gen 2" wins over "Rival 3"
    for prefix in sorted(SVG_MAP, key=len, reverse=True):
        if profile_name == prefix or profile_name.startswith(prefix):
            filename = SVG_MAP[prefix]
            break
    if not filename:
        return None
    for d in _candidate_dirs():
        p = os.path.join(d, filename)
        if os.path.isfile(p):
            return p
    return None


def parse_buttons_mapping(text, buttons_dict):
    """Parse 'buttons(button1=...; layout=qwerty)' into {lower_name: mapping}.

    Unknown / missing entries fall back to each button's default.
    """
    result = {}
    for key, info in buttons_dict.items():
        result[key.lower()] = info.get("default", "button1")
    if not text:
        return result
    m = re.search(r"buttons\s*\((.*)\)\s*$", text.strip(), re.IGNORECASE | re.DOTALL)
    if not m:
        return result
    for part in m.group(1).split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        k, v = k.strip().lower(), v.strip()
        if k == "layout":
            result["_layout"] = v
            continue
        if k in result:
            result[k] = v
    return result


def build_buttons_mapping(values, layout="qwerty"):
    """Build 'buttons(...)' string from {lower_name: mapping}."""
    parts = [f"{k}={v}" for k, v in values.items() if not k.startswith("_") and v]
    parts.append(f"layout={values.get('_layout', layout)}")
    return f"buttons({'; '.join(parts)})"


# Common remap targets offered in the per-button dropdowns.
# Combos stay editable so any keyboard key / alias can still be typed.
COMMON_TARGETS = [
    "button1",
    "button2",
    "button3",
    "button4",
    "button5",
    "dpi",
    "scrollup",
    "scrolldown",
    "disabled",
    "Mute",
    "PlayPause",
    "Next",
    "Previous",
    "VolumeUp",
    "VolumeDown",
]
