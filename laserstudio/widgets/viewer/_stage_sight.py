from __future__ import annotations
from typing import Any
from PyQt6.QtCore import QPointF, QRectF
from laserstudio.widgets.stagesight import StageSight, StageInstrument, CameraInstrument
from laserstudio.instruments.probe import ProbeInstrument
from laserstudio.instruments.stage import Vector
from ._base import _ViewerBase


class _StageSightMixin(_ViewerBase):
    """Wiring between the Viewer and its StageSight: creation, camera/stage
    signal plumbing, and the soft-limits / max-distance guardrail items."""

    def add_stage_sight(
        self,
        stage: StageInstrument | None,
        camera: CameraInstrument | None,
        probes: list[ProbeInstrument] = [],
    ):
        """Instantiate a stage sight associated with given stage.

        :param stage: The stage instrument to be associated with the stage sight
        """
        # Add StageSight item
        self.stage_sight = StageSight(stage, camera, probes)
        self.stage_sight.setZValue(1)
        self._scene.addItem(self.stage_sight)

        self._camera_fit_pending = camera is not None
        if camera is not None:
            camera.new_image.connect(self._on_camera_new_image)
            camera.parameter_changed.connect(self._on_camera_parameter_changed)

        self._stage_fit_pending = stage is not None
        if stage is not None:
            stage.soft_limits_changed.connect(self.refresh_soft_limits_item)
            self.refresh_soft_limits_item()
            stage.guardrail_changed.connect(self.refresh_max_distance_item)
            # Recenter the circle from the stage sight scene position, which does
            # not have the side effect of re-emitting stage.position_changed
            # (reading StageInstrument.position emits that signal).
            self.stage_sight.position_changed.connect(self._on_stage_sight_moved)
            self.refresh_max_distance_item()
            stage.position_changed.connect(self._on_stage_position_for_fit)
            # Place the sight on the first known hardware position before fitting.
            self.stage_sight.update_pos()

        self.schedule_fit_view()

    def _on_stage_position_for_fit(self, _position: Vector) -> None:
        if not self._auto_fit_view or not self._stage_fit_pending:
            return
        self._stage_fit_pending = False
        self.schedule_fit_view()

    def _on_camera_parameter_changed(self, parameter: str, _value: Any) -> None:
        if self._auto_fit_view and parameter in ("objective", "resolution"):
            self.schedule_fit_view()

    def _on_camera_new_image(self, _image: Any) -> None:
        if not self._auto_fit_view or not self._camera_fit_pending:
            return
        self._camera_fit_pending = False
        self.schedule_fit_view()

    def refresh_soft_limits_item(self):
        """Synchronize the soft-limits box in the view with the stage model."""
        stage = self.stage_sight.stage if self.stage_sight is not None else None
        if stage is None:
            return
        minimum = stage.soft_limits_min
        maximum = stage.soft_limits_max
        if minimum is not None and maximum is not None and len(minimum) >= 2:
            self.soft_limits_item.set_bounds(
                minimum[0], minimum[1], maximum[0], maximum[1]
            )

    def set_soft_limits_editable(self, editable: bool):
        """Show or hide the editable soft-limits box in the view."""
        if editable:
            self.refresh_soft_limits_item()
            self.soft_limits_item.show()
        else:
            self.soft_limits_item.hide()

    def _push_soft_limits_to_stage(self, rect: QRectF):
        """Write the XY box edited in the view back to the stage model."""
        stage = self.stage_sight.stage if self.stage_sight is not None else None
        if stage is None:
            return
        stage.set_soft_limits_xy(rect.left(), rect.top(), rect.right(), rect.bottom())

    def _on_stage_sight_moved(self, scene_pos: QPointF) -> None:
        """Recenter the max-distance circle on the stage sight scene position."""
        self.max_distance_item.set_center(scene_pos.x(), scene_pos.y())

    def refresh_max_distance_item(self):
        """Synchronize the max-distance circle with the stage guardrail.

        The center is taken from the stage sight scene position to avoid reading
        ``StageInstrument.position`` (which emits ``position_changed``).
        """
        stage = self.stage_sight.stage if self.stage_sight is not None else None
        if stage is None or self.stage_sight is None:
            return
        center = self.stage_sight.pos()
        self.max_distance_item.set_center(center.x(), center.y())
        self.max_distance_item.set_radius(stage.guardrail)

    def set_max_distance_editable(self, editable: bool):
        """Show or hide the editable max-distance circle in the view."""
        if editable:
            self.refresh_max_distance_item()
            self.max_distance_item.show()
        else:
            self.max_distance_item.hide()

    def _push_max_distance_to_stage(self, radius: float):
        """Write the radius edited in the view back to the stage guardrail."""
        stage = self.stage_sight.stage if self.stage_sight is not None else None
        if stage is None:
            return
        stage.guardrail = float(radius)
