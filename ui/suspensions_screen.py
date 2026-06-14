"""
suspensions_screen.py — Suspensiones escolares PAE Control 0.9 Alpha

Registra suspensiones disciplinarias del colegio para estudiantes.
Durante esos días el sistema excusa sus ausencias al PAE:
  - No se generan strikes por las comidas no asistidas
  - El estudiante sigue pudiendo escanear si estuviera presente

Flujo:
  1. Buscar estudiante (search live)
  2. Seleccionar en tabla
  3. Establecer fecha_inicio, fecha_fin, motivo
  4. Guardar → inasistencias de esos días quedan excusadas
  5. Lista de suspensiones activas/futuras con botón eliminar
"""

from datetime import date, timedelta
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QAbstractItemView, QLineEdit,
    QDateEdit, QPushButton, QSizePolicy
)
from PyQt6.QtCore import Qt, QDate, QTimer
from PyQt6.QtGui import QColor

import db
import utils
from ui.theme   import C, sound
from ui.widgets import AButton, HDivider, SectionHeader, SavedIndicator, RUNLineEdit


# ── Calendario chileno ─────────────────────────────────────────────────────

# Semana Santa (Viernes + Sábado Santo) precalculada hasta 2030
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
    (1,  1),   # Año Nuevo
    (5,  1),   # Día del Trabajo
    (5, 21),   # Glorias Navales
    (6, 20),   # Pueblos Indígenas
    (8, 15),   # Asunción de la Virgen
    (9, 18),   # Fiestas Patrias
    (9, 19),   # Día del Ejército
    (10, 12),  # Encuentro de los Mundos
    (10, 31),  # Iglesias Evangélicas
    (11,  1),  # Todos los Santos
    (12,  8),  # Inmaculada Concepción
    (12, 25),  # Navidad
]


def _feriados_chile(year: int) -> set:
    """Retorna un set de date con todos los feriados chilenos del año."""
    dias = {date(year, m, d) for m, d in _FERIADOS_FIJOS}
    for m, d in _SEMANA_SANTA.get(year, []):
        dias.add(date(year, m, d))
    return dias


def _calc_end_date(start: date, n_dias: int, habiles: bool) -> date:
    """
    Calcula la fecha fin de una suspensión.
    habiles=False (corridos): suma n_dias-1 días calendario.
    habiles=True: avanza n_dias días hábiles (L–V sin feriados chilenos).
    El día inicio cuenta como día 1.
    """
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


class SuspensionsScreen(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_run  = None
        self._mode_habiles  = False   # False=corridos, True=hábiles
        self._manual_end    = False   # True cuando el usuario activa fecha fin manual
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(300)
        self._debounce.timeout.connect(self._run_search)
        self._build_ui()
        self._load_active()

    def _build_ui(self):
        self.setStyleSheet(f"background: {C.BG};")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # ── Title ────────────────────────────────────
        title = QLabel("Suspensiones escolares")
        title.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: {C.TEXT}; background: transparent;"
        )
        root.addWidget(title)

        sub = QLabel(
            "Registra días de suspensión escolar (disciplinaria). "
            "Las ausencias al PAE durante esos días no generan strikes."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet(
            f"font-size: 12px; color: {C.TEXT3}; background: transparent;"
        )
        root.addWidget(sub)

        # ── Two columns ────────────────────────────────
        cols = QHBoxLayout()
        cols.setSpacing(16)

        # ── LEFT: student search ──────────────────────
        left = QVBoxLayout()
        left.setSpacing(10)

        left.addWidget(SectionHeader("Buscar estudiante"))

        search_bar = QFrame()
        search_bar.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border: 1.5px solid {C.BORDER};
                border-radius: 12px;
            }}
        """)
        sb_lay = QHBoxLayout(search_bar)
        sb_lay.setContentsMargins(12, 10, 12, 10)
        sb_lay.setSpacing(8)

        lupa = QLabel("⌕")
        lupa.setStyleSheet(
            f"font-size: 16px; color: {C.TEXT3}; background: transparent;"
        )
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
        sb_lay.addWidget(self._inp_search, stretch=1)
        left.addWidget(search_bar)

        self._tbl_search = QTableWidget()
        self._tbl_search.setColumnCount(4)
        self._tbl_search.setHorizontalHeaderLabels(["RUN", "Apellidos", "Nombres", "Curso"])
        self._tbl_search.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._tbl_search.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self._tbl_search.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tbl_search.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tbl_search.verticalHeader().setVisible(False)
        self._tbl_search.setAlternatingRowColors(True)
        self._tbl_search.setShowGrid(False)
        self._tbl_search.verticalHeader().setDefaultSectionSize(36)
        self._tbl_search.setStyleSheet(self._table_style())
        self._tbl_search.itemSelectionChanged.connect(self._on_student_selected)
        left.addWidget(self._tbl_search, stretch=1)

        cols.addLayout(left, stretch=1)

        # ── RIGHT: form ────────────────────────────────
        right_card = QFrame()
        right_card.setFixedWidth(300)
        right_card.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border: 1.5px solid {C.BORDER};
                border-radius: 14px;
            }}
        """)
        form_lay = QVBoxLayout(right_card)
        form_lay.setContentsMargins(20, 18, 20, 18)
        form_lay.setSpacing(14)

        form_lay.addWidget(SectionHeader("Registrar suspensión escolar"))

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
            btn.setFixedHeight(30)
        self._btn_corridos.clicked.connect(lambda: self._set_mode(False))
        self._btn_habiles.clicked.connect( lambda: self._set_mode(True))
        mode_row.addWidget(self._btn_corridos)
        mode_row.addWidget(self._btn_habiles)
        mode_row.addStretch()
        form_lay.addLayout(mode_row)

        # Botones de duración rápida: 1 / 3 / 5 / 7 días
        form_lay.addWidget(self._flabel("Duración rápida"))
        dur_row = QHBoxLayout()
        dur_row.setSpacing(6)
        _dur_btn_style = f"""
            QPushButton {{
                background: {C.SURFACE2};
                color: {C.TEXT2};
                border: 1px solid {C.BORDER};
                border-radius: 7px;
                padding: 5px 10px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: {C.NAVY_700}; color: {C.TEXT}; }}
        """
        for label, days in [("1 día", 1), ("3 días", 3), ("5 días", 5), ("7 días", 7)]:
            btn = AButton(label, sound_type="click")
            btn.setStyleSheet(_dur_btn_style)
            btn.clicked.connect(lambda checked, d=days: self._set_duration(d))
            dur_row.addWidget(btn)
        dur_row.addStretch()
        form_lay.addLayout(dur_row)

        # Fecha fin calculada (auto, read-only chip)
        self._lbl_fin_calc = QLabel("Selecciona duración rápida")
        self._lbl_fin_calc.setStyleSheet(
            f"font-size: 12px; color: {C.TEXT3}; background: transparent; font-style: italic;"
        )
        form_lay.addWidget(self._lbl_fin_calc)

        # Toggle: ingresar fecha fin manualmente
        self._btn_toggle_fin = AButton("Ingresar fecha fin manualmente ›", sound_type="click")
        self._btn_toggle_fin.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {C.BLUE};
                border: none;
                padding: 0 2px;
                font-size: 11px;
                font-weight: 500;
                text-align: left;
            }}
            QPushButton:hover {{ color: {C.TEXT}; }}
        """)
        self._btn_toggle_fin.clicked.connect(self._toggle_manual_end)
        form_lay.addWidget(self._btn_toggle_fin)

        # Hasta — oculto por defecto, visible solo en modo manual
        self._lbl_hasta = self._flabel("Hasta")
        self._lbl_hasta.setVisible(False)
        form_lay.addWidget(self._lbl_hasta)

        self._date_fin = QDateEdit()
        self._date_fin.setCalendarPopup(True)
        self._date_fin.setDate(QDate.currentDate())
        self._date_fin.setDisplayFormat("dd/MM/yyyy")
        self._date_fin.setVisible(False)
        form_lay.addWidget(self._date_fin)

        # Aplicar estilos iniciales al toggle
        from PyQt6.QtCore import QTimer as _QT
        _QT.singleShot(50, lambda: self._set_mode(False))

        # Motivo
        form_lay.addWidget(self._flabel("Motivo"))
        self._inp_motivo = QLineEdit()
        self._inp_motivo.setPlaceholderText("Ej: Exceso de inasistencias, sanción disciplinaria…")
        form_lay.addWidget(self._inp_motivo)

        form_lay.addSpacing(4)

        # Save button
        self._btn_save = AButton("Registrar suspensión", sound_type="save")
        self._btn_save.setEnabled(False)
        self._btn_save.setStyleSheet(self._btn_save_style(False))
        self._btn_save.clicked.connect(self._save_suspension)
        form_lay.addWidget(self._btn_save)

        self._saved_ind = SavedIndicator()
        form_lay.addWidget(self._saved_ind)
        form_lay.addStretch()

        cols.addWidget(right_card)
        root.addLayout(cols)

        # ── Active suspensions table ──────────────────
        act_hdr = QHBoxLayout()
        act_hdr.addWidget(SectionHeader("Suspensiones activas y próximas"))
        act_hdr.addStretch()
        btn_refresh = AButton("↻", sound_type="click")
        btn_refresh.setFixedSize(30, 28)
        btn_refresh.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT3};
                border: 1px solid {C.BORDER}; border-radius: 6px;
                font-size: 13px;
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
        self._tbl_active.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._tbl_active.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.ResizeMode.Stretch
        )
        self._tbl_active.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tbl_active.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tbl_active.verticalHeader().setVisible(False)
        self._tbl_active.setAlternatingRowColors(True)
        self._tbl_active.setShowGrid(False)
        self._tbl_active.setMaximumHeight(220)
        self._tbl_active.verticalHeader().setDefaultSectionSize(38)
        self._tbl_active.setStyleSheet(self._table_style())
        root.addWidget(self._tbl_active)

    # ─────────────────────────────────────────────
    #  DATA
    # ─────────────────────────────────────────────

    def _run_search(self):
        query = self._inp_search.text().strip()
        if not query:
            self._tbl_search.setRowCount(0)
            return
        rows = db.search_students(query, limit=50)
        self._tbl_search.setRowCount(len(rows))
        for i, s in enumerate(rows):
            run_fmt   = utils.run_display(s["run"])
            apellidos = (
                f"{s['apellido_paterno'] or ''} {s['apellido_materno'] or ''}"
            ).strip()
            nombres = s["nombres"] or ""
            curso   = s["curso"] or ""
            for col, txt in enumerate([run_fmt, apellidos, nombres, curso]):
                item = QTableWidgetItem(txt)
                item.setData(Qt.ItemDataRole.UserRole, s["run"])
                self._tbl_search.setItem(i, col, item)

    def _on_student_selected(self):
        row = self._tbl_search.currentRow()
        if row < 0:
            return
        item = self._tbl_search.item(row, 0)
        if not item:
            return
        run = item.data(Qt.ItemDataRole.UserRole)
        self._selected_run = run
        s = db.get_student(run)
        if s:
            apellidos = (
                f"{s['apellido_paterno'] or ''} {s['apellido_materno'] or ''}"
            ).strip()
            self._lbl_selected.setText(
                f"{apellidos}\n{utils.run_display(run)}  ·  {s['curso'] or ''}"
            )
            self._lbl_selected.setStyleSheet(
                f"font-size: 13px; font-weight: 600; color: {C.TEXT}; background: transparent;"
            )
        self._btn_save.setEnabled(True)
        self._btn_save.setStyleSheet(self._btn_save_style(True))

    def _load_active(self):
        rows = db.get_active_and_upcoming_suspensions(date.today().isoformat())
        today = date.today().isoformat()
        self._tbl_active.setRowCount(len(rows))
        for i, row in enumerate(rows):
            run_fmt   = utils.run_display(row["run"])
            apellidos = (
                f"{row['apellido_paterno'] or ''} {row['apellido_materno'] or ''}"
            ).strip()
            curso     = row["curso"] or ""
            desde     = utils.format_fecha_display(row["fecha_inicio"])
            hasta     = utils.format_fecha_display(row["fecha_fin"])
            motivo    = row["motivo"] or ""

            # Color: rojo si activa hoy, amber si futura
            is_active = row["fecha_inicio"] <= today <= row["fecha_fin"]
            color = C.RED if is_active else C.AMBER

            for col, txt in enumerate([run_fmt, apellidos, curso, desde, hasta, motivo]):
                item = QTableWidgetItem(txt)
                item.setData(Qt.ItemDataRole.UserRole, row["id"])
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
                )
                if col in (3, 4) and is_active:
                    item.setForeground(QColor(color))
                    f = item.font(); f.setBold(True); item.setFont(f)
                self._tbl_active.setItem(i, col, item)

            # Delete button
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
            btn_del.clicked.connect(lambda _, sid=susp_id: self._delete_suspension(sid))
            self._tbl_active.setCellWidget(i, 6, btn_del)

    # ─────────────────────────────────────────────
    #  ACTIONS
    # ─────────────────────────────────────────────

    def _set_mode(self, habiles: bool):
        self._mode_habiles = habiles
        _act = f"""
            QPushButton {{
                background: {C.BLUE_DIM};
                color: {C.BLUE};
                border: 1.5px solid {C.BLUE}55;
                border-radius: 7px;
                padding: 5px 12px;
                font-size: 11px;
                font-weight: 700;
            }}
        """
        _inact = f"""
            QPushButton {{
                background: {C.SURFACE2};
                color: {C.TEXT3};
                border: 1px solid {C.BORDER};
                border-radius: 7px;
                padding: 5px 12px;
                font-size: 11px;
                font-weight: 500;
            }}
            QPushButton:hover {{ background: {C.SURFACE3}; color: {C.TEXT2}; }}
        """
        self._btn_habiles.setStyleSheet( _act  if habiles  else _inact)
        self._btn_corridos.setStyleSheet(_inact if habiles  else _act)

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
        # Actualizar chip de fecha calculada
        fin_txt = utils.format_fecha_display(fin.isoformat())
        tipo = "hábiles" if self._mode_habiles else "corridos"
        self._lbl_fin_calc.setText(f"Termina el: {fin_txt}  ({n_dias} días {tipo})")
        self._lbl_fin_calc.setStyleSheet(
            f"font-size: 12px; color: {C.BLUE}; background: transparent; font-weight: 600;"
        )

    def _save_suspension(self):
        if not self._selected_run:
            return
        inicio = self._date_inicio.date().toString("yyyy-MM-dd")
        fin    = self._date_fin.date().toString("yyyy-MM-dd")
        if fin < inicio:
            self._saved_ind.show_error("✗  La fecha fin es anterior al inicio")
            sound.error()
            return
        motivo = self._inp_motivo.text().strip()
        db.add_student_suspension(self._selected_run, inicio, fin, motivo)
        self._saved_ind.show_saved(
            f"✓  Suspendido {utils.format_fecha_display(inicio)} → {utils.format_fecha_display(fin)}"
        )
        sound.save()
        self._load_active()
        self._inp_motivo.clear()

    def _delete_suspension(self, suspension_id: int):
        db.delete_student_suspension(suspension_id)
        self._load_active()
        self._saved_ind.show_saved("✓  Suspensión eliminada")
        sound.save()

    # ─────────────────────────────────────────────
    #  HELPERS
    # ─────────────────────────────────────────────

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
                background: {C.SURFACE};
                border: 1.5px solid {C.BORDER};
                border-radius: 10px;
                outline: none;
            }}
            QTableWidget::item {{
                padding: 7px 12px; border: none;
                font-size: 12px; color: {C.TEXT2};
            }}
            QTableWidget::item:selected {{
                background: {C.NAVY_700}; color: {C.TEXT};
            }}
            QTableWidget::item:alternate {{ background: {C.SURFACE2}; }}
        """

    @staticmethod
    def _btn_save_style(enabled: bool) -> str:
        if enabled:
            return f"""
                QPushButton {{
                    background: {C.RED_DIM};
                    color: {C.RED};
                    border: 1.5px solid {C.RED}66;
                    border-radius: 10px;
                    padding: 10px 20px;
                    font-size: 13px; font-weight: 700;
                }}
                QPushButton:hover {{ background: {C.RED}33; }}
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
