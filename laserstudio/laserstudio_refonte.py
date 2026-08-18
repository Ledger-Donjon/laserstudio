from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .instruments.instruments import Instruments
from .utils.scanzones import ScanZones
from .utils.util import resource_path
from .utils.yaml_types import Config
from .widgets.newui import lucide, theme
from .widgets.newui.status_bar import StatusBar
from .widgets.newui.viewer_hud import ViewerArea
from .widgets.viewer import Viewer
from .widgets.workspace import (
    AnalyzeWorkspace,
    ConfigWorkspace,
    PhotoemissionWorkspace,
    ScanWorkspace,
    SettingsWorkspace,
    Workspace,
)


class LaserStudioRefonte(QMainWindow):
    """
    New Laser Studio window — progressive UI redesign.

    Runs alongside the classic window; shares the same Instruments instance
    so no hardware connection is duplicated. The window is a thin orchestrator:
    it holds a list of :class:`Workspace` objects and wires each one's panel
    (left column) and content (right side) into stacked widgets. All
    per-workspace logic lives in ``widgets/workspace.py``.
    """

    def __init__(
        self,
        instruments: Instruments,
        config_path: Path | None = None,
        config_loaded: bool = False,
        yaml_config: Config | None = None,
        scan_zones: ScanZones | None = None,
    ) -> None:
        """:param scan_zones: Scan zone model shared with the classic window."""
        super().__init__()
        self.instruments = instruments
        config_path = config_path or Path("config.yaml")
        self.yaml_config = yaml_config
        self.laser_armed = False
        self._scan_zones = scan_zones

        self.setWindowTitle("Laser Studio · New UI")
        self.setMinimumSize(1200, 720)

        # The ordered set of workspaces shown as tabs.
        self._workspaces: list[Workspace] = [
            ConfigWorkspace(yaml_config, config_path, config_loaded, self),
            SettingsWorkspace(self),
            PhotoemissionWorkspace(),
            ScanWorkspace(self),
            AnalyzeWorkspace(),
        ]

        root = QWidget()
        root.setObjectName("ls-root")
        root.setStyleSheet(f"QWidget#ls-root {{ background: {theme.BG_ROOT}; }}")
        self.setCentralWidget(root)

        vbox = QVBoxLayout(root)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        vbox.addWidget(self._build_topbar())
        vbox.addWidget(theme.hline())

        content = QWidget()
        content.setObjectName("ls-content")
        content.setStyleSheet(f"QWidget#ls-content {{ background: {theme.BG_ROOT}; }}")
        hbox = QHBoxLayout(content)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(0)

        # Viewer must exist before workspace panels are built (Settings wires it).
        self._viewer_area = self._build_viewer_area()

        # Left column: one panel per workspace.
        self._sidebar = QStackedWidget()
        self._sidebar.setMinimumWidth(theme.SIDEBAR_MIN_WIDTH)
        self._sidebar.setObjectName("ls-sidebar")
        self._sidebar.setStyleSheet(theme.SIDEBAR_SS)
        for ws in self._workspaces:
            self._sidebar.addWidget(ws.build_panel())

        # Right side: the shared viewer (index 0) plus any custom workspace
        # content pages. Workspaces without content fall back to the viewer.
        self._right_stack = QStackedWidget()
        self._right_stack.setMinimumWidth(300)
        self._right_stack.addWidget(self._viewer_area)  # index 0
        self._content_index: dict[int, int] = {}
        for i, ws in enumerate(self._workspaces):
            widget = ws.build_content()
            if widget is not None:
                self._right_stack.addWidget(widget)
                self._content_index[i] = self._right_stack.count() - 1

        # A draggable splitter separates the sidebar from the content area.
        splitter = theme.LineSplitter()
        splitter.addWidget(self._sidebar)
        splitter.addWidget(self._right_stack)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 1040])
        hbox.addWidget(splitter)
        vbox.addWidget(content, stretch=1)

        self._status_bar = StatusBar()
        vbox.addWidget(self._status_bar)

        self._wire_position_updates()
        self._init_status_bar()
        self._install_shortcuts()
        self._select_workspace(0)

    def _install_shortcuts(self) -> None:
        """Viewer mode shortcuts — same bindings as the classic window."""
        QShortcut(QKeySequence(Qt.Key.Key_M), self).activated.connect(
            lambda: self.viewer.select_mode(Viewer.Mode.STAGE)
        )
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self).activated.connect(
            lambda: self.viewer.select_mode(Viewer.Mode.NONE)
        )

    @property
    def viewer(self):
        return self._viewer_area.viewer

    # ── Top bar ───────────────────────────────────────────────────────────────

    def _build_topbar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("ls-topbar")
        bar.setFixedHeight(56)
        bar.setStyleSheet(f"QWidget#ls-topbar {{ background: {theme.BG_PANEL}; }}")

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(0)

        brand = QHBoxLayout()
        brand.setContentsMargins(0, 0, 0, 0)
        brand.setSpacing(10)

        ledger_logo = QLabel()
        ledger_logo.setPixmap(
            lucide.svg_file_pixmap(
                resource_path(":/icons/ledger-single-white.svg"), 18
            )
        )
        ledger_logo.setFixedSize(18, 18)
        ledger_logo.setStyleSheet("background: transparent;")
        brand.addWidget(ledger_logo)

        divider = QFrame()
        divider.setFixedSize(1, 16)
        divider.setStyleSheet("background: rgba(255,255,255,0.18);")
        brand.addWidget(divider)

        donjon_logo = QLabel()
        donjon_logo.setPixmap(
            lucide.svg_file_pixmap(resource_path(":/icons/logo.svg"), 18)
        )
        donjon_logo.setFixedSize(18, 18)
        donjon_logo.setStyleSheet("background: transparent;")
        brand.addWidget(donjon_logo)

        title = QLabel("LASER STUDIO")
        title.setStyleSheet(
            f"color: {theme.TEXT}; font-family: 'Brut Grotesque'; font-weight: 700;"
            " font-size: 14px; letter-spacing: 0.28px;"
        )
        brand.addWidget(title)

        brand_wrap = QWidget()
        brand_wrap.setStyleSheet("background: transparent;")
        brand_wrap.setLayout(brand)
        layout.addWidget(brand_wrap)
        layout.addSpacing(24)

        tabs_bg = QWidget()
        tabs_bg.setObjectName("ls-tabs-bg")
        tabs_bg.setStyleSheet(
            f"QWidget#ls-tabs-bg {{"
            f"  background: {theme.BG_TABS};"
            f"  border: 1px solid {theme.BORDER_SUBTLE};"
            f"  border-radius: 8px;"
            f"}}"
            f"{theme.TAB_SS}"
        )
        tabs_layout = QHBoxLayout(tabs_bg)
        tabs_layout.setContentsMargins(4, 4, 4, 4)
        tabs_layout.setSpacing(2)

        self._tab_buttons: list[QPushButton] = []
        self._tab_group = QButtonGroup(self)
        self._tab_group.setExclusive(True)

        for i, ws in enumerate(self._workspaces):
            btn = QPushButton(ws.label)
            btn.setCheckable(True)
            btn.setIcon(lucide.icon(ws.icon, 15, theme.TAB_INACTIVE))
            btn.clicked.connect(lambda _checked, idx=i: self._select_workspace(idx))
            self._tab_group.addButton(btn)
            self._tab_buttons.append(btn)
            tabs_layout.addWidget(btn)

        layout.addWidget(tabs_bg)
        layout.addStretch()
        return bar

    # ── Viewer area ───────────────────────────────────────────────────────────

    def _build_viewer_area(self) -> ViewerArea:
        area = ViewerArea(scan_zones=self._scan_zones)
        instr = self.instruments
        if instr.stage is not None or instr.camera is not None:
            area.viewer.add_stage_sight(
                instr.stage,
                instr.camera,
                instr.probes + [*instr.lasers],
            )
        area.viewer.schedule_fit_view()
        return area

    # ── Status / HUD wiring ─────────────────────────────────────────────────────

    def _init_status_bar(self) -> None:
        stage = self.instruments.stage
        self._status_bar.set_connected(stage is not None)
        self._status_bar.set_laser_armed(self.laser_armed)

        camera = self.instruments.camera
        if self.yaml_config:
            cam_cfg = self.yaml_config.get("camera")
            if isinstance(cam_cfg, dict):
                obj = cam_cfg.get("objective")
                if obj is not None:
                    self._status_bar.set_objective(f"{obj:g}×")

        if stage is not None:
            self._update_position_display(stage.position.data)

    def _wire_position_updates(self) -> None:
        stage = self.instruments.stage
        if stage is not None:
            stage.position_changed.connect(self._on_stage_position_changed)

    def _on_stage_position_changed(self, position) -> None:
        self._update_position_display(position.data)

    def _update_position_display(self, coords: list[float]) -> None:
        self._status_bar.set_position(coords)

    def set_laser_armed(self, armed: bool) -> None:
        self.laser_armed = armed
        self._status_bar.set_laser_armed(armed)

    # ── Workspace switching ───────────────────────────────────────────────────

    def _select_workspace(self, index: int) -> None:
        self._sidebar.setCurrentIndex(index)
        ws = self._workspaces[index]
        for j, btn in enumerate(self._tab_buttons):
            active = j == index
            btn.setChecked(active)
            btn.setIcon(
                lucide.icon(
                    self._workspaces[j].icon,
                    15,
                    "#0A0A0A" if active else theme.TAB_INACTIVE,
                )
            )
        # Show this workspace's custom content, or fall back to the viewer.
        self._right_stack.setCurrentIndex(self._content_index.get(index, 0))
        self._status_bar.set_workspace(ws.label)
        self._viewer_area.hud.set_workspace(ws.label)
