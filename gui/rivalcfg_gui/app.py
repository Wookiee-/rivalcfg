"""Generic PySide6 GUI for rivalcfg (Linux / Windows / macOS).

Dynamically builds the form from the device profile so it works with
any mouse supported by rivalcfg, not just the Rival 3.
"""

import sys
import traceback

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
)

from . import backend
from . import profiles
from .widgets import DiagramGroup


def _describe_setting(info):
    parts = [info.get("description", "")]
    if "default" in info:
        parts.append(f"Default: {info['default']}")
    if info.get("value_type") == "choice" and "choices" in info:
        parts.append(f"Values: {', '.join(str(k) for k in info['choices'])}")
    if "input_range" in info:
        parts.append(f"Range: {info['input_range']}")
    return "\n".join(p for p in parts if p)


class SettingRow(QWidget):
    """Holds the editor widget(s) for one setting and value get/set."""

    def __init__(self, name, info, profile_name=None, parent=None):
        super().__init__(parent)
        self.name = name
        self.info = info
        self.value_type = info.get("value_type", "")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.editor = None
        self.color_preview = None

        if self.value_type == "choice":
            combo = QComboBox()
            for key in info["choices"].keys():
                combo.addItem(str(key), key)
            default = info.get("default")
            idx = combo.findText(str(default))
            if idx >= 0:
                combo.setCurrentIndex(idx)
            self.editor = combo
            layout.addWidget(combo, 1)
        elif self.value_type in ("rgbcolor", "reactive_rgbcolor"):
            edit = QLineEdit(str(info.get("default", "")))
            edit.setPlaceholderText("e.g. red, #ff0000, ff0000")
            pick = QPushButton("Pick…")
            preview = QLabel("  ")
            preview.setAutoFillBackground(True)
            pick.clicked.connect(lambda: self._pick_color(edit, preview))
            self._update_preview(edit.text(), preview)
            edit.textChanged.connect(lambda t: self._update_preview(t, preview))
            self.editor = edit
            self.color_preview = preview
            layout.addWidget(edit, 1)
            layout.addWidget(preview)
            layout.addWidget(pick)
        elif self.value_type == "buttons":
            group = DiagramGroup(
                profile_name or "",
                info.get("buttons", {}),
                str(info.get("default", "")),
            )
            self.editor = group.editor  # ButtonsEditor; DiagramGroup.diagram shown alongside
            self.diagram_group = group
            layout.addWidget(group, 1)
        elif self.value_type in ("none", None, ""):
            btn = QPushButton(info.get("label", name))
            btn.clicked.connect(lambda: self._run_nop())
            self.editor = btn
            layout.addWidget(btn, 1)
        else:
            # range / range_choice / multidpi_* / rgbgradient* : free text,
            # prefilled with default. Dedicated sliders come later.
            edit = QLineEdit(str(info.get("default", "")))
            self.editor = edit
            layout.addWidget(edit, 1)

        if self.value_type not in ("none",):
            hint = _describe_setting(info)
            if hint:
                self.setToolTip(hint)

    def _pick_color(self, edit, preview):
        color = QColorDialog.getColor(QColor(edit.text()), self)
        if color.isValid():
            edit.setText(color.name())

    @staticmethod
    def _update_preview(text, label):
        try:
            c = QColor(text if "#" in text else f"#{text}" if len(text) in (3, 6) else text)
            # QColor understands named colors like "red" directly
            c = QColor(text)
            if c.isValid():
                label.setStyleSheet(f"background: {c.name()}; border: 1px solid #888;")
                return
        except Exception:
            pass
        label.setStyleSheet("background: transparent; border: 1px dashed #888;")

    def _run_nop(self):
        pass  # 'none' settings take no value; applied via set_<name>()

    def value(self):
        # ButtonsEditor (Piper-style) exposes value()/set_value()
        if hasattr(self.editor, "value") and not isinstance(
            self.editor, (QComboBox, QTextEdit, QLineEdit, QPushButton)
        ):
            try:
                return self.editor.value()
            except Exception:
                return None
        if isinstance(self.editor, QComboBox):
            return self.editor.currentData()
        if isinstance(self.editor, QTextEdit):
            return self.editor.toPlainText().strip()
        if isinstance(self.editor, QLineEdit):
            text = self.editor.text().strip()
            # coerce ints for choice-like numeric settings
            default = self.info.get("default")
            if isinstance(default, int):
                try:
                    return int(text)
                except ValueError:
                    return text
            return text
        return None  # 'none' type

    def set_value(self, value):
        if hasattr(self.editor, "set_value") and not isinstance(
            self.editor, (QComboBox, QTextEdit, QLineEdit)
        ):
            try:
                self.editor.set_value(value)
                return
            except Exception:
                pass
        if isinstance(self.editor, QComboBox):
            idx = self.editor.findText(str(value))
            if idx >= 0:
                self.editor.setCurrentIndex(idx)
        elif isinstance(self.editor, QTextEdit):
            self.editor.setPlainText(str(value))
        elif isinstance(self.editor, QLineEdit):
            self.editor.setText(str(value))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("rivalcfg GUI")
        self.resize(920, 640)
        self._rows = {}
        self._profile = None
        self._vid = self._pid = None

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # Device bar
        dev_bar = QHBoxLayout()
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(300)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh_devices)
        dev_bar.addWidget(QLabel("Device:"))
        dev_bar.addWidget(self.device_combo, 1)
        dev_bar.addWidget(refresh)
        root.addLayout(dev_bar)

        self.info_label = QLabel("No device selected.")
        root.addWidget(self.info_label)

        # Dynamic form
        self.form = QFormLayout()
        form_wrap = QWidget()
        form_wrap.setLayout(self.form)
        root.addWidget(form_wrap, 1)

        # Options
        opt_bar = QHBoxLayout()
        self.persist_check = QCheckBox("Save to onboard memory")
        self.persist_check.setChecked(True)
        self.persist_check.setToolTip("Uncheck = --no-save (test without persisting)")
        opt_bar.addWidget(self.persist_check)
        root.addLayout(opt_bar)

        # Buttons
        btn_bar = QHBoxLayout()
        self.apply_btn = QPushButton("Apply")
        self.reset_btn = QPushButton("Reset to factory")
        self.save_profile_btn = QPushButton("Save profile…")
        self.load_profile_btn = QPushButton("Load profile…")
        self.apply_btn.clicked.connect(self.on_apply)
        self.reset_btn.clicked.connect(self.on_reset)
        self.save_profile_btn.clicked.connect(self.on_save_profile)
        self.load_profile_btn.clicked.connect(self.on_load_profile)
        for b in (self.apply_btn, self.reset_btn, self.save_profile_btn, self.load_profile_btn):
            btn_bar.addWidget(b)
        root.addLayout(btn_bar)

        self.statusBar().showMessage("Ready")
        self.refresh_devices()
        self.device_combo.currentIndexChanged.connect(self.on_device_changed)

    # -- device handling --
    def refresh_devices(self):
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        found = backend.list_devices()
        if not found:
            # fall back to all supported so UI can be browsed without hardware
            self.info_label.setText("No plugged mouse found — browsing all supported models.")
            for d in backend.list_all_supported()[:0]:
                pass
            # still offer plugged-device debug override hint
            self._profile = None
            self._rebuild_form(None)
        else:
            self.info_label.setText(f"{len(found)} device(s) found.")
            for d in found:
                self.device_combo.addItem(
                    f"{d['name']} ({d['vendor_id']:04x}:{d['product_id']:04x})", d
                )
        self.device_combo.blockSignals(False)
        if self.device_combo.count():
            self.on_device_changed(0)

    def on_device_changed(self, idx):
        data = self.device_combo.itemData(idx)
        if not data:
            return
        self._vid, self._pid = data["vendor_id"], data["product_id"]
        try:
            self._profile = backend.get_profile(self._vid, self._pid)
        except Exception as e:
            QMessageBox.warning(self, "Unsupported device", str(e))
            self._profile = None
            self._rebuild_form(None)
            return
        extra = ""
        try:
            mouse = backend.open_mouse(self._vid, self._pid)
            try:
                extra = f" | Firmware: {mouse.firmware_version}"
                bat = mouse.battery
                if bat.get("level") is not None:
                    extra += f" | Battery: {bat['level']}%"
            finally:
                mouse.close()
        except Exception:
            extra = " (could not open device — check permissions/udev)"
        self.info_label.setText(f"{self._profile['name']}{extra}")
        self._rebuild_form(self._profile)

    def _clear_form(self):
        while self.form.rowCount():
            self.form.removeRow(0)
        self._rows = {}

    def _rebuild_form(self, profile):
        self._clear_form()
        if not profile:
            self.form.addRow(QLabel("Plug in a supported mouse and press Refresh."))
            return
        for name, info in profile.get("settings", {}).items():
            row = SettingRow(name, info, profile_name=profile.get("name", ""))
            label = info.get("label", name)
            self.form.addRow(QLabel(label), row)
            self._rows[name] = row

    def _collect_values(self):
        return {name: row.value() for name, row in self._rows.items() if row.value() is not None}

    # -- actions --
    def on_apply(self):
        if not self._profile:
            return
        values = self._collect_values()
        try:
            mouse = backend.open_mouse(self._vid, self._pid)
        except Exception as e:
            QMessageBox.critical(self, "Cannot open device", f"{e}\n\nLinux: run `sudo rivalcfg --update-udev` once.")
            return
        try:
            backend.apply_settings(mouse, values, persist=self.persist_check.isChecked())
            try:
                mouse.close()
            except Exception:
                pass
            self.statusBar().showMessage(f"Applied {len(values)} setting(s).", 5000)
        except Exception:
            QMessageBox.critical(self, "Apply failed", traceback.format_exc(limit=3))

    def on_reset(self):
        if not self._profile:
            return
        if QMessageBox.question(self, "Reset", "Reset all settings to factory default?") != QMessageBox.Yes:
            return
        try:
            mouse = backend.open_mouse(self._vid, self._pid)
            try:
                mouse.reset_settings()
                if self.persist_check.isChecked():
                    mouse.save()
            finally:
                try:
                    mouse.close()
                except Exception:
                    pass
            self.on_device_changed(self.device_combo.currentIndex())  # reload defaults
            self.statusBar().showMessage("Reset to factory defaults.", 5000)
        except Exception:
            QMessageBox.critical(self, "Reset failed", traceback.format_exc(limit=3))

    def on_save_profile(self):
        if not self._profile:
            return
        name, ok = QInputDialog.getText(self, "Save profile", "Profile name:")
        if not ok or not name.strip():
            return
        path = profiles.save_profile(name.strip(), self._vid, self._pid, self._collect_values())
        self.statusBar().showMessage(f"Profile saved: {path}", 5000)

    def on_load_profile(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load profile", profiles.PROFILE_DIR, "JSON (*.json)"
        )
        if not path:
            return
        try:
            data = profiles.load_profile(path)
        except Exception as e:
            QMessageBox.critical(self, "Load failed", str(e))
            return
        for name, val in data.get("values", {}).items():
            if name in self._rows:
                try:
                    self._rows[name].set_value(val)
                except Exception:
                    pass
        self.statusBar().showMessage(f"Profile loaded: {path}", 5000)


def main(argv=None):
    app = QApplication(sys.argv if argv is None else argv)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
