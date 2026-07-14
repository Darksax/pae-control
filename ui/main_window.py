"""
main_window.py — Ventana principal MiAppoderado 0.9 Alpha
macOS Sonoma dark · Liceo Bicentenario palette
"""

from datetime import date
import threading

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QFrame, QDialog, QDialogButtonBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QSizePolicy, QScrollArea,
    QSpacerItem, QPushButton, QComboBox, QTextEdit,
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QColor, QPixmap, QPainter

from ui.theme   import C, sound, apply_theme
from ui.widgets import NavItem, AnimatedStack, HDivider, AButton

from ui.scan_screen         import ScanScreen
from ui.students_screen     import StudentsScreen
from ui.reports_screen      import ReportsScreen
from ui.quotas_screen       import QuotasScreen
from ui.inspectoria_screen   import InspectoriaScreen
from ui.config_screen       import ConfigScreen
from ui.import_screen       import ImportScreen
from ui.sync_screen         import SyncScreen
from ui.assistant_widget    import AssistantOverlay

import db
import utils
import session



# ── Nav config: (key, icon, label, screen_class, roles_permitidos)
# pae         → Escaneo, Cupos, Estudiantes (solo RSH)
# inspectoria → Inspectoría (atrasos/pases/licencias), Estudiantes (nombre/curso/tel, sin RSH)
# admin       → todo
_ALL_NAV = [
    ("scan",        "scan-line",     "Escaneo",           ScanScreen,         ["pae", "admin"]),
    ("inspectoria", "shield-check",  "Inspectoría",       InspectoriaScreen,  ["inspectoria", "admin"]),
    ("students",    "users",        "Estudiantes",       StudentsScreen,     ["pae", "inspectoria", "admin"]),
    ("quotas",      "calendar-days", "Cupos por día",     QuotasScreen,       ["pae", "admin"]),
    ("reports",     "chart-column",  "Reportes",          ReportsScreen,      ["admin", "pae", "inspectoria"]),
    ("import",      "upload",        "Importar",          ImportScreen,       ["admin"]),
    ("sync",        "refresh-cw",    "Sync Supabase",     SyncScreen,         ["admin"]),
    ("config",      "settings",      "Configuración",     ConfigScreen,       ["admin"]),
]


def _nav_for_rol(rol: str) -> list:
    return [item for item in _ALL_NAV if rol in item[4]]


NAV_ITEMS = _ALL_NAV  # compatibilidad


class Sidebar(QFrame):
    """
    Left sidebar: logo block + nav items + version footer.
    Fixed width 220px.
    """

    def __init__(self, on_nav, nav_items=None, parent=None):
        super().__init__(parent)
        self._on_nav   = on_nav
        self._items    = {}
        self._current  = None
        self._nav_items = nav_items or _ALL_NAV

        self.setFixedWidth(220)
        self.setStyleSheet(
            f"background: {C.SIDEBAR_BG}; "
            f"border-right: 1px solid {C.BORDER};"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 0, 10, 0)
        root.setSpacing(0)

        # ── Logo block ──────────────────────────────
        logo_block = QWidget()
        logo_block.setFixedHeight(96)
        logo_block.setStyleSheet("background: transparent;")
        logo_lay = QHBoxLayout(logo_block)
        logo_lay.setContentsMargins(8, 12, 8, 10)
        logo_lay.setSpacing(10)

        # Escudo — carga desde assets/escudo.png si existe
        import os as _os
        _escudo_path = _os.path.join(
            _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
            "assets", "escudo.png"
        )
        if _os.path.exists(_escudo_path):
            escudo_lbl = QLabel()
            pix = QPixmap(_escudo_path).scaled(
                56, 64,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            escudo_lbl.setPixmap(pix)
            escudo_lbl.setFixedSize(56, 64)
            escudo_lbl.setStyleSheet("background: transparent;")
            logo_lay.addWidget(escudo_lbl)

        # Texto
        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        text_col.setContentsMargins(0, 0, 0, 0)

        title = QLabel("MiAppoderado")
        title.setStyleSheet(
            f"font-size: 15px; font-weight: 700; color: {C.TEXT}; background: transparent;"
        )
        subtitle = QLabel("Liceo Bicentenario")
        subtitle.setStyleSheet(
            f"font-size: 9px; color: {C.TEXT2}; background: transparent;"
        )
        subtitle2 = QLabel("Héroes de la Concepción · Laja")
        subtitle2.setStyleSheet(
            f"font-size: 8px; color: {C.TEXT3}; background: transparent;"
        )
        text_col.addStretch()
        text_col.addWidget(title)
        text_col.addWidget(subtitle)
        text_col.addWidget(subtitle2)
        text_col.addStretch()

        logo_lay.addLayout(text_col, stretch=1)
        root.addWidget(logo_block)

        root.addWidget(HDivider())
        root.addSpacing(8)

        # ── Section label ────────────────────────────
        sec = QLabel("MENÚ")
        sec.setStyleSheet(
            f"font-size: 9px; font-weight: 700; letter-spacing: 1.2px; "
            f"color: {C.TEXT3}; padding: 0 6px; background: transparent;"
        )
        root.addWidget(sec)
        root.addSpacing(4)

        # ── Nav items (filtrados por rol) ───────────
        for key, icon, label, _, _roles in self._nav_items:
            item = NavItem(icon, label)
            item.mousePressEvent = self._make_handler(key, item)
            self._items[key] = item
            root.addWidget(item)
            root.addSpacing(2)

        root.addStretch()
        root.addWidget(HDivider())

        # ── Footer: versión desde patchnotes ────────
        import patchnotes as _pn
        footer = QLabel(f"v{_pn.VERSION}")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet(
            f"font-size: 10px; color: {C.TEXT3}; padding: 12px 0; background: transparent;"
        )
        root.addWidget(footer)

    def _make_handler(self, key, item):
        def handler(event):
            sound.click()
            self.set_active(key)
            self._on_nav(key)
        return handler

    def set_active(self, key: str):
        if self._current:
            self._items[self._current].set_active(False)
        self._items[key].set_active(True)
        self._current = key


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(
            db.get_config("nombre_establecimiento", "MiAppoderado") + " — MiAppoderado"
        )
        self.setMinimumSize(1160, 700)
        self.resize(1280, 760)
        # Filtrar nav según rol del usuario autenticado
        self._active_nav = _nav_for_rol(session.rol())
        self._build_ui()
        self._check_alerta_semana()
        # Check remoto de updates: 3 segundos después del render
        QTimer.singleShot(3000, self._start_update_check)
        # WhatsApp: reintentar mensajes pendientes cada 60s
        import whatsapp as _wa
        self._wa_retry_timer = _wa.iniciar_retry_timer(60_000)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top toolbar ──────────────────────────────
        toolbar = self._build_toolbar()
        root.addWidget(toolbar)

        # Toolbar bottom border
        tb_sep = QFrame()
        tb_sep.setFixedHeight(1)
        tb_sep.setStyleSheet(f"background: {C.BORDER}; border: none;")
        root.addWidget(tb_sep)

        # ── Main area (sidebar + content) ───────────
        content_row = QWidget()
        content_row.setStyleSheet(f"background: {C.BG};")
        row_lay = QHBoxLayout(content_row)
        row_lay.setContentsMargins(0, 0, 0, 0)
        row_lay.setSpacing(0)

        # ── Sidebar ──────────────────────────────────
        self.sidebar = Sidebar(on_nav=self._nav, nav_items=self._active_nav)
        row_lay.addWidget(self.sidebar)

        # ── Thin separator line ──────────────────────
        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"background: {C.BORDER}; border: none;")
        row_lay.addWidget(sep)

        # ── Screen stack ────────────────────────────
        self.stack = AnimatedStack()
        self._screens: dict[str, tuple[int, QWidget]] = {}

        for i, (key, _icon, _label, cls, _roles) in enumerate(self._active_nav):
            screen = cls()
            scroll = QScrollArea()
            scroll.setWidget(screen)
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setStyleSheet(f"background: {C.BG}; border: none;")
            self.stack.addWidget(scroll)
            self._screens[key] = (i, screen)

        row_lay.addWidget(self.stack, stretch=1)
        root.addWidget(content_row, stretch=1)

        # Default: primera pantalla disponible
        first_key = self._active_nav[0][0] if self._active_nav else None
        if first_key:
            self._nav(first_key)

        # ── Asistente IA (overlay flotante, sobre toda pantalla activa) ──
        # reposition() depende de central.width()/height(), que todavía no
        # tienen su valor final en este punto del __init__ (el primer layout
        # real ocurre recién cuando el event loop procesa el show() de la
        # ventana) — se difiere con singleShot(0, …) para que corra después.
        self._assistant = AssistantOverlay(central)
        self._assistant.show()
        QTimer.singleShot(0, self._assistant.reposition)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_assistant"):
            self._assistant.reposition()

    def _build_toolbar(self) -> QFrame:
        """Barra superior: clima · stats · reloj — sin accesos rápidos (están en el sidebar)."""
        bar = QFrame()
        bar.setFixedHeight(44)
        bar.setStyleSheet(f"background: {C.SURFACE}; border: none;")

        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(6)

        # ── Nombre del establecimiento (izquierda) ───
        nombre_est = db.get_config("nombre_establecimiento", "MiAppoderado")
        name_lbl = QLabel(nombre_est)
        name_lbl.setStyleSheet(
            f"font-size: 12px; font-weight: 700; color: {C.TEXT}; "
            f"background: transparent; padding: 0 4px;"
        )
        lay.addWidget(name_lbl)

        def _vsep():
            v = QFrame()
            v.setFixedSize(1, 22)
            v.setStyleSheet(f"background: {C.BORDER2}; border: none;")
            return v

        lay.addWidget(_vsep())
        lay.addSpacing(4)

        lay.addStretch()

        # ── Stats chips ──────────────────────────────
        self._tb_chip_pae = self._stat_chip_tb("—", "PAE activos", C.GREEN, icon_name="users")
        self._tb_chip_alm = self._stat_chip_tb("—", "Almuerzos hoy", C.BLUE, icon_name="utensils")
        lay.addWidget(self._tb_chip_pae)
        lay.addSpacing(6)
        lay.addWidget(self._tb_chip_alm)
        lay.addSpacing(8)

        lay.addWidget(_vsep())
        lay.addSpacing(6)

        # ── Chip usuario activo ──────────────────────
        _ROL_LABEL = {"admin": "Admin", "pae": "PAE", "inspectoria": "Inspectoría"}
        _user_nombre = session.nombre()
        _user_rol    = _ROL_LABEL.get(session.rol(), session.rol())
        self._user_btn = QPushButton(f"  {_user_nombre}  ·  {_user_rol}  ▾")
        self._user_btn.setFixedHeight(30)
        self._user_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.SURFACE2};
                color: {C.TEXT};
                border: 1px solid {C.BORDER};
                border-radius: 7px;
                padding: 0 10px;
                font-size: 11px; font-weight: 500;
            }}
            QPushButton:hover {{ background: {C.SURFACE3}; border-color: {C.BORDER2}; }}
        """)
        self._user_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._user_btn.clicked.connect(self._cambiar_usuario)
        lay.addWidget(self._user_btn)
        lay.addSpacing(4)

        lay.addWidget(_vsep())
        lay.addSpacing(6)

        # ── Botón Reportar Error (naranja, siempre visible) ──
        self._btn_bug = QPushButton("Reportar bug")
        self._btn_bug.setFixedHeight(30)
        self._btn_bug.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_bug.setStyleSheet(f"""
            QPushButton {{
                background: #d97706;
                color: #ffffff;
                border: none;
                border-radius: 7px;
                padding: 0 12px;
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 0.2px;
            }}
            QPushButton:hover  {{ background: #b45309; }}
            QPushButton:pressed {{ background: #92400e; }}
        """)
        self._btn_bug.clicked.connect(self._open_bug_report)
        lay.addWidget(self._btn_bug)
        lay.addSpacing(6)

        lay.addWidget(_vsep())
        lay.addSpacing(6)

        # ── Selector de período ──────────────────────
        self._period_btn = QPushButton()
        self._period_btn.setFixedHeight(30)
        self._period_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._period_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.SURFACE2};
                color: {C.TEXT2};
                border: 1px solid {C.BORDER};
                border-radius: 7px;
                padding: 0 10px;
                font-size: 11px; font-weight: 600;
            }}
            QPushButton:hover {{ background: {C.SURFACE3}; color: {C.TEXT}; border-color: {C.BORDER2}; }}
        """)
        self._period_btn.clicked.connect(self._open_period_selector)
        self._refresh_period_btn()
        lay.addWidget(self._period_btn)
        lay.addSpacing(4)

        lay.addWidget(_vsep())
        lay.addSpacing(6)

        # ── Botón Novedades ─────────────────────────
        self._btn_novedades = AButton("? Novedades", sound_type="click")
        self._btn_novedades.setFixedHeight(30)
        self._btn_novedades.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {C.TEXT3};
                border: 1px solid transparent;
                border-radius: 7px;
                padding: 0 10px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {C.SURFACE2};
                color: {C.TEXT};
                border-color: {C.BORDER};
            }}
        """)
        self._btn_novedades.clicked.connect(self._open_novedades)
        lay.addWidget(self._btn_novedades)
        lay.addSpacing(2)

        # ── Botón "buscar actualizaciones ahora" ─────
        # El chequeo automático (3s después de abrir) es silencioso si no
        # encuentra nada — sin este botón no había forma de pedirle a la app
        # que buscara de nuevo ni de saber si ya está en la última versión.
        from ui.icons import load_icon
        self._btn_check_update = AButton("", sound_type="click")
        self._btn_check_update.setIcon(load_icon("refresh-cw", C.TEXT3, 15))
        self._btn_check_update.setFixedSize(30, 30)
        self._btn_check_update.setToolTip("Buscar actualizaciones ahora")
        self._btn_check_update.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: 7px;
            }}
            QPushButton:hover {{
                background: {C.SURFACE2};
                border-color: {C.BORDER};
            }}
        """)
        self._btn_check_update.clicked.connect(self._manual_update_check)
        lay.addWidget(self._btn_check_update)
        lay.addSpacing(4)

        lay.addWidget(_vsep())
        lay.addSpacing(6)

        # ── Selector de tema (Oscuro/Claro/Pride Month) ──
        from ui.icons import load_icon
        self._theme_btn = QPushButton()
        self._theme_btn.setFixedSize(30, 30)
        self._theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._theme_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.SURFACE2};
                border: 1px solid {C.BORDER};
                border-radius: 7px;
            }}
            QPushButton:hover {{ background: {C.SURFACE3}; border-color: {C.BORDER2}; }}
        """)
        self._theme_btn.clicked.connect(self._open_theme_selector)
        self._refresh_theme_btn()
        lay.addWidget(self._theme_btn)
        lay.addSpacing(4)

        lay.addWidget(_vsep())
        lay.addSpacing(6)

        # ── Reloj en vivo ────────────────────────────
        self._clock_lbl = QLabel()
        self._clock_lbl.setStyleSheet(
            f"font-size: 12px; color: {C.TEXT3}; background: transparent; padding: 0 4px;"
        )
        self._clock_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self._clock_lbl)

        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._tick_clock)
        self._clock_timer.start(1000)
        self._tick_clock()

        # Timer de stats cada 15 s
        self._stats_timer = QTimer(self)
        self._stats_timer.timeout.connect(self._tick_stats)
        self._stats_timer.start(15000)
        self._tick_stats()

        return bar

    @staticmethod
    def _stat_chip_tb(value: str, label: str, color: str, icon_name: str = "") -> QFrame:
        chip = QFrame()
        chip.setStyleSheet(f"""
            QFrame {{
                background: transparent;
                border: 1px solid {color}44;
                border-radius: 8px;
                padding: 0 2px;
            }}
        """)
        lay = QHBoxLayout(chip)
        lay.setContentsMargins(8, 3, 8, 3)
        lay.setSpacing(5)

        if icon_name:
            from ui.icons import load_pixmap
            dot = QLabel()
            dot.setPixmap(load_pixmap(icon_name, color, 12))
        else:
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {color}; font-size: 7px;")
        dot.setStyleSheet(dot.styleSheet() + " background: transparent;")

        val = QLabel(value)
        val.setObjectName("chipval")
        val.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {color}; background: transparent;")

        lbl = QLabel(label)
        lbl.setObjectName("chiplbl")
        lbl.setStyleSheet(f"font-size: 11px; color: {C.TEXT3}; background: transparent;")

        lay.addWidget(dot)
        lay.addWidget(val)
        lay.addWidget(lbl)
        return chip

    def _tick_stats(self):
        def _set(chip, val_txt, lbl_txt=None):
            v = chip.findChild(QLabel, "chipval")
            if v:
                v.setText(val_txt)
            if lbl_txt is not None:
                l = chip.findChild(QLabel, "chiplbl")
                if l:
                    l.setText(lbl_txt)

        rol = session.rol()
        if rol == "inspectoria":
            try:
                info = db.get_pases_stats_hoy()
                _set(self._tb_chip_pae, str(info["pases_hoy"]),  "Pases hoy")
                _set(self._tb_chip_alm, str(info["sin_firmar"]), "Sin firmar")
            except Exception:
                pass
        else:
            try:
                import logic as _logic
                info = _logic.get_capacidad_info()
                _set(self._tb_chip_pae, str(info["activos"]),    "PAE activos")
                _set(self._tb_chip_alm, str(info["disponibles"]), "Almuerzos hoy")
            except Exception:
                pass

    def _tick_clock(self):
        from datetime import datetime
        now = datetime.now()
        # Lunes 9 jun · 14:35
        dias = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
        meses = ["ene", "feb", "mar", "abr", "may", "jun",
                 "jul", "ago", "sep", "oct", "nov", "dic"]
        txt = f"{dias[now.weekday()]} {now.day} {meses[now.month-1]}  ·  {now.strftime('%H:%M')}"
        self._clock_lbl.setText(txt)

    def _nav(self, key: str):
        idx, _ = self._screens[key]
        self.sidebar.set_active(key)
        self.stack.slide_to(idx)

    # ── Selector de período ───────────────────────────────────────────────────

    def _refresh_period_btn(self):
        """Actualiza el texto del botón de período."""
        p = session.viewing_period()
        activo = db.get_periodo_activo()
        suffix = " ★" if p == activo else ""
        self._period_btn.setText(f"📅 {p}{suffix}")

    def _open_period_selector(self):
        """Despliega menú de períodos disponibles."""
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        periodos = db.get_periodos_disponibles()
        activo = db.get_periodo_activo()
        viewing = session.viewing_period()

        for p in periodos:
            if len(p) == 4:
                label = f"📆 {p} (año completo)"
            else:
                yr, sem = p.split("-")
                label = f"📅 {p}"
                if p == activo:
                    label += "  ← activo"
            action = menu.addAction(label)
            if p == viewing:
                action.setCheckable(True)
                action.setChecked(True)
            action.triggered.connect(lambda _, periodo=p: self._set_viewing_period(periodo))

        menu.exec(self._period_btn.mapToGlobal(
            self._period_btn.rect().bottomLeft()
        ))

    # ─────────────────────────────────────────────
    #  Tema — Oscuro / Claro / Pride Month
    # ─────────────────────────────────────────────

    _THEME_ICONS = {"dark": "moon", "light": "sun", "pride": "sparkles"}

    def _refresh_theme_btn(self):
        from ui.icons import load_icon
        from ui.theme import current_theme, THEME_LABELS
        actual = current_theme()
        icon_name = self._THEME_ICONS.get(actual, "moon")
        self._theme_btn.setIcon(load_icon(icon_name, C.TEXT2, 16))
        self._theme_btn.setToolTip(f"Tema: {THEME_LABELS.get(actual, actual)}")

    def _open_theme_selector(self):
        from PyQt6.QtWidgets import QMenu
        from ui.theme import available_themes, current_theme, THEME_LABELS
        from ui.icons import load_icon

        menu = QMenu(self)
        actual = current_theme()
        for name in available_themes():
            action = menu.addAction(load_icon(self._THEME_ICONS.get(name, "moon"), C.TEXT2, 16),
                                     THEME_LABELS.get(name, name))
            action.setCheckable(True)
            action.setChecked(name == actual)
            action.triggered.connect(lambda _, n=name: self._switch_theme(n))

        menu.exec(self._theme_btn.mapToGlobal(
            self._theme_btn.rect().bottomLeft()
        ))

    def _switch_theme(self, name: str):
        """Guarda el tema elegido y reconstruye la ventana para aplicarlo —
        cambiar los colores de C no repinta por sí solo los widgets que ya
        fijaron su stylesheet con los valores viejos al construirse."""
        if name == db.get_config("theme_mode", "dark"):
            return
        db.set_config("theme_mode", name)

        from ui.theme import set_theme, apply_theme
        from PyQt6.QtWidgets import QApplication
        set_theme(name)
        apply_theme(QApplication.instance())

        self.close()
        new_win = MainWindow()
        new_win.show()
        self._new_win_ref = new_win   # evitar garbage collection

    def _set_viewing_period(self, periodo: str):
        """Cambia el período visualizado y refresca la pantalla activa."""
        session.set_viewing_period(periodo)
        self._refresh_period_btn()
        # Refrescar screen activo si tiene método refresh_period()
        current_widget = self.stack.currentWidget()
        if current_widget:
            inner = current_widget.widget() if hasattr(current_widget, "widget") else current_widget
            if hasattr(inner, "refresh_period"):
                inner.refresh_period()
            elif hasattr(inner, "showEvent"):
                # Fallback: simular re-apertura de pantalla
                from PyQt6.QtCore import QEvent
                inner.showEvent(QEvent(QEvent.Type.Show))

    # ─────────────────────────────────────────────
    #  Novedades / updates
    # ─────────────────────────────────────────────

    def _cambiar_usuario(self):
        """Cierra la sesión actual y muestra el login sin cerrar la app."""
        from PyQt6.QtWidgets import QMessageBox, QDialog
        from ui.login_screen import LoginScreen
        import session as _sess

        resp = QMessageBox.question(
            self, "Cambiar usuario",
            f"¿Cerrar sesión de {_sess.nombre()} y cambiar usuario?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
        )
        if resp != QMessageBox.StandardButton.Yes:
            return

        _sess.clear()
        self.hide()

        login = LoginScreen()
        if login.exec() == QDialog.DialogCode.Accepted:
            # Reiniciar la ventana principal con el nuevo rol
            import main as _main_mod
            self.close()
            new_win = MainWindow()
            new_win.show()
            self._new_win_ref = new_win   # evitar GC
        else:
            # Si cancela el login, volver a mostrarse con la sesión anterior
            _sess.set_user({"id": 0, "nombre": "Sin sesión", "rol": "pae"})
            self.show()

    def _open_novedades(self):
        from ui.startup_screen import StartupDialog
        dlg = StartupDialog(self)
        dlg.exec()

    # ── Bug reporter ─────────────────────────────────────────────────────────

    def _open_bug_report(self):
        """Abre el diálogo de reporte de bugs."""
        dlg = _BugReportDialog(self)
        dlg.exec()

    def _start_update_check(self):
        """
        Comprueba updates en background (no bloquea UI).
        Si hay nueva versión disponible, actualiza el botón y descarga parches.
        """
        try:
            import patchnotes as pn
            from updater import check_for_updates_async, download_patch_files

            def _on_found(manifest):
                new_ver = manifest.get("version", "?")
                # Volver al hilo principal para actualizar UI
                QTimer.singleShot(0, lambda: self._notify_update(manifest, new_ver))

            check_for_updates_async(
                manifest_url     = pn.GITHUB_MANIFEST,
                current_version  = pn.VERSION,
                on_update_found  = _on_found,
            )
        except Exception:
            pass

    def _manual_update_check(self):
        """Chequeo manual (botón de la toolbar) — siempre da feedback, a diferencia
        del chequeo silencioso automático al abrir."""
        from PyQt6.QtWidgets import QMessageBox

        self._btn_check_update.setEnabled(False)
        self._btn_check_update.setToolTip("Buscando…")

        # El timeout de 6s que updater._fetch_json() le pasa a urlopen NO
        # cubre la resolución DNS en todas las plataformas — en algunas
        # redes (típico de un firewall/proxy de colegio) el lookup de
        # github.com se puede colgar mucho más de 6s sin que urllib nunca
        # levante una excepción, dejando el botón pegado en "Buscando…"
        # para siempre (reportado en vivo: nunca termina). Este watchdog en
        # el hilo de UI acota la espera visible pase lo que pase del otro
        # lado, sin depender de que la librería de red respete su propio
        # timeout.
        resolved = {"done": False}

        def _reset_btn():
            self._btn_check_update.setEnabled(True)
            self._btn_check_update.setToolTip("Buscar actualizaciones ahora")

        def _watchdog():
            if resolved["done"]:
                return
            resolved["done"] = True
            _reset_btn()
            QMessageBox.warning(
                self, "Buscar actualizaciones",
                "La comprobación tardó demasiado y se canceló — probable "
                "problema de red (revisa el firewall/proxy si esto se repite)."
            )

        QTimer.singleShot(20000, _watchdog)

        try:
            import patchnotes as pn
            from updater import check_for_updates_async

            def _on_found(manifest):
                if resolved["done"]:
                    return
                resolved["done"] = True
                new_ver = manifest.get("version", "?")
                QTimer.singleShot(0, _reset_btn)
                QTimer.singleShot(0, lambda: self._notify_update(manifest, new_ver))

            def _on_no_update():
                if resolved["done"]:
                    return
                resolved["done"] = True
                QTimer.singleShot(0, _reset_btn)
                QTimer.singleShot(0, lambda: QMessageBox.information(
                    self, "Buscar actualizaciones",
                    f"Ya tienes la última versión instalada (v{pn.VERSION})."
                ))

            def _on_error(msg):
                if resolved["done"]:
                    return
                resolved["done"] = True
                QTimer.singleShot(0, _reset_btn)
                QTimer.singleShot(0, lambda: QMessageBox.warning(
                    self, "Buscar actualizaciones",
                    f"No se pudo comprobar si hay actualizaciones.\n\n{msg}"
                ))

            check_for_updates_async(
                manifest_url     = pn.GITHUB_MANIFEST,
                current_version  = pn.VERSION,
                on_update_found  = _on_found,
                on_no_update     = _on_no_update,
                on_error         = _on_error,
            )
        except Exception as exc:
            resolved["done"] = True
            self._btn_check_update.setEnabled(True)
            self._btn_check_update.setToolTip("Buscar actualizaciones ahora")
            QMessageBox.warning(self, "Buscar actualizaciones", str(exc))

    def _notify_update(self, manifest: dict, new_ver: str):
        """Update disponible: deja el botón como respaldo y además pregunta directo."""
        self._set_update_button(f"↓ v{new_ver} disponible", C.BLUE)
        self._btn_novedades.clicked.connect(
            lambda: self._download_update(manifest, new_ver)
        )

        from PyQt6.QtWidgets import QMessageBox
        notas = manifest.get("notes") or []
        detalle = "\n".join(f"• {n}" for n in notas[:6])
        resp = QMessageBox.question(
            self, "Actualización disponible",
            f"Hay una nueva versión disponible: v{new_ver}\n\n{detalle}\n\n"
            f"¿Instalarla ahora? La app se reiniciará al terminar.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if resp == QMessageBox.StandardButton.Yes:
            self._download_update(manifest, new_ver)

    def _set_update_button(self, text: str, color: str):
        self._btn_novedades.setText(text)
        self._btn_novedades.setStyleSheet(f"""
            QPushButton {{
                background: {color}22;
                color: {color};
                border: 1px solid {color}44;
                border-radius: 7px;
                padding: 0 10px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {color}33;
            }}
        """)

    def _download_update(self, manifest: dict, new_ver: str):
        from updater import download_patch_files

        try:
            self._btn_novedades.clicked.disconnect()
        except Exception:
            pass
        self._set_update_button("Descargando…", C.BLUE)
        self._btn_novedades.setEnabled(False)

        def _do_download():
            ok, errors = download_patch_files(manifest)
            QTimer.singleShot(0, lambda: self._after_download(ok, errors, new_ver, manifest))

        import threading
        t = threading.Thread(target=_do_download, daemon=True, name="pae-download")
        t.start()

    def _after_download(self, ok: bool, errors: list, new_ver: str, manifest: dict):
        if ok:
            self._set_update_button(f"✓ v{new_ver} — Reiniciar para aplicar", C.GREEN)
            self._btn_novedades.setEnabled(True)
            try:
                self._btn_novedades.clicked.disconnect()
            except Exception:
                pass
            self._btn_novedades.clicked.connect(self._restart_app)

            from PyQt6.QtWidgets import QMessageBox
            resp = QMessageBox.question(
                self, "Actualización instalada",
                f"v{new_ver} se descargó correctamente.\n\n¿Reiniciar la app ahora para aplicarla?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if resp == QMessageBox.StandardButton.Yes:
                self._restart_app()
        else:
            self._set_update_button("⚠ Error en descarga", C.RED)
            self._btn_novedades.setEnabled(True)

    def _restart_app(self):
        """Relanza el ejecutable (o `python main.py` en modo fuente) y cierra esta instancia."""
        import subprocess
        import sys
        import os
        from PyQt6.QtWidgets import QApplication
        try:
            if getattr(sys, "frozen", False):
                subprocess.Popen([sys.executable])
            else:
                subprocess.Popen([sys.executable, os.path.abspath("main.py")])
        except Exception as exc:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, "No se pudo reiniciar",
                f"Cierra y abre MiAppoderado manualmente para aplicar la actualización.\n\n{exc}"
            )
            return
        QApplication.quit()

    # ─────────────────────────────────────────────
    #  Friday weekly alert
    # ─────────────────────────────────────────────

    def _check_alerta_semana(self):
        if not utils.es_viernes():
            return
        reporte = db.get_resumen_semana()
        if reporte["total_strikes"] == 0:
            return
        QTimer.singleShot(900, lambda: self._show_weekly_alert(reporte))

    def _show_weekly_alert(self, reporte: dict):
        from logic import generar_reporte_semana
        datos = generar_reporte_semana()

        dlg = QDialog(self)
        dlg.setWindowTitle("Resumen semanal PAE")
        dlg.setMinimumWidth(740)
        dlg.setStyleSheet(f"background: {C.SURFACE}; color: {C.TEXT};")
        lay = QVBoxLayout(dlg)
        lay.setSpacing(16)
        lay.setContentsMargins(28, 24, 28, 24)

        # Header
        title = QLabel("Resumen semanal — Ausencias")
        title.setStyleSheet(
            f"font-size: 20px; font-weight: 700; color: {C.GOLD_500};"
        )
        lay.addWidget(title)

        res = datos["resumen"]
        meta = QLabel(
            f"Semana {res['desde']} → {res['hasta']}   ·   "
            f"{res['total_registros']} registros   ·   "
            f"{res['total_strikes']} strikes   ·   "
            f"{res['estudiantes_con_strikes']} estudiantes afectados"
        )
        meta.setStyleSheet(f"color: {C.TEXT2}; font-size: 12px;")
        lay.addWidget(meta)

        lay.addWidget(HDivider())

        # Table
        tabla = QTableWidget()
        tabla.setStyleSheet(f"""
            QTableWidget {{
                background: {C.SURFACE2}; color: {C.TEXT};
                gridline-color: {C.BORDER}; border: none;
                border-radius: 10px;
            }}
            QHeaderView::section {{
                background: {C.SURFACE2}; color: {C.TEXT2};
                padding: 8px 12px; border: none;
                border-bottom: 1.5px solid {C.BORDER};
                font-weight: 600; font-size: 11px;
                text-transform: uppercase;
            }}
            QTableWidget::item {{ padding: 10px 12px; }}
            QTableWidget::item:selected {{ background: {C.NAVY_700}; }}
        """)
        tabla.setColumnCount(5)
        tabla.setHorizontalHeaderLabels(["#", "RUN", "Nombre", "Curso", "Strikes"])
        tabla.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tabla.verticalHeader().setVisible(False)
        tabla.setAlternatingRowColors(True)

        top25 = datos["top25"]
        tabla.setRowCount(len(top25))
        for i, row in enumerate(top25):
            nombre = (
                f"{row.get('apellido_paterno','')} "
                f"{row.get('apellido_materno','')}, "
                f"{row.get('nombres','')}"
            ).strip(", ")
            values = [
                str(i + 1),
                utils.run_display(row["run_estudiante"]),
                nombre,
                row.get("curso", ""),
                str(row["total_strikes"]),
            ]
            for col, txt in enumerate(values):
                item = QTableWidgetItem(txt)
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                if col == 4:
                    color = C.RED if i < 5 else C.AMBER
                    item.setForeground(QColor(color))
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                tabla.setItem(i, col, item)

        tabla.setMinimumHeight(360)
        lay.addWidget(tabla)

        # Close button
        close_btn = AButton("Cerrar", sound_type="click")
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.NAVY_700}; color: {C.TEXT};
                border: none; border-radius: 10px;
                padding: 10px 28px; font-size: 13px; font-weight: 600;
            }}
            QPushButton:hover {{ background: {C.NAVY_600}; }}
        """)
        close_btn.clicked.connect(dlg.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)

        dlg.exec()


# ─────────────────────────────────────────────────────────────────────────────
#  Diálogo de reporte de bugs
# ─────────────────────────────────────────────────────────────────────────────

class _BugReportDialog(QDialog):
    """
    Diálogo para enviar reportes de bugs/sugerencias.
    El destinatario de email es interno y no se muestra en ningún campo.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Reportar un problema")
        self.setMinimumWidth(520)
        self.setModal(True)
        self.setStyleSheet(f"background: {C.SURFACE}; color: {C.TEXT};")
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(14)
        lay.setContentsMargins(28, 24, 28, 24)

        # Título
        title = QLabel("Reportar un problema")
        title.setStyleSheet(
            f"font-size: 17px; font-weight: 700; color: {C.TEXT};"
        )
        lay.addWidget(title)

        sub = QLabel(
            "Describe lo que pasó. El reporte incluye logs del sistema y se guarda en Supabase."
        )
        sub.setStyleSheet(f"color: {C.TEXT2}; font-size: 12px;")
        sub.setWordWrap(True)
        lay.addWidget(sub)

        lay.addWidget(HDivider())

        # Tipo
        tipo_row = QHBoxLayout()
        tipo_lbl = QLabel("Tipo:")
        tipo_lbl.setStyleSheet(f"color: {C.TEXT2}; font-size: 12px;")
        tipo_lbl.setFixedWidth(60)
        self._tipo = QComboBox()
        self._tipo.addItems(["Error / Bug", "Crash (se cerró la app)", "Sugerencia"])
        self._tipo.setStyleSheet(f"""
            QComboBox {{
                background: {C.SURFACE2}; color: {C.TEXT};
                border: 1.5px solid {C.BORDER}; border-radius: 7px;
                padding: 4px 10px; font-size: 12px;
            }}
            QComboBox::drop-down {{ border: none; }}
        """)
        tipo_row.addWidget(tipo_lbl)
        tipo_row.addWidget(self._tipo)
        tipo_row.addStretch()
        lay.addLayout(tipo_row)

        # Descripción
        desc_lbl = QLabel("Descripción del problema:")
        desc_lbl.setStyleSheet(f"color: {C.TEXT2}; font-size: 12px;")
        lay.addWidget(desc_lbl)

        self._desc = QTextEdit()
        self._desc.setPlaceholderText(
            "Describe paso a paso lo que hiciste y qué ocurrió..."
        )
        self._desc.setMinimumHeight(120)
        self._desc.setMaximumHeight(200)
        self._desc.setStyleSheet(f"""
            QTextEdit {{
                background: {C.SURFACE2}; color: {C.TEXT};
                border: 1.5px solid {C.BORDER}; border-radius: 8px;
                padding: 8px; font-size: 13px;
            }}
            QTextEdit:focus {{ border-color: {C.AMBER}; }}
        """)
        lay.addWidget(self._desc)

        # Estado de envío
        self._lbl_status = QLabel("")
        self._lbl_status.setStyleSheet(f"color: {C.TEXT2}; font-size: 11px;")
        self._lbl_status.setWordWrap(True)
        lay.addWidget(self._lbl_status)

        lay.addWidget(HDivider())

        # Botones
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setFixedHeight(34)
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background: {C.SURFACE2}; color: {C.TEXT};
                border: 1.5px solid {C.BORDER}; border-radius: 8px;
                padding: 0 18px; font-size: 13px;
            }}
            QPushButton:hover {{ background: {C.NAVY_700}; }}
        """)
        btn_cancel.clicked.connect(self.reject)

        self._btn_send = QPushButton("  Enviar reporte")
        self._btn_send.setFixedHeight(34)
        self._btn_send.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_send.setStyleSheet("""
            QPushButton {
                background: #d97706; color: #ffffff;
                border: none; border-radius: 8px;
                padding: 0 20px; font-size: 13px; font-weight: 700;
            }
            QPushButton:hover  { background: #b45309; }
            QPushButton:pressed { background: #92400e; }
            QPushButton:disabled { background: #6b7280; color: #9ca3af; }
        """)
        self._btn_send.clicked.connect(self._enviar)

        btn_row.addWidget(btn_cancel)
        btn_row.addSpacing(8)
        btn_row.addWidget(self._btn_send)
        lay.addLayout(btn_row)

    def _tipo_code(self) -> str:
        mapping = {
            "Error / Bug": "bug",
            "Crash (se cerró la app)": "crash",
            "Sugerencia": "sugerencia",
        }
        return mapping.get(self._tipo.currentText(), "bug")

    def _enviar(self):
        desc = self._desc.toPlainText().strip()
        if not desc:
            self._lbl_status.setText("Escribe una descripción antes de enviar.")
            self._lbl_status.setStyleSheet("color: #ef4444; font-size: 11px;")
            return

        self._btn_send.setEnabled(False)
        self._btn_send.setText("  Enviando...")
        self._lbl_status.setStyleSheet(f"color: {C.TEXT2}; font-size: 11px;")
        self._lbl_status.setText("Recopilando información del sistema...")

        tipo = self._tipo_code()

        import threading

        def _do():
            import bug_reporter
            ok, msg, ruta = bug_reporter.enviar_reporte(desc, tipo=tipo)
            QTimer.singleShot(0, lambda: self._on_sent(ok, msg, ruta))

        threading.Thread(target=_do, daemon=True, name="bug-send").start()

    @staticmethod
    def _short_path(ruta: str) -> str:
        home = os.path.expanduser("~")
        return ruta.replace(home, "~") if ruta else ""

    def _on_sent(self, ok: bool, msg: str, ruta: str):
        self._btn_send.setEnabled(True)
        self._btn_send.setText("  Enviar reporte")
        ruta_corta = self._short_path(ruta)
        if ok:
            self._lbl_status.setStyleSheet("color: #22c55e; font-size: 11px;")
            self._lbl_status.setText(f"Reporte enviado. Copia local: {ruta_corta}")
            QTimer.singleShot(2500, self.accept)
        else:
            self._lbl_status.setStyleSheet("color: #f59e0b; font-size: 11px;")
            self._lbl_status.setText(
                f"Guardado localmente ({ruta_corta}). Email: {msg}"
            )
