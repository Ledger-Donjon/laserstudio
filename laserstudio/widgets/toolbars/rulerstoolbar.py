from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDockWidget,
    QMenu,
    QPushButton,
    QSizePolicy,
    QToolBar,
)
from ..return_line_edit import ReturnDoubleSpinBox
from ..rulerslist import RulersView
from ..viewer import Viewer
from ..coloredbutton import ColoredPushButton
from ...utils.util import create_color_qicon
from ...utils.colors import LedgerColors, MARKERS_COLORS


class RulersListDockWidget(QDockWidget):
    def __init__(self, viewer: Viewer):
        super().__init__("Rulers List")
        self.setObjectName("toolbar-rulers-list")  # For settings save and restore
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )

        self.list = RulersView(viewer)
        self.setWidget(self.list)


class RulersToolBar(QToolBar):
    def __init__(self, viewer: Viewer):
        super().__init__("Rulers")
        self.setObjectName("toolbar-rulers")  # For settings save and restore
        self.setAllowedAreas(Qt.ToolBarArea.TopToolBarArea)
        self.setFloatable(True)

        self.viewer = viewer

        # Ruler mode: draw a new measurement by dragging in the view
        self.ruler_button = w = ColoredPushButton(parent=self)
        w.setText("Ruler")
        w.setCheckable(True)
        w.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        w.setToolTip(
            "Measure a distance by dragging in the view. "
            "Shortcut: L — leave with Esc."
        )
        w.clicked.connect(self.toggle_ruler_mode)
        self.addWidget(w)
        self.viewer.mode_changed.connect(self.update_ruler_button)

        # Clear all rulers
        w = QPushButton("Clear", self)
        w.setToolTip("Remove all rulers")
        w.clicked.connect(self.viewer.clear_rulers)
        self.addWidget(w)

        # Color of the next created rulers
        self.color_button = w = QPushButton(self)
        w.setToolTip("Color for new rulers")
        color_menu = QMenu("Set color for new rulers", self)
        for color, name in MARKERS_COLORS:
            color_menu.addAction(
                create_color_qicon(color),
                name,
                lambda c=color: self.set_color(c),  # type: ignore
            )
        w.setMenu(color_menu)
        self.addWidget(w)
        self.set_color(self.viewer.default_ruler_color)

        # Graduation interval of the next created rulers
        self.graduation_sp = w = ReturnDoubleSpinBox()
        w.setSuffix("\xa0µm")
        w.setToolTip(
            "Graduation interval for new rulers (0 to draw a plain line)."
        )
        w.setMinimum(0.0)
        w.setDecimals(1)
        w.setSingleStep(10.0)
        w.setMaximum(1e6)
        w.setValue(self.viewer.default_ruler_graduation or 0.0)
        w.reset()
        w.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        w.returnPressed2.connect(self.set_graduation)
        self.addWidget(w)

        # Show list of all rulers
        w = ColoredPushButton(parent=self)
        w.setText("Show list")
        w.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        w.setToolTip("Show a list of all rulers")
        w.setCheckable(True)
        w.clicked.connect(self.show_rulers_list)
        self.addWidget(w)

        # Dock widget: Rulers' List
        self.rulers_list_dockwidget = RulersListDockWidget(viewer)

    def toggle_ruler_mode(self):
        self.viewer.select_mode(Viewer.Mode.RULER, True)

    def update_ruler_button(self, mode: int):
        self.ruler_button.setChecked(mode == int(Viewer.Mode.RULER))

    def show_rulers_list(self, state: bool):
        if state:
            self.rulers_list_dockwidget.show()
        else:
            self.rulers_list_dockwidget.hide()

    def set_color(self, color: QColor | Qt.GlobalColor | int | LedgerColors):
        if isinstance(color, LedgerColors):
            color = color.value
        self.viewer.default_ruler_color = QColor(color)
        self.color_button.setIcon(create_color_qicon(color))

    def set_graduation(self):
        value = self.graduation_sp.value()
        self.viewer.default_ruler_graduation = value if value > 0 else None
