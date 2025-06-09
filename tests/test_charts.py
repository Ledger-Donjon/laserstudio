from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCharts import QLineSeries, QChart
from PyQt6.QtGui import QPainter
from laserstudio.utils.util import ChartViewWithVMarker
from random import randint


def test_line_vertical():
    """
    Test the line vertical function.
    """
    # Create a QApplication instance
    app = QApplication([])

    # Create a QLineSeries object
    series = QLineSeries()

    # Add random points to the series
    max = 0
    max_x = 0
    for i in range(10):
        y = randint(0, 10)
        series.append(i, y)
        if y > max:
            max = y
            max_x = i

    # Create a QChart object
    chart = QChart()

    chart.setAnimationOptions(QChart.AnimationOption.AllAnimations)
    chart.setTheme(QChart.ChartTheme.ChartThemeDark)

    # Add the series to the chart
    chart.addSeries(series)

    # Create a QChartView object
    chart_view = ChartViewWithVMarker(chart)
    chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
    chart_view.vmarker = max_x

    # Set the chart view size
    chart_view.setMinimumSize(QSize(800, 600))

    # Set the chart view title
    chart_view.setWindowTitle("Test Line Vertical")

    # Show the chart view
    chart_view.show()
    # Execute the application
    app.exec()

    # Clean up
    chart_view.deleteLater()
    chart.deleteLater()
    series.deleteLater()
    app.quit()
