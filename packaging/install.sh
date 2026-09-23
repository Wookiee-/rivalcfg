#!/usr/bin/env bash
# Native install (Fedora/RHEL-friendly): app + autostart re-apply + udev note.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"

echo "[1/4] Installing Python packages (needs pip)…"
pip install --user -e "$REPO" "PySide6>=6.6" hidapi

echo "[2/4] Installing .desktop (app launcher)…"
mkdir -p ~/.local/share/applications
cp "$REPO/packaging/rivalcfg-gui.desktop" ~/.local/share/applications/
# point Exec at this checkout until we ship a console script
sed -i "s|^Exec=.*|Exec=/usr/bin/python3 $REPO/gui/run_gui.py --gg|" ~/.local/share/applications/rivalcfg-gui.desktop || true
update-desktop-database ~/.local/share/applications || true

echo "[3/4] Installing re-apply on login (systemd user unit + XDG autostart)…"
mkdir -p ~/.config/systemd/user ~/.config/autostart
cp "$REPO/packaging/rivalcfg-gui-apply.service" ~/.config/systemd/user/
# make the unit see this checkout
sed -i "s|^ExecStart=.*|ExecStart=/usr/bin/python3 $REPO/gui/run_gui.py --apply-last|" ~/.config/systemd/user/rivalcfg-gui-apply.service || true
systemctl --user daemon-reload || true
systemctl --user enable --now rivalcfg-gui-apply.service || true
cat > ~/.config/autostart/rivalcfg-gui-apply.desktop <<EOF
[Desktop Entry]
Type=Application
Name=Rivalcfg GUI re-apply
Exec=/usr/bin/python3 $REPO/gui/run_gui.py --apply-last
X-GNOME-Autostart-enabled=true
NoDisplay=true
EOF

echo "[4/4] udev (one-time, needs root)…"
echo "  Running: sudo rivalcfg --update-udev"
sudo python3 -m rivalcfg --update-udev || sudo rivalcfg --update-udev || true

echo "Done. Launch: Rivalcfg GUI (or: python $REPO/gui/run_gui.py --gg)"
