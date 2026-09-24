"""System-tray support (cross-desktop).

Uses Qt's QSystemTrayIcon, which talks StatusNotifierItem (SNI D-Bus) on
modern desktops (KDE, XFCE, MATE, Cinnamon, GNOME + AppIndicator extension,
 LXQt, COSMIC) and falls back to XEmbed systray where offered. No
desktop-specific code paths.

GNOME without the AppIndicator extension has no tray at all — the window
still works normally; we just log a warning.
"""

import logging
import os

log = logging.getLogger("rivalcfg-gui.tray")

APP_ICON = "rivalcfg-gui"


def find_icon_file():
    """Locate the SVG icon: installed theme first, then repo checkout."""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        # repo checkout: <root>/packaging/icons/rivalcfg-gui.svg
        os.path.normpath(os.path.join(here, "..", "..", "packaging", "icons", "rivalcfg-gui.svg")),
        "/usr/share/icons/hicolor/scalable/apps/rivalcfg-gui.svg",
        os.path.expanduser("~/.local/share/icons/hicolor/scalable/apps/rivalcfg-gui.svg"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return None


def app_icon():
    """QIcon for window + tray: theme icon if installed, else bundled SVG."""
    from PySide6.QtGui import QIcon

    icon = QIcon.fromTheme(APP_ICON)
    if not icon.isNull():
        return icon
    path = find_icon_file()
    if path:
        return QIcon(path)
    return QIcon()  # last resort: Qt default


def tray_available():
    from PySide6.QtWidgets import QSystemTrayIcon

    return QSystemTrayIcon.isSystemTrayAvailable()


def setup_tray(app, window, on_apply_last=None):
    """Attach a tray icon to an open window. Returns QSystemTrayIcon or None."""
    from PySide6.QtWidgets import QSystemTrayIcon, QMenu
    from PySide6.QtGui import QAction

    if not tray_available():
        log.warning("No system tray on this desktop — running windowed.")
        return None

    tray = QSystemTrayIcon(app)
    tray.setIcon(app_icon())
    tray.setToolTip("Rivalcfg GUI — SteelSeries mouse settings")

    menu = QMenu()
    show_act = QAction("Show / Hide", menu)
    show_act.triggered.connect(window.toggle_visible)
    menu.addAction(show_act)

    if on_apply_last is not None:
        apply_act = QAction("Re-apply settings now", menu)
        apply_act.triggered.connect(on_apply_last)
        menu.addAction(apply_act)
        menu.addSeparator()

    quit_act = QAction("Quit", menu)
    quit_act.triggered.connect(app.quit)
    menu.addAction(quit_act)

    tray.setContextMenu(menu)
    # Clicks always SHOW (never toggle): toggle-on-click breaks on SNI/Plasma
    # where double-clicks arrive as two Triggers (slow ones show+hide, so it
    # looks like nothing happens). Hiding stays explicit: tray menu, X button.
    tray.activated.connect(
        lambda reason: window.show_window() if reason in (2, 3, 4) else None
    )
    tray.show()
    return tray
