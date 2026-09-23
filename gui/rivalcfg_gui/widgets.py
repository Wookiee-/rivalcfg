"""Piper-style widgets: mouse diagram + per-button remap editor."""

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    from PySide6.QtSvgWidgets import QSvgWidget
    HAS_SVG = True
except Exception:
    HAS_SVG = False

from . import diagram


class MouseDiagram(QWidget):
    """Shows the doc SVG diagram for the current mouse (read-only reference)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._svg = QSvgWidget() if HAS_SVG else None
        self._fallback = QLabel()
        self._fallback.setWordWrap(True)
        if self._svg:
            self._svg.setMinimumSize(320, 240)
            self._svg.setMaximumHeight(300)
            layout.addWidget(self._svg)
        layout.addWidget(self._fallback)
        self._fallback.hide()

    def load(self, profile_name):
        path = diagram.get_diagram_svg(profile_name or "")
        if path and self._svg:
            self._svg.load(path)
            self._svg.show()
            self._fallback.hide()
            self.setToolTip(f"Diagram: {path}")
        else:
            if self._svg:
                self._svg.hide()
            self._fallback.setText(
                f"No button diagram available for “{profile_name}”."
                if profile_name else "No device selected."
            )
            self._fallback.show()


class ButtonsEditor(QWidget):
    """Per-button dropdowns (Piper-style) synced with the raw buttons() string."""

    def __init__(self, buttons_dict, default_text="", parent=None):
        super().__init__(parent)
        self._buttons_dict = buttons_dict  # {"Button1": {...}, ...} from profile
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        form = QFormLayout()
        self._combos = {}
        # Preserve profile order; ScrollUp/Down last
        for key in buttons_dict.keys():
            combo = QComboBox()
            combo.setEditable(True)
            combo.addItems(diagram.COMMON_TARGETS)
            combo.setToolTip("Pick a target or type any keyboard key (e.g. A, F5, semicolon) or multimedia key.")
            combo.currentTextChanged.connect(self._sync_to_text)
            combo.editTextChanged.connect(self._sync_to_text)
            self._combos[key.lower()] = combo
            form.addRow(QLabel(key), combo)
        root.addLayout(form)

        adv_bar = QHBoxLayout()
        adv_bar.addWidget(QLabel("Advanced:"))
        parse_btn = QPushButton("Parse text → dropdowns")
        parse_btn.clicked.connect(self._sync_from_text)
        adv_bar.addWidget(parse_btn, 1)
        root.addLayout(adv_bar)

        self._text = QTextEdit(default_text)
        self._text.setMaximumHeight(70)
        self._text.setPlaceholderText("buttons(button1=button1; ...; layout=qwerty)")
        root.addWidget(self._text)
        self._syncing = False
        self.set_value(default_text)

    def _sync_to_text(self, *args):
        if self._syncing:
            return
        self._syncing = True
        try:
            values = {k: c.currentText().strip() for k, c in self._combos.items()}
            # keep layout if user edited it in text
            parsed = diagram.parse_buttons_mapping(self._text.toPlainText(), self._buttons_dict)
            if "_layout" in parsed:
                values["_layout"] = parsed["_layout"]
            self._text.setPlainText(diagram.build_buttons_mapping(values))
        finally:
            self._syncing = False

    def _sync_from_text(self):
        if self._syncing:
            return
        self._syncing = True
        try:
            parsed = diagram.parse_buttons_mapping(self._text.toPlainText(), self._buttons_dict)
            for k, combo in self._combos.items():
                val = parsed.get(k, "")
                if val:
                    idx = combo.findText(val)
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
                    else:
                        combo.setEditText(val)
        finally:
            self._syncing = False

    def value(self):
        self._sync_to_text()
        return self._text.toPlainText().strip()

    def set_value(self, text):
        self._syncing = True
        try:
            self._text.setPlainText(str(text or ""))
        finally:
            self._syncing = False
        self._sync_from_text()


class DiagramGroup(QGroupBox):
    """Diagram + buttons editor side by side, like Piper."""

    def __init__(self, profile_name, buttons_dict, default_text, parent=None):
        super().__init__("Buttons (diagram + remapping)", parent)
        layout = QHBoxLayout(self)
        self.diagram = MouseDiagram()
        self.diagram.load(profile_name)
        self.editor = ButtonsEditor(buttons_dict, default_text)
        layout.addWidget(self.diagram, 1)
        layout.addWidget(self.editor, 1)
