# rivalcfg GUI (branch `rivalcfg-gui`)

Cross-platform PySide6 GUI for rivalcfg. Generic: builds the form
dynamically from the plugged mouse's profile, so all devices work.

## Run (from repo root)

```bash
pip install -e . "PySide6>=6.6" hidapi
python gui/run_gui.py            # GG-style layout, native system theme
python gui/run_gui.py --dark     # forced GG dark look (or RIVALCFG_GUI_THEME=dark)
python gui/run_gui.py --tray     # start minimized to the system tray
python gui/run_gui.py --classic  # old single-form layout
QT_QPA_PLATFORM=offscreen python gui/run_gui.py  # smoke test, no display
```

On Linux, allow regular users once:

```bash
sudo rivalcfg --update-udev
```

## Layout

* `gui/rivalcfg_gui/gg_window.py` — GG-style 3-pane window (configs+buttons |
  diagram | performance), native theme by default, `--dark` opt-in
* `gui/rivalcfg_gui/tray.py` — `QSystemTrayIcon` (SNI D-Bus, all DEs with a
  tray host) + `--tray` start-hidden + close-to-tray
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

## Tray + autostart (all desktops)

* `--tray`: starts hidden, Show/Hide + Re-apply + Quit menu, close button
  minimizes to tray. Works wherever a tray/SNI host exists (KDE, XFCE,
  MATE, Cinnamon, LXQt, COSMIC, GNOME + AppIndicator extension).
  GNOME without the extension has no tray — window mode still works.
* Reboot persistence: every SAVE records to
  `~/.config/rivalcfg-gui/last-applied/`; `rivalcfg-gui --apply-last`
  re-applies via systemd user unit + XDG autostart entry.

## Icons

Red-badge mouse glyph (`packaging/icons/rivalcfg-gui.svg`, from upstream
`doc/images/favicon.svg`) + rendered hicolor PNGs 16–256px — readable on
light and dark themes, launchers and trays.

## Distro packages (all install `rivalcfg-gui` + udev via post-install)

* Fedora/RHEL: `packaging/rpm/rivalcfg-gui.spec`
  (`rpmbuild -ba packaging/rpm/rivalcfg-gui.spec` from a versioned tarball)
* Arch: `packaging/arch/PKGBUILD` (`makepkg -si` from a versioned tarball)
* Debian/Ubuntu: `bash packaging/deb/build-deb.sh` (needs only `dpkg-deb`)
* Dev checkout: `bash packaging/install.sh` (pip --user + desktop + autostart)
