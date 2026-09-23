# rivalcfg GUI (scaffold, `feat/gui` branch)

Cross-platform PySide6 GUI for rivalcfg. Generic: builds the form
dynamically from the plugged mouse's profile, so all devices work.

## Run (from repo root)

```bash
pip install -e . "PySide6>=6.6" hidapi
python gui/run_gui.py
# or
PYTHONPATH=. python -m rivalcfg_gui.app  # with gui/ on path
QT_QPA_PLATFORM=offscreen python gui/run_gui.py  # smoke test, no display
```

On Linux, allow regular users once:

```bash
sudo rivalcfg --update-udev
```

## Layout

* `gui/rivalcfg_gui/backend.py` — wrapper over `rivalcfg.devices` + `rivalcfg.mouse`
* `gui/rivalcfg_gui/app.py` — `MainWindow`, dynamic `SettingRow` per `value_type`
* `gui/rivalcfg_gui/profiles.py` — JSON profiles in `~/.config/rivalcfg-gui/profiles/`

## Widget mapping (scaffold)

* `choice` → dropdown (polling rate, light effect, …)
* `rgbcolor` / `reactive_rgbcolor` → text + color picker
* `buttons` → Piper-style `DiagramGroup`: doc SVG diagram
  (`doc/devices/images/rival_3_buttons.svg`, etc.) + per-button dropdowns
  (editable, so any keyboard/multimedia key can be typed) synced with the
  raw `buttons(...; layout=qwerty)` string
* `range`, `range_choice`, `multidpi_*`, `rgbgradient*` → text prefilled with default
  (dedicated sliders/gradient editors are next step)
* `none` → button

## GG wishlist vs rivalcfg reality

Supported now: DPI stages, polling, zones/effects, simple button remap,
`--no-save` toggle, reset, firmware, JSON profiles.
Not in firmware/CLI: angle snapping, accel curves, timed macros,
app auto-switch, GameSense. Those need new reverse-engineering + daemon.
