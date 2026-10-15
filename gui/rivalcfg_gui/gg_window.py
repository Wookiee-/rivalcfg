"""GG-style generic layout (like the screenshot, but device-agnostic).

Columns:
  left   = configurations (JSON profiles) + actions (physical buttons)
  center = Settings | Illumination tabs + mouse diagram
  right  = sensitivity levels + polling (+ disabled accel/angle-snapping stubs)
  bottom = NEW | CONFIGS | LIVE PREVIEW | REVERT | SAVE

Only settings the plugged mouse's profile actually exposes are enabled.
Anything rivalcfg doesn't expose (accel curves, angle snapping, timed macros)
is shown disabled with a tooltip, so the layout matches GG without faking HW.
"""

import traceback

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStyle,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QFrame,
    QGridLayout,
)

from . import backend
from . import persistence
from . import profiles
from .app import SettingRow
from .widgets import MouseDiagram, ButtonsEditor
from .tray import app_icon, setup_tray


class GGWindow(QMainWindow):
    def __init__(self, force_dark=False, tray_mode=False):
        super().__init__()
        self.setWindowTitle("rivalcfg GUI")
        self.setWindowIcon(app_icon())
        self.resize(1180, 700)
        self.setMinimumSize(980, 620)
        self._tray_mode = tray_mode
        self._tray = None
        self._profile = None
        self._vid = self._pid = None
        self._rows = {}  # non-button settings
        # Keep the GG view visually consistent across desktop environments.
        # ``force_dark`` is retained for CLI/API compatibility; the polished
        # app theme is now the default presentation for this window.
        self._load_qss()

        central = QWidget()
        central.setObjectName("appRoot")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 18, 20, 14)
        root.setSpacing(14)

        # top device bar (not in GG shot, needed for generic multi-mouse)
        top = QHBoxLayout()
        top.setObjectName("deviceBar")
        top.setSpacing(10)
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(320)
        self.device_combo.setMinimumHeight(38)
        refresh = QPushButton("Refresh")
        refresh.setObjectName("secondaryButton")
        refresh.setMinimumHeight(38)
        refresh.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        refresh.clicked.connect(self.refresh_devices)
        device_label = QLabel("DEVICE")
        device_label.setObjectName("eyebrow")
        top.addWidget(device_label)
        top.addWidget(self.device_combo, 1)
        top.addWidget(refresh)
        root.addLayout(top)

        cols = QHBoxLayout()
        cols.setSpacing(14)
        root.addLayout(cols, 1)
        cols.addWidget(self._left_pane(), 1)
        cols.addWidget(self._center_pane(), 2)
        cols.addWidget(self._right_pane(), 1)

        root.addLayout(self._bottom_bar())
        self.statusBar().showMessage("Ready")
        self.refresh_devices()
        self.device_combo.currentIndexChanged.connect(self.on_device_changed)

    # ---------- styling ----------
    def _load_qss(self):
        try:
            import os
            qss = os.path.join(os.path.dirname(__file__), "theme.qss")
            if os.path.isfile(qss):
                with open(qss) as f:
                    self.setStyleSheet(f.read())
        except Exception:
            pass

    # ---------- panes ----------
    def _left_pane(self):
        box = QGroupBox("CONFIGURATIONS / BUTTONS")
        box.setObjectName("card")
        box.setMinimumWidth(300)
        box.setMaximumWidth(340)
        layout = QVBoxLayout(box)
        layout.setSpacing(8)
        self.config_list = QComboBox()
        self.config_list.setObjectName("configList")
        self.config_list.setToolTip("Saved JSON profiles (~/.config/rivalcfg-gui/profiles/)")
        layout.addWidget(QLabel("Configuration:"))
        layout.addWidget(self.config_list)
        self.device_info = QLabel("")
        self.device_info.setWordWrap(True)
        layout.addWidget(self.device_info)
        layout.addWidget(QLabel("Button remapping:"))
        # Compact single-column remaps (the supported profiles fit without a
        # scrollbar; the advanced editor remains in the fixed footer below).
        host_wrap = QWidget()
        host_wrap.setObjectName("leftButtonsHost")
        self.left_buttons_host = QVBoxLayout(host_wrap)
        self.left_buttons_host.setContentsMargins(0, 0, 0, 0)
        self.left_buttons_host.setSpacing(8)
        layout.addWidget(host_wrap, 1)
        self.left_advanced_host = QWidget()
        self.left_advanced_layout = QVBoxLayout(self.left_advanced_host)
        self.left_advanced_layout.setContentsMargins(0, 4, 0, 0)
        self.left_advanced_host.hide()
        layout.addWidget(self.left_advanced_host)
        self.buttons_editor = None
        return box

    def _center_pane(self):
        box = QGroupBox("Mouse")
        box.setObjectName("card")
        layout = QVBoxLayout(box)
        self.tabs = QTabWidget()
        self.tab_settings = QWidget()
        self.tab_light = QWidget()
        self.tabs.addTab(self.tab_settings, "Settings")
        self.tabs.addTab(self.tab_light, "Illumination")
        layout.addWidget(self.tabs)

        # settings tab: large aspect-correct diagram only (remaps live on the left)
        s_layout = QVBoxLayout(self.tab_settings)
        self.diagram = MouseDiagram()
        s_layout.addWidget(self.diagram, 1)

        # illumination tab: rebuilt per-device from *color/*effect/*brightness settings
        l_layout = QVBoxLayout(self.tab_light)
        self.light_host = QVBoxLayout()
        l_layout.addLayout(self.light_host, 1)
        return box

    def _right_pane(self):
        from PySide6.QtWidgets import QSpinBox
        box = QGroupBox("Performance")
        box.setObjectName("card")
        box.setMaximumWidth(300)
        layout = QVBoxLayout(box)
        layout.setSpacing(10)
        cpi_head = QHBoxLayout()
        dpi_title = QLabel("DPI STAGES")
        dpi_title.setObjectName("sectionHeader")
        cpi_head.addWidget(dpi_title)
        self.cpi_count = QSpinBox()
        self.cpi_count.setMinimum(1)
        self.cpi_count.setMaximum(5)
        self.cpi_count.setValue(2)
        self.cpi_count.setToolTip("Number of DPI presets (up to 5, per device)")
        self.cpi_count.valueChanged.connect(self._apply_cpi_count)
        cpi_head.addWidget(self.cpi_count)
        layout.addLayout(cpi_head)
        self.cpi_edits = []
        self.cpi_cards = []
        cpi_box = QVBoxLayout()
        cpi_box.setSpacing(6)
        for i in range(5):  # up to 5 presets; shown per-device count
            card = QFrame()
            card.setObjectName("metricCard")
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(10, 6, 8, 6)
            level = QLabel(f"LEVEL {i + 1}")
            level.setObjectName("metricLabel")
            e = QLineEdit()
            e.setPlaceholderText("DPI")
            e.setObjectName("metricValue")
            e.setMinimumHeight(34)
            card_layout.addWidget(level)
            card_layout.addWidget(e, 1)
            cpi_box.addWidget(card)
            self.cpi_edits.append(e)
            self.cpi_cards.append(card)
        layout.addLayout(cpi_box)
        self.cpi_hint = QLabel("")
        self.cpi_hint.setObjectName("valueHint")
        self.cpi_hint.setWordWrap(True)
        layout.addWidget(self.cpi_hint)

        polling_title = QLabel("POLLING RATE")
        polling_title.setObjectName("sectionHeader")
        layout.addWidget(polling_title)
        self.poll_combo = QComboBox()
        self.poll_combo.setMinimumHeight(38)
        layout.addWidget(self.poll_combo)
        layout.addStretch(1)
        return box

    def _apply_cpi_count(self, n):
        for i, (edit, card) in enumerate(zip(self.cpi_edits, self.cpi_cards)):
            visible = i < n
            card.setVisible(visible)
            if not visible:
                edit.clear()  # hidden boxes must not leak stale DPI into SAVE

    def _bottom_bar(self):
        bar = QGridLayout()
        bar.setObjectName("bottomBar")
        bar.setHorizontalSpacing(8)
        new_btn = QPushButton("+ NEW")
        new_btn.setObjectName("secondaryButton")
        new_btn.clicked.connect(self.on_new_profile)
        configs_btn = QPushButton("CONFIGS")
        configs_btn.setObjectName("secondaryButton")
        configs_btn.clicked.connect(self.on_load_profile)
        self.live_check = QCheckBox("LIVE PREVIEW ON")
        self.live_check.setChecked(True)
        self.live_check.setToolTip("Apply immediately on SAVE. Off = record only.")
        revert_btn = QPushButton("REVERT")
        revert_btn.setObjectName("secondaryButton")
        revert_btn.setIcon(self.style().standardIcon(QStyle.SP_ArrowBack))
        revert_btn.clicked.connect(self.on_revert)
        save_btn = QPushButton("SAVE")
        save_btn.setObjectName("primaryButton")
        save_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        save_btn.clicked.connect(self.on_save)
        self.persist_check = QCheckBox("Save to onboard")
        self.persist_check.setChecked(True)
        checks = QWidget()
        checks_layout = QHBoxLayout(checks)
        checks_layout.setContentsMargins(0, 0, 0, 0)
        checks_layout.setSpacing(24)
        checks_layout.addWidget(self.live_check)
        checks_layout.addWidget(self.persist_check)

        left_actions = QWidget()
        left_layout = QHBoxLayout(left_actions)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)
        left_layout.addWidget(new_btn)
        left_layout.addWidget(configs_btn)

        right_actions = QWidget()
        right_layout = QHBoxLayout(right_actions)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)
        right_layout.addWidget(revert_btn)
        right_layout.addWidget(save_btn)

        # Equal-width side sections keep the checkbox group centered against
        # the entire bottom bar, regardless of button-label widths.
        side_width = max(left_actions.sizeHint().width(), right_actions.sizeHint().width())
        left_actions.setMinimumWidth(side_width)
        right_actions.setMinimumWidth(side_width)
        bar.setColumnStretch(0, 1)
        bar.setColumnStretch(1, 1)
        bar.setColumnStretch(2, 1)
        bar.addWidget(left_actions, 0, 0, Qt.AlignLeft)
        bar.addWidget(checks, 0, 1, Qt.AlignCenter)
        bar.addWidget(right_actions, 0, 2, Qt.AlignRight)
        return bar

    def toggle_visible(self):
        self.setVisible(not self.isVisible())
        if self.isVisible():
            self.raise_()
            self.activateWindow()

    def show_window(self):
        # Idempotent show for tray clicks: clicking always opens, never
        # accidentally closes (a slow double-click must not show+hide).
        # Hiding is explicit via the tray menu, the close button, or REVERT.
        if not self.isVisible():
            self.setVisible(True)
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        # Close-to-tray when a tray icon owns us; real quit via tray menu.
        if self._tray_mode and self._tray is not None and self._tray.isVisible():
            event.ignore()
            self.hide()
        else:
            super().closeEvent(event)

    # ---------- device handling ----------
    def refresh_devices(self):
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        for d in backend.list_devices():
            self.device_combo.addItem(f"{d['name']} ({d['vendor_id']:04x}:{d['product_id']:04x})", d)
        self.device_combo.blockSignals(False)
        self._refresh_configs()
        if self.device_combo.count():
            self.on_device_changed(0)
        else:
            self.statusBar().showMessage("No plugged mouse — plug one in and press Refresh.")

    def _refresh_configs(self):
        self.config_list.clear()
        self.config_list.addItem("(Default — device values)", None)
        for p in profiles.list_profiles():
            self.config_list.addItem(p.split("/")[-1], p)

    def on_device_changed(self, idx):
        data = self.device_combo.itemData(idx)
        if not data:
            return
        self._vid, self._pid = data["vendor_id"], data["product_id"]
        try:
            self._profile = backend.get_profile(self._vid, self._pid)
        except Exception as e:
            QMessageBox.warning(self, "Unsupported device", str(e))
            return
        self._rebuild()

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _rebuild(self):
        p = self._profile
        settings = p.get("settings", {})
        self.diagram.load(p.get("name", ""))
        self.statusBar().showMessage(p.get("name", ""))

        # left: single-column button remaps (GG-style ACTIONS list)
        self._clear_layout(self.left_buttons_host)
        self._clear_layout(self.left_advanced_layout)
        self.buttons_editor = None
        if "buttons_mapping" in settings:
            info = settings["buttons_mapping"]
            self.buttons_editor = ButtonsEditor(
                info.get("buttons", {}),
                str(info.get("default", "")),
                columns=1,
                show_advanced=False,
            )
            self.left_buttons_host.addWidget(self.buttons_editor)
            self.left_advanced_layout.addWidget(self.buttons_editor.advanced_panel)
        else:
            self.left_buttons_host.addWidget(QLabel("Remapping not supported on this device."))
            self.left_advanced_host.hide()
        if "buttons_mapping" in settings:
            self.left_advanced_host.show()

        # center/illumination: every *color / *effect / *brightness / rainbow / default_lighting
        self._clear_layout(self.light_host)
        self._rows = {}
        for name, info in settings.items():
            if name == "buttons_mapping":
                continue
            vt = info.get("value_type", "")
            is_light = ("color" in name) or ("effect" in name) or ("light" in name) or ("brightness" in name) or ("led" in name)
            host = self.light_host if is_light else None
            if host is None:
                continue  # sensitivity/polling handled in right pane
            row = SettingRow(name, info, profile_name=p.get("name", ""))
            self.light_host.addWidget(QLabel(info.get("label", name)))
            self.light_host.addWidget(row)
            self._rows[name] = row

        # left: device summary (actions live only in center now — no duplication)
        try:
            n_buttons = len(settings.get("buttons_mapping", {}).get("buttons", {}))
        except Exception:
            n_buttons = 0
        self.device_info.setText(
            f"{p.get('name','')}\n{n_buttons} remappable buttons" if n_buttons else p.get("name", "")
        )

        # right: sensitivity + polling
        if "sensitivity" in settings:
            info = settings["sensitivity"]
            self.cpi_hint.setText(f"Range: {info.get('input_range','')}  Default: {info.get('default','')}")
            default_cpis = [s.strip() for s in str(info.get("default", "")).split(",") if s.strip()]
            n = max(1, min(5, len(default_cpis)))
            self.cpi_count.blockSignals(True)
            self.cpi_count.setValue(n)
            self.cpi_count.blockSignals(False)
            for i, card in enumerate(self.cpi_cards):
                card.setVisible(i < n)
                self.cpi_edits[i].setText(default_cpis[i] if i < len(default_cpis) else "")
        else:
            self.cpi_hint.setText("Sensitivity not exposed on this device.")
            for card in self.cpi_cards:
                card.setVisible(False)
        self.poll_combo.clear()
        if "polling_rate" in settings:
            choices = list(settings["polling_rate"].get("choices", {}).keys())
            for c in choices:
                self.poll_combo.addItem(str(c), c)
            default = settings["polling_rate"].get("default")
            idx = self.poll_combo.findText(str(default))
            if idx >= 0:
                self.poll_combo.setCurrentIndex(idx)
            self.poll_combo.setEnabled(True)
        else:
            self.poll_combo.setEnabled(False)

        # Seed the form from your last SAVE so reopening shows your values,
        # not factory defaults. (Writes were fine — only the display reset.)
        try:
            saved = persistence.load(self._vid, self._pid) or {}
            vals = saved.get("values", {})
        except Exception:
            vals = {}
        if vals:
            if "sensitivity" in vals and "sensitivity" in settings:
                parts = [s.strip() for s in str(vals["sensitivity"]).split(",") if s.strip()]
                if parts:
                    n = max(1, min(5, len(parts)))
                    self.cpi_count.blockSignals(True)
                    self.cpi_count.setValue(n)
                    self.cpi_count.blockSignals(False)
                    for i, card in enumerate(self.cpi_cards):
                        card.setVisible(i < n)
                        self.cpi_edits[i].setText(parts[i] if i < len(parts) else "")
            if "polling_rate" in vals and self.poll_combo.count():
                idx = self.poll_combo.findText(str(vals["polling_rate"]))
                if idx >= 0:
                    self.poll_combo.setCurrentIndex(idx)
            for name, row in self._rows.items():
                if name in vals:
                    try:
                        row.set_value(vals[name])
                    except Exception:
                        pass
            if "buttons_mapping" in vals and getattr(self, "buttons_editor", None):
                try:
                    self.buttons_editor.set_value(vals["buttons_mapping"])
                except Exception:
                    pass

    # ---------- bottom actions ----------
    def _collect_all(self):
        values = {}
        # sensitivity from visible CPI boxes only (hidden ones are cleared too)
        if self._profile and "sensitivity" in self._profile.get("settings", {}):
            cpis = [
                edit.text().strip()
                for edit, card in zip(self.cpi_edits, self.cpi_cards)
                if card.isVisible() and edit.text().strip()
            ]
            if cpis:
                values["sensitivity"] = ", ".join(cpis)
        if self._profile and "polling_rate" in self._profile.get("settings", {}):
            if self.poll_combo.count():
                values["polling_rate"] = self.poll_combo.currentData()
        for name, row in self._rows.items():
            v = row.value()
            if v is not None:
                values[name] = v
        if getattr(self, "buttons_editor", None):
            values["buttons_mapping"] = self.buttons_editor.value()
        return values

    def on_save(self):
        if not self._profile:
            return
        values = self._collect_all()
        if self.live_check.isChecked():
            try:
                mouse = backend.open_mouse(self._vid, self._pid)
                try:
                    backend.apply_settings(mouse, values, persist=self.persist_check.isChecked())
                finally:
                    try:
                        mouse.close()
                    except Exception:
                        pass
            except Exception:
                QMessageBox.critical(self, "Apply failed", traceback.format_exc(limit=3))
                return
        try:
            path = persistence.record(self._vid, self._pid, values, self.persist_check.isChecked())
            self.statusBar().showMessage(f"Saved ({len(values)} settings). Re-applied on login/boot: {path}", 8000)
        except Exception:
            QMessageBox.critical(self, "Record failed", traceback.format_exc(limit=3))

    def on_revert(self):
        self._rebuild()
        self.statusBar().showMessage("Reverted to device defaults.", 5000)

    def on_new_profile(self):
        name, ok = QInputDialog.getText(self, "New configuration", "Name:")
        if not ok or not name.strip():
            return
        profiles.save_profile(name.strip(), self._vid, self._pid, self._collect_all())
        self._refresh_configs()
        self.statusBar().showMessage(f"Configuration “{name.strip()}” saved.", 5000)

    def on_load_profile(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load configuration", profiles.PROFILE_DIR, "JSON (*.json)")
        if not path:
            return
        try:
            data = profiles.load_profile(path)
        except Exception as e:
            QMessageBox.critical(self, "Load failed", str(e))
            return
        vals = data.get("values", {})
        if "sensitivity" in vals:
            for i, part in enumerate(str(vals["sensitivity"]).split(",")):
                if i < len(self.cpi_edits):
                    self.cpi_edits[i].setText(part.strip())
        for name, row in self._rows.items():
            if name in vals:
                try:
                    row.set_value(vals[name])
                except Exception:
                    pass
        if "buttons_mapping" in vals and getattr(self, "buttons_editor", None):
            self.buttons_editor.set_value(vals["buttons_mapping"])
        self.statusBar().showMessage(f"Loaded {path}. Press SAVE to apply.", 8000)


def main(argv=None):
    import os
    import sys
    from PySide6.QtWidgets import QApplication
    args = sys.argv if argv is None else argv
    # Native system theme by default (works on GNOME/XFCE/KDE/Win/macOS).
    # Opt into the GG dark look with --dark or RIVALCFG_GUI_THEME=dark.
    force_dark = ("--dark" in args) or (os.environ.get("RIVALCFG_GUI_THEME") == "dark")
    tray_mode = "--tray" in args
    app = QApplication(args)
    app.setApplicationName("rivalcfg GUI")
    app.setQuitOnLastWindowClosed(not tray_mode)
    if tray_mode:
        # Autostart path: restore last-saved settings first so a reboot
        # leaves the mouse exactly as the GUI last saved it.
        try:
            from .apply_last import main as apply_last_main

            rc = apply_last_main()
            print(f"rivalcfg-gui: startup re-apply {'ok' if rc == 0 else 'had errors'}", flush=True)
        except Exception as e:
            print(f"rivalcfg-gui: startup re-apply skipped ({e})", flush=True)
    win = GGWindow(force_dark=force_dark, tray_mode=tray_mode)
    if tray_mode:
        from .apply_last import main as apply_last_main

        def _reapply():
            win.statusBar().showMessage("Re-applying saved settings…")
            rc = apply_last_main()
            win.statusBar().showMessage(
                "Settings re-applied." if rc == 0 else "Re-apply had errors — see terminal.", 8000
            )

        win._tray = setup_tray(app, win, on_apply_last=_reapply)
        if win._tray is None:
            win._tray_mode = False  # no tray here (e.g. plain GNOME): normal window life
            win.show()
        # else: start hidden in the tray
    else:
        win.show()
    return app.exec()
