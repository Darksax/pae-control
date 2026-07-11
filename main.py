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

# ── 1b. Diagnóstico — ANTES de importar PyQt6 ───────────────────────────────
# faulthandler captura crashes nativos (p.ej. durante el propio import de Qt).
# Con --debug o PAE_DEBUG=1 activa registro completo en ~/pae_control/logs/.
import debug_mode
from debug_mode import logger
debug_mode.init()

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
from PyQt6.QtGui     import QIcon

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
    logger.info("Creando QApplication...")
    app = QApplication(sys.argv)
    app.setApplicationName("PAE Control")
    app.setApplicationVersion(pn.VERSION)
    app.setOrganizationName("Liceo Bicentenario")
    debug_mode.attach_qt()

    # ── Ícono de la aplicación (ventana + barra de tareas) ─────────────────
    _ico_path = os.path.join(BASE_DIR, "assets", "AppIcon.ico")
    if os.path.exists(_ico_path):
        app.setWindowIcon(QIcon(_ico_path))

    logger.info("Aplicando tema...")
    apply_theme(app)

    logger.info("Inicializando base de datos...")
    db.init_db()

    # ── Login con PIN ───────────────────────────────────────────────────────
    logger.info("Mostrando pantalla de login...")
    from ui.login_screen import LoginScreen
    from PyQt6.QtWidgets import QDialog
    login = LoginScreen()
    if login.exec() != QDialog.DialogCode.Accepted:
        logger.info("Login cancelado — saliendo")
        sys.exit(0)
    logger.info(f"Login exitoso: {__import__('session').nombre()} ({__import__('session').rol()})")

    logger.info("Creando ventana principal...")
    window = MainWindow()
    window.show()
    logger.info("Ventana visible — entrando al event loop")

    # Mostrar novedades 600ms después del render (no bloquea la carga)
    QTimer.singleShot(600, lambda: _maybe_show_startup(window))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
