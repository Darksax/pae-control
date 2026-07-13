"""
inspectoria_screen.py — Pantalla principal de Inspectoría MiAppoderado

Tabs:
  1. Atrasos      — scanner RUN + stats + notificación WA
  2. Inasistencias — scanner RUN + stats
  3. Retiros       — scanner RUN + stats + justificación comidas
  4. Firma Apoderado — búsqueda + listado de pases + firma
  5. Licencias     — formulario simple fecha + días

Lógica compartida:
  - Al registrar pase → db.justificar_strikes_por_pase() retroactivo
  - Stats por estudiante: mes / semestre / total / sin firmar
  - Threshold sin firmar → banner "Llamar apoderado"
"""

from __future__ import annotations

import threading
from datetime import date, datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTabWidget, QLineEdit, QPushButton, QSizePolicy,
    QScrollArea, QListWidget, QListWidgetItem, QAbstractItemView,
    QDateEdit, QSpinBox, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
)
from PyQt6.QtCore import Qt, QTimer, QDate, pyqtSignal, QObject
from PyQt6.QtGui import QColor

import db
import utils
from ui.theme   import C, sound
from ui.widgets import AButton, HDivider, SectionHeader, SavedIndicator, RUNLineEdit, PhoneLineEdit

# ── Threshold de pases sin firmar que activa alerta ──────────────────────────
_DEFAULT_THRESHOLD = 3

# ── Etiquetas legibles por tipo ───────────────────────────────────────────────
_TIPO_LABEL = {
    "atraso":       "Atraso",
    "inasistencia": "Inasistencia",
    "retiro":       "Retiro",
    "licencia":     "Licencia médica",
}
_TIPO_COLOR = {
    "atraso":       C.AMBER,
    "inasistencia": C.RED,
    "retiro":       C.BLUE,
    "licencia":     C.TEXT2,
}

# ─────────────────────────────────────────────────────────────────────────────
#  Barra de búsqueda por nombre (reutiliza lógica de scan_screen._NameSearchBar)
# ─────────────────────────────────────────────────────────────────────────────

class _NameSearch(QFrame):
    """Búsqueda de estudiante por nombre con popup de resultados."""
    run_selected = pyqtSignal(str)
    dismissed    = pyqtSignal()   # ESC o clic fuera — para que el padre devuelva foco al RUN

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        self.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border: none;
                border-radius: 12px;
            }}
        """)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(8)

        lbl = QLabel("☰")
        lbl.setStyleSheet(f"color: {C.TEXT3}; font-size: 15px; background: transparent;")
        lay.addWidget(lbl)

        self._field = QLineEdit()
        self._field.setPlaceholderText("Buscar estudiante por nombre o apellido…")
        self._field.setStyleSheet(
            f"background: transparent; border: none; font-size: 14px; color: {C.TEXT};"
        )
        lay.addWidget(self._field, stretch=1)

        # Popup flotante — Tool+FramelessHint evita que robe el foco (vs Popup que sí lo roba)
        self._selecting = False   # guard: evita devolver foco al seleccionar ítem
        self._popup = QListWidget()
        self._popup.setWindowFlags(
            Qt.WindowType.Tool |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self._popup.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._popup.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._popup.setStyleSheet(f"""
            QListWidget {{
                background: {C.SURFACE};
                border: 1.5px solid {C.BORDER};
                border-radius: 10px;
                font-size: 13px;
                color: {C.TEXT};
            }}
            QListWidget::item {{ padding: 8px 14px; }}
            QListWidget::item:hover {{ background: {C.SURFACE2}; }}
            QListWidget::item:selected {{ background: {C.BLUE_DIM}; color: {C.BLUE}; }}
        """)
        self._popup.hide()
        self._popup.itemClicked.connect(self._on_item_clicked)
        # Instalar event filter en popup y campo — DESPUÉS de crear self._popup:
        # instalarlo antes (p.ej. junto con self._field más arriba) deja una
        # ventana donde un evento de layout llega a eventFilter() mientras
        # self._popup todavía no existe, y la línea 133 revienta con
        # AttributeError en cada evento sintético del armado del layout.
        self._field.installEventFilter(self)
        self._popup.installEventFilter(self)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(200)
        self._debounce.timeout.connect(self._do_search)
        self._field.textChanged.connect(lambda t: self._debounce.start() if len(t) >= 2 else self._popup.hide())
        self._field.returnPressed.connect(self._do_search)

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if obj is self._field and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                self._field.clear()
                self._popup.hide()
                self.dismissed.emit()
                return True
        # Cuando el popup se oculta sin que el usuario haya elegido un ítem,
        # devolver el foco al campo de búsqueda para que no quede bloqueado.
        if obj is self._popup and event.type() == QEvent.Type.Hide:
            if not self._selecting:
                QTimer.singleShot(0, self._field.setFocus)
            return False
        return super().eventFilter(obj, event)

    def is_active(self) -> bool:
        """True si el campo tiene foco o el popup está visible."""
        return self._field.hasFocus() or self._popup.isVisible()

    def _do_search(self):
        q = self._field.text().strip()
        if len(q) < 2:
            self._popup.hide()
            return
        try:
            rows = db.search_students(q, limit=10)
        except Exception:
            rows = []
        if not rows:
            self._popup.hide()
            return
        _map = db.get_cursos_nombres_map()
        self._popup.clear()
        for r in rows:
            ap = f"{r.get('apellido_paterno','') or ''} {r.get('apellido_materno','') or ''}".strip()
            nombre = r.get("nombres", "") or ""
            curso  = db.display_curso(r.get("curso",""), _map) or ""
            item = QListWidgetItem(f"{ap}, {nombre}  —  {curso}")
            item.setData(Qt.ItemDataRole.UserRole, r["run"])
            self._popup.addItem(item)
        # Posicionar popup debajo del campo
        pos = self.mapToGlobal(self.rect().bottomLeft())
        self._popup.setGeometry(pos.x(), pos.y(), self.width(), min(len(rows) * 36 + 8, 260))
        self._popup.show()

    def _on_item_clicked(self, item: QListWidgetItem):
        self._selecting = True   # no devolver foco al campo tras esta selección
        self._popup.hide()
        self._selecting = False
        self._field.clear()
        self.run_selected.emit(item.data(Qt.ItemDataRole.UserRole))

    def clear(self):
        self._field.clear()
        self._popup.hide()


# ─────────────────────────────────────────────────────────────────────────────
#  Card de estudiante con stats de pases
# ─────────────────────────────────────────────────────────────────────────────

class _StudentCard(QFrame):
    """Muestra datos del estudiante + stats de pases + alerta threshold."""

    def __init__(self, threshold: int = _DEFAULT_THRESHOLD, parent=None):
        super().__init__(parent)
        self._threshold = threshold
        self.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border: none;
                border-radius: 14px;
            }}
        """)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(120)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(10)

        # ── Nombre + curso ──────────────────────────────
        self._lbl_nombre = QLabel("—")
        self._lbl_nombre.setStyleSheet(
            f"font-size: 18px; font-weight: 700; color: {C.TEXT}; background: transparent;"
        )
        root.addWidget(self._lbl_nombre)

        info_row = QHBoxLayout()
        self._lbl_run   = QLabel("")
        self._lbl_curso = QLabel("")
        for lbl in (self._lbl_run, self._lbl_curso):
            lbl.setStyleSheet(f"font-size: 12px; color: {C.TEXT2}; background: transparent;")
        info_row.addWidget(self._lbl_run)
        info_row.addSpacing(16)
        info_row.addWidget(self._lbl_curso)
        info_row.addStretch()
        root.addLayout(info_row)

        root.addWidget(HDivider())

        # ── Stats: mes / semestre / total / sin firmar ──
        stats_row = QHBoxLayout()
        stats_row.setSpacing(24)
        self._stat_mes      = self._make_stat("Este mes",    "—")
        self._stat_sem      = self._make_stat("Semestre",    "—")
        self._stat_total    = self._make_stat("Total",       "—")
        self._stat_sinfirma = self._make_stat("Sin firma",   "—", accent=C.AMBER)
        for s in (self._stat_mes, self._stat_sem, self._stat_total, self._stat_sinfirma):
            stats_row.addLayout(s[0])
        stats_row.addStretch()
        root.addLayout(stats_row)

        # ── Banner alerta threshold ─────────────────────
        self._alerta = QLabel("")
        self._alerta.setStyleSheet(f"""
            background: {C.RED}22; color: {C.RED};
            border: 1px solid {C.RED}44; border-radius: 8px;
            font-size: 12px; font-weight: 700;
            padding: 6px 14px;
        """)
        self._alerta.setWordWrap(True)
        self._alerta.hide()
        root.addWidget(self._alerta)

        self.hide()

    def _make_stat(self, label: str, value: str, accent: str = C.TEXT):
        lay = QVBoxLayout()
        lay.setSpacing(2)
        lbl_v = QLabel(value)
        lbl_v.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: {accent}; background: transparent;"
        )
        lbl_l = QLabel(label)
        lbl_l.setStyleSheet(
            f"font-size: 10px; color: {C.TEXT3}; background: transparent;"
        )
        lay.addWidget(lbl_v)
        lay.addWidget(lbl_l)
        return lay, lbl_v

    def load(self, run: str):
        st = db.get_student(run)
        if not st:
            self.hide()
            return
        ap      = f"{st.get('apellido_paterno','') or ''} {st.get('apellido_materno','') or ''}".strip()
        nombre  = st.get("nombres", "") or ""
        curso   = db.display_curso(st.get("curso",""), db.get_cursos_nombres_map()) or ""
        self._lbl_nombre.setText(f"{ap}, {nombre}")
        self._lbl_run.setText(utils.run_display(run))
        self._lbl_curso.setText(curso)

        stats = db.get_pases_estudiante(run)
        self._stat_mes[1].setText(str(stats["mes"]))
        self._stat_sem[1].setText(str(stats["semestre"]))
        self._stat_total[1].setText(str(stats["total"]))
        sf = stats["sin_firmar"]
        self._stat_sinfirma[1].setText(str(sf))
        # Color dinámico sin firma
        color = C.RED if sf >= self._threshold else (C.AMBER if sf > 0 else C.GREEN)
        self._stat_sinfirma[1].setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: {color}; background: transparent;"
        )
        # Alerta threshold
        if sf >= self._threshold:
            self._alerta.setText(
                f"⚠  {sf} pases sin firma — LLAMAR AL APODERADO"
            )
            self._alerta.show()
        else:
            self._alerta.hide()

        self.show()

    def clear(self):
        self.hide()


# ─────────────────────────────────────────────────────────────────────────────
#  Tab de pase con scanner (Atrasos / Inasistencias / Retiros)
# ─────────────────────────────────────────────────────────────────────────────

class _PaseTab(QWidget):
    """Tab genérico de escaneo para un tipo de pase."""

    pase_registrado = pyqtSignal(str, str)   # (run, tipo)

    def __init__(self, tipo: str, threshold: int = _DEFAULT_THRESHOLD, parent=None):
        super().__init__(parent)
        self._tipo       = tipo
        self._threshold  = threshold
        self._current_run: str | None = None
        self._auto_reset_ms = 5000

        self._timer_reset = QTimer(self)
        self._timer_reset.setSingleShot(True)
        self._timer_reset.timeout.connect(self._do_reset)

        self._build_ui()
        self._load_config()

    def _build_ui(self):
        self.setStyleSheet(f"background: {C.BG};")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        # ── Título ──────────────────────────────────────
        hdr = QHBoxLayout()
        lbl_tipo = QLabel(_TIPO_LABEL.get(self._tipo, self._tipo))
        lbl_tipo.setStyleSheet(
            f"font-size: 20px; font-weight: 700; "
            f"color: {_TIPO_COLOR.get(self._tipo, C.TEXT)}; background: transparent;"
        )
        hdr.addWidget(lbl_tipo)
        hdr.addStretch()

        # ── Toggle de impresión ─────────────────────────
        self._btn_print = QPushButton()
        self._btn_print.setCheckable(True)
        self._btn_print.setFixedSize(130, 32)
        self._btn_print.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_print.setStyleSheet(self._print_btn_style(False))
        self._btn_print.toggled.connect(self._on_print_toggled)
        self._update_print_btn_text(False)
        hdr.addWidget(self._btn_print)

        hdr.addSpacing(16)

        # ── Botones de auto-reset ───────────────────────
        lbl_ar = QLabel("Reset:")
        lbl_ar.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: {C.TEXT3}; "
            f"background: transparent; letter-spacing: 0.5px;"
        )
        hdr.addWidget(lbl_ar)
        for ms, lbl in [(0, "No"), (3000, "3s"), (5000, "5s"), (10000, "10s")]:
            btn = QPushButton(lbl)
            btn.setFixedHeight(30)
            btn.setMinimumWidth(36)
            btn.setCheckable(True)
            btn.setProperty("reset_ms", ms)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(self._reset_btn_style(False))
            btn.clicked.connect(lambda _, v=ms: self._set_auto_reset(v))
            setattr(self, f"_rbtn_{ms}", btn)
            hdr.addWidget(btn)
        root.addLayout(hdr)

        # ── Campo de escaneo ────────────────────────────
        scan_frame = QFrame()
        scan_frame.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border: 2px solid {C.BORDER};
                border-radius: 16px;
            }}
        """)
        scan_lay = QHBoxLayout(scan_frame)
        scan_lay.setContentsMargins(16, 10, 16, 10)

        lbl_scan = QLabel("RUN")
        lbl_scan.setStyleSheet(
            f"font-size: 12px; font-weight: 700; letter-spacing: 1px; "
            f"color: {C.TEXT3}; background: transparent;"
        )
        scan_lay.addWidget(lbl_scan)

        self._inp = RUNLineEdit()
        self._inp.setStyleSheet(f"""
            QLineEdit {{
                background: transparent; border: none;
                font-size: 26px; font-weight: 600;
                color: {C.TEXT}; letter-spacing: 1px;
            }}
        """)
        self._inp.setPlaceholderText("Escanear o escribir RUN…")
        self._inp.returnPressed.connect(self._on_scan)
        self._inp.scan_ready.connect(self._on_scan)
        scan_lay.addWidget(self._inp, stretch=1)

        btn_ok = AButton("↩  Registrar", sound_type="click")
        btn_ok.setStyleSheet(f"""
            QPushButton {{
                background: {_TIPO_COLOR.get(self._tipo, C.BLUE)};
                color: white; border: none; border-radius: 10px;
                padding: 10px 20px; font-size: 13px; font-weight: 700;
            }}
            QPushButton:hover {{ opacity: 0.85; }}
        """)
        btn_ok.clicked.connect(self._on_scan)
        scan_lay.addWidget(btn_ok)
        root.addWidget(scan_frame)

        # ── Card de resultado ────────────────────────────
        self._card = _StudentCard(threshold=self._threshold)
        root.addWidget(self._card)

        # ── Panel fecha (solo inasistencias) ─────────────
        if self._tipo == "inasistencia":
            self._date_panel = QFrame()
            self._date_panel.setStyleSheet(f"""
                QFrame {{
                    background: {C.SURFACE}; border: 1.5px solid {C.BORDER};
                    border-radius: 12px;
                }}
            """)
            dp_lay = QHBoxLayout(self._date_panel)
            dp_lay.setContentsMargins(16, 10, 16, 10)
            dp_lay.setSpacing(12)

            lbl_f = QLabel("Fecha:")
            lbl_f.setStyleSheet(f"color: {C.TEXT2}; background: transparent;")
            dp_lay.addWidget(lbl_f)

            from datetime import date as _d, timedelta as _td
            _ayer = _d.today() - _td(days=1)
            self._date_inasis = QDateEdit(
                QDate(_ayer.year, _ayer.month, _ayer.day)
            )
            self._date_inasis.setCalendarPopup(True)
            self._date_inasis.setDisplayFormat("dd/MM/yyyy")
            dp_lay.addWidget(self._date_inasis)

            self._btn_ayer = QPushButton("Ayer")
            self._btn_hoy_inasis = QPushButton("Hoy")
            for b in (self._btn_ayer, self._btn_hoy_inasis):
                b.setFixedHeight(28)
                b.setCursor(Qt.CursorShape.PointingHandCursor)
                b.setStyleSheet(f"""
                    QPushButton {{
                        background: transparent; color: {C.TEXT2};
                        border: 1px solid {C.BORDER}; border-radius: 7px;
                        padding: 0 10px; font-size: 11px;
                    }}
                    QPushButton:hover {{ background: {C.SURFACE2}; }}
                """)
            self._btn_ayer.clicked.connect(self._set_ayer)
            self._btn_hoy_inasis.clicked.connect(self._set_hoy_inasis)
            dp_lay.addWidget(self._btn_ayer)
            dp_lay.addWidget(self._btn_hoy_inasis)
            dp_lay.addStretch()

            # Banner licencia activa
            self._lbl_licencia = QLabel()
            self._lbl_licencia.setStyleSheet(f"""
                color: {C.GREEN}; font-size: 12px; font-weight: 600;
                background: {C.GREEN}18; border: 1px solid {C.GREEN}44;
                border-radius: 6px; padding: 4px 10px;
            """)
            self._lbl_licencia.hide()
            dp_lay.addWidget(self._lbl_licencia)

            # Botón confirmar explícito para inasistencias
            self._btn_confirmar = QPushButton("✓  Registrar pase")
            self._btn_confirmar.setCursor(Qt.CursorShape.PointingHandCursor)
            self._btn_confirmar.setEnabled(False)
            self._btn_confirmar.setStyleSheet(f"""
                QPushButton {{
                    background: {C.RED}; color: white;
                    border: none; border-radius: 8px;
                    padding: 6px 18px; font-size: 13px; font-weight: 700;
                }}
                QPushButton:hover {{ background: #CC2F26; }}
                QPushButton:disabled {{ background: {C.BORDER}; color: {C.TEXT3}; }}
            """)
            self._btn_confirmar.clicked.connect(self._confirmar_inasistencia)
            dp_lay.addWidget(self._btn_confirmar)

            root.addWidget(self._date_panel)
            self._date_panel.hide()   # visible solo tras cargar estudiante
            self._date_inasis.dateChanged.connect(self._on_fecha_inasis_changed)
        else:
            self._date_panel = None

        # ── Saved indicator ──────────────────────────────
        self._saved = SavedIndicator()
        root.addWidget(self._saved)

        # ── Búsqueda por nombre ──────────────────────────
        root.addWidget(self._make_label("Buscar por nombre:"))
        self._search = _NameSearch()
        self._search.run_selected.connect(self._load_student)
        # ESC en búsqueda → devolver foco al campo RUN
        self._search.dismissed.connect(lambda: self._inp.setFocus())
        # Mientras el usuario escribe en búsqueda → detener el timer de reset
        self._search._field.textChanged.connect(
            lambda t: self._timer_reset.stop() if t else None
        )
        root.addWidget(self._search)

        # ── WA stats + reimpresión (solo atrasos) ────────
        if self._tipo == "atraso":
            self._wa_strip = self._build_wa_strip()
            root.addWidget(self._wa_strip)
            self._reprint_panel = self._build_reprint_panel()
            root.addWidget(self._reprint_panel)

        root.addStretch()

    # ── WA Stats strip ───────────────────────────────────────────────────────

    def _build_wa_strip(self) -> QFrame:
        """Franja compacta con stats de mensajes WA del mes."""
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border: none;
                border-radius: 10px;
            }}
        """)
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(14, 8, 14, 8)
        lay.setSpacing(0)

        icon = QLabel("📲")
        icon.setStyleSheet("background: transparent; font-size: 14px;")
        lay.addWidget(icon)
        lay.addSpacing(8)

        self._wa_lbl_stats = QLabel("WhatsApp: cargando…")
        self._wa_lbl_stats.setStyleSheet(
            f"font-size: 11px; color: {C.TEXT2}; background: transparent;"
        )
        self._wa_lbl_stats.setWordWrap(False)
        lay.addWidget(self._wa_lbl_stats, stretch=1)

        btn_ref = QPushButton("↻")
        btn_ref.setFixedSize(26, 26)
        btn_ref.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_ref.setToolTip("Actualizar stats")
        btn_ref.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT3};
                border: none; font-size: 14px; font-weight: 700;
            }}
            QPushButton:hover {{ color: {C.TEXT}; }}
        """)
        btn_ref.clicked.connect(self._refresh_wa_strip)
        lay.addWidget(btn_ref)

        QTimer.singleShot(300, self._refresh_wa_strip)
        return frame

    def _refresh_wa_strip(self):
        """Calcula y muestra stats WA del mes en la franja."""
        if not hasattr(self, "_wa_lbl_stats"):
            return
        try:
            from datetime import date as _d
            import calendar as _cal
            hoy = _d.today()
            mes_str = hoy.strftime("%Y-%m")
            conn = db.get_conn()
            # Mensajes enviados este mes
            row = conn.execute(
                "SELECT COUNT(*) as n FROM whatsapp_pendientes "
                "WHERE enviado=1 AND substr(creado_en,1,7)=?",
                (mes_str,)
            ).fetchone()
            enviados = int((row["n"] if row else 0) or 0)
            conn.close()

            # Días del mes
            dias_mes = _cal.monthrange(hoy.year, hoy.month)[1]
            dia_actual = hoy.day
            dias_restantes = dias_mes - dia_actual  # excluye hoy

            # Costo estimado (USD $0.023 por mensaje utility Chile)
            costo_usd = enviados * 0.023

            # Promedio diario (solo días transcurridos con al menos 1)
            prom_dia = round(enviados / max(dia_actual, 1), 1)

            # Proyección al cierre del mes
            proyeccion = round(enviados + prom_dia * dias_restantes)

            txt = (
                f"WA este mes: <b>{enviados}</b> enviados"
                f"  ·  ~<b>${costo_usd:.2f} USD</b>"
                f"  ·  <b>{prom_dia}/día</b> promedio"
                f"  ·  proyección: <b>~{proyeccion}</b> al cierre"
                f"  ·  <b>{dias_restantes}</b> días restantes"
            )
            self._wa_lbl_stats.setText(txt)
            self._wa_lbl_stats.setTextFormat(Qt.TextFormat.RichText)
        except Exception as exc:
            self._wa_lbl_stats.setText(f"WA stats: error ({exc})")

    # ── Reimpresión manual ────────────────────────────────────────────────────

    def _build_reprint_panel(self) -> QFrame:
        """Panel plegable con últimos atrasos para reimprimir."""
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border: none;
                border-radius: 10px;
            }}
        """)
        outer = QVBoxLayout(frame)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Cabecera plegable ──
        hdr = QFrame()
        hdr.setStyleSheet("background: transparent; border: none;")
        hdr_lay = QHBoxLayout(hdr)
        hdr_lay.setContentsMargins(14, 8, 14, 8)

        lbl_hdr = QLabel("🖨  Reimprimir pase anterior")
        lbl_hdr.setStyleSheet(
            f"font-size: 11px; font-weight: 700; color: {C.TEXT2}; "
            f"letter-spacing: 0.4px; background: transparent;"
        )
        hdr_lay.addWidget(lbl_hdr)
        hdr_lay.addStretch()

        self._reprint_toggle = QPushButton("▼ Mostrar")
        self._reprint_toggle.setFlat(True)
        self._reprint_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reprint_toggle.setStyleSheet(
            f"font-size: 11px; color: {C.BLUE}; background: transparent; border: none;"
        )
        hdr_lay.addWidget(self._reprint_toggle)
        outer.addWidget(hdr)

        # ── Contenido plegable ──
        self._reprint_body = QFrame()
        self._reprint_body.setStyleSheet("background: transparent; border: none;")
        self._reprint_body.hide()
        body_lay = QVBoxLayout(self._reprint_body)
        body_lay.setContentsMargins(10, 4, 10, 10)
        body_lay.setSpacing(4)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background: {C.BORDER}; border: none; max-height: 1px;")
        body_lay.addWidget(sep)

        self._reprint_list_lay = QVBoxLayout()
        self._reprint_list_lay.setSpacing(3)
        body_lay.addLayout(self._reprint_list_lay)
        outer.addWidget(self._reprint_body)

        # Toggle
        self._reprint_expanded = False
        def _toggle():
            self._reprint_expanded = not self._reprint_expanded
            if self._reprint_expanded:
                self._reprint_toggle.setText("▲ Ocultar")
                self._reload_reprint_list()
                self._reprint_body.show()
            else:
                self._reprint_toggle.setText("▼ Mostrar")
                self._reprint_body.hide()
        self._reprint_toggle.clicked.connect(_toggle)

        return frame

    def _reload_reprint_list(self):
        """Carga los últimos 10 atrasos en el panel de reimpresión."""
        # Limpiar layout anterior
        while self._reprint_list_lay.count():
            item = self._reprint_list_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        try:
            conn = db.get_conn()
            rows = conn.execute("""
                SELECT ss.id, ss.run, ss.fecha_inicio, ss.motivo,
                       s.nombres, s.apellido_paterno, s.apellido_materno
                FROM student_suspensions ss
                JOIN students s ON s.run = ss.run
                WHERE ss.tipo = 'atraso'
                ORDER BY ss.creado_en DESC
                LIMIT 10
            """).fetchall()
            conn.close()
        except Exception:
            rows = []

        if not rows:
            lbl = QLabel("Sin atrasos registrados")
            lbl.setStyleSheet(f"color: {C.TEXT3}; font-size: 11px; background: transparent;")
            self._reprint_list_lay.addWidget(lbl)
            return

        for row in rows:
            sus_id   = row["id"]
            run      = row["run"]
            fecha    = row["fecha_inicio"]
            motivo   = row["motivo"] or ""
            # Extraer hora del motivo "Atraso — HH:MM"
            hora = motivo.split("—")[-1].strip() if "—" in motivo else "—"
            nombre = f"{row['apellido_paterno']} {row['nombres']}"

            fila = QFrame()
            fila.setStyleSheet(f"""
                QFrame {{
                    background: {C.SURFACE2};
                    border: none;
                    border-radius: 7px;
                }}
            """)
            fila_lay = QHBoxLayout(fila)
            fila_lay.setContentsMargins(10, 5, 10, 5)
            fila_lay.setSpacing(10)

            lbl_info = QLabel(f"<b>{nombre}</b>  ·  {fecha}  ·  {hora} hrs  ·  {run}")
            lbl_info.setStyleSheet(
                f"font-size: 11px; color: {C.TEXT2}; background: transparent;"
            )
            lbl_info.setTextFormat(Qt.TextFormat.RichText)
            fila_lay.addWidget(lbl_info, stretch=1)

            btn = QPushButton("🖨 Reimprimir")
            btn.setFixedHeight(26)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {C.BLUE}; color: white;
                    border: none; border-radius: 6px;
                    padding: 0 10px; font-size: 11px; font-weight: 600;
                }}
                QPushButton:hover {{ background: #2563EB; }}
            """)
            btn.clicked.connect(lambda _, r=run, h=hora, f=fecha: self._imprimir_pase(r, h, f))
            fila_lay.addWidget(btn)

            self._reprint_list_lay.addWidget(fila)

    def _update_print_btn_text(self, active: bool):
        if active:
            self._btn_print.setText("  Imprimir  |  ON")
        else:
            self._btn_print.setText("  Imprimir  |  OFF")

    def _print_btn_style(self, active: bool) -> str:
        if active:
            return f"""
                QPushButton {{
                    background: {C.GREEN};
                    color: #ffffff;
                    border: none;
                    border-radius: 8px;
                    font-size: 12px; font-weight: 700;
                    letter-spacing: 0.3px;
                }}
                QPushButton:hover {{ background: #16a34a; }}
            """
        return f"""
            QPushButton {{
                background: {C.RED}cc;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 12px; font-weight: 600;
                letter-spacing: 0.3px;
            }}
            QPushButton:hover {{ background: {C.RED}; }}
        """

    def _on_print_toggled(self, checked: bool):
        self._btn_print.setStyleSheet(self._print_btn_style(checked))
        self._update_print_btn_text(checked)
        try:
            db.set_config("print_pase_auto", "1" if checked else "0")
        except Exception:
            pass

    def _make_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"font-size: 11px; color: {C.TEXT3}; background: transparent;")
        return lbl

    def _reset_btn_style(self, active: bool) -> str:
        if active:
            return f"""
                QPushButton {{
                    background: {C.BLUE_DIM}; color: {C.BLUE};
                    border: 1px solid {C.BLUE}44; border-radius: 7px;
                    font-size: 11px; font-weight: 700;
                }}
            """
        return f"""
            QPushButton {{
                background: transparent; color: {C.TEXT3};
                border: 1px solid {C.BORDER}; border-radius: 7px;
                font-size: 11px; font-weight: 500;
            }}
            QPushButton:hover {{ background: {C.SURFACE2}; color: {C.TEXT2}; }}
        """

    def _set_auto_reset(self, ms: int):
        self._auto_reset_ms = ms
        for v in [0, 3000, 5000, 10000]:
            btn = getattr(self, f"_rbtn_{v}", None)
            if btn:
                btn.setStyleSheet(self._reset_btn_style(v == ms))

    def _load_config(self):
        cfg = db.get_all_config()
        delay_ms = int(cfg.get("scan_submit_delay_ms", "180"))
        self._inp.set_submit_delay(delay_ms)
        autoreset_s = int(cfg.get("scan_auto_reset_default_s", "5"))
        self._set_auto_reset(autoreset_s * 1000)
        # Toggle de impresión — cargar estado guardado
        print_on = cfg.get("print_pase_auto", "0") == "1"
        self._btn_print.blockSignals(True)
        self._btn_print.setChecked(print_on)
        self._btn_print.setStyleSheet(self._print_btn_style(print_on))
        self._update_print_btn_text(print_on)
        self._btn_print.blockSignals(False)

    # ── Lógica de escaneo ─────────────────────────────────

    def _on_scan(self):
        run_raw = self._inp.text().strip()
        if not run_raw:
            return
        run = utils.normalizar_run(run_raw)
        if not utils.validar_run(run):
            self._saved.show_error("✗  RUN inválido")
            return
        self._inp.clear()
        self._load_student(run)

    def _load_student(self, run: str):
        self._current_run = run
        st = db.get_student(run)
        if not st:
            self._card.clear()
            self._saved.show_error(f"✗  RUN {utils.run_display(run)} no encontrado")
            return
        self._card.load(run)

        if self._tipo == "inasistencia":
            # Mostrar panel fecha y esperar confirmación explícita
            self._date_panel.show()
            self._btn_confirmar.setEnabled(True)
            self._check_licencia_banner()
        else:
            self._registrar_pase(run)

    def _set_ayer(self):
        from datetime import date as _d, timedelta as _td
        ayer = _d.today() - _td(days=1)
        self._date_inasis.setDate(QDate(ayer.year, ayer.month, ayer.day))

    def _set_hoy_inasis(self):
        hoy = date.today()
        self._date_inasis.setDate(QDate(hoy.year, hoy.month, hoy.day))

    def _on_fecha_inasis_changed(self):
        self._check_licencia_banner()

    def _check_licencia_banner(self):
        """Muestra banner verde si hay licencia que cubre la fecha seleccionada."""
        if not self._current_run:
            return
        fecha = self._date_inasis.date().toString("yyyy-MM-dd")
        tiene = db.tiene_licencia_activa(self._current_run, fecha)
        if tiene:
            self._lbl_licencia.setText("✓ Licencia médica vigente — se firmará automáticamente")
            self._lbl_licencia.show()
        else:
            self._lbl_licencia.hide()

    def _confirmar_inasistencia(self):
        """Registra inasistencia con la fecha del selector."""
        if not self._current_run:
            return
        fecha = self._date_inasis.date().toString("yyyy-MM-dd")
        tiene_lic = db.tiene_licencia_activa(self._current_run, fecha)
        self._registrar_pase(self._current_run, fecha_override=fecha,
                             auto_firmar=tiene_lic)
        self._date_panel.hide()
        self._btn_confirmar.setEnabled(False)
        self._lbl_licencia.hide()

    def _registrar_pase(self, run: str, fecha_override: str | None = None,
                        auto_firmar: bool = False):
        hoy  = fecha_override or date.today().isoformat()
        hora = datetime.now().strftime("%H:%M")

        try:
            # 1. Registrar pase
            db.add_student_suspension(run, hoy, hoy,
                                       f"{_TIPO_LABEL[self._tipo]} — {hora}",
                                       self._tipo)

            # 2. Si tiene licencia activa → firmar automáticamente
            if auto_firmar:
                conn = db.get_conn()
                pase_row = conn.execute(
                    "SELECT id FROM student_suspensions WHERE run=? AND fecha_inicio=? AND tipo=? "
                    "ORDER BY id DESC LIMIT 1",
                    (run, hoy, self._tipo)
                ).fetchone()
                conn.close()
                if pase_row:
                    db.firmar_pase(pase_row["id"], "Licencia médica")

            # 3. Justificar strikes retroactivos
            n_just = db.justificar_strikes_por_pase(run, hoy, self._tipo, hora)

            # 4. Recargar stats
            self._card.load(run)

            msg = f"✓  Pase registrado — {hora}"
            if auto_firmar:
                msg += "  (firmado: licencia médica)"
            elif n_just:
                msg += f"  ({n_just} comida{'s' if n_just != 1 else ''} justificada{'s' if n_just != 1 else ''})"
            self._saved.show_saved(msg)
            sound.scan_ok()

            # 5. WhatsApp para atrasos
            if self._tipo == "atraso":
                self._enviar_wa(run, hora)

            # 6. Imprimir pase si toggle activo
            if self._btn_print.isChecked():
                self._imprimir_pase(run, hora, hoy)

            # 7. Emitir señal para reportes
            self.pase_registrado.emit(run, self._tipo)

            # 8. Auto-reset
            if self._auto_reset_ms > 0:
                self._timer_reset.start(self._auto_reset_ms)

        except Exception as e:
            self._saved.show_error(f"✗  {e}")
            sound.error()

    def _enviar_wa(self, run: str, hora: str):
        def _send():
            try:
                import whatsapp
                whatsapp.enviar_atraso(run, hora)
            except Exception:
                pass
            # Refrescar stats WA después del envío (con pequeño delay)
            QTimer.singleShot(2000, self._refresh_wa_strip)
        threading.Thread(target=_send, daemon=True, name="wa-insp").start()

    def _imprimir_pase(self, run: str, hora: str, fecha_iso: str):
        """Genera e imprime el pase ESC/POS en hilo daemon."""
        try:
            import thermal_print
            st = db.get_student(run)
            if not st:
                return
            nombre  = f"{st.get('apellido_paterno','') or ''} {st.get('apellido_materno','') or ''}, {st.get('nombres','') or ''}".strip(", ")
            curso   = st.get("curso", "") or ""
            # Contar pases sin firmar
            conn = db.get_conn()
            row_sf = conn.execute(
                "SELECT COUNT(*) AS n FROM student_suspensions "
                "WHERE run=? AND firmado=0",
                (run,)
            ).fetchone()
            conn.close()
            n_sf = int((row_sf["n"] if row_sf else 0) or 0)
            # Fecha legible
            from datetime import date as _dt
            try:
                d = _dt.fromisoformat(fecha_iso)
                _DIAS   = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
                _MESES  = ["enero","febrero","marzo","abril","mayo","junio",
                           "julio","agosto","septiembre","octubre","noviembre","diciembre"]
                fecha_lbl = f"{_DIAS[d.weekday()]} {d.day} de {_MESES[d.month-1]} de {d.year}"
            except Exception:
                fecha_lbl = fecha_iso
            establecimiento = db.get_config("nombre_establecimiento", "MiAppoderado")
            contenido = thermal_print.generar_pase(
                run=utils.run_display(run),
                nombre=nombre,
                curso=curso,
                tipo=self._tipo,
                fecha=fecha_lbl,
                hora=hora,
                n_sin_firmar=n_sf,
                establecimiento=establecimiento,
            )

            def _on_error(msg: str):
                # Mostrar error de impresora sin interrumpir el flujo principal
                try:
                    self._saved.show_error(f"🖨 ✗  {msg}")
                except Exception:
                    pass

            thermal_print.imprimir_async(contenido, on_error=_on_error)
        except Exception as exc:
            try:
                self._saved.show_error(f"🖨 ✗  {exc}")
            except Exception:
                pass

    def _do_reset(self):
        self._current_run = None
        self._card.clear()
        self._saved.clear() if hasattr(self._saved, 'clear') else None
        self._inp.clear()
        # No robar foco si el usuario está escribiendo en el buscador de nombres
        if not self._search.is_active():
            self._inp.setFocus()

    def showEvent(self, event):
        super().showEvent(event)
        self._load_config()
        if not self._search.is_active():
            self._inp.setFocus()


# ─────────────────────────────────────────────────────────────────────────────
#  Tab de Licencias (formulario simple)
# ─────────────────────────────────────────────────────────────────────────────

_LIC_TBL_STYLE = f"""
    QTableWidget {{
        background: {C.SURFACE}; border: none; border-radius: 10px; outline: none;
    }}
    QTableWidget::item {{ padding: 5px 10px; border: none; }}
    QTableWidget::item:alternate {{ background: {C.SURFACE2}; }}
    QHeaderView::section {{
        background: {C.SURFACE2}; color: {C.TEXT3};
        padding: 6px 10px; border: none; font-size: 11px; font-weight: 600;
    }}
"""


class _LicenciasTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_run: str | None = None
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet(f"background: {C.BG};")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        root.addWidget(SectionHeader("Licencias médicas"))

        # ── Búsqueda + RUN ──────────────────────────────
        self._search = _NameSearch()
        self._search.run_selected.connect(self._select_student)
        root.addWidget(self._search)

        run_row = QHBoxLayout()
        self._inp_run = RUNLineEdit()
        self._inp_run.setPlaceholderText("O escribir RUN directamente…")
        self._inp_run.setStyleSheet(f"""
            QLineEdit {{
                background: {C.SURFACE}; border: 1.5px solid {C.BORDER};
                border-radius: 10px; padding: 8px 14px;
                font-size: 16px; color: {C.TEXT};
            }}
        """)
        self._inp_run.returnPressed.connect(self._on_run_entered)
        self._inp_run.scan_ready.connect(self._on_run_entered)
        run_row.addWidget(self._inp_run)
        root.addLayout(run_row)

        # Info estudiante
        self._lbl_student = QLabel("Busca un estudiante para ver sus licencias")
        self._lbl_student.setStyleSheet(
            f"font-size: 14px; color: {C.TEXT2}; background: transparent;"
        )
        root.addWidget(self._lbl_student)

        root.addWidget(HDivider())

        # ── Layout dos columnas: formulario | tabla ──────
        cols = QHBoxLayout()
        cols.setSpacing(20)

        # Columna izq: formulario nueva licencia
        form_frame = QFrame()
        form_frame.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE}; border: 1.5px solid {C.BORDER};
                border-radius: 12px;
            }}
        """)
        form_frame.setFixedWidth(260)
        form_lay = QVBoxLayout(form_frame)
        form_lay.setContentsMargins(16, 14, 16, 14)
        form_lay.setSpacing(10)

        lbl_nueva = QLabel("Nueva licencia")
        lbl_nueva.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {C.TEXT}; background: transparent;"
        )
        form_lay.addWidget(lbl_nueva)

        lbl_fi = QLabel("Fecha inicio:")
        lbl_fi.setStyleSheet(f"color: {C.TEXT2}; font-size: 12px; background: transparent;")
        form_lay.addWidget(lbl_fi)
        self._fecha = QDateEdit(QDate.currentDate())
        self._fecha.setCalendarPopup(True)
        self._fecha.setDisplayFormat("dd/MM/yyyy")
        form_lay.addWidget(self._fecha)

        dias_row = QHBoxLayout()
        lbl_dias = QLabel("Días:")
        lbl_dias.setStyleSheet(f"color: {C.TEXT2}; font-size: 12px; background: transparent;")
        self._spin_dias = QSpinBox()
        self._spin_dias.setRange(1, 90)
        self._spin_dias.setValue(1)
        dias_row.addWidget(lbl_dias)
        dias_row.addWidget(self._spin_dias)
        dias_row.addStretch()
        form_lay.addLayout(dias_row)

        # Fecha fin calculada
        self._lbl_fecha_fin = QLabel("Hasta: —")
        self._lbl_fecha_fin.setStyleSheet(
            f"color: {C.TEXT3}; font-size: 11px; background: transparent;"
        )
        form_lay.addWidget(self._lbl_fecha_fin)
        self._fecha.dateChanged.connect(self._update_fecha_fin)
        self._spin_dias.valueChanged.connect(self._update_fecha_fin)
        self._update_fecha_fin()

        form_lay.addStretch()

        btn_save = QPushButton("✓  Registrar")
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.setStyleSheet(f"""
            QPushButton {{
                background: {C.BLUE}; color: white;
                border: none; border-radius: 8px;
                padding: 8px 0; font-size: 13px; font-weight: 600;
            }}
            QPushButton:hover {{ background: {C.NAVY_600}; }}
            QPushButton:disabled {{ background: {C.BORDER}; color: {C.TEXT3}; }}
        """)
        btn_save.clicked.connect(self._save)
        form_lay.addWidget(btn_save)

        self._saved = SavedIndicator()
        form_lay.addWidget(self._saved)

        cols.addWidget(form_frame)

        # Columna der: tabla de licencias del estudiante
        tbl_frame = QVBoxLayout()
        tbl_frame.setSpacing(6)

        hdr_row = QHBoxLayout()
        self._lbl_tbl_titulo = QLabel("Licencias registradas")
        self._lbl_tbl_titulo.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {C.TEXT}; background: transparent;"
        )
        hdr_row.addWidget(self._lbl_tbl_titulo)
        hdr_row.addStretch()

        # Filtro activas/todas
        self._btn_activas = self._filter_btn("Activas", True)
        self._btn_todas   = self._filter_btn("Todas",   False)
        self._btn_activas.clicked.connect(lambda: self._set_filtro("activas"))
        self._btn_todas.clicked.connect(lambda: self._set_filtro("todas"))
        hdr_row.addWidget(self._btn_activas)
        hdr_row.addWidget(self._btn_todas)
        tbl_frame.addLayout(hdr_row)

        self._tbl_lic = QTableWidget()
        self._tbl_lic.setColumnCount(4)
        self._tbl_lic.setHorizontalHeaderLabels(["Desde", "Hasta", "Días", "Estado"])
        self._tbl_lic.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents)
        self._tbl_lic.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents)
        self._tbl_lic.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents)
        self._tbl_lic.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch)
        self._tbl_lic.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tbl_lic.verticalHeader().setVisible(False)
        self._tbl_lic.setAlternatingRowColors(True)
        self._tbl_lic.setShowGrid(False)
        self._tbl_lic.verticalHeader().setDefaultSectionSize(32)
        self._tbl_lic.setStyleSheet(_LIC_TBL_STYLE)
        tbl_frame.addWidget(self._tbl_lic)

        cols.addLayout(tbl_frame, stretch=1)
        root.addLayout(cols, stretch=1)

        self._filtro = "activas"

    def _filter_btn(self, label: str, active: bool) -> QPushButton:
        btn = QPushButton(label)
        btn.setCheckable(True)
        btn.setChecked(active)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(26)
        self._style_filter_btn(btn)
        return btn

    def _style_filter_btn(self, btn: QPushButton):
        if btn.isChecked():
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {C.BLUE}; color: white;
                    border: none; border-radius: 7px; padding: 0 12px; font-size: 11px;
                }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {C.TEXT2};
                    border: 1px solid {C.BORDER}; border-radius: 7px;
                    padding: 0 12px; font-size: 11px;
                }}
                QPushButton:hover {{ background: {C.SURFACE2}; }}
            """)

    def _set_filtro(self, filtro: str):
        self._filtro = filtro
        self._btn_activas.setChecked(filtro == "activas")
        self._btn_todas.setChecked(filtro == "todas")
        self._style_filter_btn(self._btn_activas)
        self._style_filter_btn(self._btn_todas)
        self._refresh_tabla()

    def _update_fecha_fin(self):
        from datetime import date as _d, timedelta
        fi  = self._fecha.date().toPyDate()
        dias = self._spin_dias.value()
        ff  = fi + timedelta(days=dias - 1)
        self._lbl_fecha_fin.setText(f"Hasta: {ff.strftime('%d/%m/%Y')}")

    def _on_run_entered(self):
        run = utils.normalizar_run(self._inp_run.text().strip())
        if utils.validar_run(run):
            self._select_student(run)
            self._inp_run.clear()

    def _select_student(self, run: str):
        st = db.get_student(run)
        if not st:
            self._saved.show_error("✗  Estudiante no encontrado")
            return
        self._current_run = run
        ap = f"{st.get('apellido_paterno','') or ''} {st.get('apellido_materno','') or ''}".strip()
        self._lbl_student.setText(
            f"✓  {utils.run_display(run)}  ·  {ap}, {st.get('nombres','')}"
        )
        self._lbl_student.setStyleSheet(
            f"font-size: 14px; color: {C.TEXT}; font-weight: 600; background: transparent;"
        )
        self._refresh_tabla()

    def _refresh_tabla(self):
        if not self._current_run:
            self._tbl_lic.setRowCount(0)
            return
        try:
            rows = db.get_licencias_estudiante(self._current_run)
        except Exception:
            rows = []

        if self._filtro == "activas":
            rows = [r for r in rows if r["activa"]]

        self._tbl_lic.setRowCount(len(rows))
        hoy = date.today()
        from datetime import timedelta
        for i, r in enumerate(rows):
            fi_str = r["fecha_inicio"] or ""
            ff_str = r["fecha_fin"]    or ""
            activa = bool(r["activa"])

            # Calcular días
            try:
                fi = date.fromisoformat(fi_str)
                ff = date.fromisoformat(ff_str)
                dias_str = str((ff - fi).days + 1)
                fi_fmt = fi.strftime("%d/%m/%Y")
                ff_fmt = ff.strftime("%d/%m/%Y")
            except Exception:
                dias_str = "—"
                fi_fmt = fi_str
                ff_fmt = ff_str

            # Estado
            if activa:
                ff_d = date.fromisoformat(ff_str) if ff_str else hoy
                restantes = (ff_d - hoy).days
                estado = f"Activa — vence en {restantes}d" if restantes > 0 else "Vence hoy"
                color_estado = C.GREEN
            else:
                estado = "Vencida"
                color_estado = C.TEXT3

            for j, v in enumerate([fi_fmt, ff_fmt, dias_str, estado]):
                it = QTableWidgetItem(v)
                if j == 3:
                    it.setForeground(QColor(color_estado))
                    if activa:
                        it.setFont(self._bold_font())
                if not activa:
                    it.setForeground(QColor(C.TEXT3))
                self._tbl_lic.setItem(i, j, it)

    def _bold_font(self):
        from PyQt6.QtGui import QFont
        f = QFont()
        f.setBold(True)
        return f

    def _save(self):
        if not self._current_run:
            self._saved.show_error("✗  Selecciona un estudiante primero")
            return
        fecha_i = self._fecha.date().toString("yyyy-MM-dd")
        dias    = self._spin_dias.value()
        from datetime import date as _d, timedelta
        fecha_f = (_d.fromisoformat(fecha_i) + timedelta(days=dias - 1)).isoformat()
        try:
            db.add_student_suspension(
                self._current_run, fecha_i, fecha_f,
                f"Licencia médica {dias} día{'s' if dias != 1 else ''}",
                "licencia"
            )
            self._saved.show_saved("✓  Licencia registrada")
            sound.save()
            self._refresh_tabla()
        except Exception as e:
            self._saved.show_error(f"✗  {e}")


# ─────────────────────────────────────────────────────────────────────────────
#  Tab de Firma de Apoderado (#17)
# ─────────────────────────────────────────────────────────────────────────────

class _FirmaTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_run: str | None = None
        self._pases_data: list = []
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet(f"background: {C.BG};")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        root.addWidget(SectionHeader("Firma de Apoderado"))

        # Barra de búsqueda + campo RUN
        self._search = _NameSearch()
        self._search.run_selected.connect(self._load_pases)
        root.addWidget(self._search)

        run_row = QHBoxLayout()
        self._inp_run = RUNLineEdit()
        self._inp_run.setPlaceholderText("O escribir RUN y presionar Enter…")
        self._inp_run.setStyleSheet(f"""
            QLineEdit {{
                background: {C.SURFACE}; border: 1.5px solid {C.BORDER};
                border-radius: 10px; padding: 8px 14px;
                font-size: 16px; color: {C.TEXT};
            }}
        """)
        self._inp_run.returnPressed.connect(self._on_run_entered)
        self._inp_run.scan_ready.connect(self._on_run_entered)
        run_row.addWidget(self._inp_run)
        root.addLayout(run_row)

        # Info + stats del estudiante
        self._lbl_student = QLabel("Busca un estudiante para ver sus pases")
        self._lbl_student.setStyleSheet(
            f"font-size: 14px; color: {C.TEXT2}; background: transparent;"
        )
        root.addWidget(self._lbl_student)

        # Stats row
        stats_row = QHBoxLayout()
        stats_row.setSpacing(20)
        self._kpi_total     = self._kpi("Total", "—")
        self._kpi_firmados  = self._kpi("Firmados", "—", C.GREEN)
        self._kpi_pendiente = self._kpi("Sin firma", "—", C.AMBER)
        for k in (self._kpi_total, self._kpi_firmados, self._kpi_pendiente):
            stats_row.addLayout(k[0])
        stats_row.addStretch()
        root.addLayout(stats_row)

        root.addWidget(HDivider())

        # Lista de pases pendientes
        lbl_pend = QLabel("Pases pendientes de firma:")
        lbl_pend.setStyleSheet(f"font-size: 12px; color: {C.TEXT3}; background: transparent;")
        root.addWidget(lbl_pend)

        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.setStyleSheet(f"""
            QListWidget {{
                background: {C.SURFACE}; border: 1.5px solid {C.BORDER};
                border-radius: 12px; font-size: 13px; color: {C.TEXT};
                outline: none;
            }}
            QListWidget::item {{ padding: 10px 14px; border-bottom: 1px solid {C.BORDER}; }}
            QListWidget::item:selected {{ background: {C.BLUE_DIM}; color: {C.BLUE}; }}
        """)
        root.addWidget(self._list, stretch=1)

        # Botón firmar
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._btn_firmar = AButton("✓  Firmar seleccionado", sound_type="save")
        self._btn_firmar.setEnabled(False)
        self._btn_firmar.setStyleSheet(f"""
            QPushButton {{
                background: {C.GREEN}; color: white;
                border: none; border-radius: 10px;
                padding: 10px 24px; font-size: 13px; font-weight: 600;
            }}
            QPushButton:hover {{ background: #2DB34A; }}
            QPushButton:disabled {{ background: {C.BORDER}; color: {C.TEXT3}; }}
        """)
        self._btn_firmar.clicked.connect(self._firmar_seleccionado)
        btn_row.addWidget(self._btn_firmar)
        root.addLayout(btn_row)

        self._list.itemSelectionChanged.connect(
            lambda: self._btn_firmar.setEnabled(bool(self._list.selectedItems()))
        )

        self._saved = SavedIndicator()
        root.addWidget(self._saved)

    def _kpi(self, label: str, val: str, color: str = C.TEXT):
        lay = QVBoxLayout()
        lay.setSpacing(2)
        v = QLabel(val)
        v.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {color}; background: transparent;")
        l = QLabel(label)
        l.setStyleSheet(f"font-size: 10px; color: {C.TEXT3}; background: transparent;")
        lay.addWidget(v)
        lay.addWidget(l)
        return (lay, v)

    def _on_run_entered(self):
        run = utils.normalizar_run(self._inp_run.text().strip())
        if utils.validar_run(run):
            self._load_pases(run)
            self._inp_run.clear()

    def _load_pases(self, run: str):
        self._current_run = run
        st = db.get_student(run)
        if not st:
            self._saved.show_error("✗  Estudiante no encontrado")
            return
        ap = f"{st.get('apellido_paterno','') or ''} {st.get('apellido_materno','') or ''}".strip()
        self._lbl_student.setText(
            f"{utils.run_display(run)}  ·  {ap}, {st.get('nombres','')}  "
            f"·  {db.display_curso(st.get('curso',''), db.get_cursos_nombres_map()) or ''}"
        )
        self._lbl_student.setStyleSheet(
            f"font-size: 14px; color: {C.TEXT}; font-weight: 600; background: transparent;"
        )

        stats = db.get_pases_estudiante(run)
        self._kpi_total[1].setText(str(stats["total"]))
        self._kpi_firmados[1].setText(str(stats["firmados"]))
        self._kpi_pendiente[1].setText(str(stats["sin_firmar"]))

        # Listar pases pendientes
        self._list.clear()
        self._pases_data = []
        for p in stats["pases"]:
            if p["firmado"]:
                continue
            tipo_lbl  = _TIPO_LABEL.get(p["tipo"], p["tipo"])
            fecha_txt = p["fecha_inicio"]
            motivo    = p.get("motivo", "") or ""
            texto     = f"{fecha_txt}  ·  {tipo_lbl}  —  {motivo[:50]}"
            item = QListWidgetItem(texto)
            item.setData(Qt.ItemDataRole.UserRole, p["id"])
            self._list.addItem(item)
            self._pases_data.append(p)

        if self._list.count() == 0:
            placeholder = QListWidgetItem("✓  Sin pases pendientes de firma")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self._list.addItem(placeholder)

    def _firmar_seleccionado(self):
        items = self._list.selectedItems()
        if not items:
            return
        pase_id = items[0].data(Qt.ItemDataRole.UserRole)
        if pase_id is None:
            return

        firmado_por = self._dialogo_firma(pase_id)
        if firmado_por is None:
            return   # cancelado

        try:
            db.firmar_pase(pase_id, firmado_por)
            self._saved.show_saved(f"✓  Pase firmado — {firmado_por}")
            sound.save()
            if self._current_run:
                self._load_pases(self._current_run)
        except Exception as e:
            self._saved.show_error(f"✗  {e}")

    def _dialogo_firma(self, pase_id: int) -> str | None:
        """
        Diálogo modal para seleccionar quién firma y con qué vínculo.
        Retorna el string de firmado_por, o None si se cancela.
        """
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QRadioButton,
            QButtonGroup, QLineEdit, QDialogButtonBox, QLabel as _QL, QFrame as _QF,
        )

        dlg = QDialog(self)
        dlg.setWindowTitle("Confirmar firma de apoderado")
        dlg.setMinimumWidth(380)
        dlg.setStyleSheet(f"background: {C.BG};")

        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)

        titulo = _QL("¿Quién firma?")
        titulo.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {C.TEXT}; background: transparent;")
        lay.addWidget(titulo)

        sub = _QL(f"Pase #{pase_id}")
        sub.setStyleSheet(f"font-size: 12px; color: {C.TEXT3}; background: transparent;")
        lay.addWidget(sub)

        sep = _QF(); sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {C.BORDER};")
        lay.addWidget(sep)

        # Radio buttons
        _radio_style = f"QRadioButton {{ color: {C.TEXT}; font-size: 14px; background: transparent; }}"
        self._rg = QButtonGroup(dlg)

        rb1 = QRadioButton("Apoderado principal")
        rb1.setStyleSheet(_radio_style)
        rb1.setChecked(True)
        rb2 = QRadioButton("Apoderado suplente")
        rb2.setStyleSheet(_radio_style)
        rb3 = QRadioButton("Otro…")
        rb3.setStyleSheet(_radio_style)

        for rb in (rb1, rb2, rb3):
            self._rg.addButton(rb)
            lay.addWidget(rb)

        # Campo libre para "Otro"
        self._inp_otro = QLineEdit()
        self._inp_otro.setPlaceholderText("Nombre y vínculo  (ej: tío Juan Pérez)")
        self._inp_otro.setEnabled(False)
        self._inp_otro.setStyleSheet(f"""
            QLineEdit {{
                background: {C.SURFACE}; border: 1.5px solid {C.BORDER};
                border-radius: 8px; padding: 7px 12px;
                font-size: 13px; color: {C.TEXT};
            }}
            QLineEdit:disabled {{ background: {C.SURFACE2}; color: {C.TEXT3}; }}
        """)
        lay.addWidget(self._inp_otro)

        rb3.toggled.connect(self._inp_otro.setEnabled)
        rb3.toggled.connect(lambda on: self._inp_otro.setFocus() if on else None)

        # Botones
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("✓  Firmar")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None

        if rb1.isChecked():
            return "Apoderado principal"
        if rb2.isChecked():
            return "Apoderado suplente"
        # rb3
        nombre = self._inp_otro.text().strip()
        return nombre if nombre else "Otro"


# ─────────────────────────────────────────────────────────────────────────────
#  Tab de Notificaciones WhatsApp (#19)
# ─────────────────────────────────────────────────────────────────────────────

_TBL_STYLE_NOTIF = f"""
    QTableWidget {{
        background: {C.SURFACE}; border: none;
        border-radius: 12px; outline: none;
    }}
    QTableWidget::item {{ padding: 6px 10px; border: none; }}
    QTableWidget::item:selected {{ background: {C.BLUE_DIM}; color: {C.TEXT}; }}
    QTableWidget::item:alternate {{ background: {C.SURFACE2}; }}
    QHeaderView::section {{
        background: {C.SURFACE2}; color: {C.TEXT2};
        padding: 8px 10px; border: none;
        font-size: 11px; font-weight: 600;
    }}
"""

# Columnas tabla notificaciones
_COL_CHECK  = 0
_COL_RUN    = 1
_COL_NOMBRE = 2
_COL_CURSO  = 3
_COL_TIPO   = 4
_COL_TEL    = 5
_COL_ESTADO = 6


class _WASender(QObject):
    """Worker que envía WhatsApp en thread separado y emite resultados."""
    resultado = pyqtSignal(int, bool, str)   # (row, ok, msg)

    def enviar(self, row: int, run: str, hora: str):
        def _run():
            try:
                import whatsapp
                ok, msg = whatsapp.enviar_atraso(run, hora)
                self.resultado.emit(row, ok, msg)
            except Exception as e:
                self.resultado.emit(row, False, str(e)[:60])
        threading.Thread(target=_run, daemon=True, name=f"wa-notif-{row}").start()


class _NotificacionesTab(QWidget):
    """
    Centro de notificaciones WhatsApp — #19.
    Muestra pases del día (o semana), permite:
    - Seleccionar con checkbox
    - Enviar batch por WA
    - Editar teléfono inline
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sender    = _WASender()
        self._sender.resultado.connect(self._on_wa_result)
        self._row_data: list[dict] = []   # cache: run, hora, telefono, etc.
        self._phone_inputs: list[QLineEdit] = []
        self._periodo = "hoy"
        self._build_ui()
        self._cargar()

    def _build_ui(self):
        self.setStyleSheet(f"background: {C.BG};")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        root.addWidget(SectionHeader("Notificaciones WhatsApp"))

        # ── Fila controles ──────────────────────────────────
        ctrl = QHBoxLayout()
        ctrl.setSpacing(8)

        self._btn_hoy    = self._filter_btn("Hoy",    True)
        self._btn_semana = self._filter_btn("Semana", False)
        self._btn_hoy.clicked.connect(lambda: self._set_periodo("hoy"))
        self._btn_semana.clicked.connect(lambda: self._set_periodo("semana"))
        ctrl.addWidget(self._btn_hoy)
        ctrl.addWidget(self._btn_semana)

        ctrl.addWidget(HDivider() if False else self._vsep())   # separador visual

        btn_todos     = self._action_btn("☑  Seleccionar todos")
        btn_ninguno   = self._action_btn("☐  Deseleccionar")
        btn_sin_tel   = self._action_btn("✗  Sin teléfono")
        btn_todos.clicked.connect(self._select_all)
        btn_ninguno.clicked.connect(self._deselect_all)
        btn_sin_tel.clicked.connect(self._select_sin_tel)
        ctrl.addWidget(btn_todos)
        ctrl.addWidget(btn_ninguno)
        ctrl.addWidget(btn_sin_tel)

        ctrl.addStretch()

        self._lbl_count = QLabel("0 pases")
        self._lbl_count.setStyleSheet(
            f"font-size: 11px; color: {C.TEXT3}; background: transparent;"
        )
        ctrl.addWidget(self._lbl_count)

        btn_refresh = self._action_btn("↺  Actualizar")
        btn_refresh.clicked.connect(self._cargar)
        ctrl.addWidget(btn_refresh)

        root.addLayout(ctrl)

        # ── Tabla ───────────────────────────────────────────
        self._tbl = QTableWidget()
        self._tbl.setColumnCount(7)
        self._tbl.setHorizontalHeaderLabels(
            ["", "RUN", "Nombre", "Curso", "Tipo", "Teléfono apoderado", "Estado"]
        )
        hdr = self._tbl.horizontalHeader()
        hdr.setSectionResizeMode(_COL_NOMBRE, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(_COL_TEL,    QHeaderView.ResizeMode.ResizeToContents)
        for col in (_COL_CHECK, _COL_RUN, _COL_TIPO, _COL_ESTADO):
            hdr.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)

        self._tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tbl.verticalHeader().setVisible(False)
        self._tbl.setAlternatingRowColors(True)
        self._tbl.setShowGrid(False)
        self._tbl.verticalHeader().setDefaultSectionSize(38)
        self._tbl.setStyleSheet(_TBL_STYLE_NOTIF)
        root.addWidget(self._tbl, stretch=1)

        # ── Barra de envío ──────────────────────────────────
        send_row = QHBoxLayout()
        send_row.setSpacing(12)

        self._lbl_sel = QLabel("0 seleccionados")
        self._lbl_sel.setStyleSheet(
            f"font-size: 12px; color: {C.TEXT2}; background: transparent;"
        )
        send_row.addWidget(self._lbl_sel)
        send_row.addStretch()

        self._saved = SavedIndicator()
        send_row.addWidget(self._saved)

        self._btn_enviar = QPushButton("📱  Enviar seleccionados")
        self._btn_enviar.setEnabled(False)
        self._btn_enviar.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_enviar.setStyleSheet(f"""
            QPushButton {{
                background: #25D366; color: white;
                border: none; border-radius: 10px;
                padding: 10px 24px; font-size: 13px; font-weight: 700;
            }}
            QPushButton:hover {{ background: #1DA855; }}
            QPushButton:disabled {{ background: {C.BORDER}; color: {C.TEXT3}; }}
        """)
        self._btn_enviar.clicked.connect(self._enviar_seleccionados)
        send_row.addWidget(self._btn_enviar)

        root.addLayout(send_row)

        # Actualizar contador al cambiar checks
        self._tbl.itemChanged.connect(self._on_item_changed)

    # ── Helpers UI ────────────────────────────────────────────

    def _filter_btn(self, label: str, active: bool) -> QPushButton:
        btn = QPushButton(label)
        btn.setCheckable(True)
        btn.setChecked(active)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(30)
        self._apply_filter_style(btn)
        return btn

    def _apply_filter_style(self, btn: QPushButton):
        if btn.isChecked():
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: #25D366; color: white;
                    border: none; border-radius: 8px;
                    padding: 0 16px; font-size: 12px; font-weight: 600;
                }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {C.TEXT2};
                    border: 1px solid {C.BORDER}; border-radius: 8px;
                    padding: 0 16px; font-size: 12px;
                }}
                QPushButton:hover {{ background: {C.SURFACE2}; }}
            """)

    def _action_btn(self, label: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(28)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT2};
                border: 1px solid {C.BORDER}; border-radius: 7px;
                padding: 0 12px; font-size: 11px;
            }}
            QPushButton:hover {{ background: {C.SURFACE2}; color: {C.TEXT}; }}
        """)
        return btn

    def _vsep(self) -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        sep.setFixedHeight(22)
        sep.setStyleSheet(f"background: {C.BORDER};")
        return sep

    # ── Carga de datos ────────────────────────────────────────

    def _set_periodo(self, p: str):
        self._periodo = p
        self._btn_hoy.setChecked(p == "hoy")
        self._btn_semana.setChecked(p == "semana")
        self._apply_filter_style(self._btn_hoy)
        self._apply_filter_style(self._btn_semana)
        self._cargar()

    def _cargar(self):
        from datetime import date, timedelta
        today = date.today()
        if self._periodo == "hoy":
            desde = hasta = today.isoformat()
        else:
            lunes = today - timedelta(days=today.weekday())
            desde = lunes.isoformat()
            hasta = today.isoformat()

        try:
            rows = db.get_pases_periodo(desde, hasta, tipo="atraso")
        except Exception:
            rows = []

        self._row_data.clear()
        self._phone_inputs.clear()
        self._tbl.blockSignals(True)
        self._tbl.setRowCount(0)
        self._tbl.setRowCount(len(rows))

        _map = db.get_cursos_nombres_map()

        for i, r in enumerate(rows):
            run   = r["run"]
            ap    = f"{r['apellido_paterno'] or ''} {r['apellido_materno'] or ''}".strip()
            nombre = f"{ap}, {r['nombres'] or ''}".strip(", ")
            curso  = db.display_curso(r["curso"] or "", _map) or "—"
            tipo   = r["tipo"] or "atraso"
            tel    = r["telefono_apoderado"] or ""
            creado = r["creado_en"] or ""
            hora   = creado[11:16] if len(creado) >= 16 else datetime.now().strftime("%H:%M")

            self._row_data.append({
                "run":    run,
                "hora":   hora,
                "tel":    tel,
                "nombre": nombre,
            })

            # Col 0 — checkbox
            chk = QTableWidgetItem()
            chk.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable |
                Qt.ItemFlag.ItemIsEnabled |
                Qt.ItemFlag.ItemIsSelectable
            )
            chk.setCheckState(Qt.CheckState.Unchecked)
            self._tbl.setItem(i, _COL_CHECK, chk)

            # Col 1–4
            for col, val in [(_COL_RUN, utils.run_display(run)), (_COL_NOMBRE, nombre),
                              (_COL_CURSO, curso), (_COL_TIPO, tipo.capitalize())]:
                it = QTableWidgetItem(val)
                if col == _COL_TIPO:
                    it.setForeground(QColor(C.AMBER))
                    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._tbl.setItem(i, col, it)

            # Col 5 — Teléfono (editable inline con auto-formato chileno)
            tel_inp = PhoneLineEdit()
            tel_inp.set_phone(tel)
            tel_inp.setStyleSheet(f"""
                QLineEdit {{
                    background: transparent; border: none;
                    font-size: 13px; color: {C.TEXT if tel else C.RED};
                    padding: 2px 8px;
                }}
                QLineEdit:focus {{
                    background: {C.SURFACE2};
                    border: 1px solid {C.BLUE};
                    border-radius: 6px; color: {C.TEXT};
                }}
            """)
            row_idx = i   # captura para closure
            tel_inp.editingFinished.connect(
                lambda r=run, idx=row_idx: self._save_tel(r, idx)
            )
            self._tbl.setCellWidget(i, _COL_TEL, tel_inp)
            self._phone_inputs.append(tel_inp)

            # Col 6 — Estado
            est_it = QTableWidgetItem("—")
            est_it.setForeground(QColor(C.TEXT3))
            est_it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._tbl.setItem(i, _COL_ESTADO, est_it)

        self._tbl.blockSignals(False)
        self._lbl_count.setText(f"{len(rows)} pase{'s' if len(rows) != 1 else ''}")
        self._update_send_btn()

    # ── Selección ─────────────────────────────────────────────

    def _select_all(self):
        self._tbl.blockSignals(True)
        for i in range(self._tbl.rowCount()):
            chk = self._tbl.item(i, _COL_CHECK)
            if chk:
                chk.setCheckState(Qt.CheckState.Checked)
        self._tbl.blockSignals(False)
        self._update_send_btn()

    def _deselect_all(self):
        self._tbl.blockSignals(True)
        for i in range(self._tbl.rowCount()):
            chk = self._tbl.item(i, _COL_CHECK)
            if chk:
                chk.setCheckState(Qt.CheckState.Unchecked)
        self._tbl.blockSignals(False)
        self._update_send_btn()

    def _select_sin_tel(self):
        """Selecciona automáticamente los que no tienen teléfono (para editarlos)."""
        self._tbl.blockSignals(True)
        for i, d in enumerate(self._row_data):
            tel = self._phone_inputs[i].text().strip() if i < len(self._phone_inputs) else d["tel"]
            chk = self._tbl.item(i, _COL_CHECK)
            if chk:
                chk.setCheckState(
                    Qt.CheckState.Checked if not tel else Qt.CheckState.Unchecked
                )
        self._tbl.blockSignals(False)
        self._update_send_btn()

    def _on_item_changed(self, item: QTableWidgetItem):
        if item.column() == _COL_CHECK:
            self._update_send_btn()

    def _update_send_btn(self):
        n = self._count_checked()
        self._lbl_sel.setText(f"{n} seleccionado{'s' if n != 1 else ''}")
        self._btn_enviar.setEnabled(n > 0)

    def _count_checked(self) -> int:
        return sum(
            1 for i in range(self._tbl.rowCount())
            if (it := self._tbl.item(i, _COL_CHECK))
            and it.checkState() == Qt.CheckState.Checked
        )

    # ── Guardar teléfono inline ───────────────────────────────

    def _save_tel(self, run: str, row_idx: int):
        if row_idx >= len(self._phone_inputs):
            return
        tel = self._phone_inputs[row_idx].text().strip()
        try:
            db.update_student_telefono_apoderado(run, tel)
            # Actualizar color
            self._phone_inputs[row_idx].setStyleSheet(f"""
                QLineEdit {{
                    background: transparent; border: none;
                    font-size: 13px; color: {C.TEXT if tel else C.RED};
                    padding: 2px 8px;
                }}
                QLineEdit:focus {{
                    background: {C.SURFACE2};
                    border: 1px solid {C.BLUE};
                    border-radius: 6px; color: {C.TEXT};
                }}
            """)
        except Exception:
            pass

    # ── Envío batch ───────────────────────────────────────────

    def _enviar_seleccionados(self):
        self._btn_enviar.setEnabled(False)
        pendientes = 0
        for i, d in enumerate(self._row_data):
            chk = self._tbl.item(i, _COL_CHECK)
            if not chk or chk.checkState() != Qt.CheckState.Checked:
                continue
            # Teléfono actualizado (puede haberse editado inline)
            tel = self._phone_inputs[i].text().strip() if i < len(self._phone_inputs) else d["tel"]
            if not tel:
                est = self._tbl.item(i, _COL_ESTADO)
                if est:
                    est.setText("✗ Sin número")
                    est.setForeground(QColor(C.RED))
                continue
            # Mostrar "Enviando…"
            est = self._tbl.item(i, _COL_ESTADO)
            if est:
                est.setText("…")
                est.setForeground(QColor(C.TEXT3))
            self._sender.enviar(i, d["run"], d["hora"])
            pendientes += 1

        if pendientes == 0:
            self._saved.show_error("✗  Ningún seleccionado tiene teléfono")
            self._btn_enviar.setEnabled(True)
        else:
            self._saved.show_saved(f"Enviando {pendientes} mensaje{'s' if pendientes > 1 else ''}…")

    def _on_wa_result(self, row: int, ok: bool, msg: str):
        est = self._tbl.item(row, _COL_ESTADO)
        if est:
            if ok:
                est.setText("✓ Enviado")
                est.setForeground(QColor(C.GREEN))
            else:
                est.setText(f"⟳ {msg[:20]}")
                est.setForeground(QColor(C.AMBER))
        # Decheck fila enviada
        chk = self._tbl.item(row, _COL_CHECK)
        if chk:
            self._tbl.blockSignals(True)
            chk.setCheckState(Qt.CheckState.Unchecked)
            self._tbl.blockSignals(False)
        self._update_send_btn()
        if self._count_checked() == 0:
            self._btn_enviar.setEnabled(False)
            self._saved.show_saved("✓  Envíos completados")
            sound.save()

    def showEvent(self, event):
        super().showEvent(event)
        self._cargar()


# ─────────────────────────────────────────────────────────────────────────────
#  Pantalla principal: InspectoriaScreen
# ─────────────────────────────────────────────────────────────────────────────

class InspectoriaScreen(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        cfg = db.get_all_config()
        self._threshold = int(cfg.get("insp_threshold_sinfirma", str(_DEFAULT_THRESHOLD)))
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet(f"background: {C.BG};")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                border-top: 3px solid {C.AMBER};
                background: {C.BG};
            }}
            QTabBar::tab {{
                background: {C.SURFACE};
                color: {C.TEXT2};
                border: none;
                border-bottom: 3px solid transparent;
                padding: 10px 22px;
                font-size: 13px;
                font-weight: 500;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background: {C.BG};
                color: {C.TEXT};
                font-weight: 700;
                border-bottom: 3px solid {C.AMBER};
            }}
            QTabBar::tab:hover:!selected {{
                background: {C.SURFACE2};
                color: {C.TEXT};
            }}
        """)

        self._tab_atraso  = _PaseTab("atraso",       self._threshold)
        self._tab_inasis  = _PaseTab("inasistencia",  self._threshold)
        self._tab_retiro  = _PaseTab("retiro",        self._threshold)
        self._tab_firma   = _FirmaTab()
        self._tab_lic     = _LicenciasTab()
        self._tab_notif   = _NotificacionesTab()

        self._tabs.addTab(self._tab_atraso,  "Atrasos")
        self._tabs.addTab(self._tab_inasis,  "Inasistencias")
        self._tabs.addTab(self._tab_retiro,  "Retiros")
        self._tabs.addTab(self._tab_firma,   "Firma Apoderado")
        self._tabs.addTab(self._tab_lic,     "Licencias")
        self._tabs.addTab(self._tab_notif,   "Notif. WhatsApp")

        root.addWidget(self._tabs)

    def showEvent(self, event):
        super().showEvent(event)
        # Foco al scanner del tab activo
        idx = self._tabs.currentIndex()
        tab = self._tabs.widget(idx)
        if hasattr(tab, "_inp"):
            QTimer.singleShot(100, tab._inp.setFocus)

    def refresh_period(self):
        """Llamado por main_window cuando el usuario cambia el período visualizado."""
        # Recarga la tabla de firma (depende del período) y notificaciones
        if hasattr(self._tab_firma, "_load_pendientes"):
            self._tab_firma._load_pendientes()
        if hasattr(self._tab_notif, "_load_atrasos"):
            self._tab_notif._load_atrasos()
