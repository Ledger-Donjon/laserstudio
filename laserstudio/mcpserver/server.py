"""MCP (Model Context Protocol) server for Laser Studio.

This server exposes Laser Studio actions as MCP *tools*, so MCP-compatible
clients (LLM agents, IDEs, ...) can drive Laser Studio. It is a thin layer on
top of the :class:`~laserstudio.lsapi.lsapi.LSAPI` REST client, which is itself
free of any PyQt dependency. The MCP server therefore runs as a standalone
process and talks to a running Laser Studio instance over its REST API.

The typed exceptions raised by ``lsapi`` are translated into clear MCP tool
errors (prefixed with the machine-readable error code) so the client gets an
explicit reason when something fails (unknown instrument, no camera, ...).
"""

from __future__ import annotations

import io
from typing import Any, Callable, TypeVar

from mcp.server.fastmcp import FastMCP, Image

from ..lsapi import LSAPI, LSAPIError

T = TypeVar("T")

INSTRUCTIONS = """\
Control a running Laser Studio instance.

Use these tools to inspect and drive the setup: list instruments, read or update
instrument settings, manage scan zones (create, rename, recolor, enable or
disable, delete), read or update the overall scan geometry, read or move the
stage, run scans (go_next), focus, manage markers, and capture camera images or
screenshots.

Scanning runs on the union of the *enabled* zones: disable a zone to exclude it
from go_next without losing its shape.

Tools fail with an explicit error message prefixed by a machine-readable code
(e.g. INSTRUMENT_NOT_FOUND, DEVICE_UNAVAILABLE, INVALID_PARAMETER) when an
action cannot be performed.
"""


def build_server(host: str = "localhost", port: int | None = None) -> FastMCP:
    """Build the Laser Studio MCP server.

    :param host: Host of the Laser Studio REST API.
    :param port: Port of the Laser Studio REST API (default: ``LSAPI.PORT``).
    :return: A configured :class:`FastMCP` server, ready to ``run()``.
    """
    api = LSAPI(host=host, port=port)
    mcp = FastMCP("LaserStudio", instructions=INSTRUCTIONS)

    def call(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Run an lsapi call, converting LSAPI errors into clear tool errors."""
        try:
            return fn(*args, **kwargs)
        except LSAPIError as exc:
            raise RuntimeError(f"[{exc.code}] {exc.message}") from exc

    # -- Instruments -------------------------------------------------------- #

    @mcp.tool()
    def list_instruments() -> list[dict[str, Any]]:
        """List the available instruments (type and label)."""
        return call(api.instruments)

    @mcp.tool()
    def get_instrument_settings(label: str) -> dict[str, Any]:
        """Get the settings of the instrument identified by its label."""
        return call(api.get_instrument_settings, label)

    @mcp.tool()
    def set_instrument_settings(label: str, settings: dict[str, Any]) -> dict[str, Any]:
        """Update the settings of the instrument identified by its label."""
        return call(api.set_instrument_settings, label, settings)

    # -- Scan geometry ------------------------------------------------------ #

    @mcp.tool()
    def get_scan_zones() -> dict[str, Any]:
        """List the scan zones (name, color, enabled, shape) and which is active."""
        return call(api.scan_zones)

    @mcp.tool()
    def add_scan_zone(
        name: str | None = None,
        color: str | None = None,
        enabled: bool | None = None,
        geometry: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a scan zone.

        Defaults: name "Zone <n>", the next color of the zone palette,
        enabled, and an empty shape. `color` is "#rrggbb".

        `geometry` shapes: polygon
        `{"polygon": {"exterior": [{"x":0.0,"y":0.0}, ...], "interiors": [[{"x":..,"y":..}, ...], ...]}}`;
        multipolygon `{"multipolygon": [{"polygon": {...}}, ...]}` (a list of
        geometry dicts, not a "polygons" key); empty shape
        `{"geometrycollection": null}`. Call get_scan_zones first to see an
        existing zone's geometry as a template.
        """
        return call(api.add_scan_zone, name, color, enabled, geometry)

    @mcp.tool()
    def update_scan_zone(
        index: int,
        name: str | None = None,
        color: str | None = None,
        enabled: bool | None = None,
        geometry: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Rename, recolor, enable/disable or reshape the scan zone at `index`.

        `index` is the stable zone id from the `id` field reported by
        get_scan_zones — not a list position. It does not change when other
        zones are deleted. Only the given fields change. Disabling a zone
        excludes it from point generation without deleting it.

        `geometry` shapes: polygon
        `{"polygon": {"exterior": [{"x":0.0,"y":0.0}, ...], "interiors": [[{"x":..,"y":..}, ...], ...]}}`;
        multipolygon `{"multipolygon": [{"polygon": {...}}, ...]}` (a list of
        geometry dicts, not a "polygons" key); empty shape
        `{"geometrycollection": null}`. Call get_scan_zones first to see the
        zone's current geometry as a template.
        """
        return call(api.update_scan_zone, index, name, color, enabled, geometry)

    @mcp.tool()
    def delete_scan_zone(index: int) -> dict[str, Any]:
        """Delete the scan zone identified by `index` (the `id` field from
        get_scan_zones) and return the remaining zones.

        Zone ids are stable: deleting a zone does not renumber the remaining
        ones, so you can safely pass multiple ids collected from a single
        get_scan_zones call without re-listing between deletes.
        """
        return call(api.delete_scan_zone, index)

    # -- Motion ------------------------------------------------------------- #

    @mcp.tool()
    def get_stage_position() -> list[float]:
        """Get the current position of the main stage."""
        return call(api.position)

    @mcp.tool()
    def move_stage(position: list[float]) -> list[float]:
        """Move the main stage to ``position`` and return the final position.

        Fewer coordinates than the number of axes leaves the remaining axes
        untouched; too many coordinates is an error.
        """
        return call(api.go_to_position, position)

    @mcp.tool()
    def go_to_memory_point(index: int) -> list[float]:
        """Move the stage to the memory point at ``index``."""
        return call(api.go_to, index)

    @mcp.tool()
    def go_next() -> dict[str, Any]:
        """Jump to the next scan position."""
        return call(api.go_next)

    @mcp.tool()
    def autofocus() -> list[float]:
        """Perform an autofocus and return the final stage position."""
        return call(api.autofocus)

    @mcp.tool()
    def magic_focus(parameters: dict[str, Any] | None = None) -> dict[str, Any]:
        """Perform a magic focus, or get its state when no parameters are given."""
        return call(api.magicfocus, parameters)

    # -- Annotations -------------------------------------------------------- #

    @mcp.tool()
    def list_markers() -> list[dict[str, Any]]:
        """List the markers currently shown in the viewer."""
        return call(api.markers)

    @mcp.tool()
    def add_marker(
        position: list[float] | None = None,
        color: list[float] | None = None,
        label: str | None = None,
        visible: bool = True,
    ) -> dict[str, Any]:
        """Add a marker in the viewer.

        :param position: ``[x, y]`` viewer coordinates. If omitted, the stage's
            current position is used.
        :param color: ``[r, g, b]`` or ``[r, g, b, a]`` channels in ``[0, 1]``.
        :param label: Optional label for the marker.
        :param visible: If False, the marker is created but not displayed.
        """
        pos = (position[0], position[1]) if position is not None else None
        rgba = tuple(color) if color is not None else (0.0, 0.0, 0.0)
        return call(
            api.marker,
            color=rgba,  # type: ignore[arg-type]
            positions=pos,
            label=label,
            visible=visible,
        )

    @mcp.tool()
    def delete_markers(ids: list[int] | None = None) -> dict[str, Any]:
        """Delete markers from the viewer.

        :param ids: Identifiers of the markers to delete (as returned by
            ``list_markers`` / ``add_marker``). If omitted, all markers are
            removed.
        :return: A dict with the list of deleted identifiers under ``deleted``.
        """
        return call(api.delete_markers, ids)

    @mcp.tool()
    def pixel_to_position(pixels: list[list[float]]) -> list[list[float]]:
        """Convert camera-image pixel coordinates to viewer coordinates.

        Useful to place markers at features detected in the camera image. The
        conversion accounts for the camera resolution, the objective, the stage
        position and any image distortion.

        :param pixels: A list of ``[px, py]`` pixel coordinates, with the origin
            at the top-left of the camera image.
        :return: The converted ``[x, y]`` viewer coordinates, in the same order.
        """
        return call(api.pixel_to_position, pixels)

    # -- Imaging ------------------------------------------------------------ #

    @mcp.tool()
    def get_camera_image() -> Image:
        """Capture and return the current main camera image (PNG)."""
        img = call(api.camera)
        if img is None:
            raise RuntimeError("[DEVICE_UNAVAILABLE] No camera image available.")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return Image(data=buffer.getvalue(), format="png")

    @mcp.tool()
    def get_screenshot() -> Image:
        """Capture and return a screenshot of the Laser Studio viewer (PNG)."""
        img = call(api.screenshot)
        if img is None:
            raise RuntimeError("[DEVICE_UNAVAILABLE] No screenshot available.")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return Image(data=buffer.getvalue(), format="png")

    @mcp.tool()
    def get_averaging() -> int:
        """Get the number of images currently averaged by the camera."""
        return call(api.averaging, False)

    @mcp.tool()
    def reset_averaging() -> int:
        """Reset the camera averaging and return the new count."""
        return call(api.averaging, True)

    return mcp


__all__ = ["build_server"]
