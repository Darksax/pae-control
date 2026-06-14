"""
main.py — Punto de entrada PAE Control.
"""

import sys
import os

# ── 1. Resolver BASE_DIR ────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, BASE_DIR)

# ── 2. Parches locales — ANTES de cualquier import de la app ────────────────
# Los .py en ~/pae_control/patches/ sobreescriben los módulos del bundle.
try:
    from updater import apply_local_patches
    apply_local_patches()
except Exception:
    pass  # Si updater falla no impide el inicio

# ── 3. Imports normales de la app ───────────────────────────────────────────
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore    import QTimer

import db
from ui.theme       import apply_theme
from ui.main_window import MainWindow
import patchnotes as pn


def _maybe_show_startup(window: MainWindow):
    """
    Muestra el diálogo de novedades si la versión actual es distinta
    a la última vista por el usuario.
    Se llama via QTimer para no bloquear el render de la ventana.
    """
    last_seen = db.get_config("last_seen_version", "")
    if last_seen == pn.VERSION:
        return

    # Importación local para no cargar Qt widgets antes de QApplication
    from ui.startup_screen import StartupDialog
    dlg = StartupDialog(window)
    dlg.exec()

    # Guardar versión para no mostrar de nuevo hasta el próximo update
    db.set_config("last_seen_version", pn.VERSION)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("PAE Control")
    app.setApplicationVersion(pn.VERSION)
    app.setOrganizationName("Liceo Bicentenario")

    apply_theme(app)
    db.init_db()

    window = MainWindow()
    window.show()

    # Mostrar novedades 600ms después del render (no bloquea la carga)
    QTimer.singleShot(600, lambda: _maybe_show_startup(window))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
