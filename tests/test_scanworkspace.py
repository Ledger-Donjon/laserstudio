"""Unit tests for laserstudio.widgets.workspace.scanworkspace.ScanWorkspace.

These build the panel headlessly (QT_QPA_PLATFORM=offscreen, no real display)
and drive it exactly like a user would: editing a row's QLineEdit and emitting
``editingFinished``, flipping a row's ``ToggleSwitch``, clicking the trash
button, etc. ``QMenu.exec`` (used by the colour-swatch picker) blocks, so
``_pick_color`` itself is never invoked here — ``_set_color`` (the part that
actually touches the model) is tested directly instead.

A full ``LaserStudioRefonte`` needs a real ``Instruments`` instance (i.e. a
loaded config), which is heavier and noisier than this test needs. Instead we
use a tiny stand-in exposing ``.viewer.scan_zones`` plus a stub viewer that
records ``select_mode``/``go_next`` calls — enough surface for
``ScanWorkspace`` to work against, matching how ``LaserStudioRefonte.viewer``
is used (``self._window.viewer.scan_zones`` / ``.select_mode`` / ``.go_next``).
"""

from __future__ import annotations

import gc
import os

# Must be set before QApplication is constructed.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6 import sip
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from laserstudio.utils.colors import MARKERS_COLORS
from laserstudio.utils.scanzones import ScanZones
from laserstudio.widgets.viewer import Viewer
from laserstudio.widgets.workspace.schemaform import ToggleSwitch
from laserstudio.widgets.workspace.scanworkspace import ScanWorkspace


@pytest.fixture(scope="module")
def qapp():
    """A single QApplication for the whole module."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class _StubViewer:
    """Records calls instead of touching a real Qt graphics viewer/stage."""

    def __init__(self, scan_zones: ScanZones) -> None:
        self.scan_zones = scan_zones
        self.select_mode_calls: list[tuple[object, bool]] = []
        self.go_next_calls = 0

    def select_mode(self, mode, toggle: bool = False) -> None:
        self.select_mode_calls.append((mode, toggle))

    def go_next(self) -> None:
        self.go_next_calls += 1


class _StubWindow:
    """Minimal stand-in for LaserStudioRefonte: only `.viewer` is used."""

    def __init__(self, scan_zones: ScanZones) -> None:
        self.viewer = _StubViewer(scan_zones)


@pytest.fixture
def zones(qapp) -> ScanZones:
    return ScanZones()


@pytest.fixture
def window(qapp, zones) -> _StubWindow:
    return _StubWindow(zones)


@pytest.fixture
def workspace(qapp, window) -> ScanWorkspace:
    ws = ScanWorkspace(window)
    # The returned QScrollArea is a top-level (unparented) widget: nothing
    # else in Qt owns it, so it must be kept alive here or PyQt garbage
    # collects the underlying C++ object (and everything parented under it,
    # including _rows_layout) as soon as build_panel() returns.
    ws._test_panel = ws.build_panel()
    return ws


def _rows(ws: ScanWorkspace) -> list:
    assert ws._rows_layout is not None
    layout: QVBoxLayout = ws._rows_layout
    return [layout.itemAt(i).widget() for i in range(layout.count())]


def _row_controls(row) -> tuple[QPushButton, QLineEdit, ToggleSwitch, QPushButton]:
    """Return (swatch, name_edit, toggle, delete_btn) for a zone row, in the
    exact order ``_zone_row`` adds them to its QHBoxLayout."""
    layout = row.layout()
    widgets = [
        item.widget()
        for i in range(layout.count())
        if (item := layout.itemAt(i)) is not None and item.widget() is not None
    ]
    # Located by type, not by index: the row gains an extra "ACTIVE" label when
    # it is the active zone, so fixed positions would only hold for some rows.
    buttons = [w for w in widgets if isinstance(w, QPushButton)]
    name_edits = [w for w in widgets if isinstance(w, QLineEdit)]
    toggles = [w for w in widgets if isinstance(w, ToggleSwitch)]
    assert len(buttons) == 2, f"expected swatch + delete, got {len(buttons)}"
    assert len(name_edits) == 1
    assert len(toggles) == 1
    swatch, delete_btn = buttons
    return swatch, name_edits[0], toggles[0], delete_btn


def _button_labelled(panel, label: str) -> QPushButton:
    """Find a QPushButton anywhere in ``panel`` by its (stripped) text.

    ``_draw_section``/``_scan_section`` prefix each button's text with a
    couple of spaces to make room for the icon (e.g. ``"  Rectangle"``), so
    matching is done on the stripped text.
    """
    matches = [
        btn
        for btn in panel.findChildren(QPushButton)
        if btn.text().strip() == label
    ]
    assert len(matches) == 1, (
        f"expected exactly one button labelled {label!r}, found {len(matches)}"
    )
    return matches[0]


# ── 1. No model attached ─────────────────────────────────────────────────────


def test_build_panel_without_model_does_not_crash(qapp):
    ws = ScanWorkspace(None)
    panel = ws.build_panel()
    assert panel is not None
    assert ws.zones is None
    # Empty-state label path: one placeholder label, no zone rows.
    rows = _rows(ws)
    assert len(rows) == 1
    assert isinstance(rows[0], type(rows[0]))  # just: it exists, no crash


# ── 2. Row count tracks the model; changed signal rebuilds rows ─────────────


def test_rows_track_model_via_changed_signal(workspace, zones):
    assert len(_rows(workspace)) == 1  # empty-state label

    zones.add_zone()
    assert len(_rows(workspace)) == 1  # one real row now (label replaced)

    zones.add_zone()
    zones.add_zone()
    assert len(_rows(workspace)) == 3


# ── 3. Add zone button creates + activates a zone ────────────────────────────


def test_add_zone_button_creates_and_activates(workspace, zones):
    assert len(zones.zones) == 0
    workspace._on_add_zone()
    assert len(zones.zones) == 1
    assert zones.active_index == 0

    workspace._on_add_zone()
    assert len(zones.zones) == 2
    assert zones.active_index == 1  # newest zone becomes active


# ── 4. Renaming via a row's QLineEdit ───────────────────────────────────────


def test_rename_via_row_line_edit_updates_model(workspace, zones):
    zones.add_zone(name="Alpha")
    row = _rows(workspace)[0]
    _swatch, name_edit, _toggle, _delete = _row_controls(row)

    name_edit.setText("Renamed")
    name_edit.editingFinished.emit()

    assert zones.zone(0).name == "Renamed"


def test_rename_does_not_fire_while_syncing(workspace, zones):
    zones.add_zone(name="Alpha")
    # Simulate being mid-rebuild: _on_rename must be a no-op in that state.
    workspace._syncing = True
    try:
        workspace._on_rename(0, "Should not apply")
    finally:
        workspace._syncing = False
    assert zones.zone(0).name == "Alpha"


# ── 5. Toggling a row's ToggleSwitch only affects that zone ─────────────────


def test_toggle_disables_only_that_zone(workspace, zones):
    zones.add_zone(name="A")
    zones.add_zone(name="B")
    zones.add_zone(name="C")
    rows = _rows(workspace)
    assert len(rows) == 3

    _swatch, _name, toggle_b, _delete = _row_controls(rows[1])
    assert toggle_b.isChecked() is True
    toggle_b.setChecked(False)  # what a click on the toggle does

    assert zones.zone(0).enabled is True
    assert zones.zone(1).enabled is False
    assert zones.zone(2).enabled is True


def test_toggle_does_not_fire_while_syncing(workspace, zones):
    zones.add_zone(name="A")
    workspace._syncing = True
    try:
        workspace._on_toggle(0, False)
    finally:
        workspace._syncing = False
    assert zones.zone(0).enabled is True


# ── 6. Deleting via a row's trash button — the stale-index risk ────────────


def test_delete_middle_of_three_removes_the_right_zone(workspace, zones):
    zones.add_zone(name="Alpha")
    zones.add_zone(name="Beta")
    zones.add_zone(name="Gamma")
    rows = _rows(workspace)
    assert len(rows) == 3

    # Delete the middle row (index 1, "Beta"). Row callbacks capture their
    # index at construction time; if the callback fired on a stale index
    # captured before some earlier rebuild, this would delete the wrong zone.
    _swatch, _name, _toggle, delete_btn = _row_controls(rows[1])
    delete_btn.clicked.emit()

    remaining = [z.name for z in zones.zones]
    assert remaining == ["Alpha", "Gamma"]

    # And the rebuilt rows reflect the surviving zones, in order.
    new_rows = _rows(workspace)
    assert len(new_rows) == 2
    _s0, name0, _t0, _d0 = _row_controls(new_rows[0])
    _s1, name1, _t1, _d1 = _row_controls(new_rows[1])
    assert name0.text() == "Alpha"
    assert name1.text() == "Gamma"


def test_delete_each_row_in_turn_removes_correct_zone(workspace, zones):
    """Delete zones one at a time via the (rebuilt-each-time) row buttons,
    always targeting row 0, and check the right zone disappears each time."""
    zones.add_zone(name="One")
    zones.add_zone(name="Two")
    zones.add_zone(name="Three")

    for expected_survivors in (["Two", "Three"], ["Three"], []):
        rows = _rows(workspace)
        _s, _n, _t, delete_btn = _row_controls(rows[0])
        delete_btn.clicked.emit()
        assert [z.name for z in zones.zones] == expected_survivors


# ── Colour swatch: _set_color directly (never _pick_color — QMenu.exec blocks) ──


def test_set_color_updates_the_right_zone(workspace, zones):
    zones.add_zone(name="A")
    zones.add_zone(name="B")
    workspace._set_color(1, QColor("#123456"))
    assert zones.zone(0).color != QColor("#123456")
    assert zones.zone(1).color == QColor("#123456")


# ── 7. Clicking a row activates that zone ───────────────────────────────────


def test_clicking_a_row_activates_it(workspace, zones):
    zones.add_zone(name="A")
    zones.add_zone(name="B")
    zones.add_zone(name="C")
    assert zones.active_index == 0  # ScanZones.add_zone leaves it untouched

    workspace._on_activate(2)
    assert zones.active_index == 2

    # Directly exercise the monkeypatched mousePressEvent too, which is what
    # actually runs when the user clicks a row.
    rows = _rows(workspace)
    rows[1].mousePressEvent(None)
    assert zones.active_index == 1


# ── 8. Density / point size / path colour write to the model ───────────────


def test_density_field_writes_to_model(workspace, zones):
    workspace._density.setValue(250)
    workspace._on_density()
    assert zones.density == 250


def test_point_size_field_writes_to_model(workspace, zones):
    workspace._point_size.setValue(42.5)
    workspace._on_point_size()
    assert zones.point_diameter == pytest.approx(42.5)


def test_path_color_combo_sets_model(workspace, zones):
    combo = workspace._path_color
    assert combo.count() > 1
    combo.setCurrentIndex(combo.count() - 1)
    workspace._on_path_color()
    expected = combo.itemData(combo.count() - 1)
    assert zones.path_color == QColor(expected)


# ── 9. Draw-mode buttons and Go-to-next-point ───────────────────────────────


def test_draw_mode_buttons_call_select_mode(workspace, window):
    """Each button built by ``_draw_section`` must call ``viewer.select_mode``
    with *its own* mode — not just any of the three. Clicking straight
    through ``workspace._select_mode(...)`` would only prove that method
    forwards correctly; it says nothing about how ``_draw_section`` wired the
    buttons, so a label/mode mismatch there (e.g. swapped list entries) would
    go unnoticed. Clicking the real buttons and checking the pairing catches
    that.
    """
    panel = workspace._test_panel
    expected = [
        ("Rectangle", Viewer.Mode.ZONE),
        ("Tilted", Viewer.Mode.ZONE_TILTED),
        ("Polygon", Viewer.Mode.ZONE_POLY),
    ]
    for label, mode in expected:
        window.viewer.select_mode_calls.clear()
        button = _button_labelled(panel, label)
        button.click()
        # toggle=True is what lets re-clicking an already-active mode button
        # return the viewer to Mode.NONE.
        assert window.viewer.select_mode_calls == [(mode, True)], (
            f"button {label!r} did not call select_mode({mode!r}, toggle=True)"
        )


def test_go_next_button_calls_viewer_go_next(workspace, window):
    button = _button_labelled(workspace._test_panel, "Go to next point")
    button.click()
    assert window.viewer.go_next_calls == 1


# ── Fix 1: the `zones.changed`/`path_changed` connections must not outlive
# the panel — regression test for a real SIGABRT ───────────────────────────


def test_dropping_panel_then_mutating_model_does_not_crash(qapp):
    """Regression test for a crash found in review.

    ``build_panel`` connects ``zones.changed``/``path_changed`` to this
    panel's sync methods and nothing used to disconnect them.
    ``ScanWorkspace`` is a plain Python object, not a ``QObject``, so Qt's
    automatic receiver-destroyed disconnect did not apply — and closures
    created for row/button callbacks (e.g. in ``_zone_row``) kept the
    ``ScanWorkspace`` instance itself alive well after its widgets were
    destroyed. The next model signal then called a sync method against an
    already-deleted Qt object, raising a ``RuntimeError`` from inside a
    C++-driven signal emission — which aborts the whole process (SIGABRT),
    not a catchable Python exception.

    If this regresses, this test does not fail cleanly: it takes the whole
    pytest process down. That is still the right test to have — an abort is
    unambiguous, and there is no clean way to "expect" a SIGABRT from
    within the same process that would suffer it.
    """
    zones = ScanZones()
    window = _StubWindow(zones)
    ws = ScanWorkspace(window)
    panel = ws.build_panel()

    # Discard every reference the test holds; only whatever ScanWorkspace's
    # own internals still keep should determine what stays alive.
    del panel
    del ws
    del window
    gc.collect()
    gc.collect()

    # None of this may crash. Before the fix, the mere act of mutating the
    # model here reliably aborted the process.
    zones.add_zone()
    zones.density = 42
    zones.point_diameter = 5.0
    zones.path_color = QColor("red")


def test_build_panel_twice_does_not_double_connect(qapp, zones, window):
    """Calling build_panel() again on the same instance (a future rebuild
    path) must not leave two live connections to the model — that would
    rebuild the rows (or push into the scan controls) twice per change."""
    ws = ScanWorkspace(window)
    first_panel = ws.build_panel()
    second_panel = ws.build_panel()
    assert second_panel is not first_panel

    rebuild_count = [0]
    real_zone_row = ws._zone_row

    def counting_zone_row(*args, **kwargs):
        rebuild_count[0] += 1
        return real_zone_row(*args, **kwargs)

    ws._zone_row = counting_zone_row
    zones.add_zone()
    assert rebuild_count[0] == 1  # not 2


def test_control_handlers_are_safe_after_the_panel_is_destroyed(
    qapp, zones, window
):
    """The scan-control handlers must be no-ops once their widgets are gone.

    ``_on_density``/``_on_point_size``/``_on_path_color`` used to read
    ``self._density`` and friends unconditionally. A queued signal arriving
    after the panel's widgets were destroyed then raised
    ``RuntimeError: wrapped C/C++ object of type ReturnSpinBox has been
    deleted`` — reproduced in review. Deleting the panel's C++ side while
    keeping the ``ScanWorkspace`` alive is exactly that state.
    """
    ws = ScanWorkspace(window)
    panel = ws.build_panel()
    before = (zones.density, zones.point_diameter, zones.path_color.name())

    sip.delete(panel)  # destroys the panel and every widget under it

    # Must not raise, and must not touch the model either.
    ws._on_density()
    ws._on_point_size()
    ws._on_path_color()

    assert (zones.density, zones.point_diameter, zones.path_color.name()) == before


# ── Fix 2: density / point size / path colour must sync *from* the model ──


def test_scan_controls_sync_from_model_changes(workspace, zones):
    """The shared model can be written by the classic toolbar or the REST
    API, not just this panel — the readouts must follow those writes too."""
    zones.density = 555
    assert workspace._density.value() == 555

    zones.point_diameter = 9.0
    assert workspace._point_size.value() == pytest.approx(9.0)

    swatch_color, swatch_name = MARKERS_COLORS[3]
    zones.path_color = QColor(swatch_color)
    assert workspace._path_color.currentText() == swatch_name


def test_scan_controls_sync_does_not_write_back_into_model(workspace, zones):
    zones.density = 555
    zones.point_diameter = 9.0
    swatch_color, _name = MARKERS_COLORS[3]
    zones.path_color = QColor(swatch_color)

    before = (zones.density, zones.point_diameter, zones.path_color.name())

    # Re-run the sync explicitly, as if another `changed`/`path_changed` had
    # fired for an unrelated reason. If pushing the model's values into the
    # widgets looped back through their on-change handlers into the model,
    # one of these would drift (e.g. rounding, or picking a different combo
    # entry than the exact colour already stored).
    workspace._sync_scan_controls()

    after = (zones.density, zones.point_diameter, zones.path_color.name())
    assert after == before


def test_scan_controls_sync_leaves_combo_alone_for_unlisted_colour(workspace, zones):
    """The model's colour need not be one of MARKERS_COLORS — in that case
    the combo must be left as-is, not forced to index 0."""
    workspace._path_color.setCurrentIndex(2)
    zones.path_color = QColor(17, 18, 19)  # not one of the offered swatches
    assert workspace._path_color.currentIndex() == 2


# ── Fix 3: an unrelated model change must not discard an in-progress rename ─


def test_typing_a_rename_survives_an_unrelated_model_change(workspace, zones):
    zones.add_zone(name="Alpha")
    zones.add_zone(name="Beta")

    # hasFocus() only reflects reality once the widget is actually shown.
    workspace._test_panel.show()
    QApplication.processEvents()

    row0 = _rows(workspace)[0]
    _swatch, name_edit, _toggle, _delete = _row_controls(row0)
    name_edit.setFocus(Qt.FocusReason.OtherFocusReason)
    QApplication.processEvents()
    assert name_edit.hasFocus()

    name_edit.setText("Alpha (typing)")
    # No editingFinished emitted — the user is still typing.

    # An unrelated model change elsewhere (a REST call, the classic
    # toolbar, a drag committing a geometry) must not discard it.
    zones.add_zone(name="Gamma")

    assert zones.zone(0).name == "Alpha (typing)"

    # The rows were rebuilt (a new QLineEdit exists for zone 0), but focus
    # and the typed text must have been carried over to it.
    QApplication.processEvents()
    rows = _rows(workspace)
    _s, restored_edit, _t, _d = _row_controls(rows[0])
    assert restored_edit is not name_edit
    assert restored_edit.text() == "Alpha (typing)"
    assert restored_edit.hasFocus()


def test_pending_rename_ignored_once_committed(workspace, zones):
    """Once a rename is committed (editingFinished fires normally), a later
    unrelated model change must not re-commit or otherwise touch it again —
    _pending_rename must only see text that differs from the model."""
    zones.add_zone(name="Alpha")
    row = _rows(workspace)[0]
    _swatch, name_edit, _toggle, _delete = _row_controls(row)

    name_edit.setText("Renamed")
    name_edit.editingFinished.emit()
    assert zones.zone(0).name == "Renamed"

    # A later unrelated change must not do anything odd with the (now
    # unfocused, already-committed) row.
    zones.add_zone(name="Beta")
    assert [z.name for z in zones.zones] == ["Renamed", "Beta"]


# ── Active-zone selection must be obvious in the list ──────────────────────


def _active_chip(row) -> QLabel | None:
    """The 'ACTIVE' marker label on a row, if it has one."""
    labels = [w for w in row.findChildren(QLabel) if w.text() == "ACTIVE"]
    return labels[0] if labels else None


def test_active_row_is_visually_distinct(workspace, zones):
    """Only the active row carries the ACTIVE marker, and its stylesheet
    picks up that zone's own colour as an accent — so which zone a drawing
    gesture will land in is readable at a glance, not inferred from a
    one-pixel border."""
    zones.add_zone(name="A", color="#ff5300")
    zones.add_zone(name="B", color="#00c8ff")
    zones.active_index = 0

    first, second = _rows(workspace)
    assert _active_chip(first) is not None
    assert _active_chip(second) is None
    # The accent uses the active zone's colour, not a generic highlight.
    assert "#ff5300" in first.styleSheet()
    assert "#00c8ff" not in second.styleSheet()
    assert first.styleSheet() != second.styleSheet()


def test_the_marker_follows_the_active_zone(workspace, zones):
    zones.add_zone(name="A", color="#ff5300")
    zones.add_zone(name="B", color="#00c8ff")

    zones.active_index = 1
    first, second = _rows(workspace)
    assert _active_chip(first) is None
    assert _active_chip(second) is not None
    assert "#00c8ff" in second.styleSheet()


def test_exactly_one_row_is_ever_marked_active(workspace, zones):
    for name in ("A", "B", "C"):
        zones.add_zone(name=name)
    for index in range(3):
        zones.active_index = index
        marked = [r for r in _rows(workspace) if _active_chip(r) is not None]
        assert len(marked) == 1
        assert marked[0].zone is zones.zone(index)
