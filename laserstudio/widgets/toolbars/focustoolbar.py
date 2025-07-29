from PyQt6.QtCore import Qt, QSize, QMargins
from PyQt6.QtGui import QIcon, QPainter
from PyQt6.QtWidgets import (
    QToolBar,
    QPushButton,
    QLabel,
    QMessageBox,
    QWidget,
    QVBoxLayout,
    QMenu,
    QDockWidget,
)
from ...utils.colors import LedgerColors
from ...utils.util import colored_image, ChartViewWithVMarker
from ..coloredbutton import ColoredPushButton
from ...instruments.camera import CameraInstrument
from ...instruments.stage import StageInstrument
from ...instruments.focus import FocusInstrument
from PyQt6.QtCharts import QLineSeries, QChart
from typing import Optional


class MagicFocusDockWidget(QDockWidget):
    """
    Dock widget for the magic focus.
    """

    def __init__(self, parent=None):
        super().__init__("Magic Focus Chart", parent)
        self.setObjectName("magic-focus-dockwidget")  # For settings save and restore

        self.chart_window = FocusChart()
        self.setWindowTitle("Magic Focus")
        self.setWidget(self.chart_window)
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea
            | Qt.DockWidgetArea.BottomDockWidgetArea
        )
        self.setVisible(False)


class FocusChart(QWidget):
    """
    Window for displaying the focus chart.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("focus-chart-window")  # For settings save and restore
        self.setWindowTitle("Focus Chart")
        self.setVisible(False)
        # Chart for focus results
        self.chart = QChart()
        self.chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        self.cv = w = ChartViewWithVMarker()
        w.setChart(self.chart)
        w.setRenderHint(QPainter.RenderHint.Antialiasing)
        w.setMinimumSize(600, 400)
        self.chart.setBackgroundVisible(False)
        self.chart.setMargins(QMargins(0, 0, 0, 0))

        self.coarse_serie = QLineSeries()
        self.coarse_serie.setName("Coarse")
        self.fine_serie = QLineSeries()
        self.fine_serie.setName("Fine")
        self.chart.addSeries(self.coarse_serie)
        self.chart.addSeries(self.fine_serie)
        self.chart.createDefaultAxes()

        # Text color
        self.chart.axes()[0].setLabelsColor(LedgerColors.SerenityPurple.value)
        self.chart.axes()[1].setLabelsColor(LedgerColors.SerenityPurple.value)
        # Set color of text in legend
        legend = self.chart.legend()
        if legend is not None:
            legend.setLabelColor(LedgerColors.SerenityPurple.value)

        self.setLayout(vbox := QVBoxLayout())
        vbox.addWidget(w)

    def new_point(self, z: float, std_dev: float, serie: QLineSeries):
        """
        Called when a new point is added to the chart.

        :param z: The z position of the point.
        :param std_dev: The standard deviation of the point.
        """
        serie.append(z, std_dev)
        p = self.coarse_serie.points() + self.fine_serie.points()
        minY = min(p, key=lambda p: p.y()).y()
        maxY = max(p, key=lambda p: p.y()).y()
        self.chart.axes()[1].setRange(minY, maxY)

    def clear(self):
        """
        Clears the chart.
        """
        self.coarse_serie.clear()
        self.fine_serie.clear()
        self.cv.vmarker = None

    @property
    def vmarker(self):
        """
        Returns the vertical marker position.
        :return: The z position of the marker.
        """
        return self.cv.vmarker

    @vmarker.setter
    def vmarker(self, z: Optional[float]):
        """
        Sets the vertical marker position.
        :param z: The z position of the marker.
        """
        self.cv.vmarker = z

    def setRange(self, z_range: tuple[float, float]):
        """
        Sets the range of the chart.
        :param z_range: The z range of the chart.
        """
        self.chart.axes()[0].setRange(z_range[0], z_range[1])


class FocusToolBar(QToolBar):
    """ToolBar for focus registration and autofocus."""

    def __init__(
        self,
        stage: StageInstrument,
        camera: CameraInstrument,
        focus_helper: FocusInstrument,
    ):
        """
        :param autofocus_helper: Stores the registered points and calculates focus on demand.
        """
        super().__init__("Focus")
        self.setObjectName("toolbar-focus")  # For settings save and restore
        self.setAllowedAreas(Qt.ToolBarArea.TopToolBarArea)
        self.setFloatable(True)

        self.focus_helper: FocusInstrument = focus_helper
        self.stage = stage
        self.camera = camera

        # Try to find focus automatically
        self.button_magic_focus = w = ColoredPushButton(
            ":/icons/fontawesome-free/wand-magic-sparkles-solid.svg", parent=self
        )
        w.setCheckable(True)
        w.setIconSize(QSize(24, 24))
        w.setToolTip(
            "Automatically find best focus position using camera image analysis."
        )
        w.clicked.connect(self.magic_focus)
        self.addWidget(w)

        # Register focus point at current position
        self.buttons_autofocus_menu = menu = QMenu("Autofocus Points", self)
        action = menu.addAction("Perform autofocus", lambda: self.autofocus())
        assert action is not None, "Autofocus action could not be created"
        self.autofocus_action = action
        menu.addAction("Register current position", lambda: self.register())
        menu.addAction("Clear all registered points", lambda: self.clear_all())

        # Autofocus
        self.autofocus_button = w = QPushButton(self)
        w.setIcon(QIcon(colored_image(":/icons/fontawesome-free/glasses-solid.svg")))
        w.setIconSize(QSize(24, 24))
        w.setToolTip("Automatically focus based on 3 registered positions.")
        w.setMenu(menu)
        self.addWidget(w)

        self.update_autofocus_buttons()

        # Show current sharpness value
        self.sharpness = QLabel("")
        self.sharpness.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sharpness.setStyleSheet("padding-left: 10px;padding-right: 10px")
        self.camera.new_image.connect(
            lambda: self.sharpness.setText(f"{self.camera.laplacian_std_dev:.2f}")
        )
        self.sharpness.setToolTip("The sharpness value of the current image.")
        self.addWidget(self.sharpness)

        self.magic_focus_dockwidget = MagicFocusDockWidget()
        self.chart_window = self.magic_focus_dockwidget.chart_window

        self.focus_helper.parameter_changed.connect(
            lambda _: self.update_autofocus_buttons()
        )

    def magic_focus(self, do_it: bool = True):
        """
        Estimates automatically the correct focus by moving the stage and analysing the
        resulting camera image. This is executed in a thread.
        """
        if not do_it:
            if self.focus_helper.focus_thread is not None:
                self.focus_helper.focus_thread.requestInterruption()
                self.focus_helper.focus_thread.wait()
            self.chart_window.clear()
            return

        assert (
            self.focus_helper.focus_thread is None
            or not self.focus_helper.focus_thread.isRunning()
        ), "Magic Focus thread is already running"

        self.chart_window.clear()
        self.chart_window.show()
        self.magic_focus_dockwidget.show()

        t = self.focus_helper.magic_focus()
        t.new_point.connect(
            lambda z, dev: self.chart_window.new_point(
                z,
                dev,
                self.chart_window.coarse_serie
                if t.tab_coarse is None
                else self.chart_window.fine_serie,
            )
        )
        t.finished.connect(self.magic_focus_finished)
        self.chart_window.setRange(t.z_range())
        t.start()

    def magic_focus_finished(self):
        """Called when focus search thread has finished."""
        # Reenable the button
        self.button_magic_focus.setChecked(False)

        # Show the graphs
        assert (t := self.focus_helper.focus_thread) is not None
        self.chart_window.vmarker = t.best_z
        self.chart_window.show()

    def update_autofocus_buttons(self) -> None:
        """
        Update the autofocus buttons to show the current focus points.
        """
        points = self.focus_helper.autofocus_helper.registered_points
        num_points = len(points)
        self.autofocus_action.setEnabled(num_points >= 3)
        self.autofocus_button.setText(str(num_points))

    def clear_all(self):
        self.focus_helper.clear()

    def register(self, index: int = 1, checked: bool = True):
        """
        Registers a new focus point.
        """
        if checked:
            pos = self.stage.position
            self.focus_helper.register((pos.x, pos.y, pos.z))
        else:
            self.focus_helper.autofocus_helper.registered_points.pop(index - 1)
        self.update_autofocus_buttons()

    def autofocus(self):
        """
        Calculate focus for the given position and apply it, if possible.
        """
        if len(self.focus_helper.autofocus_helper) < 3:
            # Prompt a dialog
            QMessageBox.critical(
                self,
                "Focus",
                f"Not enough points registered for autofocus ({len(self.focus_helper.autofocus_helper)} over 3 required).",
            )
            return

        try:
            self.focus_helper.autofocus()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Focus",
                str(e),
            )
            return
