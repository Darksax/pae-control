"""
suspensions_screen.py — Justificaciones MiAppoderado

Registra suspensiones, licencias médicas, retiros y atrasos.
Cada tipo excusa las ausencias al PAE en el rango de fechas registrado.

Tabs:
  1. Suspensiones       — disciplinarias
  2. Licencias Médicas  — reposo médico
  3. Retiros            — retiro temporal del colegio
  4. Atrasos            — llegada tarde (usar misma fecha en inicio y fin)
  5. Justificar comidas — justifica comidas específicas para cualquier tipo
"""

from datetime import date, timedelta
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QAbstractItemView, QLineEdit,
    QDateEdit, QPushButton, QSizePolicy, QTabWidget,
    QCheckBox, QComboBox, QScrollArea
)
from PyQt6.QtCore import Qt, QDate, QTimer
from PyQt6.QtGui import QColor

import db
import utils
from ui.theme   import C, sound
from ui.widgets import AButton, HDivider, SectionHeader, SavedIndicator, RUNLineEdit


# ── Calendario chileno ─────────────────────────────────────────────────────

_SEMANA_SANTA = {
    2024: [(3, 29), (3, 30)],
    2025: [(4, 18), (4, 19)],
    2026: [(4,  3), (4,  4)],
    2027: [(3, 26), (3, 27)],
    2028: [(4, 14), (4, 15)],
    2029: [(3, 30), (3, 31)],
    2030: [(4, 19), (4, 20)],
}

_FERIADOS_FIJOS = [
    (1,  1), (5,  1), (5, 21), (6, 20), (8, 15),
    (9, 18), (9, 19), (10, 12), (10, 31), (11,  1),
    (12,  8), (12, 25),
]


def _feriados_chile(year: int) -> set:
    dias = {date(year, m, d) for m, d in _FERIADOS_FIJOS}
    for m, d in _SEMANA_SANTA.get(year, []):
        dias.add(date(year, m, d))
    return dias


def _calc_end_date(start: date, n_dias: int, habiles: bool) -> date:
    if not habiles:
        return start + timedelta(days=n_dias - 1)
    feriados = _feriados_chile(start.year) | _feriados_chile(start.year + 1)
    current = start
    counted = 1
    while counted < n_dias:
        current += timedelta(days=1)
        if current.weekday() < 5 and current not in feriados:
            counted += 1
    return current


# ── Config por tipo ────────────────────────────────────────────────────────

TIPOS = {
    'suspension': {
        'label':    'Suspensiones',
        'color':    C.RED,
        'dim':      C.RED_DIM,
        'btn_text': 'Registrar suspensión',
        'sub':      'Registra días de suspensión disciplinaria. Las ausencias al PAE no generan strikes.',
    },
    'licencia': {
        'label':    'Lic. Médicas',
        'color':    C.BLUE,
        'dim':      C.BLUE_DIM,
        'btn_text': 'Registrar licencia',
        'sub':      'Registra licencias médicas. El estudiante queda excusado del PAE durante el reposo.',
    },
    'retiro': {
        'label':    'Retiros',
        'color':    C.AMBER,
        'dim':      '#3a2d0a',
        'btn_text': 'Registrar retiro',
        'sub':      'Registra retiros temporales del establecimiento. Las ausencias quedan excusadas.',
    },
    'atraso': {
        'label':    'Atrasos',
        'color':    C.GREEN,
        'dim':      '#0a2d1a',
        'btn_text': 'Registrar atraso',
        'sub':      'Registra atrasos. Usa la misma fecha en inicio y fin para un día puntual.',
    },
}


# ══════════════════════════════════════════════════════
#  TAB DE REGISTRO (Suspensiones / Licencias / Retiros / Atrasos)
# ══════════════════════════════════════════════════════

class _SuspensionTab(QWidget):
    """Widget reutilizable para cada tipo de justificación de rango."""

    def __init__(self, tipo: str, parent=None):
        super().__init__(parent)
        self._tipo         = tipo
        self._cfg          = TIPOS[tipo]
        self._selected_run = None
        self._mode_habiles = False
        self._manual_end   = False
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(250)
        self._debounce.timeout.connect(self._run_search)
        self._build_ui()
        self._load_active()

    def _build_ui(self):
        self.setStyleSheet(f"background: {C.BG};")
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(14)

        # Sub-título
        sub = QLabel(self._cfg['sub'])
        sub.setWordWrap(True)
        sub.setStyleSheet(f"font-size: 12px; color: {C.TEXT3}; background: transparent;")
        root.addWidget(sub)

        # ── Dos columnas ─────────────────────────────
        cols = QHBoxLayout()
        cols.setSpacing(16)

        # ── LEFT: búsqueda ───────────────────────────
        left = QVBoxLayout()
        left.setSpacing(10)
        left.addWidget(SectionHeader("Buscar estudiante"))

        search_bar = QFrame()
        search_bar.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border: none;
                border-radius: 12px;
            }}
        """)
        sb_lay = QHBoxLayout(search_bar)
        sb_lay.setContentsMargins(12, 8, 12, 8)
        sb_lay.setSpacing(8)

        lupa = QLabel("⌕")
        lupa.setStyleSheet(f"font-size: 16px; color: {C.TEXT3}; background: transparent;")
        sb_lay.addWidget(lupa)

        self._inp_search = QLineEdit()
        self._inp_search.setPlaceholderText("RUN, nombre o curso…")
        self._inp_search.setStyleSheet(f"""
            QLineEdit {{
                background: transparent; border: none;
                font-size: 13px; color: {C.TEXT};
            }}
        """)
        self._inp_search.textChanged.connect(self._on_text_changed)
        self._inp_search.returnPressed.connect(self._run_search)
        sb_lay.addWidget(self._inp_search, stretch=1)
        left.addWidget(search_bar)

        self._tbl_search = QTableWidget()
        self._tbl_search.setColumnCount(4)
        self._tbl_search.setHorizontalHeaderLabels(["RUN", "Apellidos", "Nombres", "Curso"])
        self._tbl_search.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._tbl_search.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._tbl_search.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tbl_search.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tbl_search.verticalHeader().setVisible(False)
        self._tbl_search.setAlternatingRowColors(True)
        self._tbl_search.setShowGrid(False)
        self._tbl_search.verticalHeader().setDefaultSectionSize(34)
        self._tbl_search.setStyleSheet(self._table_style())
        self._tbl_search.itemSelectionChanged.connect(self._on_student_selected)
        left.addWidget(self._tbl_search, stretch=1)

        cols.addLayout(left, stretch=1)

        # ── RIGHT: formulario ────────────────────────
        right_card = QFrame()
        right_card.setFixedWidth(300)
        right_card.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border: none;
                border-radius: 14px;
            }}
        """)
        form_lay = QVBoxLayout(right_card)
        form_lay.setContentsMargins(20, 16, 20, 16)
        form_lay.setSpacing(12)

        form_lay.addWidget(SectionHeader(f"Registrar {self._cfg['label'].lower().rstrip('s')}"))

        self._lbl_selected = QLabel("Sin estudiante seleccionado")
        self._lbl_selected.setWordWrap(True)
        self._lbl_selected.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {C.TEXT3}; background: transparent;"
        )
        form_lay.addWidget(self._lbl_selected)
        form_lay.addWidget(HDivider())

        # Fecha inicio
        form_lay.addWidget(self._flabel("Desde"))
        self._date_inicio = QDateEdit()
        self._date_inicio.setCalendarPopup(True)
        self._date_inicio.setDate(QDate.currentDate())
        self._date_inicio.setDisplayFormat("dd/MM/yyyy")
        form_lay.addWidget(self._date_inicio)

        # Toggle Corridos / Hábiles
        form_lay.addWidget(self._flabel("Tipo de días"))
        mode_row = QHBoxLayout()
        mode_row.setSpacing(6)
        self._btn_corridos = AButton("Corridos", sound_type="click")
        self._btn_habiles  = AButton("Hábiles",  sound_type="click")
        for btn in (self._btn_corridos, self._btn_habiles):
            btn.setFixedHeight(28)
        self._btn_corridos.clicked.connect(lambda: self._set_mode(False))
        self._btn_habiles.clicked.connect( lambda: self._set_mode(True))
        mode_row.addWidget(self._btn_corridos)
        mode_row.addWidget(self._btn_habiles)
        mode_row.addStretch()
        form_lay.addLayout(mode_row)

        # Duración rápida
        form_lay.addWidget(self._flabel("Duración rápida"))
        dur_row = QHBoxLayout()
        dur_row.setSpacing(6)
        _dur_style = f"""
            QPushButton {{
                background: {C.SURFACE2}; color: {C.TEXT2};
                border: 1px solid {C.BORDER}; border-radius: 7px;
                padding: 4px 9px; font-size: 11px; font-weight: 600;
            }}
            QPushButton:hover {{ background: {C.NAVY_700}; color: {C.TEXT}; }}
        """
        for label, days in [("1 día", 1), ("3 días", 3), ("5 días", 5), ("7 días", 7)]:
            btn = AButton(label, sound_type="click")
            btn.setStyleSheet(_dur_style)
            btn.clicked.connect(lambda checked, d=days: self._set_duration(d))
            dur_row.addWidget(btn)
        dur_row.addStretch()
        form_lay.addLayout(dur_row)

        self._lbl_fin_calc = QLabel("Selecciona duración rápida")
        self._lbl_fin_calc.setStyleSheet(
            f"font-size: 12px; color: {C.TEXT3}; background: transparent; font-style: italic;"
        )
        form_lay.addWidget(self._lbl_fin_calc)

        # Fecha fin manual (toggle)
        self._btn_toggle_fin = AButton("Ingresar fecha fin manualmente ›", sound_type="click")
        self._btn_toggle_fin.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.BLUE}; border: none;
                padding: 0 2px; font-size: 11px; font-weight: 500; text-align: left;
            }}
            QPushButton:hover {{ color: {C.TEXT}; }}
        """)
        self._btn_toggle_fin.clicked.connect(self._toggle_manual_end)
        form_lay.addWidget(self._btn_toggle_fin)

        self._lbl_hasta = self._flabel("Hasta")
        self._lbl_hasta.setVisible(False)
        form_lay.addWidget(self._lbl_hasta)

        self._date_fin = QDateEdit()
        self._date_fin.setCalendarPopup(True)
        self._date_fin.setDate(QDate.currentDate())
        self._date_fin.setDisplayFormat("dd/MM/yyyy")
        self._date_fin.setVisible(False)
        form_lay.addWidget(self._date_fin)

        QTimer.singleShot(50, lambda: self._set_mode(False))

        # Motivo
        form_lay.addWidget(self._flabel("Motivo (opcional)"))
        self._inp_motivo = QLineEdit()
        self._inp_motivo.setPlaceholderText("Ej: art. 33 RICE, reposo médico, tardanza…")
        form_lay.addWidget(self._inp_motivo)

        form_lay.addSpacing(4)

        color = self._cfg['color']
        dim   = self._cfg['dim']

        self._btn_save = AButton(self._cfg['btn_text'], sound_type="save")
        self._btn_save.setEnabled(False)
        self._btn_save.setStyleSheet(self._btn_save_style(False))
        self._btn_save.clicked.connect(self._save)
        form_lay.addWidget(self._btn_save)

        self._saved_ind = SavedIndicator()
        form_lay.addWidget(self._saved_ind)
        form_lay.addStretch()

        cols.addWidget(right_card)
        root.addLayout(cols)

        # ── Tabla activos ─────────────────────────────
        act_hdr = QHBoxLayout()
        act_hdr.addWidget(SectionHeader(f"{self._cfg['label']} activos y próximos"))
        act_hdr.addStretch()
        btn_refresh = AButton("↻", sound_type="click")
        btn_refresh.setFixedSize(30, 28)
        btn_refresh.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT3};
                border: 1px solid {C.BORDER}; border-radius: 6px; font-size: 13px;
            }}
            QPushButton:hover {{ background: {C.SURFACE2}; color: {C.TEXT}; }}
        """)
        btn_refresh.clicked.connect(self._load_active)
        act_hdr.addWidget(btn_refresh)
        root.addLayout(act_hdr)

        self._tbl_active = QTableWidget()
        self._tbl_active.setColumnCount(7)
        self._tbl_active.setHorizontalHeaderLabels(
            ["RUN", "Apellidos", "Curso", "Desde", "Hasta", "Motivo", ""]
        )
        self._tbl_active.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._tbl_active.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self._tbl_active.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tbl_active.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tbl_active.verticalHeader().setVisible(False)
        self._tbl_active.setAlternatingRowColors(True)
        self._tbl_active.setShowGrid(False)
        self._tbl_active.setMaximumHeight(200)
        self._tbl_active.verticalHeader().setDefaultSectionSize(36)
        self._tbl_active.setStyleSheet(self._table_style())
        root.addWidget(self._tbl_active)

    # ── Datos ────────────────────────────────────────

    def _on_text_changed(self):
        self._debounce.start()

    def _run_search(self):
        query = self._inp_search.text().strip()
        if not query:
            self._tbl_search.setRowCount(0)
            return
        try:
            rows = db.search_students(query, limit=50)
        except Exception:
            rows = []
        self._tbl_search.setRowCount(len(rows))
        for i, s in enumerate(rows):
            run_fmt   = utils.run_display(s["run"])
            apellidos = f"{s['apellido_paterno'] or ''} {s['apellido_materno'] or ''}".strip()
            nombres   = s["nombres"] or ""
            curso     = s["curso"] or ""
            for col, txt in enumerate([run_fmt, apellidos, nombres, curso]):
                item = QTableWidgetItem(txt)
                item.setData(Qt.ItemDataRole.UserRole, s["run"])
                self._tbl_search.setItem(i, col, item)
        self._tbl_search.resizeColumnToContents(0)

    def _on_student_selected(self):
        row = self._tbl_search.currentRow()
        if row < 0:
            return
        item = self._tbl_search.item(row, 0)
        if not item:
            return
        run = item.data(Qt.ItemDataRole.UserRole)
        self._selected_run = run
        try:
            s = db.get_student(run)
        except Exception:
            s = None
        if s:
            apellidos = f"{s['apellido_paterno'] or ''} {s['apellido_materno'] or ''}".strip()
            self._lbl_selected.setText(
                f"{apellidos}\n{utils.run_display(run)}  ·  {s['curso'] or ''}"
            )
            self._lbl_selected.setStyleSheet(
                f"font-size: 13px; font-weight: 600; color: {C.TEXT}; background: transparent;"
            )
        self._btn_save.setEnabled(True)
        self._btn_save.setStyleSheet(self._btn_save_style(True))

    def _load_active(self):
        try:
            rows = db.get_active_and_upcoming_suspensions(
                date.today().isoformat(), tipo=self._tipo
            )
        except Exception:
            rows = []
        today = date.today().isoformat()
        self._tbl_active.setRowCount(len(rows))
        for i, row in enumerate(rows):
            run_fmt   = utils.run_display(row["run"])
            apellidos = f"{row['apellido_paterno'] or ''} {row['apellido_materno'] or ''}".strip()
            curso     = row["curso"] or ""
            desde     = utils.format_fecha_display(row["fecha_inicio"])
            hasta     = utils.format_fecha_display(row["fecha_fin"])
            motivo    = row["motivo"] or ""

            is_active = row["fecha_inicio"] <= today <= row["fecha_fin"]
            color = self._cfg['color'] if is_active else C.AMBER

            for col, txt in enumerate([run_fmt, apellidos, curso, desde, hasta, motivo]):
                item = QTableWidgetItem(txt)
                item.setData(Qt.ItemDataRole.UserRole, row["id"])
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                if col in (3, 4) and is_active:
                    item.setForeground(QColor(color))
                    f = item.font(); f.setBold(True); item.setFont(f)
                self._tbl_active.setItem(i, col, item)

            btn_del = AButton("✕", sound_type="click")
            btn_del.setFixedSize(32, 28)
            btn_del.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {C.RED};
                    border: 1px solid {C.RED}55; border-radius: 6px;
                    font-size: 13px; font-weight: 700;
                }}
                QPushButton:hover {{ background: {C.RED_DIM}; }}
            """)
            susp_id = row["id"]
            btn_del.clicked.connect(lambda _, sid=susp_id: self._delete(sid))
            self._tbl_active.setCellWidget(i, 6, btn_del)

    # ── Acciones ─────────────────────────────────────

    def _set_mode(self, habiles: bool):
        self._mode_habiles = habiles
        _act = f"""
            QPushButton {{
                background: {C.BLUE_DIM}; color: {C.BLUE};
                border: 1.5px solid {C.BLUE}55; border-radius: 7px;
                padding: 4px 12px; font-size: 11px; font-weight: 700;
            }}
        """
        _inact = f"""
            QPushButton {{
                background: {C.SURFACE2}; color: {C.TEXT3};
                border: 1px solid {C.BORDER}; border-radius: 7px;
                padding: 4px 12px; font-size: 11px; font-weight: 500;
            }}
            QPushButton:hover {{ background: {C.SURFACE3}; color: {C.TEXT2}; }}
        """
        self._btn_habiles.setStyleSheet( _act  if habiles else _inact)
        self._btn_corridos.setStyleSheet(_inact if habiles else _act)

    def _toggle_manual_end(self):
        self._manual_end = not self._manual_end
        self._lbl_hasta.setVisible(self._manual_end)
        self._date_fin.setVisible(self._manual_end)
        if self._manual_end:
            self._btn_toggle_fin.setText("‹ Ocultar fecha manual")
            self._lbl_fin_calc.setVisible(False)
        else:
            self._btn_toggle_fin.setText("Ingresar fecha fin manualmente ›")
            self._lbl_fin_calc.setVisible(True)

    def _set_duration(self, n_dias: int):
        q_inicio = self._date_inicio.date()
        inicio   = date(q_inicio.year(), q_inicio.month(), q_inicio.day())
        fin      = _calc_end_date(inicio, n_dias, self._mode_habiles)
        self._date_fin.setDate(QDate(fin.year, fin.month, fin.day))
        fin_txt = utils.format_fecha_display(fin.isoformat())
        tipo_str = "hábiles" if self._mode_habiles else "corridos"
        self._lbl_fin_calc.setText(f"Termina el: {fin_txt}  ({n_dias} días {tipo_str})")
        self._lbl_fin_calc.setStyleSheet(
            f"font-size: 12px; color: {C.BLUE}; background: transparent; font-weight: 600;"
        )

    def _save(self):
        if not self._selected_run:
            return
        inicio = self._date_inicio.date().toString("yyyy-MM-dd")
        fin    = self._date_fin.date().toString("yyyy-MM-dd")
        if fin < inicio:
            self._saved_ind.show_error("✗  Fecha fin anterior al inicio")
            sound.error()
            return
        motivo = self._inp_motivo.text().strip()
        try:
            db.add_student_suspension(self._selected_run, inicio, fin, motivo, self._tipo)
        except Exception as e:
            self._saved_ind.show_error(f"✗  Error: {e}")
            return
        self._saved_ind.show_saved(
            f"✓  {utils.format_fecha_display(inicio)} → {utils.format_fecha_display(fin)}"
        )
        sound.save()
        self._load_active()
        self._inp_motivo.clear()

    def _delete(self, suspension_id: int):
        try:
            db.delete_student_suspension(suspension_id)
        except Exception:
            pass
        self._load_active()
        self._saved_ind.show_saved("✓  Registro eliminado")
        sound.save()

    # ── Helpers ──────────────────────────────────────

    def _flabel(self, text: str) -> QLabel:
        l = QLabel(text.upper())
        l.setStyleSheet(
            f"font-size: 10px; font-weight: 700; letter-spacing: 0.8px; "
            f"color: {C.TEXT2}; background: transparent;"
        )
        return l

    def _table_style(self) -> str:
        return f"""
            QTableWidget {{
                background: {C.SURFACE}; border: 1.5px solid {C.BORDER};
                border-radius: 10px; outline: none;
            }}
            QTableWidget::item {{
                padding: 6px 12px; border: none;
                font-size: 12px; color: {C.TEXT2};
            }}
            QTableWidget::item:selected {{ background: {C.NAVY_700}; color: {C.TEXT}; }}
            QTableWidget::item:alternate {{ background: {C.SURFACE2}; }}
        """

    def _btn_save_style(self, enabled: bool) -> str:
        color = self._cfg['color']
        dim   = self._cfg['dim']
        if enabled:
            return f"""
                QPushButton {{
                    background: {dim}; color: {color};
                    border: 1.5px solid {color}66; border-radius: 10px;
                    padding: 10px 20px; font-size: 13px; font-weight: 700;
                }}
                QPushButton:hover {{ background: {color}33; }}
            """
        return f"""
            QPushButton {{
                background: {C.SURFACE2}; color: {C.TEXT3};
                border: none; border-radius: 10px;
                padding: 10px 20px; font-size: 13px; font-weight: 700;
            }}
        """

    def showEvent(self, event):
        super().showEvent(event)
        self._load_active()


# ══════════════════════════════════════════════════════
#  TAB SIMPLIFICADO (Retiro / Atraso)
# ══════════════════════════════════════════════════════

class _SimpleExcusalTab(QWidget):
    """
    Tab liviano para Retiro y Atraso:
    solo buscar estudiante → elegir día → elegir comida(s) → guardar.
    No tiene rango de fechas ni cálculo de días.
    """

    def __init__(self, tipo: str, parent=None):
        super().__init__(parent)
        self._tipo         = tipo
        self._cfg          = TIPOS[tipo]
        self._selected_run = None
        self._comida_checks: list[tuple[QCheckBox, dict]] = []
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(250)
        self._debounce.timeout.connect(self._run_search)
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet(f"background: {C.BG};")
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(14)

        sub = QLabel(self._cfg['sub'])
        sub.setWordWrap(True)
        sub.setStyleSheet(f"font-size: 12px; color: {C.TEXT3}; background: transparent;")
        root.addWidget(sub)

        cols = QHBoxLayout()
        cols.setSpacing(16)

        # ── LEFT: búsqueda ───────────────────────────
        left = QVBoxLayout()
        left.setSpacing(10)
        left.addWidget(SectionHeader("Buscar estudiante"))

        search_bar = QFrame()
        search_bar.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border: none;
                border-radius: 12px;
            }}
        """)
        sb_lay = QHBoxLayout(search_bar)
        sb_lay.setContentsMargins(12, 8, 12, 8)
        sb_lay.setSpacing(8)

        lupa = QLabel("⌕")
        lupa.setStyleSheet(f"font-size: 16px; color: {C.TEXT3}; background: transparent;")
        sb_lay.addWidget(lupa)

        self._inp_search = QLineEdit()
        self._inp_search.setPlaceholderText("RUN, nombre o curso…")
        self._inp_search.setStyleSheet(f"""
            QLineEdit {{
                background: transparent; border: none;
                font-size: 13px; color: {C.TEXT};
            }}
        """)
        self._inp_search.textChanged.connect(lambda: self._debounce.start())
        self._inp_search.returnPressed.connect(self._run_search)
        sb_lay.addWidget(self._inp_search, stretch=1)
        left.addWidget(search_bar)

        self._tbl_search = QTableWidget()
        self._tbl_search.setColumnCount(4)
        self._tbl_search.setHorizontalHeaderLabels(["RUN", "Apellidos", "Nombres", "Curso"])
        self._tbl_search.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._tbl_search.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._tbl_search.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tbl_search.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tbl_search.verticalHeader().setVisible(False)
        self._tbl_search.setAlternatingRowColors(True)
        self._tbl_search.setShowGrid(False)
        self._tbl_search.verticalHeader().setDefaultSectionSize(34)
        self._tbl_search.setStyleSheet(self._table_style())
        self._tbl_search.itemSelectionChanged.connect(self._on_student_selected)
        left.addWidget(self._tbl_search, stretch=1)

        cols.addLayout(left, stretch=1)

        # ── RIGHT: formulario ────────────────────────
        color = self._cfg['color']
        dim   = self._cfg['dim']

        right_card = QFrame()
        right_card.setFixedWidth(300)
        right_card.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border: none;
                border-radius: 14px;
            }}
        """)
        form_lay = QVBoxLayout(right_card)
        form_lay.setContentsMargins(20, 16, 20, 16)
        form_lay.setSpacing(12)

        form_lay.addWidget(SectionHeader(f"Justificar comida — {self._cfg['label']}"))

        self._lbl_selected = QLabel("Sin estudiante seleccionado")
        self._lbl_selected.setWordWrap(True)
        self._lbl_selected.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {C.TEXT3}; background: transparent;"
        )
        form_lay.addWidget(self._lbl_selected)
        form_lay.addWidget(HDivider())

        # Fecha única
        form_lay.addWidget(self._flabel("Fecha"))
        self._date_just = QDateEdit()
        self._date_just.setCalendarPopup(True)
        self._date_just.setDate(QDate.currentDate())
        self._date_just.setDisplayFormat("dd/MM/yyyy")
        form_lay.addWidget(self._date_just)

        # Comidas
        form_lay.addWidget(self._flabel("Comidas a justificar"))
        comidas_frame = QFrame()
        comidas_frame.setStyleSheet(
            f"background: {C.SURFACE2}; border: 1px solid {C.BORDER}; border-radius: 8px;"
        )
        comidas_lay = QVBoxLayout(comidas_frame)
        comidas_lay.setContentsMargins(12, 10, 12, 10)
        comidas_lay.setSpacing(6)

        try:
            comidas = db.get_all_comidas()
        except Exception:
            comidas = []

        if not comidas:
            lbl = QLabel("Sin comidas configuradas")
            lbl.setStyleSheet(f"font-size: 12px; color: {C.TEXT3}; background: transparent;")
            comidas_lay.addWidget(lbl)
        else:
            for c in comidas:
                cb = QCheckBox(f"{c['nombre']}  ({c['hora_inicio']}–{c['hora_fin']})")
                cb.setChecked(True)
                cb.setStyleSheet(f"""
                    QCheckBox {{
                        font-size: 12px; color: {C.TEXT2}; background: transparent;
                    }}
                    QCheckBox::indicator {{
                        width: 16px; height: 16px;
                        border: 1.5px solid {C.BORDER}; border-radius: 4px;
                        background: {C.SURFACE};
                    }}
                    QCheckBox::indicator:checked {{
                        background: {color}; border-color: {color};
                    }}
                """)
                comidas_lay.addWidget(cb)
                self._comida_checks.append((cb, dict(c)))

        form_lay.addWidget(comidas_frame)
        form_lay.addSpacing(4)

        self._btn_save = AButton(self._cfg['btn_text'], sound_type="save")
        self._btn_save.setEnabled(False)
        self._btn_save.setStyleSheet(self._btn_style(False))
        self._btn_save.clicked.connect(self._save)
        form_lay.addWidget(self._btn_save)

        self._saved_ind = SavedIndicator()
        form_lay.addWidget(self._saved_ind)
        form_lay.addStretch()

        cols.addWidget(right_card)
        root.addLayout(cols)

    # ── Datos ────────────────────────────────────────

    def _run_search(self):
        query = self._inp_search.text().strip()
        if not query:
            self._tbl_search.setRowCount(0)
            return
        try:
            rows = db.search_students(query, limit=50)
        except Exception:
            rows = []
        self._tbl_search.setRowCount(len(rows))
        for i, s in enumerate(rows):
            run_fmt   = utils.run_display(s["run"])
            apellidos = f"{s['apellido_paterno'] or ''} {s['apellido_materno'] or ''}".strip()
            for col, txt in enumerate([run_fmt, apellidos, s["nombres"] or "", s["curso"] or ""]):
                item = QTableWidgetItem(txt)
                item.setData(Qt.ItemDataRole.UserRole, s["run"])
                self._tbl_search.setItem(i, col, item)
        self._tbl_search.resizeColumnToContents(0)

    def _on_student_selected(self):
        row = self._tbl_search.currentRow()
        if row < 0:
            return
        item = self._tbl_search.item(row, 0)
        if not item:
            return
        run = item.data(Qt.ItemDataRole.UserRole)
        self._selected_run = run
        try:
            s = db.get_student(run)
        except Exception:
            s = None
        if s:
            apellidos = f"{s['apellido_paterno'] or ''} {s['apellido_materno'] or ''}".strip()
            self._lbl_selected.setText(
                f"{apellidos}\n{utils.run_display(run)}  ·  {s['curso'] or ''}"
            )
            self._lbl_selected.setStyleSheet(
                f"font-size: 13px; font-weight: 600; color: {C.TEXT}; background: transparent;"
            )
        self._btn_save.setEnabled(True)
        self._btn_save.setStyleSheet(self._btn_style(True))

    # ── Acción ───────────────────────────────────────

    def _save(self):
        if not self._selected_run:
            return
        fecha = self._date_just.date().toString("yyyy-MM-dd")
        comidas_sel = [c for cb, c in self._comida_checks if cb.isChecked()]
        if not comidas_sel:
            self._saved_ind.show_error("✗  Selecciona al menos una comida")
            return
        tipo_txt = self._cfg['label']
        try:
            n = db.justify_meals_bulk(
                run=self._selected_run,
                fechas=[fecha],
                comidas=comidas_sel,
                tipo_justif=tipo_txt,
                texto_justif="",
            )
        except Exception as e:
            self._saved_ind.show_error(f"✗  Error: {e}")
            return

        # Para atrasos: registrar en student_suspensions + notificar WhatsApp
        if self._tipo == 'atraso':
            try:
                db.add_student_suspension(
                    self._selected_run, fecha, fecha,
                    "Atraso registrado por Inspectoría", "atraso"
                )
            except Exception:
                pass  # Ya existe o tabla aún no inicializada
            self._notificar_whatsapp_atraso()

        if n > 0:
            self._saved_ind.show_saved(
                f"✓  {n} comida(s) para {utils.format_fecha_display(fecha)}"
            )
            sound.save()
        else:
            self._saved_ind.show_error("⚠  Ya registradas (sin cambios)")

    def _notificar_whatsapp_atraso(self):
        """Envía WhatsApp al apoderado en hilo background."""
        import threading
        from datetime import datetime as _dt

        run  = self._selected_run
        hora = _dt.now().strftime("%H:%M")

        def _send():
            try:
                import whatsapp
                ok, msg = whatsapp.enviar_atraso(run, hora)
                # Actualizar indicador en hilo principal
                from PyQt6.QtCore import QTimer
                if ok:
                    QTimer.singleShot(0, lambda: self._saved_ind.show_saved("✓  WhatsApp enviado"))
                else:
                    # No error crítico — el mensaje quedó encolado o no hay número
                    pass
            except Exception:
                pass

        t = threading.Thread(target=_send, daemon=True, name="wa-atraso")
        t.start()

    # ── Helpers ──────────────────────────────────────

    def _flabel(self, text: str) -> QLabel:
        l = QLabel(text.upper())
        l.setStyleSheet(
            f"font-size: 10px; font-weight: 700; letter-spacing: 0.8px; "
            f"color: {C.TEXT2}; background: transparent;"
        )
        return l

    def _table_style(self) -> str:
        return f"""
            QTableWidget {{
                background: {C.SURFACE}; border: 1.5px solid {C.BORDER};
                border-radius: 10px; outline: none;
            }}
            QTableWidget::item {{
                padding: 6px 12px; border: none; font-size: 12px; color: {C.TEXT2};
            }}
            QTableWidget::item:selected {{ background: {C.NAVY_700}; color: {C.TEXT}; }}
            QTableWidget::item:alternate {{ background: {C.SURFACE2}; }}
        """

    def _btn_style(self, enabled: bool) -> str:
        color = self._cfg['color']
        dim   = self._cfg['dim']
        if enabled:
            return f"""
                QPushButton {{
                    background: {dim}; color: {color};
                    border: 1.5px solid {color}66; border-radius: 10px;
                    padding: 10px 20px; font-size: 13px; font-weight: 700;
                }}
                QPushButton:hover {{ background: {color}33; }}
            """
        return f"""
            QPushButton {{
                background: {C.SURFACE2}; color: {C.TEXT3};
                border: none; border-radius: 10px;
                padding: 10px 20px; font-size: 13px; font-weight: 700;
            }}
        """


# ══════════════════════════════════════════════════════
#  TAB JUSTIFICAR COMIDAS
# ══════════════════════════════════════════════════════

class _JustificarTab(QWidget):
    """
    Justifica comidas específicas para un estudiante:
    - Seleccionar estudiante
    - Seleccionar fecha(s)
    - Seleccionar comida(s) a justificar
    - Motivo (tipo + texto libre)
    Inserta registros con metodo='justificado' para que no generen strike.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_run = None
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(250)
        self._debounce.timeout.connect(self._run_search)
        self._comida_checks: list[tuple[QCheckBox, dict]] = []
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet(f"background: {C.BG};")
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(14)

        sub = QLabel(
            "Justifica comidas puntuales para un estudiante. "
            "Las comidas justificadas se registran como asistidas (no generan strike)."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet(f"font-size: 12px; color: {C.TEXT3}; background: transparent;")
        root.addWidget(sub)

        cols = QHBoxLayout()
        cols.setSpacing(16)

        # ── LEFT: búsqueda ───────────────────────────
        left = QVBoxLayout()
        left.setSpacing(10)
        left.addWidget(SectionHeader("Buscar estudiante"))

        search_bar = QFrame()
        search_bar.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border: none;
                border-radius: 12px;
            }}
        """)
        sb_lay = QHBoxLayout(search_bar)
        sb_lay.setContentsMargins(12, 8, 12, 8)
        sb_lay.setSpacing(8)

        lupa = QLabel("⌕")
        lupa.setStyleSheet(f"font-size: 16px; color: {C.TEXT3}; background: transparent;")
        sb_lay.addWidget(lupa)

        self._inp_search = QLineEdit()
        self._inp_search.setPlaceholderText("RUN, nombre o curso…")
        self._inp_search.setStyleSheet(f"""
            QLineEdit {{ background: transparent; border: none; font-size: 13px; color: {C.TEXT}; }}
        """)
        self._inp_search.textChanged.connect(lambda: self._debounce.start())
        self._inp_search.returnPressed.connect(self._run_search)
        sb_lay.addWidget(self._inp_search, stretch=1)
        left.addWidget(search_bar)

        self._tbl_search = QTableWidget()
        self._tbl_search.setColumnCount(4)
        self._tbl_search.setHorizontalHeaderLabels(["RUN", "Apellidos", "Nombres", "Curso"])
        self._tbl_search.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._tbl_search.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._tbl_search.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tbl_search.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tbl_search.verticalHeader().setVisible(False)
        self._tbl_search.setAlternatingRowColors(True)
        self._tbl_search.setShowGrid(False)
        self._tbl_search.verticalHeader().setDefaultSectionSize(34)
        self._tbl_search.setStyleSheet(self._table_style())
        self._tbl_search.itemSelectionChanged.connect(self._on_student_selected)
        left.addWidget(self._tbl_search, stretch=1)

        cols.addLayout(left, stretch=1)

        # ── RIGHT: formulario ────────────────────────
        right_card = QFrame()
        right_card.setFixedWidth(320)
        right_card.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border: none;
                border-radius: 14px;
            }}
        """)
        form_lay = QVBoxLayout(right_card)
        form_lay.setContentsMargins(20, 16, 20, 16)
        form_lay.setSpacing(12)

        form_lay.addWidget(SectionHeader("Justificar comidas"))

        self._lbl_selected = QLabel("Sin estudiante seleccionado")
        self._lbl_selected.setWordWrap(True)
        self._lbl_selected.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {C.TEXT3}; background: transparent;"
        )
        form_lay.addWidget(self._lbl_selected)
        form_lay.addWidget(HDivider())

        # Fecha
        form_lay.addWidget(self._flabel("Fecha"))
        self._date_just = QDateEdit()
        self._date_just.setCalendarPopup(True)
        self._date_just.setDate(QDate.currentDate())
        self._date_just.setDisplayFormat("dd/MM/yyyy")
        form_lay.addWidget(self._date_just)

        # Comidas (checkboxes)
        form_lay.addWidget(self._flabel("Comidas a justificar"))
        self._comidas_frame = QFrame()
        self._comidas_frame.setStyleSheet(
            f"background: {C.SURFACE2}; border: 1px solid {C.BORDER}; border-radius: 8px;"
        )
        comidas_lay = QVBoxLayout(self._comidas_frame)
        comidas_lay.setContentsMargins(12, 10, 12, 10)
        comidas_lay.setSpacing(6)

        try:
            comidas = db.get_all_comidas()
        except Exception:
            comidas = []

        if not comidas:
            lbl = QLabel("Sin comidas configuradas")
            lbl.setStyleSheet(f"font-size: 12px; color: {C.TEXT3}; background: transparent;")
            comidas_lay.addWidget(lbl)
        else:
            for c in comidas:
                cb = QCheckBox(f"{c['nombre']}  ({c['hora_inicio']}–{c['hora_fin']})")
                cb.setChecked(True)
                cb.setStyleSheet(f"""
                    QCheckBox {{
                        font-size: 12px; color: {C.TEXT2}; background: transparent;
                    }}
                    QCheckBox::indicator {{
                        width: 16px; height: 16px;
                        border: 1.5px solid {C.BORDER}; border-radius: 4px;
                        background: {C.SURFACE};
                    }}
                    QCheckBox::indicator:checked {{
                        background: {C.BLUE}; border-color: {C.BLUE};
                    }}
                """)
                comidas_lay.addWidget(cb)
                self._comida_checks.append((cb, dict(c)))

        form_lay.addWidget(self._comidas_frame)

        # Tipo de justificación
        form_lay.addWidget(self._flabel("Tipo de justificación"))
        self._combo_tipo = QComboBox()
        self._combo_tipo.addItems(["Suspensión", "Licencia médica", "Retiro", "Atraso", "Otro"])
        self._combo_tipo.setStyleSheet(f"""
            QComboBox {{
                background: {C.SURFACE2}; color: {C.TEXT};
                border: 1.5px solid {C.BORDER}; border-radius: 8px;
                padding: 6px 12px; font-size: 12px;
            }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox QAbstractItemView {{
                background: {C.SURFACE2}; color: {C.TEXT};
                selection-background-color: {C.NAVY_700};
            }}
        """)
        form_lay.addWidget(self._combo_tipo)

        # Texto libre
        form_lay.addWidget(self._flabel("Detalle (opcional)"))
        self._inp_detalle = QLineEdit()
        self._inp_detalle.setPlaceholderText("Ej: carta médica, acuerdo convivencia…")
        form_lay.addWidget(self._inp_detalle)

        form_lay.addSpacing(4)

        self._btn_justificar = AButton("Justificar comidas", sound_type="save")
        self._btn_justificar.setEnabled(False)
        self._btn_justificar.setStyleSheet(self._btn_style(False))
        self._btn_justificar.clicked.connect(self._do_justify)
        form_lay.addWidget(self._btn_justificar)

        self._saved_ind = SavedIndicator()
        form_lay.addWidget(self._saved_ind)
        form_lay.addStretch()

        cols.addWidget(right_card)
        root.addLayout(cols)

    # ── Datos ────────────────────────────────────────

    def _run_search(self):
        query = self._inp_search.text().strip()
        if not query:
            self._tbl_search.setRowCount(0)
            return
        try:
            rows = db.search_students(query, limit=50)
        except Exception:
            rows = []
        self._tbl_search.setRowCount(len(rows))
        for i, s in enumerate(rows):
            run_fmt   = utils.run_display(s["run"])
            apellidos = f"{s['apellido_paterno'] or ''} {s['apellido_materno'] or ''}".strip()
            for col, txt in enumerate([run_fmt, apellidos, s["nombres"] or "", s["curso"] or ""]):
                item = QTableWidgetItem(txt)
                item.setData(Qt.ItemDataRole.UserRole, s["run"])
                self._tbl_search.setItem(i, col, item)
        self._tbl_search.resizeColumnToContents(0)

    def _on_student_selected(self):
        row = self._tbl_search.currentRow()
        if row < 0:
            return
        item = self._tbl_search.item(row, 0)
        if not item:
            return
        run = item.data(Qt.ItemDataRole.UserRole)
        self._selected_run = run
        try:
            s = db.get_student(run)
        except Exception:
            s = None
        if s:
            apellidos = f"{s['apellido_paterno'] or ''} {s['apellido_materno'] or ''}".strip()
            self._lbl_selected.setText(
                f"{apellidos}\n{utils.run_display(run)}  ·  {s['curso'] or ''}"
            )
            self._lbl_selected.setStyleSheet(
                f"font-size: 13px; font-weight: 600; color: {C.TEXT}; background: transparent;"
            )
        self._btn_justificar.setEnabled(True)
        self._btn_justificar.setStyleSheet(self._btn_style(True))

    # ── Acción ───────────────────────────────────────

    def _do_justify(self):
        if not self._selected_run:
            return
        fecha = self._date_just.date().toString("yyyy-MM-dd")
        comidas_sel = [c for cb, c in self._comida_checks if cb.isChecked()]
        if not comidas_sel:
            self._saved_ind.show_error("✗  Selecciona al menos una comida")
            return
        tipo_txt   = self._combo_tipo.currentText()
        detalle    = self._inp_detalle.text().strip()
        try:
            n = db.justify_meals_bulk(
                run=self._selected_run,
                fechas=[fecha],
                comidas=comidas_sel,
                tipo_justif=tipo_txt,
                texto_justif=detalle,
            )
        except Exception as e:
            self._saved_ind.show_error(f"✗  Error: {e}")
            return
        if n > 0:
            self._saved_ind.show_saved(f"✓  {n} comida(s) justificada(s) para {utils.format_fecha_display(fecha)}")
            sound.save()
        else:
            self._saved_ind.show_error("⚠  Ya estaban registradas (sin cambios)")

    # ── Helpers ──────────────────────────────────────

    def _flabel(self, text: str) -> QLabel:
        l = QLabel(text.upper())
        l.setStyleSheet(
            f"font-size: 10px; font-weight: 700; letter-spacing: 0.8px; "
            f"color: {C.TEXT2}; background: transparent;"
        )
        return l

    def _table_style(self) -> str:
        return f"""
            QTableWidget {{
                background: {C.SURFACE}; border: 1.5px solid {C.BORDER};
                border-radius: 10px; outline: none;
            }}
            QTableWidget::item {{
                padding: 6px 12px; border: none; font-size: 12px; color: {C.TEXT2};
            }}
            QTableWidget::item:selected {{ background: {C.NAVY_700}; color: {C.TEXT}; }}
            QTableWidget::item:alternate {{ background: {C.SURFACE2}; }}
        """

    def _btn_style(self, enabled: bool) -> str:
        if enabled:
            return f"""
                QPushButton {{
                    background: {C.BLUE_DIM}; color: {C.BLUE};
                    border: 1.5px solid {C.BLUE}66; border-radius: 10px;
                    padding: 10px 20px; font-size: 13px; font-weight: 700;
                }}
                QPushButton:hover {{ background: {C.BLUE}33; }}
            """
        return f"""
            QPushButton {{
                background: {C.SURFACE2}; color: {C.TEXT3};
                border: none; border-radius: 10px;
                padding: 10px 20px; font-size: 13px; font-weight: 700;
            }}
        """


# ══════════════════════════════════════════════════════
#  PANTALLA PRINCIPAL
# ══════════════════════════════════════════════════════

class SuspensionsScreen(QWidget):

    # Color del borde activo por índice de tab
    _TAB_COLORS = [C.RED, C.BLUE, C.AMBER, C.GREEN, C.BLUE]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _tab_stylesheet(self, active_idx: int) -> str:
        color = self._TAB_COLORS[active_idx] if active_idx < len(self._TAB_COLORS) else C.BLUE
        return f"""
            QTabWidget::pane {{
                background: {C.BG};
                border: none;
            }}
            QTabBar::tab {{
                background: {C.SURFACE2};
                color: {C.TEXT3};
                border: 1px solid {C.BORDER};
                border-bottom: none;
                border-radius: 8px 8px 0 0;
                padding: 8px 20px;
                margin-right: 4px;
                font-size: 12px;
                font-weight: 600;
                min-width: 100px;
            }}
            QTabBar::tab:selected {{
                background: {C.SURFACE};
                color: {C.TEXT};
                border-bottom: 3px solid {color};
                padding-bottom: 7px;
            }}
            QTabBar::tab:hover:!selected {{
                background: {C.NAVY_700};
                color: {C.TEXT2};
            }}
        """

    def _build_ui(self):
        self.setStyleSheet(f"background: {C.BG};")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 12)
        root.setSpacing(12)

        # Título
        title = QLabel("Justificaciones y Suspensiones")
        title.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: {C.TEXT}; background: transparent;"
        )
        root.addWidget(title)

        # TabWidget
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(self._tab_stylesheet(0))

        # Tabs de tipo — Retiro y Atraso usan tab simplificado
        _ORDEN = [
            ('suspension', "⊘  Suspensiones",  _SuspensionTab),
            ('licencia',   "⊕  Lic. Médicas",   _SuspensionTab),
            ('retiro',     "↑  Retiros",         _SimpleExcusalTab),
            ('atraso',     "◷  Atrasos",         _SimpleExcusalTab),
        ]
        for tipo, label, cls in _ORDEN:
            self._tabs.addTab(cls(tipo), label)

        # Tab justificar
        self._tabs.addTab(_JustificarTab(), "✓  Justificar comidas")

        # Sonido + color dinámico al cambiar tab
        def _on_tab_changed(idx: int):
            sound.click()
            self._tabs.setStyleSheet(self._tab_stylesheet(idx))

        self._tabs.currentChanged.connect(_on_tab_changed)

        root.addWidget(self._tabs, stretch=1)

    def showEvent(self, event):
        super().showEvent(event)
        w = self._tabs.currentWidget()
        if hasattr(w, '_load_active'):
            w._load_active()
