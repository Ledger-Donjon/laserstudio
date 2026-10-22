"""Shared load logic for ``settings.yaml``.

Both the classic ``LaserStudio`` and the new ``LaserStudioRefonte`` restore the
same runtime settings; the logic lives here so the two UIs stay in sync. The
object passed as ``ui`` only needs an ``instruments`` attribute and a ``viewer``
(with ``stage_sight`` and ``settings``), which both main windows expose.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import yaml


def load_settings_file(path: str = "settings.yaml") -> dict[str, Any] | None:
    """Load and parse ``settings.yaml``. Returns None if it does not exist."""
    try:
        with open(path, "r") as f:
            return yaml.load(f, yaml.SafeLoader)
    except FileNotFoundError:
        logging.getLogger("laserstudio").warning(
            "Settings file not found in directory " + os.getcwd()
        )
        return None


def apply_settings(ui: Any, data: dict[str, Any]) -> None:
    """Apply a parsed ``settings.yaml`` payload to a main window's instruments.

    ``ui`` must expose ``instruments`` and ``viewer``.
    """
    log = logging.getLogger("laserstudio")

    # Camera settings (maybe missing from settings)
    camera = data.get("camera")
    if (ui.instruments.camera is not None) and (camera is not None):
        ui.instruments.camera.settings = camera
        if ui.viewer is not None and ui.viewer.stage_sight is not None:
            ui.viewer.stage_sight.distortion = ui.instruments.camera.correction_matrix

    # Lighting system settings
    lighting = data.get("lighting")
    if (ui.instruments.light is not None) and (lighting is not None):
        ui.instruments.light.settings = lighting

    # Scans geometry
    scans = data.get("scans", data.get("scangeometry"))
    log.debug(f"Scans settings: {scans}...")
    if scans is not None:
        ui.instruments.scans.settings = scans

    # Annotations (rulers, markers) — fall back to legacy viewer section.
    annotations = data.get("annotations")
    if annotations is not None:
        ui.instruments.annotations.settings = annotations
    else:
        viewer_legacy = data.get("viewer")
        if isinstance(viewer_legacy, dict):
            migrated: dict[str, Any] = {}
            if "marker_size" in viewer_legacy:
                migrated["marker_size"] = viewer_legacy["marker_size"]
            if "rulers" in viewer_legacy:
                migrated["rulers"] = viewer_legacy["rulers"]
            if migrated:
                ui.instruments.annotations.settings = migrated

    # Probes
    probes = data.get("probes", [])
    for pdata, probe in zip(probes, ui.instruments.probes):
        probe.settings = pdata

    # Lasers — never restore the 'on_off' state, to avoid arming a laser on load.
    lasers = data.get("lasers", [])
    for pdata, laser in zip(lasers, ui.instruments.lasers):
        if "on_off" in pdata:
            log.warning(
                f"Laser {laser.label} 'on_off' is ignored during settings "
                "restoration to prevent any risk."
            )
        _ = pdata.pop("on_off", None)
        laser.settings = pdata

    # Focus
    focus = data.get("focus")
    if ui.instruments.focus_helper is not None and focus is not None:
        ui.instruments.focus_helper.settings = focus

    # Viewer's configuration
    viewer = data.get("viewer")
    if viewer is not None and ui.viewer is not None:
        ui.viewer.settings = viewer

    # Stage
    stage = data.get("stage")
    if ui.instruments.stage is not None and stage is not None:
        ui.instruments.stage.settings = stage


def reload_settings(ui: Any, path: str = "settings.yaml") -> bool:
    """Load ``settings.yaml`` and apply it to ``ui``. Returns True on success."""
    data = load_settings_file(path)
    if data is None:
        return False
    apply_settings(ui, data)
    return True
