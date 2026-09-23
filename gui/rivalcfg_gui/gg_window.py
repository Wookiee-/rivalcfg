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
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import backend
from . import persistence
from . import profiles
from .app import SettingRow
from .widgets import MouseDiagram, ButtonsEditor


class GGWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("rivalcfg GUI")
        self.resize(1180, 700)
        self._profile = None
        self._vid = self._pid = None
        self._rows = {}  # non-button settings
        self._load_qss()

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # top device bar (not in GG shot, needed for generic multi-mouse)
        top = QHBoxLayout()
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(320)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh_devices)
        top.addWidget(QLabel("Device:"))
        top.addWidget(self.device_combo, 1)
        top.addWidget(refresh)
        root.addLayout(top)

        cols = QHBoxLayout()
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
        box = QGroupBox("CONFIGURATIONS / ACTIONS")
        layout = QVBoxLayout(box)
        self.config_list = QComboBox()
        self.config_list.setToolTip("Saved JSON profiles (~/.config/rivalcfg-gui/profiles/)")
        layout.addWidget(QLabel("Configuration:"))
        layout.addWidget(self.config_list)
        self.actions_box = QVBoxLayout()
        actions_wrap = QWidget()
        actions_wrap.setLayout(self.actions_box)
        layout.addWidget(QLabel("Actions (physical buttons):"))
        layout.addWidget(actions_wrap, 1)
        macro = QPushButton("Macro Editor (not in rivalcfg) — LAUNCH")
        macro.setEnabled(False)
        macro.setToolTip("Timed macros need new reverse-engineering + a background daemon. Not exposed by rivalcfg.")
        layout.addWidget(macro)
        return box

    def _center_pane(self):
        box = QGroupBox("Mouse")
        layout = QVBoxLayout(box)
        self.tabs = QTabWidget()
        self.tab_settings = QWidget()
        self.tab_light = QWidget()
        self.tabs.addTab(self.tab_settings, "Settings")
        self.tabs.addTab(self.tab_light, "Illumination")
        layout.addWidget(self.tabs)

        # settings tab: diagram + button remaps (generic)
        s_layout = QVBoxLayout(self.tab_settings)
        self.diagram = MouseDiagram()
        s_layout.addWidget(self.diagram)
        self.buttons_host = QVBoxLayout()
        s_layout.addLayout(self.buttons_host, 1)

        # illumination tab: rebuilt per-device from *color/*effect/*brightness settings
        l_layout = QVBoxLayout(self.tab_light)
        self.light_host = QVBoxLayout()
        l_layout.addLayout(self.light_host, 1)
        return box

    def _right_pane(self):
        box = QGroupBox("Performance")
        layout = QVBoxLayout(box)
        layout.addWidget(QLabel("Mouse Sensitivity Levels"))
        self.cpi_edits = []
        cpi_box = QVBoxLayout()
        for _ in range(5):  # up to 5 presets; hidden per-device as needed
            e = QLineEdit()
            e.setPlaceholderText("DPI")
            self.cpi_edits.append(e)
            cpi_box.addWidget(e)
        layout.addLayout(cpi_box)
        self.cpi_hint = QLabel("")
        self.cpi_hint.setWordWrap(True)
        layout.addWidget(self.cpi_hint)

        layout.addWidget(QLabel("Polling Rate"))
        poll_row = QHBoxLayout()
        self.poll_combo = QComboBox()
        self.poll_slider = QSlider(Qt.Horizontal)
        self.poll_slider.setMinimum(0)
        self.poll_slider.setMaximum(3)
        poll_row.addWidget(self.poll_combo, 1)
        layout.addLayout(poll_row)
        layout.addWidget(self.poll_slider)

        # GG shows these; rivalcfg does not expose them -> disabled stubs
        for title in ("ACCELERATION / DECELERATION", "ANGLE SNAPPING"):
            g = QGroupBox(title)
            g.setEnabled(False)
            g.setToolTip("Not exposed by rivalcfg firmware profiles. Would need new reverse-engineering.")
            gl = QVBoxLayout(g)
            gl.addWidget(QLabel("Not supported on this device via rivalcfg."))
            layout.addWidget(g)
        layout.addStretch(1)
        return box

    def _bottom_bar(self):
        bar = QHBoxLayout()
        new_btn = QPushButton("+ NEW")
        new_btn.clicked.connect(self.on_new_profile)
        configs_btn = QPushButton("CONFIGS")
        configs_btn.clicked.connect(self.on_load_profile)
        self.live_check = QCheckBox("LIVE PREVIEW ON")
        self.live_check.setChecked(True)
        self.live_check.setToolTip("Apply immediately on SAVE. Off = record only.")
        revert_btn = QPushButton("REVERT")
        revert_btn.clicked.connect(self.on_revert)
        save_btn = QPushButton("SAVE")
        save_btn.clicked.connect(self.on_save)
        self.persist_check = QCheckBox("Save to onboard")
        self.persist_check.setChecked(True)
        for w in (new_btn, configs_btn, self.live_check, self.persist_check, revert_btn, save_btn):
            bar.addWidget(w)
        return bar

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
        self.statusBar().showMessage(f"{p.get('name','')} — generic GG layout")

        # center/settings: buttons editor
        self._clear_layout(self.buttons_host)
        self.buttons_editor = None
        if "buttons_mapping" in settings:
            info = settings["buttons_mapping"]
            self.buttons_editor = ButtonsEditor(info.get("buttons", {}), str(info.get("default", "")))
            self.buttons_host.addWidget(self.buttons_editor)

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

        # left/actions: one row per physical button
        self._clear_layout(self.actions_box)
        self.action_combos = {}
        if "buttons_mapping" in settings:
            for key in settings["buttons_mapping"].get("buttons", {}).keys():
                row = QHBoxLayout()
                row.addWidget(QLabel(key))
                combo = QComboBox()
                combo.setEditable(True)
                from .diagram import COMMON_TARGETS
                combo.addItems(COMMON_TARGETS)
                combo.currentTextChanged.connect(self._actions_to_editor)
                self.action_combos[key.lower()] = combo
                wrap = QWidget()
                wrap.setLayout(row)
                row.addWidget(combo, 1)
                self.actions_box.addWidget(wrap)

        # right: sensitivity + polling
        if "sensitivity" in settings:
            info = settings["sensitivity"]
            self.cpi_hint.setText(f"{info.get('description','')} Range: {info.get('input_range','')} Default: {info.get('default','')}")
            from .diagram import parse_buttons_mapping  # noqa (keep import local, no cycle)
            default_cpis = str(info.get("default", "")).split(",")
            for i, edit in enumerate(self.cpi_edits):
                edit.setVisible(i < 5)
                edit.setText(default_cpis[i].strip() if i < len(default_cpis) else "")
        else:
            self.cpi_hint.setText("Sensitivity not exposed on this device.")
            for e in self.cpi_edits:
                e.setVisible(False)
        self.poll_combo.clear()
        if "polling_rate" in settings:
            choices = list(settings["polling_rate"].get("choices", {}).keys())
            for c in choices:
                self.poll_combo.addItem(str(c), c)
            self.poll_combo.setEnabled(True)
            self.poll_slider.setEnabled(True)
        else:
            self.poll_combo.setEnabled(False)
            self.poll_slider.setEnabled(False)

    def _actions_to_editor(self):
        if not getattr(self, "buttons_editor", None):
            return
        vals = {k: c.currentText() for k, c in self.action_combos.items()}
        from .diagram import build_buttons_mapping
        try:
            self.buttons_editor.set_value(build_buttons_mapping(vals))
        except Exception:
            pass

    # ---------- bottom actions ----------
    def _collect_all(self):
        values = {}
        # sensitivity from CPI boxes (non-empty boxes only; hidden boxes are skipped by being empty)
        if self._profile and "sensitivity" in self._profile.get("settings", {}):
            cpis = [e.text().strip() for e in self.cpi_edits if e.text().strip()]
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
    import sys
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv if argv is None else argv)
    win = GGWindow()
    win.show()
    return app.exec()
