"""
main_window.py — Ventana principal PAE Control 0.9 Alpha
macOS Sonoma dark · Liceo Bicentenario palette
"""

from datetime import date
import threading
import urllib.request
import urllib.parse
import json
import ssl
from xml.etree import ElementTree as ET

# macOS: Python no siempre tiene el bundle de certificados del sistema.
# ssl.create_default_context() se crea sin errores pero FALLA al conectar con
# CERTIFICATE_VERIFY_FAILED si los certs no están instalados.
# Para APIs públicas de solo lectura (clima, noticias, geocoding) usamos
# contexto sin verificación de certificado — no hay datos sensibles en tránsito.
def _ssl_ctx():
    ctx = ssl._create_unverified_context()
    return ctx

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
from ui.bulk_screen         import BulkScreen
from ui.quotas_screen       import QuotasScreen
from ui.suspensions_screen   import SuspensionsScreen
from ui.inspectoria_screen   import InspectoriaScreen
from ui.junaeb_screen       import JunaebScreen
from ui.config_screen       import ConfigScreen
from ui.import_screen       import ImportScreen
from ui.sync_screen         import SyncScreen

import db
import utils
import session



class _NewsTicker(QWidget):
    """Barra de noticias scrolling — ticker estilo bursátil."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(26)
        self._text     = "Cargando noticias de educación…"
        self._prefix   = "  EDUCACIÓN  ▶  "
        self._offset   = 0.0
        self._text_w   = 0
        self._prefix_w = 0
        self._ready    = False        # True una vez que tenemos font metrics

        self._timer = QTimer(self)
        self._timer.setInterval(20)   # 50 fps
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _init_metrics(self):
        """Calcula anchos con la fuente real del widget. Llamar tras show."""
        from PyQt6.QtGui import QFont, QFontMetrics
        fm_bold = QFontMetrics(QFont(self.font().family(), -1, QFont.Weight.Bold))
        fm_bold.setPointSize = None   # ignorar — usar pixelSize
        f_bold = QFont(self.font())
        f_bold.setBold(True)
        f_bold.setPixelSize(11)
        f_norm = QFont(f_bold)
        f_norm.setBold(False)
        self._prefix_w = QFontMetrics(f_bold).horizontalAdvance(self._prefix)
        self._text_w   = QFontMetrics(f_norm).horizontalAdvance(self._text + "            ")
        self._offset   = float(self.width())
        self._ready    = True

    def showEvent(self, event):
        super().showEvent(event)
        if not self._ready:
            self._init_metrics()

    def set_text(self, text: str):
        """Llamar desde hilo principal después de fetch."""
        from PyQt6.QtGui import QFont, QFontMetrics
        self._text = text + "            "
        f_bold = QFont(self.font())
        f_bold.setBold(True)
        f_bold.setPixelSize(11)
        f_norm = QFont(f_bold)
        f_norm.setBold(False)
        self._prefix_w = QFontMetrics(f_bold).horizontalAdvance(self._prefix)
        self._text_w   = QFontMetrics(f_norm).horizontalAdvance(self._text)
        self._offset   = float(self.width())
        self._ready    = True
        self.update()

    def _tick(self):
        if not self._ready:
            return
        self._offset -= 1.4
        if self._text_w > 0 and self._offset < -self._text_w:
            self._offset = float(self.width())
        self.update()

    def paintEvent(self, event):
        if not self._ready:
            self._init_metrics()

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setClipRect(self.rect())

        # Fondo + borde inferior
        p.fillRect(self.rect(), QColor(C.SURFACE))
        p.setPen(QColor(C.BORDER))
        p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)

        y = int(self.height() * 0.74)

        from PyQt6.QtGui import QFont
        # Prefijo estático "EDUCACIÓN ▶" en azul
        f_bold = QFont(self.font())
        f_bold.setBold(True)
        f_bold.setPixelSize(11)
        p.setFont(f_bold)
        p.setPen(QColor(C.BLUE))
        p.drawText(4, y, self._prefix)

        # Texto scrolling
        f_norm = QFont(f_bold)
        f_norm.setBold(False)
        p.setFont(f_norm)
        p.setPen(QColor(C.TEXT2))

        x = int(self._prefix_w + 4 + self._offset)
        p.drawText(x, y, self._text)
        if self._text_w > 0:
            p.drawText(x + self._text_w, y, self._text)   # copia para loop continuo
        p.end()


# ── Nav config: (key, icon, label, screen_class, roles_permitidos)
# pae         → Escaneo, Registro masivo, Cupos, JUNAEB, Estudiantes (solo RSH)
# inspectoria → Inspectoría (atrasos/pases/licencias), Estudiantes (nombre/curso/tel, sin RSH)
# admin       → todo
_ALL_NAV = [
    ("scan",        "▷", "Escaneo",           ScanScreen,         ["pae", "admin"]),
    ("inspectoria", "◎", "Inspectoría",       InspectoriaScreen,  ["inspectoria", "admin"]),
    ("suspensions", "◈", "Pases (legacy)",    SuspensionsScreen,  ["admin"]),
    ("students",    "≡", "Estudiantes",       StudentsScreen,     ["pae", "inspectoria", "admin"]),
    ("bulk",        "⊞", "Registro masivo",   BulkScreen,         ["pae", "admin"]),
    ("quotas",      "▦", "Cupos por día",     QuotasScreen,       ["pae", "admin"]),
    ("junaeb",      "◉", "Menú JUNAEB",       JunaebScreen,       ["pae", "admin"]),
    ("reports",     "▤", "Reportes",          ReportsScreen,      ["admin", "pae", "inspectoria"]),
    ("import",      "⇧", "Importar",          ImportScreen,       ["admin"]),
    ("sync",        "↻", "Sync Supabase",     SyncScreen,         ["admin"]),
    ("config",      "⚙", "Configuración",     ConfigScreen,       ["admin"]),
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

        title = QLabel("PAE Control")
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
            db.get_config("nombre_establecimiento", "PAE Control") + " — PAE Control"
        )
        self.setMinimumSize(1160, 700)
        self.resize(1280, 760)
        # Filtrar nav según rol del usuario autenticado
        self._active_nav = _nav_for_rol(session.rol())
        self._build_ui()
        self._check_alerta_semana()
        # Check remoto de updates: 3 segundos después del render
        QTimer.singleShot(3000, self._start_update_check)
        # Noticias: fetch inicial a los 4s, luego cada 30 min
        QTimer.singleShot(4000, self._fetch_news)
        self._news_refresh = QTimer(self)
        self._news_refresh.setInterval(30 * 60 * 1000)
        self._news_refresh.timeout.connect(self._fetch_news)
        self._news_refresh.start()
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

        # ── News ticker (debajo del toolbar) ─────────
        self._news_ticker = _NewsTicker()
        self._news_ticker.setVisible(
            db.get_config("news_ticker_enabled", "1") == "1"
        )
        root.addWidget(self._news_ticker)

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

    def _build_toolbar(self) -> QFrame:
        """Barra superior: clima · stats · reloj — sin accesos rápidos (están en el sidebar)."""
        bar = QFrame()
        bar.setFixedHeight(44)
        bar.setStyleSheet(f"background: {C.SURFACE}; border: none;")

        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(6)

        # ── Nombre del establecimiento (izquierda) ───
        nombre_est = db.get_config("nombre_establecimiento", "PAE Control")
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
        self._tb_chip_pae = self._stat_chip_tb("—", "PAE activos", C.GREEN)
        self._tb_chip_alm = self._stat_chip_tb("—", "Almuerzos hoy", C.BLUE)
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
    def _stat_chip_tb(value: str, label: str, color: str) -> QFrame:
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

        dot = QLabel("●")
        dot.setStyleSheet(f"color: {color}; font-size: 7px; background: transparent;")

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

    def _notify_update(self, manifest: dict, new_ver: str):
        """Notifica update disponible en el botón toolbar."""
        self._btn_novedades.setText(f"↓ v{new_ver} disponible")
        self._btn_novedades.setStyleSheet(f"""
            QPushButton {{
                background: {C.BLUE_DIM};
                color: {C.BLUE};
                border: 1px solid {C.BLUE}44;
                border-radius: 7px;
                padding: 0 10px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {C.BLUE}22;
            }}
        """)
        # Desconectar handler anterior y conectar el de descarga
        try:
            self._btn_novedades.clicked.disconnect()
        except Exception:
            pass
        self._btn_novedades.clicked.connect(
            lambda: self._download_update(manifest, new_ver)
        )

    def _download_update(self, manifest: dict, new_ver: str):
        from updater import download_patch_files
        from ui.startup_screen import StartupDialog

        self._btn_novedades.setText("Descargando…")
        self._btn_novedades.setEnabled(False)

        def _do_download():
            ok, errors = download_patch_files(manifest)
            QTimer.singleShot(0, lambda: self._after_download(ok, errors, new_ver, manifest))

        import threading
        t = threading.Thread(target=_do_download, daemon=True, name="pae-download")
        t.start()

    def _after_download(self, ok: bool, errors: list, new_ver: str, manifest: dict):
        if ok:
            self._btn_novedades.setText(f"✓ v{new_ver} — Reiniciar para aplicar")
            self._btn_novedades.setStyleSheet(f"""
                QPushButton {{
                    background: {C.GREEN}22;
                    color: {C.GREEN};
                    border: 1px solid {C.GREEN}44;
                    border-radius: 7px;
                    padding: 0 10px;
                    font-size: 12px;
                    font-weight: 600;
                }}
            """)
            self._btn_novedades.setEnabled(True)
        else:
            self._btn_novedades.setText("⚠ Error en descarga")
            self._btn_novedades.setEnabled(True)

    # ─────────────────────────────────────────────
    #  Clima & noticias
    # ─────────────────────────────────────────────

    def reload_news(self):
        """Llamar desde ConfigScreen para recargar noticias inmediatamente."""
        self._fetch_news()

    def _fetch_news(self):
        """Lanza fetch de noticias de educación en background.
        Fuente primaria: Google News RSS Chile (sin API key, muy fiable).
        Fallback: Emol educación.
        """
        if db.get_config("news_ticker_enabled", "1") != "1":
            return

        def _do():
            headlines = []
            # Fuente configurada por el usuario (puede ser "custom" o un preset)
            custom_url = db.get_config("news_rss_url", "")
            _DEFAULT_FEEDS = [
                "https://news.google.com/rss/search?q=educaci%C3%B3n+chile&hl=es-CL&gl=CL&ceid=CL:es",
                "https://www.emol.com/rss/Educacion.xml",
                "https://www.biobiochile.cl/lista/categorias/educacion/feed",
            ]
            feeds = [custom_url] + _DEFAULT_FEEDS if custom_url else _DEFAULT_FEEDS
            ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) PAEControl/1.1"

            import re as _re
            for url in feeds:
                if not url:
                    continue
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": ua})
                    with urllib.request.urlopen(req, timeout=10, context=_ssl_ctx()) as r:
                        raw = r.read()
                    raw_str = raw.decode("utf-8", errors="replace")

                    # Intento 1: xml.etree (falla con algunos CDATA mal formados)
                    try:
                        root_el = ET.fromstring(raw)
                        items = root_el.findall(".//item")
                        for item in items[:10]:
                            title = item.findtext("title") or ""
                            title = _re.sub(r"<[^>]+>", "", title)   # strip HTML tags
                            title = title.split(" - ")[0].strip()
                            if title and len(title) > 12:
                                headlines.append(title)
                    except ET.ParseError:
                        # Fallback: regex sobre el texto crudo
                        found = _re.findall(
                            r"<title[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>",
                            raw_str, _re.DOTALL)
                        for t in found[1:11]:       # saltar el título del canal
                            t = _re.sub(r"<[^>]+>", "", t)
                            t = t.split(" - ")[0].strip()
                            if t and len(t) > 12:
                                headlines.append(t)

                    if len(headlines) >= 3:
                        break
                except Exception as e:
                    last_err = f"{type(e).__name__}: {e}"
                    continue

            if headlines:
                text = "   ·   ".join(headlines)
            else:
                err_info = locals().get("last_err", "sin conexión")
                text = f"Noticias no disponibles ({err_info})"

            QTimer.singleShot(0, lambda: self._news_ticker.set_text(text))

        threading.Thread(target=_do, daemon=True, name="pae-news").start()

    def reload_ticker_visibility(self):
        """Llamar desde ConfigScreen al guardar cambios."""
        self._news_ticker.setVisible(
            db.get_config("news_ticker_enabled", "1") == "1"
        )

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
