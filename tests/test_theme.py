"""Checks on the Ledger theme that a screenshot would otherwise be needed for."""

from __future__ import annotations

from collections import Counter

import pytest
from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QPushButton,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from laserstudio.utils.colors import apply_ledger_theme
from laserstudio.widgets.newui import theme


@pytest.fixture(scope="module")
def app() -> QApplication:
    instance = QApplication.instance()
    return instance if isinstance(instance, QApplication) else QApplication([])


@pytest.fixture
def themed_app(app: QApplication):
    """Apply the theme over a desktop theme that wants black text on tooltips."""
    saved_palette = app.palette()
    saved_stylesheet = app.styleSheet()

    desktop = QPalette()
    for role in (QPalette.ColorRole.ToolTipBase, QPalette.ColorRole.Window):
        desktop.setColor(role, QColor(255, 255, 220))
    for role in (QPalette.ColorRole.ToolTipText, QPalette.ColorRole.WindowText):
        desktop.setColor(role, QColor(0, 0, 0))
    app.setPalette(desktop, "QTipLabel")

    apply_ledger_theme(app)
    yield app

    # The style is owned by the application once set, so it is not restored.
    app.setStyleSheet(saved_stylesheet)
    app.setPalette(saved_palette)


def _tooltip_contrast(app: QApplication, ancestor_stylesheet: str | None) -> int:
    """Lightness gap between a tooltip's background and its text."""
    panel = QWidget()
    panel.resize(240, 120)
    if ancestor_stylesheet:
        panel.setStyleSheet(ancestor_stylesheet)
    layout = QVBoxLayout(panel)
    button = QPushButton("x")
    layout.addWidget(button)
    panel.show()
    app.processEvents()

    try:
        QToolTip.showText(QPoint(10, 10), "Fit all", button)
        app.processEvents()
        tip = next(
            widget
            for widget in app.allWidgets()
            if (meta := widget.metaObject()) is not None
            and meta.className() == "QTipLabel"
            and widget.isVisible()
        )
        image = tip.grab().toImage()
        counts = Counter(
            image.pixelColor(x, y).name()
            for y in range(image.height())
            for x in range(image.width())
        )
        background = counts.most_common(1)[0][0]
        # Antialiasing spreads the glyphs over many shades; keep the ones that
        # cover enough pixels to be actual text rather than edge smoothing.
        ink = max(
            (color for color, count in counts.items() if count >= 15),
            key=lambda color: abs(
                QColor(color).lightness() - QColor(background).lightness()
            ),
        )
        return abs(QColor(ink).lightness() - QColor(background).lightness())
    finally:
        QToolTip.hideText()
        app.processEvents()
        panel.hide()
        panel.deleteLater()


@pytest.mark.parametrize(
    "ancestor_stylesheet",
    [
        pytest.param(None, id="classic-ui"),
        pytest.param(f"background: {theme.BG_PANEL};", id="newui-sidebar"),
        pytest.param(f"background: {theme.BG_CARD};", id="newui-card"),
        pytest.param("background: transparent;", id="newui-hud"),
    ],
)
def test_tooltips_stay_readable(themed_app: QApplication, ancestor_stylesheet):
    """Tooltips must not end up as dark text over the new UI's dark backgrounds.

    A tooltip is a child of the widget it documents, so a widget that sets its
    own background hands it to the tooltip as well.
    """
    assert _tooltip_contrast(themed_app, ancestor_stylesheet) >= 40
