"""Unit tests for laserstudio.widgets.toolbars.scantoolbar.ScanToolBar.

These build the toolbar headlessly (QT_QPA_PLATFORM=offscreen, no real
display) and drive it exactly like a user or the shared model would: adding
zones through ``ScanZones``, selecting entries in the combo box, clicking the
"+" button, and renaming/recoloring zones through the model.

Building a ``ScanToolBar`` needs a ``LaserStudio``-like object. A real
``LaserStudio`` requires a fully loaded configuration (instruments, main
window chrome, etc.) which is heavy and irrelevant to this widget. Instead —
mirroring ``tests/test_scanworkspace.py``'s approach for ``ScanWorkspace`` — a
small stand-in is used, exposing exactly the surface ``ScanToolBar.__init__``
touches: ``viewer_buttons_group`` (a real ``QButtonGroup``, since the toolbar
adds real checkable buttons to it), ``viewer.Mode`` (the real ``Viewer.Mode``
enum, used only as ``QButtonGroup`` ids), ``viewer.scan_zones`` (a real
``ScanZones``, since that is exactly what this feature synchronizes with),
``viewer.scan_geometry`` (a tiny stub exposing ``.scan_path_generator``,
mirroring how the real ``ScanGeometry.scan_path_generator`` property forwards
to ``zones.scan_path_generator`` — needed because the (untouched) density
spinbox reads it once at construction time), ``viewer.default_marker_size``,
``scanning_enabled`` and ``handle_go_next``.
"""

from __future__ import annotations

import gc
import os

# Must be set before QApplication is constructed.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication, QButtonGroup, QWidget

from laserstudio.utils.scanzones import ScanZones
from laserstudio.widgets.viewer import Viewer
from laserstudio.widgets.toolbars.scantoolbar import ScanToolBar
from laserstudio.widgets.workspace.scanworkspace import ScanWorkspace


@pytest.fixture(scope="module")
def qapp():
    """A single QApplication for the whole module."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class _StubScanGeometry:
    """Mirrors the one attribute of the real ScanGeometry that ScanToolBar
    reads at construction time: `.scan_path_generator` (which the real
    ScanGeometry itself simply forwards from its ScanZones)."""

    def __init__(self, zones: ScanZones) -> None:
        self.scan_path_generator = zones.scan_path_generator


class _StubViewer:
    """Records nothing; just exposes the attributes ScanToolBar reads."""

    Mode = Viewer.Mode

    def __init__(self, scan_zones: ScanZones) -> None:
        self.scan_zones = scan_zones
        self.scan_geometry = _StubScanGeometry(scan_zones)
        self.default_marker_size = 10.0


class _StubLaserStudio(QWidget):
    """Minimal stand-in for LaserStudio: only what ScanToolBar.__init__ uses.

    Must be a real QWidget (not a plain object): ScanToolBar's __init__
    passes it straight to QToolBar's `parent` argument
    (``super().__init__("Scanning Zones", laser_studio)``), which PyQt only
    accepts as an actual QWidget instance.
    """

    def __init__(self, scan_zones: ScanZones | None = None) -> None:
        super().__init__()
        self.viewer_buttons_group = QButtonGroup()
        self.viewer = _StubViewer(scan_zones if scan_zones is not None else ScanZones())
        self.scanning_enabled = True
        self.go_next_calls = 0

    def handle_go_next(self) -> None:
        self.go_next_calls += 1


class _StubRefonteWindow:
    """Minimal stand-in for LaserStudioRefonte, for the two-window smoke test:
    only `.viewer.scan_zones` is used by ScanWorkspace."""

    def __init__(self, scan_zones: ScanZones) -> None:
        self.viewer = _StubViewer(scan_zones)


@pytest.fixture
def zones(qapp) -> ScanZones:
    return ScanZones()


@pytest.fixture
def laser_studio(qapp, zones) -> _StubLaserStudio:
    return _StubLaserStudio(zones)


@pytest.fixture
def toolbar(qapp, laser_studio) -> ScanToolBar:
    return ScanToolBar(laser_studio)


# ── 1. Combo lists one entry per zone, in order ─────────────────────────────


def test_combo_lists_zones_in_order(toolbar, zones):
    zones.add_zone(name="Alpha")
    zones.add_zone(name="Beta")
    zones.add_zone(name="Gamma")

    combo = toolbar.zone_combobox
    assert combo.count() == 3
    assert [combo.itemText(i) for i in range(3)] == ["Alpha", "Beta", "Gamma"]


# ── 2. Adding a zone through the model updates the combo (changed signal) ──


def test_adding_zone_via_model_updates_combo(toolbar, zones):
    assert toolbar.zone_combobox.count() == 0
    zones.add_zone(name="Solo")
    assert toolbar.zone_combobox.count() == 1
    assert toolbar.zone_combobox.itemText(0) == "Solo"


# ── 3. The "+" button creates AND activates a zone ──────────────────────────


def test_add_button_creates_and_activates_zone(toolbar, zones):
    add_button = _find_add_button(toolbar)

    assert len(zones.zones) == 0
    add_button.click()
    assert len(zones.zones) == 1
    assert zones.active_index == 0
    assert toolbar.zone_combobox.currentIndex() == 0

    add_button.click()
    assert len(zones.zones) == 2
    assert zones.active_index == 1  # newest zone becomes active
    assert toolbar.zone_combobox.currentIndex() == 1


def _find_add_button(toolbar: ScanToolBar):
    from PyQt6.QtWidgets import QPushButton

    matches = [btn for btn in toolbar.findChildren(QPushButton) if btn.text() == "+"]
    assert len(matches) == 1
    return matches[0]


# ── 4. Selecting a combo entry sets active_index on the model ───────────────


def test_selecting_combo_entry_sets_active_index(toolbar, zones):
    zones.add_zone(name="A")
    zones.add_zone(name="B")
    zones.add_zone(name="C")
    assert zones.active_index == 0

    toolbar.zone_combobox.setCurrentIndex(2)
    assert zones.active_index == 2

    toolbar.zone_combobox.setCurrentIndex(1)
    assert zones.active_index == 1


# ── 5. Changing active_index on the model updates the combo, without a
#      feedback loop writing back into the model ────────────────────────────


def test_model_active_index_change_updates_combo_without_feedback(toolbar, zones):
    zones.add_zone(name="A")
    zones.add_zone(name="B")
    zones.add_zone(name="C")
    assert zones.active_index == 0

    zones.active_index = 2
    assert toolbar.zone_combobox.currentIndex() == 2
    # Sanity: the sync did not itself trigger another write to active_index
    # (e.g. via a re-entrant currentIndexChanged -> __on_zone_selected loop).
    assert zones.active_index == 2


# ── 6. Renaming / recoloring a zone through the model updates combo text ──


def test_rename_via_model_updates_combo_text(toolbar, zones):
    zones.add_zone(name="Original")
    assert toolbar.zone_combobox.itemText(0) == "Original"

    zones.update_zone(0, name="Renamed")
    assert toolbar.zone_combobox.itemText(0) == "Renamed"


def test_recolor_via_model_does_not_crash_and_keeps_text(toolbar, zones):
    zones.add_zone(name="Colorful")
    zones.update_zone(0, color=QColor("#123456"))
    # The icon changed (not directly inspectable via text), but the entry
    # must still be present with its name intact and no exception raised.
    assert toolbar.zone_combobox.count() == 1
    assert toolbar.zone_combobox.itemText(0) == "Colorful"
    assert not toolbar.zone_combobox.itemIcon(0).isNull()


# ── 7. An empty model leaves the combo empty without raising ───────────────


def test_empty_model_leaves_combo_empty(toolbar, zones):
    assert toolbar.zone_combobox.count() == 0
    assert toolbar.zone_combobox.currentIndex() == -1


def test_toolbar_with_zones_already_present_at_construction(qapp):
    """__sync_zones() called at the end of __init__ must correctly reflect a
    model that already has zones before the toolbar exists (e.g. loaded from
    settings before the toolbar is built)."""
    zones = ScanZones()
    zones.add_zone(name="Pre-existing")
    zones.active_index = 0
    laser_studio = _StubLaserStudio(zones)
    tb = ScanToolBar(laser_studio)
    assert tb.zone_combobox.count() == 1
    assert tb.zone_combobox.itemText(0) == "Pre-existing"
    assert tb.zone_combobox.currentIndex() == 0


# ── Regression: ScanToolBar's connection to zones.changed must not outlive
#    the toolbar. Unlike ScanWorkspace (a plain Python object needing the
#    _ScanModelBridge helper), ScanToolBar *is* a QObject (a QToolBar), so
#    Qt's native "disconnect everything when a QObject is destroyed"
#    behaviour applies to it directly with no extra machinery needed. ─────


def test_dropping_toolbar_then_mutating_model_does_not_crash(qapp):
    zones = ScanZones()
    laser_studio = _StubLaserStudio(zones)
    toolbar = ScanToolBar(laser_studio)

    del toolbar
    del laser_studio
    gc.collect()
    gc.collect()

    # None of this may crash or raise: if the `zones.changed` connection had
    # outlived the toolbar (as it would for a plain, non-QObject receiver),
    # this would call back into a destroyed C++ object.
    zones.add_zone()
    zones.active_index = 0


# ── Headless two-window smoke test: classic toolbar + new UI panel agree ───


def test_toolbar_and_scanworkspace_panel_stay_in_agreement(qapp):
    """Both windows subscribe independently to the one shared ScanZones
    model. Mutating it through the model (as a REST call or either UI would)
    must keep the classic toolbar's combo and the new panel's zone rows in
    sync with each other, not just each individually correct."""
    shared_zones = ScanZones()

    classic_laser_studio = _StubLaserStudio(shared_zones)
    toolbar = ScanToolBar(classic_laser_studio)

    refonte_window = _StubRefonteWindow(shared_zones)
    workspace = ScanWorkspace(refonte_window)
    panel = workspace.build_panel()  # noqa: F841 - keep the QScrollArea alive

    def combo_names() -> list[str]:
        combo = toolbar.zone_combobox
        return [combo.itemText(i) for i in range(combo.count())]

    def panel_row_names() -> list[str]:
        from PyQt6.QtWidgets import QLineEdit

        assert workspace._rows_layout is not None
        layout = workspace._rows_layout
        names = []
        for i in range(layout.count()):
            row = layout.itemAt(i).widget()
            row_layout = row.layout() if row is not None else None
            if row_layout is None or row_layout.count() < 2:
                continue
            name_edit = row_layout.itemAt(1).widget()
            if isinstance(name_edit, QLineEdit):
                names.append(name_edit.text())
        return names

    shared_zones.add_zone(name="Zone A")
    shared_zones.add_zone(name="Zone B")

    assert combo_names() == ["Zone A", "Zone B"]
    assert panel_row_names() == ["Zone A", "Zone B"]
    assert len(panel_row_names()) == toolbar.zone_combobox.count()

    shared_zones.update_zone(0, name="Zone A Renamed")

    assert combo_names() == ["Zone A Renamed", "Zone B"]
    assert panel_row_names() == ["Zone A Renamed", "Zone B"]
