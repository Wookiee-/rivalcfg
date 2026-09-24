#!/usr/bin/env bash
# Build a .deb with plain dpkg-deb (no debhelper toolchain needed).
# Run from the repo root on a Debian/Ubuntu machine:
#   bash packaging/deb/build-deb.sh
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
VER="${VER:-4.17.0}"
WORK="$(mktemp -d)"
PKG="$WORK/rivalcfg-gui_${VER}_all"
trap 'rm -rf "$WORK"' EXIT

mkdir -p "$PKG/DEBIAN" \
  "$PKG/usr/lib/python3/dist-packages" \
  "$PKG/usr/share/rivalcfg-gui" \
  "$PKG/usr/bin" \
  "$PKG/usr/share/applications" \
  "$PKG/etc/xdg/autostart" \
  "$PKG/usr/lib/systemd/user"
for s in 16 22 24 32 48 64 128 256; do
  mkdir -p "$PKG/usr/share/icons/hicolor/${s}x${s}/apps"
done
mkdir -p "$PKG/usr/share/icons/hicolor/scalable/apps"

cat > "$PKG/DEBIAN/control" <<EOF
Package: rivalcfg-gui
Version: $VER
Section: utils
Priority: optional
Architecture: all
Depends: python3, python3-hidapi, python3-pyside6.qtgui, python3-pyside6.qtwidgets, python3-pyside6.qtsvg, hicolor-icon-theme
Maintainer: rivalcfg-gui contributors
Description: Unofficial GG-style GUI for SteelSeries mice (rivalcfg)
 Cross-desktop PySide6 GUI: DPI stages, polling rate, multi-zone RGB,
 button remapping with mouse diagram, JSON profiles, system-tray mode
 with re-apply on login (survives reboot).
EOF

cat > "$PKG/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
# allow regular users to open the mice
python3 -m rivalcfg --update-udev >/dev/null 2>&1 || true
# refresh icon cache if present
gtk-update-icon-cache -f -t /usr/share/icons/hicolor >/dev/null 2>&1 || true
# enable the user re-apply unit for each already-created user session is left
# to first GUI launch (it self-enables via install.sh); package only ships it.
exit 0
EOF
chmod 0755 "$PKG/DEBIAN/postinst"

cp -r "$REPO/rivalcfg" "$PKG/usr/lib/python3/dist-packages/"
cp -r "$REPO/gui/rivalcfg_gui" "$PKG/usr/share/rivalcfg-gui/"
cp "$REPO/gui/run_gui.py" "$PKG/usr/share/rivalcfg-gui/"
cp "$REPO/packaging/rivalcfg-gui" "$PKG/usr/bin/rivalcfg-gui"
chmod 0755 "$PKG/usr/bin/rivalcfg-gui"
cp "$REPO/packaging/rivalcfg-gui.desktop" "$PKG/usr/share/applications/"
cp "$REPO/packaging/rivalcfg-gui-autostart.desktop" "$PKG/etc/xdg/autostart/rivalcfg-gui.desktop"
cp "$REPO/packaging/rivalcfg-gui-apply.service" "$PKG/usr/lib/systemd/user/"
sed -i 's|^ExecStart=.*|ExecStart=/usr/bin/rivalcfg-gui --apply-last|' \
  "$PKG/usr/lib/systemd/user/rivalcfg-gui-apply.service"
for s in 16 22 24 32 48 64 128 256; do
  cp "$REPO/packaging/icons/hicolor/${s}x${s}/apps/rivalcfg-gui.png" \
    "$PKG/usr/share/icons/hicolor/${s}x${s}/apps/"
done
cp "$REPO/packaging/icons/rivalcfg-gui.svg" \
  "$PKG/usr/share/icons/hicolor/scalable/apps/"

find "$PKG/usr/lib/python3/dist-packages/rivalcfg" \
     "$PKG/usr/share/rivalcfg-gui" -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true

dpkg-deb -b "$PKG" "$REPO/rivalcfg-gui_${VER}_all.deb"
echo "Built: $REPO/rivalcfg-gui_${VER}_all.deb"
