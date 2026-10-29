"""Запуск приложения, менеджер стикеров и значок в трее."""
from __future__ import annotations

import os
import sys

from PyQt6.QtCore import QObject, QPoint, QStandardPaths, QTimer
from PyQt6.QtGui import QColor, QFont, QGuiApplication, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (QApplication, QMenu, QMessageBox,
                             QSystemTrayIcon)

from .model import Note, Store, Task
from .sticky import StickyWindow
from .theme import FONT_FAMILIES, PALETTES


def app_icon() -> QIcon:
    pm = QPixmap(64, 64)
    pm.fill(QColor(0, 0, 0, 0))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QColor(0, 0, 0, 40))
    p.setBrush(QColor(PALETTES[0].bg))
    p.drawRoundedRect(6, 6, 52, 52, 12, 12)
    p.setPen(QColor(229, 184, 0))
    for y in (24, 34, 44):
        p.drawLine(16, y, 48 if y != 44 else 34, y)
    p.end()
    return QIcon(pm)


class Manager(QObject):
    def __init__(self, store: Store):
        super().__init__()
        self.store = store
        self.windows: dict[str, StickyWindow] = {}
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(400)  # не пишем на диск при каждом символе
        self.save_timer.timeout.connect(self.save)

        notes = store.load() or [self._welcome()]
        for n in notes:
            self.open(n)
        self.tray = self._make_tray()

    @staticmethod
    def _welcome() -> Note:
        n = Note.new("yellow", 140, 120)
        n.title = "Добро пожаловать"
        n.tasks = [
            Task("Нажми на кружок, чтобы отметить задачу"),
            Task("Тяни стикер за верхнюю полосу"),
            Task("В меню ⋯ — цвет, тег и срок"),
        ]
        return n

    def open(self, note: Note) -> StickyWindow:
        # если монитор отключили, возвращаем стикер на видимое место
        if QGuiApplication.screenAt(QPoint(note.x + 40, note.y + 40)) is None:
            geo = QGuiApplication.primaryScreen().availableGeometry()
            note.x, note.y = geo.x() + 80, geo.y() + 80
        w = StickyWindow(note)
        w.changed.connect(self.save_timer.start)
        w.newRequested.connect(lambda w=w: self.new_note(near=w))
        w.deleteRequested.connect(self.delete)
        w.quitRequested.connect(self.quit)
        self.windows[note.id] = w
        w.show()
        return w

    def new_note(self, near: StickyWindow | None = None) -> None:
        color = PALETTES[len(self.windows) % len(PALETTES)].key
        if near is not None:
            x, y = near.x() + 36, near.y() + 36
        else:
            geo = QGuiApplication.primaryScreen().availableGeometry()
            x, y = geo.x() + 120, geo.y() + 120
        w = self.open(Note.new(color, x, y))
        w.title.setFocus()
        self.save()

    def delete(self, win: StickyWindow) -> None:
        note = win.note
        if note.title or note.tasks:
            ok = QMessageBox.question(
                win, "Удалить стикер?",
                f"«{note.title or 'Без названия'}» будет удалён без возможности восстановления.",
            )
            if ok != QMessageBox.StandardButton.Yes:
                return
        if len(self.windows) == 1:  # приложение не должно остаться без окон
            self.new_note()
        self.windows.pop(note.id, None)
        win.close()
        win.deleteLater()
        self.save()

    def show_all(self) -> None:
        for w in self.windows.values():
            w.show()
            w.raise_()
            w.activateWindow()

    def save(self) -> None:
        self.store.save([w.note for w in self.windows.values()])

    def quit(self) -> None:
        self.save()
        QApplication.quit()

    def _make_tray(self) -> QSystemTrayIcon | None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return None
        tray = QSystemTrayIcon(app_icon(), self)
        menu = QMenu()
        menu.addAction("Новый стикер", self.new_note)
        menu.addAction("Показать все", self.show_all)
        menu.addSeparator()
        menu.addAction("Выйти", self.quit)
        tray.setContextMenu(menu)
        tray.activated.connect(lambda _: self.show_all())
        tray.setToolTip("Стикеры")
        tray.show()
        # с треем закрытие всех окон не завершает приложение
        QApplication.setQuitOnLastWindowClosed(False)
        self._tray_menu = menu
        return tray


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("VirtualStickies")
    app.setApplicationDisplayName("Стикеры")
    app.setWindowIcon(app_icon())
    font = QFont()
    font.setFamilies(FONT_FAMILIES)
    font.setPointSize(10)
    app.setFont(font)

    data_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    manager = Manager(Store(os.path.join(data_dir, "notes.json")))
    app.aboutToQuit.connect(manager.save)
    return app.exec()
