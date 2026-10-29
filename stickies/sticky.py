"""Окно одного стикера."""
from __future__ import annotations

from datetime import date, timedelta

from PyQt6.QtCore import QDate, QSize, Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QKeySequence, QPixmap, QPainter, QShortcut
from PyQt6.QtWidgets import (QCalendarWidget, QDialog, QFrame,
                             QGraphicsDropShadowEffect, QHBoxLayout,
                             QInputDialog, QLabel, QLineEdit, QMenu,
                             QPushButton, QScrollArea, QSizeGrip, QSizePolicy, QVBoxLayout,
                             QWidget)

from .model import Note, Task
from .theme import BY_KEY, INK, INK_SECONDARY, IOS_ORANGE, IOS_RED, PALETTES
from .widgets import GrowingTextEdit, IconButton, TaskRow, repolish

MONTHS = ["янв", "фев", "мар", "апр", "мая", "июн",
          "июл", "авг", "сен", "окт", "ноя", "дек"]
MARGIN = 16  # поле вокруг карточки под тень


def color_icon(hex_color: str) -> QIcon:
    pm = QPixmap(16, 16)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(hex_color))
    p.setPen(QColor(0, 0, 0, 40))
    p.drawEllipse(1, 1, 14, 14)
    p.end()
    return QIcon(pm)


class DragHeader(QWidget):
    """Верхняя полоса, за которую стикер перетаскивается."""

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            handle = self.window().windowHandle()
            if handle:
                handle.startSystemMove()


class DeadlineDialog(QDialog):
    def __init__(self, current: date | None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Срок")
        self.removed = False
        lay = QVBoxLayout(self)
        self.cal = QCalendarWidget()
        self.cal.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
        self.cal.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.cal.setSelectedDate(QDate(current.year, current.month, current.day)
                                 if current else QDate.currentDate())
        lay.addWidget(self.cal)
        row = QHBoxLayout()
        clear = QPushButton("Убрать срок")
        cancel = QPushButton("Отмена")
        ok = QPushButton("Готово")
        ok.setDefault(True)
        clear.setEnabled(current is not None)
        row.addWidget(clear)
        row.addStretch()
        row.addWidget(cancel)
        row.addWidget(ok)
        lay.addLayout(row)
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        clear.clicked.connect(self._clear)

    def _clear(self):
        self.removed = True
        self.accept()

    def selected(self) -> date:
        d = self.cal.selectedDate()
        return date(d.year(), d.month(), d.day())


class StickyWindow(QWidget):
    changed = pyqtSignal()
    newRequested = pyqtSignal()
    deleteRequested = pyqtSignal(object)
    quitRequested = pyqtSignal()
    hideRequested = pyqtSignal(object)

    def __init__(self, note: Note):
        flags = Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
        if note.pinned:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        super().__init__(None, flags)
        self.note = note
        self.rows: list[TaskRow] = []
        self._animating = False
        self._expanded_height = note.h
        self._restoring = True
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle(note.title or "Стикер")
        self.setMinimumSize(300, 230)
        self._build()
        self._apply_color()
        for t in note.tasks:
            self._add_row(t)
        self._refresh_chips()
        self.resize(note.w, note.h)
        self.move(note.x, note.y)
        self._restoring = False
        if note.collapsed:
            self.set_collapsed(True, animate=False)

        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.newRequested.emit)
        QShortcut(QKeySequence(QKeySequence.StandardKey.Quit), self,
                  activated=self.quitRequested.emit)

    def show_animated(self):
        if hasattr(self, "_fade"):
            self._fade.stop()
        self.setWindowOpacity(0.0)
        self.show()
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(140)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.start()

    def hide_animated(self, after=None):
        if hasattr(self, "_fade"):
            self._fade.stop()
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(140)
        self._fade.setStartValue(self.windowOpacity())
        self._fade.setEndValue(0.0)
        def finish():
            self.hide()
            self.setWindowOpacity(1.0)
            if after:
                after()
        self._fade.finished.connect(finish)
        self._fade.start()

    # ---------- построение интерфейса ----------
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(MARGIN, MARGIN, MARGIN, MARGIN)

        self.card = QFrame()
        self.card.setObjectName("card")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 70))
        self.card.setGraphicsEffect(shadow)
        root.addWidget(self.card)

        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(16, 6, 16, 12)
        lay.setSpacing(6)

        # шапка
        self.collapsed_title = QLabel(self.note.title or "Стикер")
        self.collapsed_title.setObjectName("collapsedTitle")
        self.collapsed_title.setWordWrap(False)
        self.collapsed_title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.collapsed_title.setToolTip(self.note.title or "Стикер")
        self.collapsed_title.setVisible(False)
        lay.addWidget(self.collapsed_title)
        self.header = DragHeader()
        self.header.setFixedHeight(34)
        hl = QHBoxLayout(self.header)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(2)
        new_btn = IconButton("plus", "Новый стикер (Ctrl+N)")
        self.pin_btn = IconButton("pin", "Закрепить поверх окон", checkable=True)
        self.pin_btn.setChecked(self.note.pinned)
        more_btn = IconButton("dots", "Ещё")
        self.collapse_btn = QPushButton("−")
        self.collapse_btn.setToolTip("Свернуть до шапки / развернуть")
        self.collapse_btn.setFixedSize(26, 28)
        self.collapse_btn.clicked.connect(lambda: self.set_collapsed(not self.note.collapsed))
        self.color_btn = QPushButton("●")
        self.color_btn.setToolTip("Цвет стикера")
        self.color_btn.setFixedSize(26, 28)
        self.color_btn.clicked.connect(self._show_colors)
        self.delete_btn = QPushButton("⌫")
        self.delete_btn.setToolTip("Удалить стикер")
        self.delete_btn.setFixedSize(26, 28)
        self.delete_btn.clicked.connect(lambda: self.deleteRequested.emit(self))
        self.hide_btn = IconButton("close", "Скрыть стикер в трей")
        self.hide_btn.clicked.connect(lambda: self.hideRequested.emit(self))
        hl.addWidget(new_btn)
        hl.addStretch()
        hl.addWidget(self.color_btn)
        hl.addWidget(self.collapse_btn)
        hl.addWidget(self.delete_btn)
        hl.addWidget(self.hide_btn)
        hl.addWidget(self.pin_btn)
        hl.addWidget(more_btn)
        lay.addWidget(self.header)
        new_btn.clicked.connect(self.newRequested.emit)
        self.pin_btn.toggled.connect(self._set_pinned)
        more_btn.clicked.connect(lambda: self._show_menu(more_btn))

        self.body = QWidget()
        lay.addWidget(self.body, 1)
        lay = QVBoxLayout(self.body)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        # заголовок
        self.title = GrowingTextEdit(self.note.title)
        self.title.setObjectName("title")
        self.title.setPlaceholderText("Заголовок")
        self.title.textChanged.connect(lambda: self._on_title(self.title.text()))
        lay.addWidget(self.title)

        # список задач
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.viewport().setAutoFillBackground(False)
        container = QWidget()
        container.setObjectName("list")
        container.setAutoFillBackground(False)
        self.list_layout = QVBoxLayout(container)
        self.list_layout.setContentsMargins(0, 2, 0, 2)
        self.list_layout.setSpacing(0)
        self.list_layout.addStretch()
        self.scroll.setWidget(container)
        lay.addWidget(self.scroll, 1)

        # поле добавления
        self.add = QLineEdit()
        self.add.setObjectName("add")
        self.add.setPlaceholderText("Новая задача")
        self.add.setFixedHeight(34)
        self.add.returnPressed.connect(self._add_from_field)
        lay.addWidget(self.add)

        # подвал
        foot = QHBoxLayout()
        foot.setContentsMargins(0, 2, 0, 0)
        foot.setSpacing(6)
        self.tag_chip = QPushButton()
        self.tag_chip.setObjectName("chip")
        self.tag_chip.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tag_chip.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.tag_chip.clicked.connect(self._edit_tag)
        self.due_chip = QPushButton()
        self.due_chip.setObjectName("chip")
        self.due_chip.setCursor(Qt.CursorShape.PointingHandCursor)
        self.due_chip.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.due_chip.clicked.connect(self._edit_deadline)
        foot.addWidget(QSizeGrip(self.card), 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft)
        foot.addWidget(self.tag_chip)
        foot.addWidget(self.due_chip)
        foot.addStretch()
        foot.addWidget(QSizeGrip(self.card), 0,
                       Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
        lay.addLayout(foot)

    def _qss(self) -> str:
        pal = BY_KEY.get(self.note.color, PALETTES[0])
        return f"""
        #card {{ background: {pal.bg}; border-radius: 18px;
                 border: 1px solid rgba(0, 0, 0, 6%); }}
        QPushButton {{ background: transparent; border: none; }}
        QPushButton:hover {{ background: rgba(255,255,255,70%); border-radius: 6px; }}
        QLineEdit {{ selection-background-color: {pal.accent}; }}
        #title {{ background: transparent; border: none; color: {INK};
                  font-size: 21px; font-weight: 700; padding: 2px 0; }}
        #task {{ background: transparent; border: none; color: {INK};
                 font-size: 15px; }}
        #description {{ background: rgba(255,255,255,35%); border: none; border-radius: 6px; color: {INK_SECONDARY}; font-size: 13px; padding: 4px; }}
        #task[done="true"] {{ color: rgba(60, 60, 67, 45%); }}
        #add {{ background: rgba(255, 255, 255, 55%); border: none;
                border-radius: 10px; padding: 0 12px; color: {INK};
                font-size: 14px; }}
        #add:focus {{ background: rgba(255, 255, 255, 85%); }}
        #chip {{ background: rgba(255, 255, 255, 60%); border: none;
                 border-radius: 12px; padding: 5px 11px; color: {INK_SECONDARY};
                 font-size: 12px; font-weight: 600; }}
        #chip:hover {{ background: rgba(255, 255, 255, 88%); }}
        #chip[tone="empty"] {{ font-weight: 500; }}
        #chip[tone="warn"] {{ color: {IOS_ORANGE}; }}
        #chip[tone="danger"] {{ color: {IOS_RED}; }}
        QScrollArea, #list {{ background: transparent; border: none; }}
        QScrollBar:vertical {{ width: 6px; background: transparent; margin: 2px; }}
        QScrollBar::handle:vertical {{ background: rgba(0, 0, 0, 22%);
                                       border-radius: 3px; min-height: 24px; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
        """

    def _apply_color(self) -> None:
        self.setStyleSheet(self._qss())
        accent = BY_KEY.get(self.note.color, PALETTES[0]).accent
        for r in self.rows:
            r.set_accent(accent)

    # ---------- задачи ----------
    def _accent(self) -> str:
        return BY_KEY.get(self.note.color, PALETTES[0]).accent

    def _add_row(self, task: Task) -> TaskRow:
        row = TaskRow(task, self._accent())
        row.changed.connect(self._sync)
        row.removeRequested.connect(self._remove_row)
        self.list_layout.insertWidget(self.list_layout.count() - 1, row)
        self.rows.append(row)
        return row

    def _add_from_field(self) -> None:
        text = self.add.text().strip()
        if not text:
            return
        self._add_row(Task(text))
        self.add.clear()
        self._sync()
        bar = self.scroll.verticalScrollBar()
        QTimer.singleShot(0, lambda: bar.setValue(bar.maximum()))

    def _remove_row(self, row: TaskRow) -> None:
        if row not in self.rows:
            return
        self.rows.remove(row)
        row.setParent(None)
        row.deleteLater()
        self._sync()

    def _clear_done(self) -> None:
        for row in [r for r in self.rows if r.check.isChecked()]:
            self._remove_row(row)

    def _sync(self) -> None:
        self.note.tasks = [r.task() for r in self.rows]
        self.changed.emit()

    def _on_title(self, text: str) -> None:
        self.note.title = text
        self.collapsed_title.setText(text or "Стикер")
        self.collapsed_title.setToolTip(text or "Стикер")
        self.setWindowTitle(text or "Стикер")
        self.changed.emit()

    # ---------- чипы: тег и срок ----------
    def _refresh_chips(self) -> None:
        if self.note.tag:
            self.tag_chip.setText(f"#{self.note.tag}")
            self.tag_chip.setProperty("tone", "normal")
        else:
            self.tag_chip.setText("+ Тег")
            self.tag_chip.setProperty("tone", "empty")

        tone, text = "empty", "+ Срок"
        if self.note.deadline:
            try:
                d = date.fromisoformat(self.note.deadline)
                today = date.today()
                label = f"{d.day} {MONTHS[d.month - 1]}"
                if d < today:
                    tone, text = "danger", label
                elif d == today:
                    tone, text = "warn", "сегодня"
                elif d == today + timedelta(days=1):
                    tone, text = "normal", "завтра"
                else:
                    tone, text = "normal", f"до {label}"
            except ValueError:
                self.note.deadline = None
        self.due_chip.setText(text)
        self.due_chip.setToolTip("Просрочено" if tone == "danger" else "Изменить срок")
        self.due_chip.setProperty("tone", tone)
        repolish(self.tag_chip)
        repolish(self.due_chip)

    def _edit_tag(self) -> None:
        text, ok = QInputDialog.getText(self, "Тег", "Например: учёба, git, быт",
                                        text=self.note.tag)
        if ok:
            self.note.tag = text.strip().lstrip("#")
            self._refresh_chips()
            self.changed.emit()

    def _edit_deadline(self) -> None:
        current = None
        if self.note.deadline:
            try:
                current = date.fromisoformat(self.note.deadline)
            except ValueError:
                pass
        dlg = DeadlineDialog(current, self)
        if dlg.exec():
            self.note.deadline = None if dlg.removed else dlg.selected().isoformat()
            self._refresh_chips()
            self.changed.emit()

    # ---------- меню, цвет, закрепление ----------
    def _show_colors(self):
        menu = QMenu(self)
        for pal in PALETTES:
            action = menu.addAction(color_icon(pal.bg), pal.title)
            action.triggered.connect(lambda _=False, key=pal.key: self._set_color(key))
        menu.exec(self.color_btn.mapToGlobal(self.color_btn.rect().bottomLeft()))

    def set_collapsed(self, collapsed: bool, animate: bool = True):
        if hasattr(self, "_height_animation"):
            self._height_animation.stop()
        if collapsed and not self.note.collapsed:
            self._expanded_height = self.height()
        self._animating = True
        self.note.collapsed = collapsed
        self.body.setVisible(not collapsed)
        self.collapsed_title.setVisible(collapsed)
        self.collapse_btn.setText("+" if collapsed else "−")
        self.collapse_btn.setToolTip((self.note.title or "Стикер") + " — развернуть" if collapsed else "Свернуть до шапки")
        self.setMinimumHeight(104 if collapsed else 230)
        target = 104 if collapsed else self._expanded_height
        if animate and self.isVisible():
            self._height_animation = QPropertyAnimation(self, b"size", self)
            self._height_animation.setDuration(180)
            self._height_animation.setStartValue(self.size())
            self._height_animation.setEndValue(QSize(self.width(), target))
            self._height_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
            self._height_animation.finished.connect(self._animation_done)
            self._height_animation.start()
        else:
            self.resize(self.width(), target)
            self._animation_done()
        self.changed.emit()

    def _animation_done(self):
        self._animating = False

    def _show_menu(self, anchor: QWidget) -> None:
        menu = QMenu(self)
        menu.addAction("Тег…", self._edit_tag)
        menu.addAction("Срок…", self._edit_deadline)
        menu.addSeparator()
        clear = menu.addAction("Убрать выполненные", self._clear_done)
        clear.setEnabled(any(r.check.isChecked() for r in self.rows))
        menu.addSeparator()
        menu.addAction("Выйти из приложения", self.quitRequested.emit)
        menu.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))

    def _set_color(self, key: str) -> None:
        self.note.color = key
        self._apply_color()
        self.changed.emit()

    def _set_pinned(self, pinned: bool) -> None:
        self.note.pinned = pinned
        geo = self.geometry()
        was_visible = self.isVisible()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, pinned)
        self.setGeometry(geo)
        if was_visible:
            self.show()  # смена флагов скрывает окно, возвращаем его
        self.changed.emit()

    # ---------- геометрия ----------
    def moveEvent(self, e):
        self.note.x, self.note.y = self.x(), self.y()
        self.changed.emit()
        super().moveEvent(e)

    def resizeEvent(self, e):
        self.note.w = self.width()
        if not self.note.collapsed and not self._animating and not self._restoring:
            self.note.h = self.height()
            self._expanded_height = self.height()
        self.changed.emit()
        super().resizeEvent(e)
