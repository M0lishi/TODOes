import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QMenu, QSizeGrip
from PyQt6.QtTest import QTest

from stickies.app import Manager, app_icon
from stickies.model import Note, Store, Task
from stickies.sticky import StickyWindow
from stickies import startup

APP = QApplication.instance() or QApplication([])


class StickiesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(str(Path(self.temp.name) / 'notes.json'))
        self.windows = []

    def tearDown(self):
        for win in self.windows:
            win.close()
            win.deleteLater()
        APP.processEvents()
        self.temp.cleanup()

    def window(self, note=None):
        win = StickyWindow(note or Note.new())
        self.windows.append(win)
        win.show()
        APP.processEvents()
        return win

    def test_old_format_and_description_roundtrip(self):
        old = Note.from_dict({'id': 'old', 'tasks': [{'text': 'Old task', 'done': True}]})
        self.assertEqual(old.tasks[0].description, '')
        old.tasks[0].description = 'Details\nSecond line'
        old.collapsed = True
        self.store.save([old])
        loaded = self.store.load()[0]
        self.assertEqual(loaded.to_dict(), old.to_dict())

    def test_long_text_wraps_and_shrinks_with_width(self):
        note = Note.new()
        note.tasks = [Task('Long task text ' * 45)]
        win = self.window(note)
        row = win.rows[0]
        narrow_height = row.edit.height()
        self.assertGreater(narrow_height, 100)
        win.resize(1000, 700)
        APP.processEvents()
        self.assertLess(row.edit.height(), narrow_height)
        self.assertEqual(row.edit.text(), note.tasks[0].text)
        self.assertEqual(len(win.findChildren(QSizeGrip)), 2)

    def test_task_description_completion_and_delete(self):
        win = self.window()
        win.add.setText('Task')
        win.add.returnPressed.emit()
        row = win.rows[0]
        row.description_btn.click()
        row.description.setPlainText('Details\nMore details')
        APP.processEvents()
        block = row.description.document().firstBlock()
        content_height = 0
        while block.isValid():
            content_height += row.description.blockBoundingRect(block).height()
            block = block.next()
        self.assertGreaterEqual(row.description.viewport().height(), content_height)
        row.check.click()
        self.assertEqual(win.note.tasks, [Task('Task', True, 'Details\nMore details')])
        row.remove_btn.click()
        self.assertEqual(win.note.tasks, [])

    def test_collapse_preserves_geometry_and_persistence(self):
        note = Note.new()
        note.h = 650
        note.w = 800
        win = self.window(note)
        win.set_collapsed(True, animate=False)
        self.assertTrue(win.body.isHidden())
        self.assertLess(win.height(), 150)
        self.assertEqual(note.h, 650)
        self.assertEqual(note.w, 800)
        self.assertEqual(win.width(), 260)
        self.store.save([note])
        restored = self.window(self.store.load()[0])
        self.assertTrue(restored.note.collapsed)
        restored.set_collapsed(False, animate=False)
        self.assertEqual(restored.height(), 650)
        self.assertEqual(restored.width(), 800)
        self.assertFalse(restored.body.isHidden())

    def test_animated_collapse_and_hide(self):
        win = self.window()
        win.resize(650, 550)
        APP.processEvents()
        original = win.size()
        win.set_collapsed(True)
        QTest.qWait(250)
        self.assertLess(win.height(), 150)
        self.assertEqual(win.width(), 260)
        win.set_collapsed(False)
        QTest.qWait(250)
        self.assertEqual(win.size(), original)
        win.hide_animated()
        QTest.qWait(200)
        self.assertTrue(win.isHidden())
        win.show_animated()
        QTest.qWait(200)
        self.assertTrue(win.isVisible())

    def test_tray_menu_targets_and_refreshes_titles(self):
        with patch('stickies.app.QSystemTrayIcon.isSystemTrayAvailable', return_value=False):
            manager = Manager(self.store, start_in_tray=True)
        self.windows.extend(manager.windows.values())
        win = next(iter(manager.windows.values()))
        self.assertTrue(win.isVisible())  # no inaccessible tray-only startup
        win.title.setPlainText('Renamed')
        menu = QMenu()
        manager._fill_notes_menu(menu)
        self.assertEqual(menu.actions()[0].text(), 'Renamed')
        win.hide()
        menu.actions()[0].trigger()
        self.assertTrue(win.isVisible())
        manager.save()
        self.assertEqual(self.store.load()[0].title, 'Renamed')
        manager.save_timer.stop()

    def test_windows_autostart_registry_toggle(self):
        registry = MagicMock()
        registry.HKEY_CURRENT_USER = 1
        registry.REG_SZ = 1
        key = registry.CreateKey.return_value.__enter__.return_value
        with patch.object(startup, 'supported', return_value=True), patch.dict('sys.modules', {'winreg': registry}):
            startup.set_enabled(True)
            registry.SetValueEx.assert_called_once_with(key, startup.APP_NAME, 0, registry.REG_SZ, startup.command())
            startup.set_enabled(False)
            registry.DeleteValue.assert_called_once_with(key, startup.APP_NAME)
            registry.QueryValueEx.return_value = (startup.command(), registry.REG_SZ)
            self.assertTrue(startup.enabled())
            registry.QueryValueEx.side_effect = FileNotFoundError
            self.assertFalse(startup.enabled())

    def test_logo_and_startup_command(self):
        self.assertFalse(app_icon().isNull())
        self.assertIn('--tray', startup.command())
        with patch.object(startup.sys, 'frozen', True, create=True), patch.object(startup.sys, 'executable', r'C:\Program Files\TODOes\TODOes.exe'):
            self.assertEqual(startup.command(), '"C:\\Program Files\\TODOes\\TODOes.exe" --tray')


if __name__ == '__main__':
    unittest.main()
