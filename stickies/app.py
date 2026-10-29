"""Запуск приложения, менеджер стикеров и значок в трее."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from PyQt6.QtSvg import QSvgRenderer

from PyQt6.QtCore import QObject, QPoint, QStandardPaths, QTimer, Qt
from PyQt6.QtGui import QColor, QFont, QGuiApplication, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (QApplication, QMenu, QMessageBox,
                             QSystemTrayIcon)

from . import startup
from .docking import compact_slot
from .model import Note, Store, Task
from .sticky import StickyWindow
from .theme import FONT_FAMILIES, PALETTES


def app_icon() -> QIcon:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    renderer = QSvgRenderer(str(root / "assets" / "todoes.svg"))
    pm = QPixmap(64, 64)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    renderer.render(painter)
    painter.end()
    return QIcon(pm)


class Manager(QObject):
    def __init__(self, store: Store, start_in_tray: bool = False):
        super().__init__()
        self.store = store
        self.start_in_tray = start_in_tray and QSystemTrayIcon.isSystemTrayAvailable()
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
            Task("Кнопка ≡ у задачи открывает описание"),
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
        w.hideRequested.connect(self.hide_note)
        self.windows[note.id] = w
        w.compact_target_provider = lambda: self._compact_target(w)
        if note.collapsed:
            w.set_collapsed(True, animate=False)
        if not self.start_in_tray:
            w.show_animated()
        return w

    def _compact_target(self, win):
        occupied = []
        for other in self.windows.values():
            if other is win or not other.note.collapsed or other.screen() != win.screen():
                continue
            occupied.append(other._dock_target if other._animating and other._dock_target is not None
                            else other.geometry())
        return compact_slot(win.screen().availableGeometry(), occupied)

    def new_note(self, near: StickyWindow | None = None) -> None:
        color = PALETTES[len(self.windows) % len(PALETTES)].key
        if near is not None:
            x, y = near.x() + 36, near.y() + 36
        else:
            geo = QGuiApplication.primaryScreen().availableGeometry()
            x, y = geo.x() + 120, geo.y() + 120
        w = self.open(Note.new(color, x, y))
        w.show_animated()
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
        win.hide_animated(win.deleteLater)
        self.save()

    def hide_note(self, win: StickyWindow) -> None:
        if self.tray is None:
            win.showMinimized()
        else:
            win.hide_animated()
        self.save()

    def show_note(self, win: StickyWindow) -> None:
        win.showNormal()
        win.show_animated()
        win.raise_()
        win.activateWindow()

    def show_all(self) -> None:
        for w in self.windows.values():
            self.show_note(w)

    def save(self) -> None:
        self.store.save([w.note for w in self.windows.values()])

    def quit(self) -> None:
        self.save()
        QApplication.quit()

    def _fill_notes_menu(self, menu: QMenu):
        menu.clear()
        for win in self.windows.values():
            action = menu.addAction(win.note.title.strip() or "Без названия")
            action.triggered.connect(lambda _=False, w=win: self.show_note(w))

    def _set_startup(self, action, checked):
        try:
            startup.set_enabled(checked)
        except OSError as error:
            action.setChecked(startup.enabled())
            QMessageBox.warning(None, "Автозапуск", str(error))

    def _make_tray(self) -> QSystemTrayIcon | None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return None
        tray = QSystemTrayIcon(app_icon(), self)
        menu = QMenu()
        menu.addAction("Новый стикер", self.new_note)
        menu.addAction("Показать все", self.show_all)
        notes_menu = menu.addMenu("Стикеры")
        notes_menu.aboutToShow.connect(lambda: self._fill_notes_menu(notes_menu))
        if startup.supported():
            auto = menu.addAction("Запускать с Windows (в трей)")
            auto.setCheckable(True)
            auto.setChecked(startup.enabled())
            auto.triggered.connect(lambda checked: self._set_startup(auto, checked))
        menu.addSeparator()
        menu.addAction("Выйти", self.quit)
        tray.setContextMenu(menu)
        tray.activated.connect(
            lambda reason: self.show_all()
            if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None
        )
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
    manager = Manager(Store(os.path.join(data_dir, "notes.json")), start_in_tray="--tray" in sys.argv)
    app.aboutToQuit.connect(manager.save)
    return app.exec()
