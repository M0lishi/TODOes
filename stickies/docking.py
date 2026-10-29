"""Размещение компактных вкладок в рабочей области монитора."""
from PyQt6.QtCore import QRect

COMPACT_WIDTH = 160
COMPACT_HEIGHT = 32


def compact_slot(area: QRect, occupied=()) -> QRect:
    """Первое свободное место справа налево, затем следующим рядом выше."""
    width = min(COMPACT_WIDTH, area.width())
    height = min(COMPACT_HEIGHT, area.height())
    columns = max(1, area.width() // width)
    rows = max(1, area.height() // height)
    for row in range(rows):
        for column in range(columns):
            target = QRect(area.right() + 1 - (column + 1) * width,
                           area.bottom() + 1 - (row + 1) * height, width, height)
            if not any(target.intersects(rect) for rect in occupied):
                return target
    raise ValueError("Нет свободного места для свёрнутого стикера на экране")
