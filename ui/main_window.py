"""
main_window.py — Ventana principal PAE Control 0.9 Alpha
macOS Sonoma dark · Liceo Bicentenario palette
"""

from datetime import date
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QFrame, QDialog, QDialogButtonBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QSizePolicy, QScrollArea,
    QSpacerItem
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QColor, QPixmap

from ui.theme   import C, sound, apply_theme
from ui.widgets import NavItem, AnimatedStack, HDivider, AButton

from ui.scan_screen         import ScanScreen
from ui.students_screen     import StudentsScreen
from ui.reports_screen      import ReportsScreen
from ui.bulk_screen         import BulkScreen
from ui.quotas_screen       import QuotasScreen
from ui.suspensions_screen  import SuspensionsScreen
from ui.junaeb_screen       import JunaebScreen
from ui.config_screen       import ConfigScreen
from ui.import_screen       import ImportScreen
from ui.sync_screen         import SyncScreen

import db
import utils


# ── Nav config: (key, icon, label, screen_class)
NAV_ITEMS = [
    ("scan",        "⊙",  "Escaneo",           ScanScreen),
    ("students",    "☰",  "Estudiantes",       StudentsScreen),
    ("bulk",        "⊞",  "Registro masivo",   BulkScreen),
    ("quotas",      "◈",  "Cupos por día",     QuotasScreen),
    ("suspensions", "⊘",  "Suspensiones",      SuspensionsScreen),
    ("junaeb",      "⊕",  "Menú JUNAEB",       JunaebScreen),
    ("reports",     "◫",  "Reportes",          ReportsScreen),
    ("import",      "↑",  "Importar",          ImportScreen),
    ("sync",        "☁",  "Sync Supabase",     SyncScreen),
    ("config",      "⚙",  "Configuración",     ConfigScreen),
]


class Sidebar(QFrame):
    """
    Left sidebar: logo block + nav items + version footer.
    Fixed width 220px, dark navy background.
    """

    def __init__(self, on_nav, parent=None):
        super().__init__(parent)
        self._on_nav  = on_nav
        self._items   = {}
        self._current = None

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

        # ── Nav items ───────────────────────────────
        for key, icon, label, _ in NAV_ITEMS:
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
        self._build_ui()
        self._check_alerta_semana()
        # Check remoto de updates: 3 segundos después del render
        QTimer.singleShot(3000, self._start_update_check)

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
        self.sidebar = Sidebar(on_nav=self._nav)
        row_lay.addWidget(self.sidebar)

        # ── Thin separator line ──────────────────────
        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"background: {C.BORDER}; border: none;")
        row_lay.addWidget(sep)

        # ── Screen stack ────────────────────────────
        self.stack = AnimatedStack()
        self._screens: dict[str, tuple[int, QWidget]] = {}

        for i, (key, _icon, _label, cls) in enumerate(NAV_ITEMS):
            screen = cls()
            # Wrap in a scroll area so content never clips
            scroll = QScrollArea()
            scroll.setWidget(screen)
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setStyleSheet(f"background: {C.BG}; border: none;")
            self.stack.addWidget(scroll)
            self._screens[key] = (i, screen)

        row_lay.addWidget(self.stack, stretch=1)
        root.addWidget(content_row, stretch=1)

        # Default: scan
        self._nav("scan")

    def _build_toolbar(self) -> QFrame:
        """Barra de herramientas de acceso rápido — 44px, macOS light."""
        bar = QFrame()
        bar.setFixedHeight(44)
        bar.setStyleSheet(
            f"background: {C.SURFACE}; border: none;"
        )

        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(4)

        # App name chip (left anchor)
        name_lbl = QLabel("PAE Control")
        name_lbl.setStyleSheet(
            f"font-size: 12px; font-weight: 700; color: {C.TEXT}; "
            f"background: transparent; padding: 0 8px;"
        )
        lay.addWidget(name_lbl)

        # Separator
        v1 = QFrame()
        v1.setFixedSize(1, 22)
        v1.setStyleSheet(f"background: {C.BORDER2}; border: none;")
        lay.addWidget(v1)

        lay.addSpacing(4)

        # ── Quick-access buttons ─────────────────────
        _QUICK = [
            ("◫  Reportes",     "reports"),
            ("↑  Importar",     "import"),
            ("⚙  Config",       "config"),
            ("⊕  Menú JUNAEB",  "junaeb"),
            ("☁  Sync",         "sync"),
        ]

        def _tb_btn(label: str, key: str) -> AButton:
            btn = AButton(label, sound_type="click")
            btn.setFixedHeight(30)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {C.TEXT2};
                    border: 1px solid transparent;
                    border-radius: 7px;
                    padding: 0 12px;
                    font-size: 12px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background: {C.SURFACE2};
                    color: {C.TEXT};
                    border-color: {C.BORDER};
                }}
                QPushButton:pressed {{
                    background: {C.SURFACE3};
                }}
            """)
            btn.clicked.connect(lambda: self._nav(key))
            return btn

        for lbl, key in _QUICK:
            lay.addWidget(_tb_btn(lbl, key))

        lay.addStretch()

        # ── Right: chips de estado en tiempo real ────
        self._tb_chip_pae = self._stat_chip_tb("—", "PAE activos", C.GREEN)
        self._tb_chip_alm = self._stat_chip_tb("—", "Almuerzos hoy", C.BLUE)
        lay.addWidget(self._tb_chip_pae)
        lay.addSpacing(6)
        lay.addWidget(self._tb_chip_alm)
        lay.addSpacing(10)

        # Botón Novedades
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

        # Separador
        v2 = QFrame()
        v2.setFixedSize(1, 22)
        v2.setStyleSheet(f"background: {C.BORDER2}; border: none;")
        lay.addWidget(v2)
        lay.addSpacing(6)

        # Reloj en vivo
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
        lbl.setStyleSheet(f"font-size: 11px; color: {C.TEXT3}; background: transparent;")

        lay.addWidget(dot)
        lay.addWidget(val)
        lay.addWidget(lbl)
        return chip

    def _tick_stats(self):
        try:
            import logic as _logic
            info = _logic.get_capacidad_info()
            def _set(chip, txt):
                v = chip.findChild(QLabel, "chipval")
                if v:
                    v.setText(txt)
            _set(self._tb_chip_pae, str(info["activos"]))
            _set(self._tb_chip_alm, str(info["disponibles"]))
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

    # ─────────────────────────────────────────────
    #  Novedades / updates
    # ─────────────────────────────────────────────

    def _open_novedades(self):
        from ui.startup_screen import StartupDialog
        dlg = StartupDialog(self)
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
