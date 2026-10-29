"""Мелкие виджеты: круглый чекбокс, иконки-кнопки, строка задачи."""
from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import (QAbstractButton, QHBoxLayout, QLineEdit,
                             QSizePolicy, QWidget)

from .model import Task


def repolish(w: QWidget) -> None:
    w.style().unpolish(w)
    w.style().polish(w)
    w.update()


class RoundCheck(QAbstractButton):
    """Круглая отметка как в «Напоминаниях» iOS."""

    def __init__(self, accent: str, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(28, 28)  # комфортная зона нажатия
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._accent = QColor(accent)

    def set_accent(self, color: str) -> None:
        self._accent = QColor(color)
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(28, 28)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(4, 4, 20, 20)
        if self.isChecked():
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(self._accent)
            p.drawEllipse(r)
            pen = QPen(QColor("white"), 2.2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPolyline(QPolygonF([QPointF(9, 14.5), QPointF(12.5, 18), QPointF(19, 10.5)]))
        else:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(60, 60, 67, 110), 1.8))
            p.drawEllipse(r)


class IconButton(QAbstractButton):
    """Плоская кнопка с нарисованной иконкой: plus, close, dots, pin."""

    def __init__(self, kind: str, tooltip: str = "", checkable: bool = False,
                 size: int = 30, parent=None):
        super().__init__(parent)
        self._kind = kind
        self._hover = False
        self.setToolTip(tooltip)
        self.setCheckable(checkable)
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        ink = QColor(28, 28, 30, 170)
        if self._hover:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 22))
            p.drawEllipse(self.rect().adjusted(1, 1, -1, -1))
        cx, cy = self.width() / 2, self.height() / 2
        pen = QPen(ink, 1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        k = self._kind
        if k == "plus":
            p.setPen(pen)
            p.drawLine(QPointF(cx - 6, cy), QPointF(cx + 6, cy))
            p.drawLine(QPointF(cx, cy - 6), QPointF(cx, cy + 6))
        elif k == "close":
            d = 4.0
            p.setPen(pen)
            p.drawLine(QPointF(cx - d, cy - d), QPointF(cx + d, cy + d))
            p.drawLine(QPointF(cx - d, cy + d), QPointF(cx + d, cy - d))
        elif k == "dots":
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(ink)
            for dx in (-6, 0, 6):
                p.drawEllipse(QPointF(cx + dx, cy), 1.9, 1.9)
        elif k == "pin":
            active = self.isChecked()
            col = QColor("#007AFF") if active else ink
            pen = QPen(col, 1.8)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.translate(cx, cy)
            p.rotate(40)
            p.setPen(pen)
            p.setBrush(col if active else Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF(-3.5, -8, 7, 10), 2, 2)
            p.drawLine(QPointF(0, 2), QPointF(0, 8))


class TaskRow(QWidget):
    """Одна задача: отметка, текст и кнопка удаления при наведении."""

    changed = pyqtSignal()
    removeRequested = pyqtSignal(object)

    def __init__(self, task: Task, accent: str, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        self.check = RoundCheck(accent)
        self.check.setChecked(task.done)
        self.edit = QLineEdit(task.text)
        self.edit.setObjectName("task")
        self.edit.setPlaceholderText("Задача")
        self.edit.setCursorPosition(0)  # длинный текст показываем с начала
        self.edit.setMinimumHeight(28)
        self.remove_btn = IconButton("close", "Удалить задачу", size=24)
        sp = self.remove_btn.sizePolicy()
        sp.setRetainSizeWhenHidden(True)
        self.remove_btn.setSizePolicy(sp)
        self.remove_btn.setVisible(False)

        lay.addWidget(self.check)
        lay.addWidget(self.edit, 1)
        lay.addWidget(self.remove_btn)

        self.check.toggled.connect(self._on_toggle)
        self.edit.textEdited.connect(lambda _: self.changed.emit())
        self.edit.editingFinished.connect(self._finish)
        self.remove_btn.clicked.connect(lambda: self.removeRequested.emit(self))
        self._apply_done(task.done)

    def enterEvent(self, e):
        self.remove_btn.setVisible(True)

    def leaveEvent(self, e):
        self.remove_btn.setVisible(False)

    def _on_toggle(self, done: bool) -> None:
        self._apply_done(done)
        self.changed.emit()

    def _finish(self) -> None:
        if not self.edit.text().strip():
            self.removeRequested.emit(self)

    def _apply_done(self, done: bool) -> None:
        f = self.edit.font()
        f.setStrikeOut(done)
        self.edit.setFont(f)
        self.edit.setProperty("done", done)
        repolish(self.edit)

    def set_accent(self, color: str) -> None:
        self.check.set_accent(color)

    def task(self) -> Task:
        return Task(self.edit.text(), self.check.isChecked())
