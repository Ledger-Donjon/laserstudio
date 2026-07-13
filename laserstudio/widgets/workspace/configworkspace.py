"""
Config workspace: load a project's config.yaml and edit the configured bench.

Layout (three columns):
  * left sidebar  — project folder, config-file status and file-level actions
                    (Save / Revert from file, enabled once the file is modified)
  * middle        — instrument *tree* (application root + instruments and their
                    sub-instruments), drawn as connected cards over a grid canvas
  * right         — the selected node's parameters as a schema-driven editable
                    form, with Update / Revert (per-instrument pending edits) and
                    Delete at the bottom

Editing model (two levels):
  * Per instrument: the form holds *pending* edits. **Update** commits them into
    the in-memory working config; **Revert** discards them. **Delete** removes the
    instrument from the working config.
  * File level: whenever the working config differs from the file on disk, the
    file is flagged *modified*. **Save** writes it back; **Revert from file**
    reloads from disk. After a successful Save, the user is offered a relaunch so
    the running instruments pick up the new configuration.
"""
from __future__ import annotations

import copy
import os
import subprocess
import sys
from pathlib import Path
from typing import Callable

import yaml
from PyQt6.QtCore import QPoint, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ... import __version__
from ...utils.yaml_types import Config
from ..newui import lucide, theme
from .schemaform import (
    SchemaField,
    ToggleSwitch,
    effective_properties,
    oneof_type_options,
    resolved_config_schema,
    type_selector_field,
)
from .workspace import Workspace

_ERROR_RED = "#F04F52"

_DELETE_BTN_SS = (
    "QPushButton {"
    "  background: rgba(240,79,82,0.10);"
    "  border: 1px solid rgba(240,79,82,0.35);"
    "  border-radius: 5px; padding: 6px 12px; }"
    "QPushButton:hover { background: rgba(240,79,82,0.18); }"
    "QPushButton:disabled {"
    "  background: rgba(255,255,255,0.02);"
    "  border-color: rgba(255,255,255,0.06); }"
)


def _short_version() -> str:
    """Short 'v1.1.0' form of the package version for compact display."""
    return "v" + __version__.split("+")[0].split(".post")[0]


def _clear_layout(layout: QLayout) -> None:
    """Remove and delete every widget/sub-layout from a layout."""
    while (item := layout.takeAt(0)) is not None:
        w = item.widget()
        if w is not None:
            w.setParent(None)
            w.deleteLater()
        else:
            child = item.layout()
            if child is not None:
                _clear_layout(child)


class InstrumentCard(QFrame):
    """
    Selectable card used as a node in the instrument tree.

    Shows an icon (any pixmap), a title, a mono subtitle and a short mono
    status on the right. Emits ``clicked`` when pressed; call
    :meth:`setSelected` to toggle the purple-accent selected state.
    """

    clicked = pyqtSignal()

    def __init__(
        self,
        icon_pixmap,
        title: str,
        subtitle: str,
        status_text: str,
        status_color: str,
        title_dim: bool = False,
    ) -> None:
        super().__init__()
        self._selected = False
        self.setObjectName("ls-inst-card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(10)

        icon = QLabel()
        icon.setPixmap(icon_pixmap)
        icon.setFixedWidth(18)
        icon.setStyleSheet("background: transparent;")
        lay.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)

        info = QVBoxLayout()
        info.setSpacing(2)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"color: {theme.TEXT_DIM if title_dim else theme.TEXT};"
            " font-size: 12px; background: transparent;"
        )
        info.addWidget(title_lbl)
        sub_lbl = QLabel(subtitle)
        sub_lbl.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-family: monospace;"
            " font-size: 10px; background: transparent;"
        )
        info.addWidget(sub_lbl)
        lay.addLayout(info, 1)

        status = QLabel(status_text)
        status.setStyleSheet(
            f"color: {status_color};"
            " font-family: monospace; font-size: 9px; background: transparent;"
        )
        lay.addWidget(status, 0, Qt.AlignmentFlag.AlignTop)

        self._apply_style()

    def _apply_style(self) -> None:
        if self._selected:
            self.setStyleSheet(
                f"QFrame#ls-inst-card {{ background: {theme.PURPLE_BG};"
                f" border: 1px solid {theme.PURPLE_BORDER}; border-radius: 5px; }}"
            )
        else:
            self.setStyleSheet(
                f"QFrame#ls-inst-card {{ background: {theme.BG_CARD};"
                f" border: 1px solid {theme.BORDER}; border-radius: 5px; }}"
                f"QFrame#ls-inst-card:hover {{ border: 1px solid {theme.BORDER_HOVER}; }}"
            )

    def setSelected(self, selected: bool) -> None:
        self._selected = selected
        self._apply_style()

    def mousePressEvent(self, a0) -> None:  # noqa: N802 (Qt override)
        self.clicked.emit()
        super().mousePressEvent(a0)


class _TreeView(QWidget):
    """
    Vertical stack of node cards, indented by depth, with continuous connector
    lines painted per parent (one vertical spine + an elbow to each child).
    """

    INDENT = 22
    BASE_W = 360

    def __init__(self) -> None:
        super().__init__()
        self.setStyleSheet("background: transparent;")
        self._connections: list[tuple[QWidget, list[QWidget]]] = []
        self._v = QVBoxLayout(self)
        self._v.setContentsMargins(0, 0, 0, 0)
        self._v.setSpacing(8)

    def add_card(self, card: QWidget, depth: int) -> None:
        card.setFixedWidth(max(200, self.BASE_W - depth * self.INDENT))
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        h = QHBoxLayout(row)
        h.setContentsMargins(depth * self.INDENT, 0, 0, 0)
        h.setSpacing(0)
        h.addWidget(card)
        self._v.addWidget(row)

    def set_connections(self, connections: list[tuple[QWidget, list[QWidget]]]) -> None:
        self._connections = connections

    def _rect_in_self(self, widget: QWidget) -> QRect:
        return QRect(widget.mapTo(self, QPoint(0, 0)), widget.size())

    def paintEvent(self, a0) -> None:  # noqa: N802 (Qt override)
        p = QPainter(self)
        color = QColor(255, 255, 255, 48)
        for parent, children in self._connections:
            if not children:
                continue
            pgeo = self._rect_in_self(parent)
            spine_x = pgeo.left() + 11
            last_mid = self._rect_in_self(children[-1]).center().y()
            top = pgeo.bottom() + 1
            p.fillRect(spine_x, top, 1, max(0, last_mid - top), color)
            for child in children:
                cgeo = self._rect_in_self(child)
                cmid = cgeo.center().y()
                p.fillRect(spine_x, cmid, cgeo.left() - spine_x, 1, color)
        p.end()


class _GridCanvas(QWidget):
    """Viewer-like backdrop: 34px grid, corner brackets and a mono HUD label."""

    def paintEvent(self, a0) -> None:  # noqa: N802 (Qt override)
        p = QPainter(self)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor(theme.BG_MAIN))

        p.setPen(QColor(255, 255, 255, 7))
        step = 34
        gx = 0
        while gx <= w:
            p.drawLine(gx, 0, gx, h)
            gx += step
        gy = 0
        while gy <= h:
            p.drawLine(0, gy, w, gy)
            gy += step

        p.setPen(QColor(255, 255, 255, 60))
        m, side = 14, 16
        p.drawLine(m, m, m + side, m)
        p.drawLine(m, m, m, m + side)
        p.drawLine(w - m - side, m, w - m, m)
        p.drawLine(w - m, m, w - m, m + side)
        p.drawLine(m, h - m, m + side, h - m)
        p.drawLine(m, h - m, m, h - m - side)
        p.drawLine(w - m - side, h - m, w - m, h - m)
        p.drawLine(w - m, h - m, w - m, h - m - side)

        p.setPen(QColor(255, 255, 255, 130))
        font = QFont("monospace")
        font.setPixelSize(10)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.5)
        p.setFont(font)
        p.drawText(22, 30, "CONFIG · INSTRUMENT TREE")
        p.end()


class ConfigWorkspace(Workspace):
    """Project folder + editable configured-bench inspector."""

    label = "Config"
    icon = "file-cog"

    #: Config keys whose value is a nested instrument, with the icon to use.
    _SUB_ICONS = {"shutter": "aperture", "light": "lightbulb", "lighting": "lightbulb"}

    def __init__(
        self,
        yaml_config: Config | None,
        config_path: Path,
        config_loaded: bool,
        window: QWidget,
    ) -> None:
        self._config_path = config_path
        self._config_loaded = config_loaded
        self._window = window  # parent for dialogs

        # Three states: file on disk (saved), in-memory committed (working),
        # and the pending edits held live in the current form's widgets.
        self._saved_config: dict = copy.deepcopy(yaml_config) if yaml_config else {}
        self._working_config: dict = copy.deepcopy(self._saved_config)
        self._file_modified = False

        try:
            self._schema: dict | None = resolved_config_schema()
        except Exception:
            self._schema = None  # editing falls back to read-only if unavailable

        # UI references (filled by build_panel / build_content)
        self._status_lbl: QLabel | None = None
        self._save_btn: QPushButton | None = None
        self._revert_file_btn: QPushButton | None = None
        self._tree_layout: QVBoxLayout | None = None
        self._detail_layout: QVBoxLayout | None = None

        # Per-form editing state
        self._selected = 0
        self._cards: list[InstrumentCard] = []
        self._field_specs: list[tuple[str, Callable[[], object], object]] = []
        self._current_entry: dict | None = None
        self._update_btn: QPushButton | None = None
        self._revert_btn: QPushButton | None = None
        self._form_draft: dict[str, object] = {}

        self._folder_name_lbl: QLabel | None = None
        self._folder_path_lbl: QLabel | None = None

        self._rebuild_model()

    # ── Instrument model ──────────────────────────────────────────────────────

    def _rebuild_model(self) -> None:
        """(Re)collect entries from the working config after any structural change."""
        self._instruments_data = self._collect_instruments()
        self._tree_root: dict = {
            "kind": "app",
            "name": "Laser Studio",
            "icon": None,
            "label": "Laser Studio",
            "subtitle": "application",
            "params": {},
            "schema": None,
            "subkeys": set(),
            "location": None,
            "children": self._instruments_data,
        }
        self._entries: list[dict] = []
        self._flatten(self._tree_root, 0, self._entries)

    def _make_entry(
        self,
        kind: str,
        name: str,
        icon: str,
        cfg: dict,
        schema: dict | None,
        location: dict,
    ) -> dict:
        """Build one entry from a config dict, nesting any sub-instruments."""
        children: list[dict] = []
        subkeys: set[str] = set()
        for key, value in cfg.items():
            # A nested dict that looks like an instrument (has type/label/enable)
            # is a sub-instrument (e.g. a laser's shutter, a camera's light).
            if isinstance(value, dict) and any(
                k in value for k in ("type", "label", "enable")
            ):
                subkeys.add(key)
                sub_icon = self._SUB_ICONS.get(key, "sliders-horizontal")
                children.append(
                    self._make_entry(
                        "subinstrument",
                        key.capitalize(),
                        sub_icon,
                        value,
                        None,
                        {"kind": "sub", "parent": cfg, "key": key},
                    )
                )
        return {
            "kind": kind,
            "name": name,
            "icon": icon,
            "label": cfg.get("label") or name,
            "enabled": cfg.get("enable", True),
            "type": cfg.get("type"),
            "params": cfg,
            "schema": schema,
            "subkeys": subkeys,
            "location": location,
            "children": children,
        }

    def _node_schema(self, key: str, is_list: bool) -> dict | None:
        if self._schema is None:
            return None
        node = self._schema.get("properties", {}).get(key)
        if not isinstance(node, dict):
            return None
        return node.get("items") if is_list else node

    def _collect_instruments(self) -> list[dict]:
        """Build the top-level instrument entries (with nested sub-instruments)."""
        sections: list[tuple[str, str, str, bool]] = [
            # (config_key, display_name, lucide_icon, is_list)
            ("camera", "Camera", "camera", False),
            ("stage", "Stage", "move", False),
            ("lasers", "Laser", "zap", True),
            ("probes", "Probe", "crosshair", True),
            ("lighting", "Light", "lightbulb", False),
            ("focus", "Focus", "scan-eye", False),
        ]
        cfg = self._working_config
        result: list[dict] = []
        for key, name, icon_name, is_list in sections:
            data = cfg.get(key)
            if data is None:
                continue
            node = self._node_schema(key, is_list)
            entries = data if (is_list and isinstance(data, list)) else [data]
            for idx, item in enumerate(entries):
                if not isinstance(item, dict):
                    continue
                if is_list:
                    location = {"kind": "list", "list_key": key, "list_index": idx}
                else:
                    location = {"kind": "single", "key": key}
                entry = self._make_entry(
                    "instrument", name, icon_name, item, node, location
                )
                if not item.get("label"):
                    entry["label"] = f"{name} {idx + 1}" if is_list else name
                result.append(entry)
        return result

    def _flatten(self, entry: dict, depth: int, out: list[dict]) -> None:
        entry["depth"] = depth
        out.append(entry)
        for child in entry.get("children", []):
            self._flatten(child, depth + 1, out)

    # ── Left panel ────────────────────────────────────────────────────────────

    def build_panel(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"QScrollArea {{ border: none; background: {theme.BG_PANEL}; }}"
        )

        inner = theme.panel_inner()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(16)

        layout.addWidget(theme.eyebrow("WORKSPACE · CONFIG"))
        layout.addWidget(theme.section_title("Project folder", "folder"))

        project_dir = Path(os.getcwd())
        folder_card = QFrame()
        folder_card.setObjectName("ls-card")
        folder_card.setStyleSheet(
            f"QFrame#ls-card {{ background: {theme.BG_CARD};"
            f" border: 1px solid {theme.BORDER}; border-radius: 5px; }}"
        )
        fc_layout = QVBoxLayout(folder_card)
        fc_layout.setContentsMargins(12, 11, 12, 11)
        fc_layout.setSpacing(8)

        name_row = QHBoxLayout()
        name_row.setSpacing(9)
        folder_icon = QLabel()
        folder_icon.setPixmap(lucide.pixmap("folder-open", 16, theme.PURPLE))
        folder_icon.setFixedWidth(20)
        folder_icon.setStyleSheet("background: transparent;")
        name_row.addWidget(folder_icon, 0, Qt.AlignmentFlag.AlignTop)
        name_info = QVBoxLayout()
        name_info.setSpacing(1)
        self._folder_name_lbl = QLabel(project_dir.name)
        self._folder_name_lbl.setStyleSheet(
            f"color: {theme.TEXT}; font-size: 12px; background: transparent;"
        )
        name_info.addWidget(self._folder_name_lbl)
        self._folder_path_lbl = QLabel(str(project_dir))
        self._folder_path_lbl.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-family: monospace; font-size: 9px;"
            " background: transparent;"
        )
        self._folder_path_lbl.setWordWrap(True)
        self._folder_path_lbl.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        name_info.addWidget(self._folder_path_lbl)
        name_row.addLayout(name_info, stretch=1)
        fc_layout.addLayout(name_row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        open_btn = QPushButton("Open…")
        open_btn.setStyleSheet(theme.GHOST_BTN)
        open_btn.setIcon(lucide.icon("folder-open", 14, theme.TEXT_MUTED))
        open_btn.clicked.connect(self._open_project_folder)
        reveal_btn = QPushButton("Reveal")
        reveal_btn.setStyleSheet(theme.GHOST_BTN)
        reveal_btn.setIcon(lucide.icon("external-link", 14, theme.TEXT_MUTED))
        reveal_btn.clicked.connect(
            lambda: subprocess.run(["open", os.getcwd()], check=False)
        )
        btn_row.addWidget(open_btn)
        btn_row.addWidget(reveal_btn)
        fc_layout.addLayout(btn_row)

        layout.addWidget(folder_card)

        # ── Configuration file: status + file-level actions ───────────────────
        layout.addWidget(theme.section_title("Bench configuration", "file-cog"))

        cfg_status_card = QFrame()
        cfg_status_card.setObjectName("ls-card")
        cfg_status_card.setStyleSheet(
            f"QFrame#ls-card {{ background: {theme.BG_CARD};"
            f" border: 1px solid {theme.BORDER}; border-radius: 5px; }}"
        )
        cs_layout = QHBoxLayout(cfg_status_card)
        cs_layout.setContentsMargins(12, 9, 12, 9)
        cfg_file_lbl = QLabel(self._config_path.name)
        cfg_file_lbl.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-family: monospace; font-size: 11px;"
            " background: transparent;"
        )
        cs_layout.addWidget(cfg_file_lbl, stretch=1)
        self._status_lbl = QLabel()
        cs_layout.addWidget(self._status_lbl)
        layout.addWidget(cfg_status_card)

        file_btns = QHBoxLayout()
        file_btns.setSpacing(8)
        self._save_btn = QPushButton("Save")
        self._save_btn.setStyleSheet(theme.PURPLE_BTN)
        self._save_btn.setIcon(lucide.icon("save", 14, theme.PURPLE))
        self._save_btn.clicked.connect(self._save_file)
        self._revert_file_btn = QPushButton("Revert")
        self._revert_file_btn.setStyleSheet(theme.GHOST_BTN)
        self._revert_file_btn.setToolTip("Discard all changes and reload from disk")
        self._revert_file_btn.clicked.connect(self._revert_from_file)
        file_btns.addWidget(self._save_btn, 1)
        file_btns.addWidget(self._revert_file_btn, 1)
        layout.addLayout(file_btns)

        layout.addStretch()
        scroll.setWidget(inner)
        self._update_file_ui()
        return scroll

    # ── Middle + right content ────────────────────────────────────────────────

    def build_content(self) -> QWidget:
        container = QWidget()
        container.setObjectName("ls-config-content")
        container.setStyleSheet(
            f"QWidget#ls-config-content {{ background: {theme.BG_MAIN}; }}"
        )
        hbox = QHBoxLayout(container)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(0)

        tree_host = QWidget()
        tree_host.setMinimumWidth(420)
        tree_host.setStyleSheet(f"background: {theme.BG_MAIN};")
        self._tree_layout = QVBoxLayout(tree_host)
        self._tree_layout.setContentsMargins(0, 0, 0, 0)

        detail_host = QWidget()
        detail_host.setMinimumWidth(300)
        detail_host.setStyleSheet(f"background: {theme.BG_PANEL};")
        self._detail_layout = QVBoxLayout(detail_host)
        self._detail_layout.setContentsMargins(0, 0, 0, 0)

        splitter = theme.LineSplitter()
        splitter.addWidget(tree_host)
        splitter.addWidget(detail_host)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([880, 340])
        hbox.addWidget(splitter)

        self._refresh_tree()
        self.select_card(0)
        return container

    def _make_card(self, entry: dict) -> InstrumentCard:
        if entry["kind"] == "app":
            return InstrumentCard(
                lucide.ledger_pixmap(16, theme.PURPLE),
                entry["label"],
                entry["subtitle"],
                _short_version(),
                theme.TEXT_DIM,
            )
        enabled = entry["enabled"]
        bits = [entry["type"], entry["name"].lower()]
        subtitle = " · ".join(str(b) for b in bits if b)
        return InstrumentCard(
            lucide.pixmap(entry["icon"], 16, theme.PURPLE if enabled else theme.TEXT_DIM),
            entry["label"],
            subtitle,
            "ENABLED" if enabled else "DISABLED",
            theme.GREEN if enabled else theme.TEXT_DIM,
            title_dim=not enabled,
        )

    def _refresh_tree(self) -> None:
        if self._tree_layout is None:
            return
        _clear_layout(self._tree_layout)
        self._tree_layout.addWidget(self._make_tree_canvas())

    def _make_tree_canvas(self) -> QWidget:
        canvas = _GridCanvas()
        canvas.setMinimumWidth(420)
        outer = QVBoxLayout(canvas)
        outer.setContentsMargins(24, 46, 24, 24)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll.viewport().setStyleSheet("background: transparent;")

        holder = QWidget()
        holder.setStyleSheet("background: transparent;")
        hv = QVBoxLayout(holder)
        hv.setContentsMargins(0, 0, 0, 0)
        hv.setSpacing(0)

        center_row = QHBoxLayout()
        center_row.setContentsMargins(0, 0, 0, 0)
        center_row.addStretch()

        tree = _TreeView()
        self._cards = []
        for index, entry in enumerate(self._entries):
            card = self._make_card(entry)
            card.clicked.connect(lambda _=False, idx=index: self.select_card(idx))
            entry["_card"] = card
            self._cards.append(card)
            tree.add_card(card, entry["depth"])

        connections: list[tuple[QWidget, list[QWidget]]] = []
        for entry in self._entries:
            children = entry.get("children", [])
            if children:
                connections.append((entry["_card"], [c["_card"] for c in children]))
        tree.set_connections(connections)

        center_row.addWidget(tree)
        center_row.addStretch()
        hv.addLayout(center_row)
        hv.addStretch()

        scroll.setWidget(holder)
        outer.addWidget(scroll)
        return canvas

    # ── Selection / detail ────────────────────────────────────────────────────

    def select_card(self, index: int) -> None:
        if not self._entries:
            return
        index = max(0, min(index, len(self._entries) - 1))
        if index != self._selected:
            self._form_draft = {}
        self._selected = index
        for j, card in enumerate(self._cards):
            card.setSelected(j == index)
        self._show_detail()

    def _show_detail(self) -> None:
        if self._detail_layout is None:
            return
        _clear_layout(self._detail_layout)
        self._field_specs = []
        self._current_entry = None
        self._update_btn = None
        self._revert_btn = None
        entry = self._entries[self._selected]
        self._current_entry = entry
        if entry["kind"] == "app":
            widget = self._build_app_page()
        else:
            widget = self._build_instrument_form(entry)
        self._detail_layout.addWidget(widget)

    def _form_shell(self) -> tuple[QScrollArea, QVBoxLayout]:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"QScrollArea {{ border: none; background: {theme.BG_PANEL}; }}"
        )
        inner = theme.panel_inner()
        col = QVBoxLayout(inner)
        col.setContentsMargins(18, 18, 18, 18)
        col.setSpacing(14)
        scroll.setWidget(inner)
        return scroll, col

    def _title_row(
        self, pixmap, name: str, chip_text: str = "",
        chip_fg: str = "", chip_bg: str = ""
    ) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)
        icon = QLabel()
        icon.setPixmap(pixmap)
        icon.setFixedWidth(26)
        icon.setStyleSheet("background: transparent;")
        row.addWidget(icon, 0, Qt.AlignmentFlag.AlignVCenter)
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(
            f"color: {theme.TEXT}; font-family: 'Brut Grotesque'; font-weight: 700;"
            " font-size: 18px; background: transparent;"
        )
        row.addWidget(name_lbl)
        row.addStretch()
        if chip_text:
            chip = QLabel(chip_text)
            chip.setStyleSheet(
                f"color: {chip_fg}; background: {chip_bg};"
                " font-family: monospace; font-size: 10px;"
                " border-radius: 4px; padding: 4px 10px;"
            )
            row.addWidget(chip, 0, Qt.AlignmentFlag.AlignVCenter)
        return row

    def _instrument_eyebrow(self, entry: dict) -> str:
        prefix = "SUB-INSTRUMENT" if entry["kind"] == "subinstrument" else "INSTRUMENT"
        return f"{prefix} · {entry['name'].upper()}"

    def _build_app_page(self) -> QWidget:
        scroll, col = self._form_shell()
        col.addWidget(theme.eyebrow("APPLICATION"))
        col.addLayout(
            self._title_row(
                lucide.ledger_pixmap(24, theme.PURPLE),
                "Laser Studio",
                _short_version(),
                theme.PURPLE,
                theme.PURPLE_BG,
            )
        )
        col.addSpacing(2)
        col.addWidget(theme.eyebrow("PARAMETERS"))

        rest = self._working_config.get("restserver")
        if isinstance(rest, dict):
            rest_text = f"{rest.get('host', 'localhost')}:{rest.get('port', 4444)}"
        else:
            rest_text = "disabled"
        rows = [
            ("version", __version__),
            ("configuration", self._config_path.name),
            ("REST server", rest_text),
            ("instruments", str(len(self._instruments_data))),
        ]
        for key, value in rows:
            col.addWidget(theme.param_row(key, value))
        col.addStretch()
        return scroll

    def _build_instrument_form(self, entry: dict) -> QWidget:
        scroll, col = self._form_shell()
        self._current_entry = entry
        enabled = entry["enabled"]
        params: dict = entry["params"]

        col.addWidget(theme.eyebrow(self._instrument_eyebrow(entry)))
        col.addLayout(
            self._title_row(
                lucide.pixmap(
                    entry["icon"], 24, theme.PURPLE if enabled else theme.TEXT_DIM
                ),
                entry["label"],
            )
        )
        col.addSpacing(2)
        col.addWidget(theme.eyebrow("PARAMETERS"))

        node = entry.get("schema")
        type_options = (
            oneof_type_options(node) if isinstance(node, dict) else []
        )
        effective_type = self._param_value(entry, "type")
        if effective_type is None:
            effective_type = entry.get("type")

        props, _req = (
            effective_properties(node, effective_type)
            if isinstance(node, dict)
            else ({}, set())
        )

        if len(type_options) > 1:
            type_sel, type_wrap = type_selector_field(
                type_options, str(effective_type or "")
            )
            committed_type = entry["params"].get("type")
            self._field_specs.append(("type", type_sel.value, committed_type))
            type_sel.changed.connect(self._on_instrument_type_changed)
            col.addWidget(type_wrap)

        skip = {"enable"} | entry.get("subkeys", set())
        ordered: list[str] = []
        for key in ("label", "type"):
            if key in props or key in params:
                ordered.append(key)
        ordered += [k for k in props if k not in ordered and k not in skip]
        ordered += [k for k in params if k not in ordered and k not in skip]

        for key in ordered:
            if key == "type" and len(type_options) > 1:
                continue
            subschema = props.get(key)
            if subschema is None:
                subschema = {"type": "string"} if key == "label" else {}
            field = SchemaField(key, subschema, self._param_value(entry, key))
            if field.editable:
                init = field.value()
                self._field_specs.append((key, field.value, init))
                field.changed.connect(self._recompute_dirty)
            col.addWidget(field)

        # "Enabled at startup" — interactive toggle bound to `enable`.
        toggle_box = QFrame()
        toggle_box.setObjectName("ls-card")
        toggle_box.setStyleSheet(
            f"QFrame#ls-card {{ background: {theme.BG_CARD};"
            f" border: 1px solid {theme.BORDER}; border-radius: 5px; }}"
        )
        tl = QHBoxLayout(toggle_box)
        tl.setContentsMargins(12, 9, 12, 9)
        tlabel = QLabel("Enabled at startup")
        tlabel.setStyleSheet(
            f"color: {theme.TEXT}; font-size: 12px; background: transparent;"
        )
        tl.addWidget(tlabel)
        tl.addStretch()
        enable_toggle = ToggleSwitch(enabled)
        self._field_specs.append(("enable", enable_toggle.isChecked, enabled))
        enable_toggle.toggled.connect(self._recompute_dirty)
        tl.addWidget(enable_toggle)
        col.addWidget(toggle_box)

        col.addStretch()

        # Bottom actions: Update / Revert (pending edits) + Delete.
        actions = QHBoxLayout()
        actions.setSpacing(8)
        self._update_btn = QPushButton("Update")
        self._update_btn.setStyleSheet(theme.PURPLE_BTN)
        self._update_btn.setEnabled(False)
        self._update_btn.setToolTip("Apply these edits to the working configuration")
        self._update_btn.clicked.connect(self._commit_update)
        self._revert_btn = QPushButton("Revert")
        self._revert_btn.setStyleSheet(theme.GHOST_BTN)
        self._revert_btn.setEnabled(False)
        self._revert_btn.setToolTip("Discard pending edits for this instrument")
        self._revert_btn.clicked.connect(self._revert_instrument)
        delete_btn = QPushButton()
        delete_btn.setIcon(lucide.icon("trash-2", 15, _ERROR_RED))
        delete_btn.setFixedWidth(40)
        delete_btn.setToolTip("Delete this instrument from the configuration")
        delete_btn.setStyleSheet(_DELETE_BTN_SS)
        delete_btn.clicked.connect(lambda: self._delete_instrument(entry))
        actions.addWidget(self._update_btn, 1)
        actions.addWidget(self._revert_btn, 1)
        actions.addWidget(delete_btn)
        col.addLayout(actions)
        return scroll

    def _param_value(self, entry: dict, key: str) -> object:
        if key in self._form_draft:
            return self._form_draft[key]
        return entry["params"].get(key)

    def _collect_form_draft(self) -> None:
        for key, getter, _init in self._field_specs:
            self._form_draft[key] = getter()

    def _on_instrument_type_changed(self, new_type: str) -> None:
        self._collect_form_draft()
        self._form_draft["type"] = new_type
        self._refresh_instrument_form()

    def _refresh_instrument_form(self) -> None:
        if self._detail_layout is None or self._current_entry is None:
            return
        entry = self._current_entry
        if entry["kind"] == "app":
            return
        _clear_layout(self._detail_layout)
        self._field_specs = []
        self._update_btn = None
        self._revert_btn = None
        widget = self._build_instrument_form(entry)
        self._detail_layout.addWidget(widget)
        self._recompute_dirty()

    # ── Per-instrument editing (pending edits) ────────────────────────────────

    def _recompute_dirty(self) -> None:
        dirty = any(getter() != init for _key, getter, init in self._field_specs)
        if self._update_btn is not None:
            self._update_btn.setEnabled(dirty)
        if self._revert_btn is not None:
            self._revert_btn.setEnabled(dirty)

    def _commit_update(self) -> None:
        entry = self._current_entry
        if entry is None:
            return
        for key, getter, init in self._field_specs:
            value = getter()
            if value != init:
                entry["params"][key] = value
        self._recompute_file_modified()
        self._rebuild_model()
        self._refresh_tree()
        self._form_draft = {}
        self.select_card(self._selected)  # rebuilds the form -> pending cleared

    def _revert_instrument(self) -> None:
        # Rebuild the form from the (unchanged) working config, dropping edits.
        self._form_draft = {}
        self._show_detail()

    def _delete_instrument(self, entry: dict) -> None:
        reply = QMessageBox.question(
            self._window,
            "Delete instrument",
            f"Remove '{entry['label']}' from the configuration?",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Ok:
            return
        loc = entry.get("location") or {}
        kind = loc.get("kind")
        if kind == "list":
            lst = self._working_config.get(loc["list_key"])
            if isinstance(lst, list) and 0 <= loc["list_index"] < len(lst):
                lst.pop(loc["list_index"])
                if not lst:
                    self._working_config.pop(loc["list_key"], None)
        elif kind == "single":
            self._working_config.pop(loc["key"], None)
        elif kind == "sub":
            loc["parent"].pop(loc["key"], None)
        self._recompute_file_modified()
        self._rebuild_model()
        self._refresh_tree()
        self.select_card(0)

    # ── File-level state (modified / save / revert) ───────────────────────────

    def _recompute_file_modified(self) -> None:
        self._file_modified = self._working_config != self._saved_config
        self._update_file_ui()

    def _update_file_ui(self) -> None:
        if self._status_lbl is not None:
            if self._file_modified:
                text, color = "MODIFIED", theme.ACCENT
            elif self._config_loaded:
                text, color = "LOADED", theme.GREEN
            else:
                text, color = "NOT FOUND", theme.ACCENT
            self._status_lbl.setText(text)
            self._status_lbl.setStyleSheet(
                f"color: {color}; font-family: monospace; font-size: 10px;"
                " background: transparent;"
            )
        if self._save_btn is not None:
            self._save_btn.setEnabled(self._file_modified)
        if self._revert_file_btn is not None:
            self._revert_file_btn.setEnabled(self._file_modified)

    def _revert_from_file(self) -> None:
        self._working_config = copy.deepcopy(self._saved_config)
        self._recompute_file_modified()
        self._rebuild_model()
        self._refresh_tree()
        self.select_card(0)

    def _save_file(self) -> None:
        self._write_config_to_disk()
        self._saved_config = copy.deepcopy(self._working_config)
        self._config_loaded = True
        self._recompute_file_modified()
        self._propose_relaunch()

    def _write_config_to_disk(self) -> None:
        # Preserve any leading comment lines (e.g. the yaml-language-server hint).
        header = ""
        try:
            with open(self._config_path) as f:
                kept = []
                for line in f:
                    if line.lstrip().startswith("#"):
                        kept.append(line)
                    else:
                        break
                header = "".join(kept)
        except OSError:
            pass
        with open(self._config_path, "w") as f:
            if header:
                f.write(header)
            yaml.safe_dump(
                self._working_config, f, sort_keys=False, allow_unicode=True
            )

    def _propose_relaunch(self) -> None:
        reply = QMessageBox.question(
            self._window,
            "Configuration saved",
            f"{self._config_path.name} has been saved.\n\n"
            "Relaunch Laser Studio now to reload all instruments with the new "
            "configuration?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            os.execv(sys.executable, [sys.executable] + sys.argv)

    # ── Project folder picker ─────────────────────────────────────────────────

    def _open_project_folder(self) -> None:
        """Open a folder picker; if the folder contains config.yaml, restart."""
        folder_str = QFileDialog.getExistingDirectory(
            self._window,
            "Select project folder",
            os.getcwd(),
        )
        if not folder_str:
            return

        folder = Path(folder_str)
        config_file = folder / "config.yaml"

        if not config_file.exists():
            QMessageBox.warning(
                self._window,
                "No config.yaml found",
                f"The selected folder does not contain a config.yaml file:\n{folder}\n\n"
                "Please choose a valid project folder.",
            )
            return

        reply = QMessageBox.question(
            self._window,
            "Change project folder",
            f"Restart Laser Studio from:\n{folder}\n\n"
            "All instruments will be reloaded with the new configuration.",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Ok:
            return

        if self._folder_name_lbl is not None:
            self._folder_name_lbl.setText(folder.name)
        if self._folder_path_lbl is not None:
            self._folder_path_lbl.setText(str(folder))

        os.chdir(str(folder))
        os.execv(sys.executable, [sys.executable] + sys.argv)
