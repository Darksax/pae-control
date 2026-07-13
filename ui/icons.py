"""
icons.py — Carga íconos SVG (Lucide, licencia ISC — ver assets/icons/LICENSE.txt)
recoloreados al vuelo para el tema oscuro de la app.

Los SVG de Lucide usan stroke="currentColor" (pensado para heredar color de
CSS en un navegador) — QSvgRenderer no entiende esa herencia, así que se
reemplaza el texto directamente por el hex deseado antes de renderizar.
"""

import os
import sys
from PyQt6.QtCore import Qt, QByteArray
from PyQt6.QtGui import QIcon, QPixmap, QPainter
from PyQt6.QtSvg import QSvgRenderer

# En un build de PyInstaller, __file__ no apunta a una ruta útil para
# ubicar los assets bundleados — hay que resolver desde sys._MEIPASS
# (mismo patrón que BASE_DIR en main.py). Sin esto, los íconos cargan
# bien en `python3 main.py` pero salen vacíos en el .exe/.app compilado.
if getattr(sys, "frozen", False):
    _BASE_DIR = sys._MEIPASS
else:
    _BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_ICONS_DIR = os.path.join(_BASE_DIR, "assets", "icons")
_cache: dict = {}


def load_pixmap(name: str, color: str, size: int = 24) -> QPixmap:
    """Carga assets/icons/<name>.svg recoloreado como QPixmap cuadrado transparente.
    Un ícono faltante/corrupto devuelve un pixmap transparente en vez de
    reventar la pantalla que lo pidió — mejor un ícono vacío que un crash."""
    key = (name, color, size)
    if key in _cache:
        return _cache[key]

    try:
        path = os.path.join(_ICONS_DIR, f"{name}.svg")
        with open(path, "r", encoding="utf-8") as f:
            svg = f.read()
        svg = svg.replace("currentColor", color)
        renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    except Exception:
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        _cache[key] = pixmap
        return pixmap

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    _cache[key] = pixmap
    return pixmap


def load_icon(name: str, color: str, size: int = 24) -> QIcon:
    return QIcon(load_pixmap(name, color, size))
