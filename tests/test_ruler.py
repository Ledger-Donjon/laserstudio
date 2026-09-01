"""Unit tests for laserstudio.widgets.ruler.

The graduations of a ruler are set either as an interval or as a number of
divisions, never both. These tests pin down that invariant and what each form
does when the ruler is resized.
"""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import QApplication

from laserstudio.widgets.ruler import Ruler, format_length


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture
def ruler(app: QApplication) -> Ruler:
    """A 150 µm horizontal ruler, the length used in the examples."""
    return Ruler((0.0, 0.0), (150.0, 0.0))


def test_a_new_ruler_is_plain(ruler: Ruler):
    assert ruler.graduation is None
    assert ruler.graduation_count is None
    assert ruler.effective_graduation is None


def test_graduation_count_derives_the_interval(ruler: Ruler):
    ruler.graduation_count = 10

    assert ruler.graduation_count == 10
    assert ruler.effective_graduation == pytest.approx(15.0)


def test_graduation_count_clears_the_interval(ruler: Ruler):
    ruler.graduation = 25.0
    ruler.graduation_count = 10

    assert ruler.graduation is None


def test_effective_graduation_clears_the_count(ruler: Ruler):
    ruler.graduation_count = 10
    ruler.graduation = 25.0

    assert ruler.graduation_count is None
    assert ruler.effective_graduation == pytest.approx(25.0)


def test_resizing_keeps_the_count_and_moves_the_interval(ruler: Ruler):
    ruler.graduation_count = 10
    ruler.set_endpoint(1, QPointF(300.0, 0.0))

    assert ruler.graduation_count == 10
    assert ruler.effective_graduation == pytest.approx(30.0)


def test_resizing_keeps_the_interval_in_interval_mode(ruler: Ruler):
    ruler.graduation = 15.0
    ruler.set_endpoint(1, QPointF(300.0, 0.0))

    assert ruler.graduation == pytest.approx(15.0)
    assert ruler.effective_graduation == pytest.approx(15.0)
    assert ruler.graduation_count is None


def test_a_fractional_count_is_allowed(ruler: Ruler):
    ruler.graduation_count = 7.5

    assert ruler.graduation_count == pytest.approx(7.5)
    assert ruler.effective_graduation == pytest.approx(20.0)


def test_interval_mode_reports_a_fractional_effective_count(ruler: Ruler):
    ruler.graduation = 20.0

    # 150 µm at 20 µm per graduation does not divide evenly.
    assert ruler.effective_graduation_count == pytest.approx(7.5)


def test_a_plain_ruler_has_no_effective_count(ruler: Ruler):
    assert ruler.effective_graduation_count is None


def test_a_zero_count_makes_the_ruler_plain(ruler: Ruler):
    ruler.graduation_count = 10
    ruler.graduation_count = 0

    assert ruler.graduation_count is None
    assert ruler.effective_graduation is None


def test_count_on_a_degenerate_ruler_has_no_interval(app: QApplication):
    degenerate = Ruler((5.0, 5.0), (5.0, 5.0))
    degenerate.graduation_count = 10

    assert degenerate.graduation_count == 10
    assert degenerate.effective_graduation is None


def test_count_mode_serializes_the_count_only(ruler: Ruler):
    ruler.graduation_count = 10
    data = ruler.to_dict()

    assert data["graduation_count"] == 10
    assert "graduation" not in data


def test_interval_mode_serializes_the_interval_only(ruler: Ruler):
    ruler.graduation = 15.0
    data = ruler.to_dict()

    assert data["graduation"] == pytest.approx(15.0)
    assert "graduation_count" not in data


def test_the_count_wins_over_nothing_but_loses_to_an_interval(app: QApplication):
    both = Ruler((0.0, 0.0), (150.0, 0.0), graduation=25.0, graduation_count=10)

    assert both.graduation == pytest.approx(25.0)
    assert both.graduation_count is None


def test_format_length_switches_to_millimeters():
    assert format_length(842.13) == "842.13\xa0µm"
    assert format_length(1420.0) == "1.420\xa0mm"
