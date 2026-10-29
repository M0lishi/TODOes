"""Generate the Windows icon from the shared vector logo."""
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtSvg import QSvgRenderer

root = Path(__file__).resolve().parent.parent
renderer = QSvgRenderer(str(root / 'assets' / 'todoes.svg'))
if not renderer.isValid():
    raise RuntimeError('Invalid logo')
image = QImage(256, 256, QImage.Format.Format_ARGB32)
image.fill(Qt.GlobalColor.transparent)
painter = QPainter(image)
renderer.render(painter)
painter.end()
if not image.save(str(root / 'assets' / 'todoes.ico')):
    raise RuntimeError('Unable to write Windows icon')
