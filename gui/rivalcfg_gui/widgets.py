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
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPainter
    HAS_SVG = True
except Exception:
    HAS_SVG = False

from . import diagram


class AspectSvgWidget(QWidget):
    """SVG view that preserves aspect ratio (fixes the squashed look)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._renderer = QSvgRenderer(self) if HAS_SVG else None
        self.setMinimumSize(280, 260)

    def load(self, path):
        if self._renderer and path:
            self._renderer.load(path)
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._renderer or not self._renderer.isValid():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        # white stage background with rounded look via stylesheet on parent;
        # paint here transparent and center with KeepAspectRatio
        size = self._renderer.defaultSize()
        if size.width() <= 0 or size.height() <= 0:
            return
        scaled = size.scaled(self.size(), Qt.KeepAspectRatio)
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        self._renderer.render(painter, __import__("PySide6.QtCore", fromlist=["QRectF"]).QRectF(x, y, scaled.width(), scaled.height()))


class MouseDiagram(QWidget):
    """Shows the doc SVG diagram for the current mouse (read-only reference)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        # Light "stage" card so the white doc SVGs read well on the dark theme
        self._stage = QWidget()
        self._stage.setObjectName("diagramStage")
        stage_layout = QVBoxLayout(self._stage)
        stage_layout.setContentsMargins(12, 8, 12, 8)
        self._svg = AspectSvgWidget() if HAS_SVG else None
        self._fallback = QLabel()
        self._fallback.setWordWrap(True)
        if self._svg:
            self._svg.setMinimumHeight(320)
            self._svg.setSizePolicy(
                __import__("PySide6.QtWidgets", fromlist=["QSizePolicy"]).QSizePolicy.Expanding,
                __import__("PySide6.QtWidgets", fromlist=["QSizePolicy"]).QSizePolicy.Expanding,
            )
            stage_layout.addWidget(self._svg, 1)
        stage_layout.addWidget(self._fallback)
        self._fallback.hide()
        layout.addWidget(self._stage, 1)

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

    def __init__(self, buttons_dict, default_text="", parent=None, columns=2):
        super().__init__(parent)
        self._buttons_dict = buttons_dict  # {"Button1": {...}, ...} from profile
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        from PySide6.QtWidgets import QGridLayout
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(2)
        self._combos = {}
        # Compact grid; left pane uses columns=1, center used columns=2
        for i, key in enumerate(buttons_dict.keys()):
            combo = QComboBox()
            combo.setEditable(True)
            combo.addItems(diagram.COMMON_TARGETS)
            combo.setToolTip("Pick a target or type any keyboard key (e.g. A, F5, semicolon) or multimedia key.")
            combo.currentTextChanged.connect(self._sync_to_text)
            combo.editTextChanged.connect(self._sync_to_text)
            self._combos[key.lower()] = combo
            if columns <= 1:
                grid.addWidget(QLabel(key), i, 0)
                grid.addWidget(combo, i, 1)
            else:
                grid.addWidget(QLabel(key), i // 2, (i % 2) * 2)
                grid.addWidget(combo, i // 2, (i % 2) * 2 + 1)
        root.addLayout(grid)

        # Advanced string collapsed by default — rarely needed
        self._adv_toggle = QPushButton("Advanced buttons() string ▸")
        self._adv_toggle.setCheckable(True)
        self._adv_toggle.setChecked(False)
        self._adv_toggle.toggled.connect(self._toggle_advanced)
        root.addWidget(self._adv_toggle)

        self._adv_wrap = QWidget()
        adv_layout = QVBoxLayout(self._adv_wrap)
        adv_layout.setContentsMargins(0, 0, 0, 0)
        adv_bar = QHBoxLayout()
        parse_btn = QPushButton("Parse text → dropdowns")
        parse_btn.clicked.connect(self._sync_from_text)
        adv_bar.addWidget(parse_btn)
        adv_layout.addLayout(adv_bar)
        self._text = QTextEdit(default_text)
        self._text.setMaximumHeight(56)
        self._text.setPlaceholderText("buttons(button1=button1; ...; layout=qwerty)")
        adv_layout.addWidget(self._text)
        self._adv_wrap.hide()
        root.addWidget(self._adv_wrap)
        self._syncing = False
        self.set_value(default_text)

    def _toggle_advanced(self, checked):
        self._adv_wrap.setVisible(checked)
        self._adv_toggle.setText("Advanced buttons() string ▾" if checked else "Advanced buttons() string ▸")

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
