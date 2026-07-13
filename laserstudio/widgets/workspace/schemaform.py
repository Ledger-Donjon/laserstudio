"""
Schema-driven editable fields for the Config workspace, styled for the Ledger
dark theme.

This mirrors the type→widget mapping of the config generator's ``SchemaWidget``
(``config_generator/config_generator_widgets.py``) — integer→spin, number→
double-spin, boolean→toggle, string→line edit, enum→combo, ``const``→read-only,
number array→row of spins — but renders each field as a "label above, control
below" block matching the redesigned UI.

The resolved config schema (all ``$ref``/``allOf`` flattened) is loaded once from
the local ``config_schema/`` directory, without touching ``sys.argv`` (which the
Apply-restart mechanism relies on).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

import laserstudio
from ..newui import theme

# ── Resolved schema (cached) ──────────────────────────────────────────────────
_RESOLVED_SCHEMA: dict | None = None


def resolved_config_schema() -> dict:
    """Return the fully-resolved config schema (cached; local files only)."""
    global _RESOLVED_SCHEMA
    if _RESOLVED_SCHEMA is None:
        from ...config_generator import ref_resolve

        base = str(Path(laserstudio.__file__).parent / "config_schema") + os.sep
        ref_resolve.set_base_url(base)
        _RESOLVED_SCHEMA = ref_resolve.resolve_references("config.schema.json")
    return _RESOLVED_SCHEMA


def effective_properties(
    node: dict, type_value: Any
) -> tuple[dict[str, dict], set[str]]:
    """
    Merge a resolved node's base ``properties`` with the ``oneOf`` branch whose
    ``type`` const matches ``type_value``. Returns (properties, required-keys).
    """
    props: dict[str, dict] = dict(node.get("properties", {}))
    required: set[str] = set(node.get("required", []))
    for branch in node.get("oneOf", []):
        if not isinstance(branch, dict):
            continue
        branch_type = branch.get("properties", {}).get("type", {})
        if branch_type.get("const") == type_value:
            props.update(branch.get("properties", {}))
            required |= set(branch.get("required", []))
            break
    return props, required


# ── Interactive toggle ─────────────────────────────────────────────────────────
class ToggleSwitch(QWidget):
    """A clickable pill toggle matching the Ledger design."""

    toggled = pyqtSignal(bool)

    def __init__(self, on: bool = False) -> None:
        super().__init__()
        self._on = on
        self.setFixedSize(38, 20)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def isChecked(self) -> bool:  # noqa: N802 (Qt-style API)
        return self._on

    def setChecked(self, on: bool) -> None:  # noqa: N802
        if on != self._on:
            self._on = on
            self.update()
            self.toggled.emit(on)

    def mousePressEvent(self, a0) -> None:  # noqa: N802 (Qt override)
        self.setChecked(not self._on)

    def paintEvent(self, a0) -> None:  # noqa: N802 (Qt override)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(Qt.PenStyle.NoPen)
        h = self.height()
        track = QColor(theme.GREEN) if self._on else QColor(255, 255, 255, 40)
        p.setBrush(track)
        p.drawRoundedRect(QRectF(0, 0, self.width(), h), h / 2, h / 2)
        d = h - 4
        x = self.width() - d - 2 if self._on else 2
        p.setBrush(QColor("#0A0A0A"))
        p.drawEllipse(QRectF(x, 2, d, d))
        p.end()


# ── Styled input stylesheets ────────────────────────────────────────────────────
_INPUT_SS = f"""
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {theme.BG_CARD};
    border: 1px solid {theme.BORDER};
    border-radius: 5px;
    color: {theme.TEXT};
    padding: 7px 10px;
    font-size: 12px;
    selection-background-color: {theme.PURPLE_BG};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: 1px solid {theme.PURPLE_BORDER};
}}
QLineEdit:read-only {{ color: {theme.TEXT_MUTED}; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background: {theme.BG_CARD};
    border: 1px solid {theme.BORDER};
    color: {theme.TEXT};
    selection-background-color: {theme.PURPLE_BG};
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 14px; }}
"""


class SchemaField(QWidget):
    """
    One editable field driven by a (resolved) JSON-schema fragment.

    ``value()`` returns the current typed value. ``changed`` fires on any edit.
    Read-only fields (``const``, unsupported types) still display their value.
    """

    changed = pyqtSignal()

    def __init__(self, key: str, subschema: dict, value: Any) -> None:
        super().__init__()
        self.key = key
        self._subschema = subschema
        self._getter: Callable[[], Any] = lambda: value
        self.editable = True

        self.setStyleSheet("background: transparent;")
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(6)

        label = QLabel(_field_label_text(key, subschema))
        label.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-family: monospace; font-size: 10px;"
            " letter-spacing: 1px; background: transparent;"
        )
        desc = subschema.get("description")
        if desc:
            label.setToolTip(desc)
        box.addWidget(label)

        control = self._build_control(subschema, value)
        box.addWidget(control)

    # ── control construction ────────────────────────────────────────────────
    def _build_control(self, schema: dict, value: Any) -> QWidget:
        stype = schema.get("type", "object")
        suffix = schema.get("suffix")

        if "const" in schema:
            w = QLineEdit(str(value if value is not None else schema["const"]))
            w.setReadOnly(True)
            w.setStyleSheet(_INPUT_SS)
            self.editable = False
            self._getter = lambda v=schema["const"]: v
            return w

        if "enum" in schema:
            w = QComboBox()
            w.setStyleSheet(_INPUT_SS)
            options = [str(o) for o in schema["enum"]]
            w.addItems(options)
            if value is not None and str(value) in options:
                w.setCurrentText(str(value))
            w.currentTextChanged.connect(lambda _=None: self.changed.emit())
            self._getter = w.currentText
            return w

        if stype == "boolean":
            w = ToggleSwitch(bool(value) if value is not None else bool(schema.get("default", False)))
            w.toggled.connect(lambda _=False: self.changed.emit())
            self._getter = w.isChecked
            return w

        if stype in ("integer", "number"):
            w = QSpinBox() if stype == "integer" else QDoubleSpinBox()
            w.setStyleSheet(_INPUT_SS)
            w.setMinimum(schema.get("minimum", schema.get("exclusiveMinimum", -1_000_000)))
            w.setMaximum(schema.get("maximum", schema.get("exclusiveMaximum", 1_000_000)))
            if suffix:
                w.setSuffix(f" {suffix}")
            if isinstance(w, QDoubleSpinBox):
                w.setDecimals(3)
            if value is not None:
                w.setValue(value)
            elif "default" in schema:
                w.setValue(schema["default"])
            w.valueChanged.connect(lambda _=0: self.changed.emit())
            self._getter = w.value
            return w

        if stype == "array":
            items = schema.get("items", {})
            if items.get("type") in ("integer", "number"):
                return self._build_number_array(items, value, suffix)
            # non-numeric array: read-only summary for now
            return self._readonly(_stringify(value))

        if stype == "string":
            w = QLineEdit("" if value is None else str(value))
            w.setStyleSheet(_INPUT_SS)
            if "default" in schema and value is None:
                w.setText(str(schema["default"]))
            w.textChanged.connect(lambda _="": self.changed.emit())
            self._getter = w.text
            return w

        # objects / unknown → read-only display (editing deferred)
        return self._readonly(_stringify(value))

    def _build_number_array(self, items: dict, value: Any, suffix: str | None) -> QWidget:
        holder = QWidget()
        holder.setStyleSheet("background: transparent;")
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        is_int = items.get("type") == "integer"
        values = list(value) if isinstance(value, (list, tuple)) else []
        if not values:
            values = [0]
        spins: list[QSpinBox | QDoubleSpinBox] = []
        for v in values:
            s = QSpinBox() if is_int else QDoubleSpinBox()
            s.setStyleSheet(_INPUT_SS)
            s.setMinimum(items.get("minimum", -1_000_000))
            s.setMaximum(items.get("maximum", 1_000_000))
            if not is_int:
                s.setDecimals(3)
            if suffix:
                s.setSuffix(f" {suffix}")
            s.setValue(v)
            s.valueChanged.connect(lambda _=0: self.changed.emit())
            spins.append(s)
            row.addWidget(s)
        self._getter = lambda: [s.value() for s in spins]
        return holder

    def _readonly(self, text: str) -> QLineEdit:
        w = QLineEdit(text)
        w.setReadOnly(True)
        w.setStyleSheet(_INPUT_SS)
        self.editable = False
        return w

    def value(self) -> Any:
        return self._getter()


# ── helpers ─────────────────────────────────────────────────────────────────
def _field_label_text(key: str, schema: dict) -> str:
    title = schema.get("title")
    base = title if title else key.replace("_", " ")
    return base.upper()


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value)
    return str(value)
