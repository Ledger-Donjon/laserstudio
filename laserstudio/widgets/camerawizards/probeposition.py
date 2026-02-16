from __future__ import annotations
import logging
from typing import TYPE_CHECKING
from PyQt6.QtCore import QCoreApplication
from PyQt6.QtGui import QColorConstants, QTextOption
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QWidget,
    QTextEdit,
    QFrame,
    QHBoxLayout,
    QLabel,
    QDoubleSpinBox,
)
from . import ProbeInstrument, LaserInstrument
from .camerapages import CameraWizardPage, CameraPositionPage, CameraWizard
from .camerapages import PagesID

if TYPE_CHECKING:
    from ...laserstudio import LaserStudio


class ProbePositionIntroductionPage(CameraWizardPage):
    def __init__(self, parent: ProbesPositionWizard):
        super().__init__(parent)
        self.setTitle("Probe position wizard")
        self.setSubTitle(
            "This tool permits to indicate where in the image "
            "the probe or the laser spot appears."
        )
        vbox = QVBoxLayout()
        text_widget = QWidget()
        text_layout = QVBoxLayout(text_widget)
        info_text = (
            "This feature allows "
            f"{QCoreApplication.applicationName()} to adjust the stage movement such that "
            "the probe or laser spot is positioned at your desired location, "
            "rather than at the center of the camera image.<br />"
            "This position is relative to the center of the camera's image "
            "(without distortion) so is dependent on the objective lens used.<br />"
            "<b>Make sure to perform this positioning operation again if you change the objective lens.</b>"
        )
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setHtml(info_text)
        text_edit.setWordWrapMode(QTextOption.WrapMode.WordWrap)
        text_edit.setFrameStyle(QFrame.Shape.NoFrame)
        # No background color
        text_edit.setStyleSheet("background-color: transparent;")
        text_layout.addWidget(text_edit)
        vbox.addWidget(text_widget)
        self.setLayout(vbox)

    def nextId(self) -> int:
        return PagesID.PROBE_POSITION


class ProbePositionPage(CameraPositionPage):
    """
    Wizard page where the user get the camera image and can click
    on it to indicate the position of a probe/spot relatively to the
    camera image
    """

    def __init__(
        self, probe_index: int, probe: ProbeInstrument, parent: ProbesPositionWizard
    ):
        super().__init__(parent=parent)
        if isinstance(probe, LaserInstrument):
            what = "Laser Spot"
            self.viewer.clicked_point_marker.color = QColorConstants.Red
        else:
            what = "Probe"
            self.viewer.clicked_point_marker.color = QColorConstants.Blue
        self.setTitle(f"{what} {probe_index + 1} positioning")
        self.setSubTitle(
            f"Indicate in the image the position of the {what}."
            f" This operation will permit {QCoreApplication.applicationName()} to move accordingly to"
            " indicated point instead of the center of the image."
        )
        self.probe = probe
        layout = self.layout()
        assert layout is not None
        size_row = QHBoxLayout()
        size_label = QLabel(f"{what} size:")
        self.size_input = QDoubleSpinBox()
        self.size_input.setToolTip(
            "Size of the probe or laser spot in micrometers, before magnification by the objective lens."
        )
        self.size_input.setDecimals(2)
        self.size_input.setRange(0.1, 100000.0)
        self.size_input.setSingleStep(1.0)
        self.size_input.setValue(self.probe.spot_size_um)
        self.size_input.valueChanged.connect(self._spot_size_changed)
        self.size_input.setSuffix("\xa0µm")
        size_row.addWidget(size_label)
        size_row.addWidget(self.size_input)
        size_container = QWidget()
        size_container.setLayout(size_row)
        layout.addWidget(size_container)

    def set_position(self, xy: tuple[int, int] | None):
        super().set_position(xy)
        # Resume the camera image update
        self.viewer.stage_sight.pause_image_update = False
        if self.clicked_point is not None:
            logging.getLogger("laserstudio").debug(
                f"Clicked point: {self.clicked_point.x():.02f}px, {self.clicked_point.y():.02f}px"
            )
            self.probe.offset_pos = self.clicked_point.x(), self.clicked_point.y()

    def _spot_size_changed(self, value: float):
        self.probe.spot_size_um = value
        self.viewer.clicked_point_marker.size = value * (
            self.viewer.stage_sight.camera.objective
            if self.viewer.stage_sight.camera is not None
            else 1
        )


class ProbesPositionWizard(CameraWizard):
    def __init__(self, laser_studio: LaserStudio, parent: QWidget | None = None):
        super().__init__(laser_studio=laser_studio, parent=parent)
        # Create the ProbePositionIntroductionPage page
        self.setPage(PagesID.INTRO, ProbePositionIntroductionPage(parent=self))

        # Create pages for probe position
        page = 0
        for probe in enumerate(laser_studio.instruments.probes):
            self.setPage(
                PagesID.PROBE_POSITION + page,
                ProbePositionPage(*probe, parent=self),
            )
            page += 1
        for laser in enumerate(laser_studio.instruments.lasers):
            self.setPage(
                PagesID.PROBE_POSITION + page,
                ProbePositionPage(*laser, parent=self),
            )
            page += 1
