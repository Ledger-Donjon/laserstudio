from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QPainter
from PyQt6.QtWidgets import (
    QToolBar,
    QPushButton,
    QLabel,
    QMessageBox,
    QWidget,
    QVBoxLayout,
)
from ...utils.util import colored_image, ChartViewWithVMarker
from ..coloredbutton import ColoredPushButton
from ...instruments.camera import CameraInstrument
from ...instruments.stage import StageInstrument
from ...instruments.focus import FocusInstrument
from PyQt6.QtCharts import QLineSeries, QChart
from typing import Optional


class FocusChartWindow(QWidget):
    """
    Window for displaying the focus chart.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("focus-chart-window")  # For settings save and restore
        self.setWindowTitle("Focus Chart")
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setGeometry(100, 100, 800, 600)
        self.setVisible(False)
        # Chart for focus results
        self.chart = QChart()
        self.chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        self.cv = w = ChartViewWithVMarker()
        w.setChart(self.chart)
        w.setRenderHint(QPainter.RenderHint.Antialiasing)
        w.setMinimumSize(600, 400)

        self.coarse_serie = QLineSeries()
        self.coarse_serie.setName("Coarse")
        self.fine_serie = QLineSeries()
        self.fine_serie.setName("Fine")
        self.chart.addSeries(self.coarse_serie)
        self.chart.addSeries(self.fine_serie)
        self.chart.createDefaultAxes()

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
        self.buttons_autofocus: list[QPushButton] = []
        for i in range(3):
            w = ColoredPushButton(
                ":/icons/fontawesome-free/wrench-solid.svg", parent=self
            )
            w.setEnabled(False)
            self.buttons_autofocus.append(w)
            w.setText(f"{i + 1}")
            w.setCheckable(True)
            w.setIconSize(QSize(24, 24))
            w.toggled.connect(lambda x, _i=i: self.register(_i, x))
            self.addWidget(w)

        # Autofocus
        self.autofocus_button = w = QPushButton(self)
        w.setIcon(QIcon(colored_image(":/icons/fontawesome-free/glasses-solid.svg")))
        w.setIconSize(QSize(24, 24))
        w.setToolTip("Automatically focus based on 3 registered positions.")
        w.clicked.connect(self.autofocus)
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

        self.chart_window = FocusChartWindow()

    def magic_focus(self):
        """
        Estimates automatically the correct focus by moving the stage and analysing the
        resulting camera image. This is executed in a thread.
        """
        assert (
            self.focus_helper.focus_thread is None
            or not self.focus_helper.focus_thread.isRunning()
        ), "Magic Focus thread is already running"
        self.button_magic_focus.setEnabled(False)

        self.chart_window.clear()
        self.chart_window.show()

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
        self.button_magic_focus.setEnabled(True)

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
        for i, b in enumerate(self.buttons_autofocus):
            b.setEnabled(i == num_points or i + 1 == num_points)
            b.blockSignals(True)
            b.setChecked(i < num_points)
            b.blockSignals(False)
            b.setToolTip(
                f"{points[i][0]:.2f} {points[i][1]:.2f} {points[i][2]:.2f}"
                if i < num_points
                else "Register current position for focusing."
            )
        self.autofocus_button.setEnabled(num_points == 3)

    def register(self, index: int, checked: bool):
        """
        Registers a new focus point. If three focus points are already defined, the
        farther point is replaced.
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
