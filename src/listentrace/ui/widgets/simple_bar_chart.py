from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from listentrace.application.dto.learning_history import ChartData

_BAR_COLOR = QColor("#2563EB")
_AXIS_COLOR = QColor("#9CA3AF")
_TEXT_COLOR = QColor("#374151")


class SimpleBarChart(QWidget):
    """A minimal, dependency-free bar chart. Always paired with a plain table
    showing the exact same `ChartData.points` (see `LearningHistoryWindow`) —
    this widget only paints what the table already lists; it never computes
    or displays anything the table doesn't."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._data: ChartData | None = None
        self.setMinimumHeight(140)

    def set_data(self, data: ChartData) -> None:
        self._data = data
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        try:
            painter.fillRect(self.rect(), Qt.GlobalColor.white)
            if self._data is None or not self._data.points:
                painter.setPen(_TEXT_COLOR)
                painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No data for the selected filters.")
                return

            points = self._data.points
            margin = 24
            width = max(self.width() - 2 * margin, 1)
            height = max(self.height() - 2 * margin, 1)
            max_value = max((p.value for p in points), default=0.0) or 1.0
            slot_width = width / len(points)
            bar_width = max(slot_width - 6, 2)

            painter.setPen(_AXIS_COLOR)
            painter.drawLine(margin, self.height() - margin, self.width() - margin, self.height() - margin)

            painter.setPen(_TEXT_COLOR)
            for index, point in enumerate(points):
                bar_height = (point.value / max_value) * height
                x = margin + index * slot_width
                y = self.height() - margin - bar_height
                painter.fillRect(int(x), int(y), int(bar_width), int(bar_height), _BAR_COLOR)
        finally:
            painter.end()
