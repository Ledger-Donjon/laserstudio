"""Histogram of the live camera image, plus black/white level adjustment."""

from __future__ import annotations

import logging
from typing import Any

from PyQt6.QtCharts import QBarSeries, QBarSet, QChart, QChartView
from PyQt6.QtCore import QMargins
from PyQt6.QtGui import QColor, QImage, QPainter
from PyQt6.QtWidgets import QPushButton, QVBoxLayout, QWidget

from laserstudio.instruments.camera import CameraInstrument
from laserstudio.widgets.newui import theme

from ._helpers import _FloatSliderRow
from ._styles import PANEL_SPACING


class _CameraImageAdjustmentSection(QWidget):
    """Live image histogram + black/white level sliders + auto-levels button.

    Mirrors the classic ``CameraImageAdjustementDockWidget``: the histogram is
    refreshed on every ``camera.new_image``, the black/white levels are kept in
    sync with the instrument via ``camera.parameter_changed``, and "Auto Levels"
    calls ``camera.levels_autoset()`` then reflects the returned values.
    """

    def __init__(
        self, camera: CameraInstrument, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._camera = camera

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(PANEL_SPACING)

        root.addWidget(theme.section_title("Image adjustment", "sliders-horizontal"))

        # Histogram, rendered with a borderless bar chart matching the panel's
        # transparent background.
        self._bar_series = QBarSeries()
        self._bar_series.setName("Histogram")
        self._chart = QChart()
        legend = self._chart.legend()
        if legend is not None:
            legend.setVisible(False)
        self._chart.addSeries(self._bar_series)
        self._chart.setMargins(QMargins())
        self._chart.setBackgroundRoundness(0)
        self._chart.setBackgroundBrush(QColor(0, 0, 0, 0))
        self._chart_view = QChartView(self._chart)
        self._chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._chart_view.setStyleSheet("background: transparent; border: none;")
        self._chart_view.setFixedHeight(90)
        root.addWidget(self._chart_view)

        camera.new_image.connect(self._on_new_image)
        self._update_histogram()

        self._black_slider = _FloatSliderRow(
            "BLACK LEVEL",
            0.0,
            1.0,
            self._read_level("black_level"),
            scale=1000,
            decimals=3,
            on_change=self._on_black_changed,
        )
        root.addWidget(self._black_slider)

        self._white_slider = _FloatSliderRow(
            "WHITE LEVEL",
            0.0,
            1.0,
            self._read_level("white_level"),
            scale=1000,
            decimals=3,
            on_change=self._on_white_changed,
        )
        root.addWidget(self._white_slider)

        auto_levels_btn = QPushButton("Auto levels")
        auto_levels_btn.setToolTip(
            "Adjust black and white levels from the current image histogram"
        )
        auto_levels_btn.setStyleSheet(theme.GHOST_BTN)
        auto_levels_btn.clicked.connect(self._on_auto_levels)
        root.addWidget(auto_levels_btn)

        camera.parameter_changed.connect(self._on_param)

    # ── device interaction ────────────────────────────────────────────────────

    def _read_level(self, attribute: str) -> float:
        try:
            return float(getattr(self._camera, attribute))
        except Exception as exc:  # keep the UI responsive on device errors
            logging.getLogger("laserstudio").warning(
                f"Failed to read the camera {attribute}: {exc}"
            )
            return 0.0 if attribute == "black_level" else 1.0

    def _update_histogram(self) -> None:
        try:
            frame = self._camera.last_frame.copy()
            histogram = self._camera.compute_histogram(frame, width=256 // 4)[0]
        except Exception as exc:
            logging.getLogger("laserstudio").warning(
                f"Failed to compute the camera histogram: {exc}"
            )
            return

        self._bar_series.clear()
        bar_set = QBarSet("Histogram")
        bar_set.append([float(v) for v in histogram])
        self._bar_series.append(bar_set)
        self._chart.createDefaultAxes()
        axes = self._chart.axes()
        maximum = float(max(histogram)) if len(histogram) else 0.0
        if len(axes) > 1:
            axes[1].setRange(0, maximum * 1.1 if maximum > 0 else 1.0)
        for axis in axes:
            axis.setLabelsVisible(False)
            axis.setGridLineVisible(False)
            axis.setLineVisible(False)
        self._chart.update()

    def _on_new_image(self, _image: QImage) -> None:
        self._update_histogram()

    def _on_black_changed(self, value: float) -> None:
        try:
            self._camera.black_level = value
        except Exception as exc:
            logging.getLogger("laserstudio").warning(
                f"Failed to set the camera black level: {exc}"
            )

    def _on_white_changed(self, value: float) -> None:
        try:
            self._camera.white_level = value
        except Exception as exc:
            logging.getLogger("laserstudio").warning(
                f"Failed to set the camera white level: {exc}"
            )

    def _on_auto_levels(self) -> None:
        try:
            black, white = self._camera.levels_autoset()
        except Exception as exc:
            logging.getLogger("laserstudio").warning(
                f"Failed to auto-set the camera levels: {exc}"
            )
            return
        self._black_slider.set_value(float(black))
        self._white_slider.set_value(float(white))

    def _on_param(self, parameter: str, value: Any) -> None:
        if parameter == "black_level" and isinstance(value, (int, float)):
            self._black_slider.set_value(float(value))
        elif parameter == "white_level" and isinstance(value, (int, float)):
            self._white_slider.set_value(float(value))
