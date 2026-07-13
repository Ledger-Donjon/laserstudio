from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .instruments.instruments import Instruments
from .utils.yaml_types import Config
from .widgets.newui import lucide, theme
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
    ) -> None:
        super().__init__()
        self.instruments = instruments
        config_path = config_path or Path("config.yaml")

        self.setWindowTitle("Laser Studio · New UI")
        self.setMinimumSize(1200, 720)

        # The ordered set of workspaces shown as tabs.
        self._workspaces: list[Workspace] = [
            ConfigWorkspace(yaml_config, config_path, config_loaded, self),
            SettingsWorkspace(),
            PhotoemissionWorkspace(),
            ScanWorkspace(),
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

        # Left column: one panel per workspace.
        self._sidebar = QStackedWidget()
        self._sidebar.setMinimumWidth(260)
        self._sidebar.setObjectName("ls-sidebar")
        self._sidebar.setStyleSheet(
            f"QStackedWidget#ls-sidebar {{ background: {theme.BG_PANEL}; }}"
        )
        for ws in self._workspaces:
            self._sidebar.addWidget(ws.build_panel())

        # Right side: the shared viewer (index 0) plus any custom workspace
        # content pages. Workspaces without content fall back to the viewer.
        self._right_stack = QStackedWidget()
        self._right_stack.setMinimumWidth(420)
        self._right_stack.addWidget(self._build_viewer_area())  # index 0
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

        self._select_workspace(0)

    # ── Top bar ───────────────────────────────────────────────────────────────

    def _build_topbar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("ls-topbar")
        bar.setFixedHeight(56)
        bar.setStyleSheet(f"QWidget#ls-topbar {{ background: {theme.BG_PANEL}; }}")

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(0)

        title = QLabel("LASER STUDIO")
        title.setStyleSheet(
            f"color: {theme.TEXT}; font-family: 'Brut Grotesque'; font-weight: 700;"
            " font-size: 14px; letter-spacing: 2px;"
        )
        layout.addWidget(title)
        layout.addSpacing(24)

        tabs_bg = QWidget()
        tabs_bg.setObjectName("ls-tabs-bg")
        tabs_bg.setStyleSheet(
            f"QWidget#ls-tabs-bg {{"
            f"  background: {theme.BG_TABS};"
            f"  border: 1px solid {theme.BORDER_SUBTLE};"
            f"  border-radius: 8px;"
            f"}}"
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
            btn.setStyleSheet(theme.TAB_SS)
            btn.setIcon(lucide.icon(ws.icon, 15, theme.TAB_INACTIVE))
            btn.clicked.connect(lambda _checked, idx=i: self._select_workspace(idx))
            self._tab_group.addButton(btn)
            self._tab_buttons.append(btn)
            tabs_layout.addWidget(btn)

        layout.addWidget(tabs_bg)
        layout.addStretch()
        return bar

    # ── Viewer area ───────────────────────────────────────────────────────────

    def _build_viewer_area(self) -> QWidget:
        from .widgets.viewer import Viewer

        container = QWidget()
        container.setObjectName("ls-viewer")
        container.setStyleSheet(f"QWidget#ls-viewer {{ background: {theme.BG_MAIN}; }}")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        self.viewer = Viewer()
        instr = self.instruments
        if instr.stage is not None or instr.camera is not None:
            self.viewer.add_stage_sight(
                instr.stage,
                instr.camera,
                instr.probes + [*instr.lasers],
            )
            self.viewer.reset_camera()
        layout.addWidget(self.viewer)
        return container

    # ── Workspace switching ───────────────────────────────────────────────────

    def _select_workspace(self, index: int) -> None:
        self._sidebar.setCurrentIndex(index)
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
