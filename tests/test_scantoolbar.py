"""Unit tests for laserstudio.widgets.toolbars.scantoolbar.ScanToolBar.

These build the toolbar headlessly (QT_QPA_PLATFORM=offscreen, no real
display) and drive it exactly like a user or the shared model would: adding
zones through ``ScansInstrument``, selecting entries in the combo box,
clicking the "+" button, and renaming/recoloring zones through the model.

Building a ``ScanToolBar`` needs a ``LaserStudio``-like object. A real
``LaserStudio`` requires a fully loaded configuration (instruments, main
window chrome, etc.) which is heavy and irrelevant to this widget. Instead —
mirroring ``tests/test_scanworkspace.py``'s approach for ``ScanWorkspace`` — a
small stand-in is used, exposing exactly the surface ``ScanToolBar.__init__``
touches: ``viewer_buttons_group`` (a real ``QButtonGroup``, since the toolbar
adds real checkable buttons to it), ``viewer.Mode`` (the real ``Viewer.Mode``
enum, used only as ``QButtonGroup`` ids), ``viewer.scans`` (a real
``ScansInstrument``, since that is exactly what this feature synchronizes
with), ``viewer.scan_geometry`` (a tiny stub exposing
``.scan_path_generator``, mirroring how the real
``ScanGeometry.scan_path_generator`` property forwards to
``zones.scan_path_generator`` — needed because the (untouched) density
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

from laserstudio.instruments.scans import ScansInstrument
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
    ScanGeometry itself simply forwards from its ScansInstrument)."""

    def __init__(self, zones: ScansInstrument) -> None:
        self.scan_path_generator = zones.scan_path_generator


class _StubViewer:
    """Records nothing; just exposes the attributes ScanToolBar reads."""

    Mode = Viewer.Mode

    def __init__(self, scans: ScansInstrument) -> None:
        self.scans = scans
        self.scan_geometry = _StubScanGeometry(scans)
        self.default_marker_size = 10.0


class _StubLaserStudio(QWidget):
    """Minimal stand-in for LaserStudio: only what ScanToolBar.__init__ uses.

    Must be a real QWidget (not a plain object): ScanToolBar's __init__
    passes it straight to QToolBar's `parent` argument
    (``super().__init__("Scanning Zones", laser_studio)``), which PyQt only
    accepts as an actual QWidget instance.
    """

    def __init__(self, scans: ScansInstrument | None = None) -> None:
        super().__init__()
        self.viewer_buttons_group = QButtonGroup()
        self.viewer = _StubViewer(scans if scans is not None else ScansInstrument({}))
        self.scanning_enabled = True
        self.go_next_calls = 0

    def handle_go_next(self) -> None:
        self.go_next_calls += 1


@pytest.fixture
def zones(qapp) -> ScansInstrument:
    return ScansInstrument({})


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
    assert zones.active_zone is zones.zone(1)
    assert toolbar.zone_combobox.currentIndex() == 0

    add_button.click()
    assert len(zones.zones) == 2
    assert zones.active_zone is zones.zone(2)  # newest zone becomes active
    assert toolbar.zone_combobox.currentIndex() == 1


def _find_add_button(toolbar: ScanToolBar):
    from PyQt6.QtWidgets import QPushButton

    matches = [btn for btn in toolbar.findChildren(QPushButton) if btn.text() == "+"]
    assert len(matches) == 1
    return matches[0]


# ── 4. Selecting a combo entry sets the active zone on the model ────────────


def test_selecting_combo_entry_sets_the_active_zone(toolbar, zones):
    a = zones.add_zone(name="A")
    zones.add_zone(name="B")
    c = zones.add_zone(name="C")
    # Zones added through the model alone leave the active one untouched.
    assert zones.active_zone is None

    toolbar.zone_combobox.setCurrentIndex(2)
    assert zones.active_zone is c

    toolbar.zone_combobox.setCurrentIndex(0)
    assert zones.active_zone is a


# ── 5. Changing the active zone on the model updates the combo, without a
#      feedback loop writing back into the model ────────────────────────────


def test_model_active_zone_change_updates_combo_without_feedback(toolbar, zones):
    zones.add_zone(name="A")
    zones.add_zone(name="B")
    c = zones.add_zone(name="C")

    zones.active_zone = c
    assert toolbar.zone_combobox.currentIndex() == 2
    # Sanity: the sync did not itself trigger another write to the active
    # zone (e.g. via a re-entrant currentIndexChanged -> __on_zone_selected
    # loop landing on a different zone).
    assert zones.active_zone is c


def test_rebuilding_the_combo_keeps_pointing_at_the_active_zone(toolbar, zones):
    """Any zone change refills the combo, which resets its selection to the
    first entry. The drawing tools would then target a zone other than the
    one shown, so the selection has to be restored."""
    a = zones.add_zone(name="A")
    zones.active_zone = a
    assert toolbar.zone_combobox.currentIndex() == 0

    zones.add_zone(name="B")  # refills the combo
    assert zones.active_zone is a
    assert toolbar.zone_combobox.currentIndex() == 0

    zones.active_zone = zones.zone(2)
    zones.add_zone(name="C")
    assert toolbar.zone_combobox.currentIndex() == 1


# ── 6. Renaming / recoloring a zone through the model updates combo text ──


def test_rename_via_model_updates_combo_text(toolbar, zones):
    zone = zones.add_zone(name="Original")
    assert toolbar.zone_combobox.itemText(0) == "Original"

    zones.update_zone_params(zone.id, name="Renamed")
    assert toolbar.zone_combobox.itemText(0) == "Renamed"


def test_recolor_via_model_does_not_crash_and_keeps_text(toolbar, zones):
    zone = zones.add_zone(name="Colorful")
    zones.update_zone_params(zone.id, color=QColor("#123456"))
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
    zones = ScansInstrument({})
    zones.active_zone = zones.add_zone(name="Pre-existing")
    laser_studio = _StubLaserStudio(zones)
    tb = ScanToolBar(laser_studio)
    assert tb.zone_combobox.count() == 1
    assert tb.zone_combobox.itemText(0) == "Pre-existing"
    assert tb.zone_combobox.currentIndex() == 0


# ── Regression: ScanToolBar's connections to the model must not outlive the
#    toolbar. Unlike ScanWorkspace (a plain Python object needing the
#    _ScanModelBridge helper), ScanToolBar *is* a QObject (a QToolBar), so
#    Qt's native "disconnect everything when a QObject is destroyed"
#    behaviour applies to it directly with no extra machinery needed. ─────


def test_dropping_toolbar_then_mutating_model_does_not_crash(qapp):
    zones = ScansInstrument({})
    laser_studio = _StubLaserStudio(zones)
    toolbar = ScanToolBar(laser_studio)

    del toolbar
    del laser_studio
    gc.collect()
    gc.collect()

    # None of this may crash or raise: if the model's connections had
    # outlived the toolbar (as they would for a plain, non-QObject
    # receiver), this would call back into a destroyed C++ object.
    zones.active_zone = zones.add_zone()


# ── Headless two-window smoke test: classic toolbar + new UI panel agree ───


def test_toolbar_and_scanworkspace_panel_stay_in_agreement(qapp):
    """Both windows subscribe independently to the one shared scan model.
    Mutating it through the model (as a REST call or either UI would) must
    keep the classic toolbar's combo and the new panel's zone rows in sync
    with each other, not just each individually correct."""
    shared_zones = ScansInstrument({})

    classic_laser_studio = _StubLaserStudio(shared_zones)
    toolbar = ScanToolBar(classic_laser_studio)

    workspace = ScanWorkspace(Viewer(scans=shared_zones), shared_zones)
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

    zone_a = shared_zones.add_zone(name="Zone A")
    shared_zones.add_zone(name="Zone B")

    assert combo_names() == ["Zone A", "Zone B"]
    assert panel_row_names() == ["Zone A", "Zone B"]
    assert len(panel_row_names()) == toolbar.zone_combobox.count()

    shared_zones.update_zone_params(zone_a.id, name="Zone A Renamed")

    assert combo_names() == ["Zone A Renamed", "Zone B"]
    assert panel_row_names() == ["Zone A Renamed", "Zone B"]
