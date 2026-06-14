"""
bulk_screen.py — Registro Masivo por Curso · PAE Control 0.9 Alpha

Flujo:
  1. Selector: curso + comida + fecha
  2. Preview: tabla de activos con estado (Pendiente / Ya registrado / En espera)
  3. Botón "Registrar todos" → BulkWorker (QThread)
  4. Resumen inline + log de operaciones anteriores (trazabilidad)

Solo registra estudiantes activos y no en lista de espera.
"""

import uuid
from datetime import date
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QFrame, QAbstractItemView, QDateEdit,
    QSizePolicy, QSplitter
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDate
from PyQt6.QtGui import QColor, QFont

import db
import utils
from ui.theme   import C, sound
from ui.widgets import AButton, HDivider, SectionHeader, SavedIndicator


# ═══════════════════════════════════════════════
#  WORKER
# ═══════════════════════════════════════════════

class BulkWorker(QThread):
    finished = pyqtSignal(dict)  # resumen: {nuevos, ya_registrados, omitidos, total}

    def __init__(self, operacion_id: str, curso: str,
                 comida_id: int, comida_nombre: str,
                 fecha: str, students: list):
        super().__init__()
        self._op_id       = operacion_id
        self._curso       = curso
        self._comida_id   = comida_id
        self._comida_nm   = comida_nombre
        self._fecha       = fecha
        self._students    = students

    def run(self):
        result = db.bulk_register(
            operacion_id  = self._op_id,
            curso         = self._curso,
            comida_id     = self._comida_id,
            comida_nombre = self._comida_nm,
            fecha         = self._fecha,
            students      = self._students,
        )
        self.finished.emit(result)


# ═══════════════════════════════════════════════
#  STATUS CHIP (inline en header)
# ═══════════════════════════════════════════════

def _chip(label: str, value: str, color: str) -> QFrame:
    f = QFrame()
    f.setStyleSheet(f"""
        QFrame {{
            background: {color}18;
            border: 1.5px solid {color}55;
            border-radius: 10px;
        }}
    """)
    lay = QHBoxLayout(f)
    lay.setContentsMargins(10, 5, 10, 5)
    lay.setSpacing(6)

    dot = QLabel("●")
    dot.setStyleSheet(f"color: {color}; font-size: 8px; background: transparent;")

    val = QLabel(value)
    val.setObjectName("val")
    val.setStyleSheet(
        f"font-size: 13px; font-weight: 700; color: {color}; background: transparent;"
    )

    lbl = QLabel(label)
    lbl.setStyleSheet(
        f"font-size: 11px; color: {C.TEXT3}; background: transparent;"
    )

    lay.addWidget(dot)
    lay.addWidget(val)
    lay.addWidget(lbl)
    return f


def _chip_update(chip: QFrame, value: str):
    v = chip.findChild(QLabel, "val")
    if v:
        v.setText(value)


# ═══════════════════════════════════════════════
#  ESTADO COLOR MAP
# ═══════════════════════════════════════════════

ESTADO_CFG = {
    "pendiente":     (C.GREEN,      "Pendiente"),
    "ya_registrado": (C.TEXT3,      "Ya registrado"),
    "lista_espera":  (C.AMBER,      "En espera"),
}


# ═══════════════════════════════════════════════
#  MAIN SCREEN
# ═══════════════════════════════════════════════

class BulkScreen(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._students: list = []
        self._worker = None
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet(f"background: {C.BG};")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # ── Title ────────────────────────────────────
        title = QLabel("Registro masivo por curso")
        title.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: {C.TEXT}; background: transparent;"
        )
        root.addWidget(title)

        sub = QLabel(
            "Registra asistencia a toda una clase en un clic. "
            "Solo se registran estudiantes activos que aún no tienen registro para la comida seleccionada."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet(
            f"font-size: 12px; color: {C.TEXT3}; background: transparent;"
        )
        root.addWidget(sub)

        # ── Selector card ─────────────────────────────
        sel_card = QFrame()
        sel_card.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border: 1.5px solid {C.BORDER};
                border-radius: 14px;
            }}
        """)
        sel_lay = QHBoxLayout(sel_card)
        sel_lay.setContentsMargins(20, 16, 20, 16)
        sel_lay.setSpacing(16)

        # Curso
        sel_lay.addWidget(self._field_label("Curso"))
        self._cmb_curso = QComboBox()
        self._cmb_curso.setMinimumWidth(160)
        self._cmb_curso.currentIndexChanged.connect(self._on_params_changed)
        sel_lay.addWidget(self._cmb_curso)

        sel_lay.addWidget(self._vsep())

        # Comida
        sel_lay.addWidget(self._field_label("Comida"))
        self._cmb_comida = QComboBox()
        self._cmb_comida.setMinimumWidth(160)
        self._cmb_comida.currentIndexChanged.connect(self._on_params_changed)
        sel_lay.addWidget(self._cmb_comida)

        sel_lay.addWidget(self._vsep())

        # Fecha
        sel_lay.addWidget(self._field_label("Fecha"))
        self._date_edit = QDateEdit()
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setDate(QDate.currentDate())
        self._date_edit.setDisplayFormat("dd/MM/yyyy")
        self._date_edit.setFixedWidth(130)
        self._date_edit.dateChanged.connect(self._on_params_changed)
        sel_lay.addWidget(self._date_edit)

        sel_lay.addStretch()

        # Chips de stats
        self._chip_total  = _chip("En curso",        "—", C.TEXT2)
        self._chip_pend   = _chip("Pendientes",      "—", C.GREEN)
        self._chip_ya     = _chip("Ya registrados",  "—", C.TEXT3)
        self._chip_espera = _chip("En espera",       "—", C.AMBER)
        for ch in (self._chip_total, self._chip_pend,
                   self._chip_ya, self._chip_espera):
            sel_lay.addWidget(ch)

        root.addWidget(sel_card)

        # ── Preview table ────────────────────────────
        prev_hdr = QHBoxLayout()
        prev_hdr.addWidget(SectionHeader("Estudiantes en el curso"))
        prev_hdr.addStretch()
        self._lbl_count = QLabel("")
        self._lbl_count.setStyleSheet(
            f"font-size: 11px; color: {C.TEXT3}; background: transparent;"
        )
        prev_hdr.addWidget(self._lbl_count)
        root.addLayout(prev_hdr)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(
            ["RUN", "Apellidos", "Nombres", "Estado", "Strikes"]
        )
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setDefaultSectionSize(38)
        self._table.setStyleSheet(f"""
            QTableWidget {{
                background: {C.SURFACE};
                border: 1.5px solid {C.BORDER};
                border-radius: 12px;
                outline: none;
            }}
            QTableWidget::item {{
                padding: 8px 12px;
                border: none;
            }}
            QTableWidget::item:selected {{
                background: {C.NAVY_700};
                color: {C.TEXT};
            }}
            QTableWidget::item:alternate {{ background: {C.SURFACE2}; }}
        """)
        root.addWidget(self._table, stretch=1)

        # ── Action bar ────────────────────────────────
        act_row = QHBoxLayout()
        act_row.setSpacing(12)

        self._btn_register = AButton("Registrar todos  →", sound_type="save")
        self._btn_register.setEnabled(False)
        self._btn_register.setStyleSheet(self._btn_style(enabled=False))
        self._btn_register.clicked.connect(self._run_bulk)
        act_row.addWidget(self._btn_register)
        act_row.addStretch()

        self._saved_ind = SavedIndicator()
        act_row.addWidget(self._saved_ind)
        root.addLayout(act_row)

        # ── Audit log ─────────────────────────────────
        log_hdr = QHBoxLayout()
        log_hdr.addWidget(SectionHeader("Historial de operaciones"))
        log_hdr.addStretch()
        btn_refresh_log = AButton("↻", sound_type="click")
        btn_refresh_log.setFixedSize(30, 28)
        btn_refresh_log.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT3};
                border: 1px solid {C.BORDER}; border-radius: 6px;
                font-size: 13px;
            }}
            QPushButton:hover {{ background: {C.SURFACE2}; color: {C.TEXT}; }}
        """)
        btn_refresh_log.clicked.connect(self._load_audit)
        log_hdr.addWidget(btn_refresh_log)
        root.addLayout(log_hdr)

        self._tbl_audit = QTableWidget()
        self._tbl_audit.setColumnCount(7)
        self._tbl_audit.setHorizontalHeaderLabels(
            ["Fecha", "Comida", "Curso", "Nuevos", "Ya reg.", "Omitidos", "Hora"]
        )
        self._tbl_audit.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self._tbl_audit.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tbl_audit.verticalHeader().setVisible(False)
        self._tbl_audit.setAlternatingRowColors(True)
        self._tbl_audit.setShowGrid(False)
        self._tbl_audit.setMaximumHeight(180)
        self._tbl_audit.verticalHeader().setDefaultSectionSize(36)
        self._tbl_audit.setStyleSheet(f"""
            QTableWidget {{
                background: {C.SURFACE};
                border: 1.5px solid {C.BORDER};
                border-radius: 10px;
                outline: none;
            }}
            QTableWidget::item {{
                padding: 6px 12px;
                border: none;
                font-size: 12px;
                color: {C.TEXT2};
            }}
            QTableWidget::item:alternate {{ background: {C.SURFACE2}; }}
        """)
        root.addWidget(self._tbl_audit)

        # ── Initial data ──────────────────────────────
        self._load_combos()
        self._load_audit()

    # ─────────────────────────────────────────────
    #  DATA LOAD
    # ─────────────────────────────────────────────

    def _load_combos(self):
        # Cursos
        self._cmb_curso.blockSignals(True)
        self._cmb_curso.clear()
        for c in db.get_cursos():
            self._cmb_curso.addItem(c, c)
        self._cmb_curso.blockSignals(False)

        # Comidas activas
        self._cmb_comida.blockSignals(True)
        self._cmb_comida.clear()
        for com in db.get_comidas():
            self._cmb_comida.addItem(com["nombre"], com["id"])
        self._cmb_comida.blockSignals(False)

        self._on_params_changed()

    def _on_params_changed(self):
        curso     = self._cmb_curso.currentData()
        comida_id = self._cmb_comida.currentData()
        fecha     = self._date_edit.date().toString("yyyy-MM-dd")

        if not curso or comida_id is None:
            self._table.setRowCount(0)
            self._students = []
            return

        self._students = db.get_students_bulk_preview(curso, comida_id, fecha)
        self._populate_table()
        self._update_chips()
        self._update_btn()

    def _populate_table(self):
        self._table.setRowCount(len(self._students))
        for i, s in enumerate(self._students):
            color, estado_txt = ESTADO_CFG.get(
                s["estado"], (C.TEXT3, s["estado"])
            )
            run_fmt   = utils.run_display(s["run"])
            apellidos = (
                f"{s.get('apellido_paterno','') or ''} "
                f"{s.get('apellido_materno','') or ''}"
            ).strip()
            nombres   = s.get("nombres", "") or ""
            strikes   = db.count_strikes(s["run"])

            values = [run_fmt, apellidos, nombres, estado_txt, str(strikes)]
            for col, txt in enumerate(values):
                item = QTableWidgetItem(txt)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
                )
                if col == 3:  # Estado
                    item.setForeground(QColor(color))
                    f = item.font()
                    f.setBold(True)
                    item.setFont(f)
                elif col == 4:  # Strikes
                    s_color = (C.RED if strikes >= 3
                               else C.AMBER if strikes > 0 else C.TEXT3)
                    item.setForeground(QColor(s_color))
                self._table.setItem(i, col, item)

        self._lbl_count.setText(f"{len(self._students)} estudiante{'s' if len(self._students) != 1 else ''}")

    def _update_chips(self):
        pendientes = sum(1 for s in self._students if s["estado"] == "pendiente")
        ya_reg     = sum(1 for s in self._students if s["estado"] == "ya_registrado")
        espera     = sum(1 for s in self._students if s["estado"] == "lista_espera")
        _chip_update(self._chip_total,  str(len(self._students)))
        _chip_update(self._chip_pend,   str(pendientes))
        _chip_update(self._chip_ya,     str(ya_reg))
        _chip_update(self._chip_espera, str(espera))

    def _update_btn(self):
        pendientes = sum(1 for s in self._students if s["estado"] == "pendiente")
        enabled = pendientes > 0
        self._btn_register.setEnabled(enabled)
        self._btn_register.setStyleSheet(self._btn_style(enabled=enabled))

    def _load_audit(self):
        rows = db.get_bulk_operations(limit=30)
        self._tbl_audit.setRowCount(len(rows))
        for i, row in enumerate(rows):
            ts = row["timestamp"][:16].replace("T", "  ") if row["timestamp"] else ""
            nuevos = row["nuevos"]
            values = [
                utils.format_fecha_display(row["fecha"]),
                row["comida_nombre"],
                row["curso"],
                str(row["nuevos"]),
                str(row["ya_registrados"]),
                str(row["omitidos"]),
                ts,
            ]
            for col, txt in enumerate(values):
                item = QTableWidgetItem(txt)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
                )
                if col == 3 and nuevos > 0:
                    item.setForeground(QColor(C.GREEN))
                self._tbl_audit.setItem(i, col, item)

    # ─────────────────────────────────────────────
    #  BULK REGISTER
    # ─────────────────────────────────────────────

    def _run_bulk(self):
        pendientes = [s for s in self._students if s["estado"] == "pendiente"]
        if not pendientes:
            return

        curso        = self._cmb_curso.currentData()
        comida_id    = self._cmb_comida.currentData()
        comida_nm    = self._cmb_comida.currentText()
        fecha        = self._date_edit.date().toString("yyyy-MM-dd")
        operacion_id = str(uuid.uuid4())[:8].upper()  # e.g. "A3F7B2C1"

        self._btn_register.setEnabled(False)
        self._btn_register.setStyleSheet(self._btn_style(enabled=False))

        self._worker = BulkWorker(
            operacion_id = operacion_id,
            curso        = curso,
            comida_id    = comida_id,
            comida_nombre = comida_nm,
            fecha        = fecha,
            students     = self._students,
        )
        self._worker.finished.connect(self._on_bulk_done)
        self._worker.start()

    def _on_bulk_done(self, result: dict):
        nuevos        = result["nuevos"]
        ya_reg        = result["ya_registrados"]
        omitidos      = result["omitidos"]

        # Refresh preview con nuevo estado
        self._on_params_changed()
        self._load_audit()

        msg = f"✓  {nuevos} registrados"
        if ya_reg:   msg += f"  ·  {ya_reg} ya tenían"
        if omitidos: msg += f"  ·  {omitidos} en espera omitidos"

        self._saved_ind.show_saved(msg)
        sound.save()

    # ─────────────────────────────────────────────
    #  HELPERS
    # ─────────────────────────────────────────────

    def _field_label(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setStyleSheet(
            f"font-size: 12px; color: {C.TEXT3}; font-weight: 600; background: transparent;"
        )
        return l

    def _vsep(self) -> QFrame:
        s = QFrame()
        s.setFrameShape(QFrame.Shape.VLine)
        s.setFixedWidth(1)
        s.setFixedHeight(32)
        s.setStyleSheet(f"background: {C.BORDER}; border: none;")
        return s

    @staticmethod
    def _btn_style(enabled: bool) -> str:
        if enabled:
            return f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 {C.GREEN_DIM}, stop:1 {C.NAVY_800});
                    color: {C.TEXT};
                    border: 1.5px solid {C.GREEN}66;
                    border-radius: 10px;
                    padding: 11px 28px;
                    font-size: 13px; font-weight: 700;
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 {C.GREEN}33, stop:1 {C.NAVY_700});
                    border-color: {C.GREEN}aa;
                }}
                QPushButton:pressed {{ background: {C.NAVY_800}; }}
            """
        return f"""
            QPushButton {{
                background: {C.SURFACE2};
                color: {C.TEXT3};
                border: none; border-radius: 10px;
                padding: 11px 28px;
                font-size: 13px; font-weight: 700;
            }}
        """

    def showEvent(self, event):
        super().showEvent(event)
        self._load_combos()
        self._load_audit()
