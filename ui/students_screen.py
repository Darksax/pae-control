"""
students_screen.py — Gestión de estudiantes MiAppoderado

Tabs: Todos | En PAE | Lista de espera
Columnas ordenables por click en encabezado
Estado: En PAE / No PAE / En espera
Puntaje RSH + puntaje extra para priorizar lista de espera
Acción masiva: seleccionar filas → cambiar estado en lote
"""

import re

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QFrame, QAbstractItemView, QSizePolicy,
    QSpinBox, QMenu, QApplication
)
from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QColor, QFont, QAction

import db
import utils
import logic
import session
from ui.theme   import C, sound, btn_primary, btn_secondary
from ui.widgets import AButton, HDivider, SectionHeader, SavedIndicator


# ── Columnas modo PAE/admin
COL_RUN      = 0
COL_APELLIDO = 1
COL_NOMBRE   = 2
COL_CURSO    = 3
COL_ESTADO   = 4
COL_RSH      = 5
COL_EXTRA    = 6
COL_STRIKES  = 7

HEADERS = ["RUN", "Apellidos", "Nombres", "Curso",
           "Estado PAE", "RSH %", "Pts extra", "Strikes"]

# ── Columnas modo Inspectoría
COL_INS_RUN       = 0
COL_INS_APELLIDO  = 1
COL_INS_NOMBRE    = 2
COL_INS_CURSO     = 3
COL_INS_SINFIRMAR = 4
COL_INS_TOTAL     = 5

HEADERS_INS = ["RUN", "Apellidos", "Nombres", "Curso",
               "Sin firmar", "Total período"]

# Tab IDs
TAB_TODOS  = 0
TAB_PAE    = 1
TAB_ESPERA = 2

# Estado → (label, color, bg_hex_alpha)
ESTADO_INFO = {
    "beneficiario":  ("Beneficiario PAE", C.GREEN,  "#34C75914"),
    "espera":        ("Lista de espera",  C.AMBER,  "#FF950014"),
    "no_beneficiario": ("No beneficiario", C.TEXT3, "transparent"),
}


def _curso_sort_key(curso: str) -> str:
    """Normaliza curso para ordenamiento: '2° medioB' → '02B'."""
    s = re.sub(r'medio\s*', '', curso or "", flags=re.IGNORECASE)
    s = re.sub(r'[°º\s]', '', s)
    m = re.match(r'(\d+)(.*)', s)
    if m:
        return f"{int(m.group(1)):02d}{m.group(2).upper()}"
    return s.upper()


class _CursoItem(QTableWidgetItem):
    """QTableWidgetItem para columna Curso con sort key normalizado."""

    def __init__(self, curso_display: str, curso_raw: str, run: str, bg=None):
        super().__init__(curso_display)
        self.setData(Qt.ItemDataRole.UserRole,     run)
        self.setData(Qt.ItemDataRole.UserRole + 2, curso_raw)  # raw para edición
        self.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        if bg:
            self.setBackground(bg)

    def __lt__(self, other):
        return _curso_sort_key(self.text()) < _curso_sort_key(other.text())


class StudentsScreen(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._modo_insp = session.rol() == "inspectoria"
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(300)
        self._debounce.timeout.connect(self._run_search)
        self._active_tab = TAB_TODOS
        self._cursos_map = db.get_cursos_nombres_map()  # {(nivel,sec): nombre}
        self._build_ui()
        self._reload_courses()
        self._run_search()

    # ─────────────────────────────────────────────
    #  BUILD UI
    # ─────────────────────────────────────────────

    def _build_ui(self):
        self.setStyleSheet(f"background: {C.BG};")
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 16)
        root.setSpacing(14)

        # ── Title row ──────────────────────────────
        top = QHBoxLayout()
        title = QLabel("Estudiantes")
        title.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: {C.TEXT};"
        )
        top.addWidget(title)
        top.addSpacing(20)

        if self._modo_insp:
            self._chip_total_pases = self._stat_chip("Total pases período", C.AMBER)
            self._chip_sin_firmar  = self._stat_chip("Sin firmar",          C.RED)
            self._chip_total       = self._stat_chip("Estudiantes",         C.TEXT3)
            for ch in (self._chip_total_pases, self._chip_sin_firmar, self._chip_total):
                top.addWidget(ch)
                top.addSpacing(6)
        else:
            self._chip_pae    = self._stat_chip("Beneficiarios", C.GREEN)
            self._chip_espera = self._stat_chip("En espera",     C.AMBER)
            self._chip_total  = self._stat_chip("Total",         C.TEXT3)
            self._chip_libres = self._stat_chip("Cupos libres",  C.BLUE)
            for ch in (self._chip_pae, self._chip_espera, self._chip_total, self._chip_libres):
                top.addWidget(ch)
                top.addSpacing(6)

        top.addStretch()
        root.addLayout(top)

        # ── Search + filter bar ────────────────────
        bar = QFrame()
        bar.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border: none;
                border-radius: 12px;
            }}
        """)
        bar_lay = QHBoxLayout(bar)
        bar_lay.setContentsMargins(14, 8, 14, 8)
        bar_lay.setSpacing(10)

        lupa = QLabel("⌕")
        lupa.setStyleSheet(f"font-size: 18px; color: {C.TEXT3};")
        bar_lay.addWidget(lupa)

        self._inp_search = QLineEdit()
        self._inp_search.setPlaceholderText("Buscar por RUN, nombre o curso…")
        self._inp_search.setStyleSheet(
            f"background: transparent; border: none; font-size: 14px; color: {C.TEXT};"
        )
        self._inp_search.textChanged.connect(lambda: self._debounce.start())
        bar_lay.addWidget(self._inp_search, stretch=1)

        bar_lay.addWidget(self._vsep())

        self._cmb_curso = QComboBox()
        self._cmb_curso.setMinimumWidth(155)
        self._cmb_curso.addItem("Todos los cursos", "")
        self._cmb_curso.currentIndexChanged.connect(self._run_search)
        bar_lay.addWidget(self._cmb_curso)

        root.addWidget(bar)

        # ── Tab segmented control ──────────────────
        tab_row = QHBoxLayout()
        tab_row.setSpacing(0)

        self._tab_btns = []
        if not self._modo_insp:
            tab_labels = ["Todos", "Beneficiarios PAE", "Lista de espera"]
            for i, lbl in enumerate(tab_labels):
                btn = QPushButton_tab(lbl, i, self._on_tab)
                self._tab_btns.append(btn)
                tab_row.addWidget(btn)

        tab_row.addStretch()

        # Botón promover por RSH (solo visible en tab espera, no en modo insp)
        self._btn_promover_rsh = AButton("↑  Promover por RSH", sound_type="save")
        self._btn_promover_rsh.setStyleSheet(f"""
            QPushButton {{
                background: {C.BLUE};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 7px 16px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: {C.NAVY_600}; }}
        """)
        self._btn_promover_rsh.clicked.connect(self._promover_por_rsh)
        self._btn_promover_rsh.setVisible(False)
        if not self._modo_insp:
            tab_row.addWidget(self._btn_promover_rsh)

        self._btn_autofill = AButton("⊞  Auto-llenar 25", sound_type="save")
        self._btn_autofill.setStyleSheet(f"""
            QPushButton {{
                background: {C.SURFACE2};
                color: {C.TEXT2};
                border: 1px solid {C.BORDER};
                border-radius: 8px;
                padding: 7px 14px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: {C.NAVY_700}; color: {C.TEXT}; }}
        """)
        self._btn_autofill.clicked.connect(self._auto_fill_waitlist)
        self._btn_autofill.setVisible(False)
        if not self._modo_insp:
            tab_row.addWidget(self._btn_autofill)

        root.addLayout(tab_row)

        # ── Table ──────────────────────────────────
        self._table = QTableWidget()
        if self._modo_insp:
            self._table.setColumnCount(len(HEADERS_INS))
            self._table.setHorizontalHeaderLabels(HEADERS_INS)
            hdr = self._table.horizontalHeader()
            hdr.setSectionResizeMode(COL_INS_RUN,       QHeaderView.ResizeMode.Interactive)
            hdr.setSectionResizeMode(COL_INS_APELLIDO,  QHeaderView.ResizeMode.Stretch)
            hdr.setSectionResizeMode(COL_INS_NOMBRE,    QHeaderView.ResizeMode.Stretch)
            hdr.setSectionResizeMode(COL_INS_CURSO,     QHeaderView.ResizeMode.Interactive)
            hdr.setSectionResizeMode(COL_INS_SINFIRMAR, QHeaderView.ResizeMode.Interactive)
            hdr.setSectionResizeMode(COL_INS_TOTAL,     QHeaderView.ResizeMode.Interactive)
            self._table.setColumnWidth(COL_INS_RUN,       110)
            self._table.setColumnWidth(COL_INS_CURSO,      95)
            self._table.setColumnWidth(COL_INS_SINFIRMAR, 110)
            self._table.setColumnWidth(COL_INS_TOTAL,      90)
        else:
            self._table.setColumnCount(len(HEADERS))
            self._table.setHorizontalHeaderLabels(HEADERS)
            hdr = self._table.horizontalHeader()
            hdr.setSectionResizeMode(COL_RUN,      QHeaderView.ResizeMode.Interactive)
            hdr.setSectionResizeMode(COL_APELLIDO, QHeaderView.ResizeMode.Stretch)
            hdr.setSectionResizeMode(COL_NOMBRE,   QHeaderView.ResizeMode.Stretch)
            hdr.setSectionResizeMode(COL_CURSO,    QHeaderView.ResizeMode.Interactive)
            hdr.setSectionResizeMode(COL_ESTADO,   QHeaderView.ResizeMode.Interactive)
            hdr.setSectionResizeMode(COL_RSH,      QHeaderView.ResizeMode.Interactive)
            hdr.setSectionResizeMode(COL_EXTRA,    QHeaderView.ResizeMode.Interactive)
            hdr.setSectionResizeMode(COL_STRIKES,  QHeaderView.ResizeMode.Interactive)
            self._table.setColumnWidth(COL_RUN,     110)
            self._table.setColumnWidth(COL_CURSO,   95)
            self._table.setColumnWidth(COL_ESTADO,  148)
            self._table.setColumnWidth(COL_RSH,     70)
            self._table.setColumnWidth(COL_EXTRA,   80)
            self._table.setColumnWidth(COL_STRIKES, 65)
        hdr.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(False)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setDefaultSectionSize(40)
        self._table.setSortingEnabled(True)
        # Click derecho → menú contextual
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._context_menu)
        # Click izquierdo → copia al portapapeles
        self._table.itemClicked.connect(self._on_cell_clicked)
        root.addWidget(self._table, stretch=1)

        # ── Bottom action bar ──────────────────────
        bot = QHBoxLayout()
        bot.setSpacing(10)

        self._lbl_count = QLabel("—")
        self._lbl_count.setStyleSheet(f"color: {C.TEXT3}; font-size: 12px;")
        bot.addWidget(self._lbl_count)

        bot.addStretch()

        self._saved_ind = SavedIndicator()
        bot.addWidget(self._saved_ind)

        if not self._modo_insp:
            # Acción masiva (solo para PAE/admin)
            lbl_mover = QLabel("Mover seleccionados →")
            lbl_mover.setStyleSheet(f"color: {C.TEXT2}; font-size: 12px;")
            bot.addWidget(lbl_mover)

            self._cmb_action = QComboBox()
            self._cmb_action.setMinimumWidth(160)
            self._cmb_action.addItem("Beneficiario PAE", "pae")
            self._cmb_action.addItem("Lista de espera", "espera")
            self._cmb_action.addItem("No beneficiario", "no_pae")
            bot.addWidget(self._cmb_action)

            btn_apply = AButton("Aplicar", sound_type="save")
            btn_apply.setStyleSheet(btn_primary())
            btn_apply.clicked.connect(self._apply_to_selected)
            bot.addWidget(btn_apply)

        root.addLayout(bot)

        # Activar tab inicial
        self._on_tab(TAB_TODOS)

    # ─────────────────────────────────────────────
    #  HELPERS
    # ─────────────────────────────────────────────

    @staticmethod
    def _rgba(hex_color: str, alpha: float) -> str:
        """Convierte #RRGGBB + alpha float → string rgba() para QSS."""
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        a = int(alpha * 255)
        return f"rgba({r},{g},{b},{a})"

    def _stat_chip(self, label: str, color: str) -> QFrame:
        chip = QFrame()
        chip.setStyleSheet(f"""
            QFrame {{
                background: {self._rgba(color, 0.08)};
                border: 1px solid {self._rgba(color, 0.28)};
                border-radius: 10px;
            }}
        """)
        lay = QHBoxLayout(chip)
        lay.setContentsMargins(10, 5, 10, 5)
        lay.setSpacing(6)

        dot = QLabel("●")
        dot.setStyleSheet(
            f"color: {color}; font-size: 8px; background: transparent;"
        )

        val = QLabel("—")
        val.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {color}; background: transparent;"
        )
        val.setObjectName("val")

        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"font-size: 11px; color: {C.TEXT2}; background: transparent;"
        )

        lay.addWidget(dot)
        lay.addWidget(val)
        lay.addWidget(lbl)
        return chip

    def _update_chip(self, chip: QFrame, value: str):
        lbl = chip.findChild(QLabel, "val")
        if lbl:
            lbl.setText(value)

    def _vsep(self) -> QFrame:
        s = QFrame()
        s.setFrameShape(QFrame.Shape.VLine)
        s.setFixedWidth(1)
        s.setStyleSheet(f"background: {C.BORDER};")
        return s

    def _on_tab(self, idx: int):
        self._active_tab = idx
        for i, btn in enumerate(self._tab_btns):
            btn.set_active(i == idx)
        if not self._modo_insp:
            self._btn_promover_rsh.setVisible(idx == TAB_ESPERA)
            self._btn_autofill.setVisible(idx == TAB_ESPERA)
        self._run_search()

    # ─────────────────────────────────────────────
    #  DATA
    # ─────────────────────────────────────────────

    def _reload_courses(self):
        self._cursos_map = db.get_cursos_nombres_map()
        current = self._cmb_curso.currentData()
        self._cmb_curso.blockSignals(True)
        self._cmb_curso.clear()
        self._cmb_curso.addItem("Todos los cursos", "")
        for c in db.get_cursos():
            label = db.display_curso(c, self._cursos_map) or c
            self._cmb_curso.addItem(label, c)  # data=raw, text=display
        idx = self._cmb_curso.findData(current)
        if idx >= 0:
            self._cmb_curso.setCurrentIndex(idx)
        self._cmb_curso.blockSignals(False)

    def _run_search(self):
        query = self._inp_search.text().strip()
        curso = self._cmb_curso.currentData()

        if query:
            rows = db.search_students(query, limit=500)
        elif curso:
            rows = db.get_students_by_curso(curso)
        else:
            rows = db.get_all_students(include_inactive=True)

        if self._modo_insp:
            # En modo inspectoría mostramos todos los estudiantes con stats de pases
            self._populate_insp(rows)
            self._refresh_chips_insp()
            return

        # Filtrar por tab (modo PAE/admin)
        if self._active_tab == TAB_PAE:
            rows = [r for r in rows if r["activo"] and not r["lista_espera"]]
        elif self._active_tab == TAB_ESPERA:
            rows = db.get_waitlist_sorted() if not query and not curso else \
                   [r for r in rows if r["lista_espera"]]

        self._populate(rows)
        self._refresh_chips()

    def _populate(self, rows: list):
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(rows))

        for i, est in enumerate(rows):
            est       = dict(est)
            run_raw   = est["run"]
            run_fmt   = utils.run_display(run_raw)
            nombres   = est.get("nombres") or ""
            ap_pat    = est.get("apellido_paterno") or ""
            ap_mat    = est.get("apellido_materno") or ""
            apellidos = f"{ap_pat} {ap_mat}".strip()
            curso     = est.get("curso") or ""
            activo    = est["activo"]
            espera    = est["lista_espera"]
            strikes   = db.count_strikes(run_raw)
            rsh_raw   = est.get("puntaje_rsh")
            extra_raw = est.get("puntaje_extra")
            rsh_txt   = str(rsh_raw) if rsh_raw is not None else "—"
            extra_txt = str(extra_raw) if extra_raw is not None else "—"

            # Estado y colores de fila
            if activo and not espera:
                estado_key = "beneficiario"
            elif espera:
                estado_key = "espera"
            else:
                estado_key = "no_beneficiario"

            estado_txt, estado_clr, row_bg = ESTADO_INFO[estado_key]
            row_color = QColor(row_bg) if row_bg != "transparent" else None

            def cell(txt, run=run_raw, bg=row_color):
                item = QTableWidgetItem(txt)
                item.setData(Qt.ItemDataRole.UserRole, run)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
                )
                if bg:
                    item.setBackground(bg)
                if txt:
                    item.setToolTip(txt)
                return item

            self._table.setItem(i, COL_RUN,     cell(run_fmt))
            self._table.setItem(i, COL_APELLIDO, cell(apellidos))
            self._table.setItem(i, COL_NOMBRE,   cell(nombres))

            # Curso con display name "1° CAB" en lugar de "1° medioA"
            curso_display = db.display_curso(curso, self._cursos_map)
            curso_item = _CursoItem(curso_display, curso, run_raw, row_color)
            self._table.setItem(i, COL_CURSO, curso_item)

            est_item = cell(estado_txt)
            est_item.setForeground(QColor(estado_clr))
            f = est_item.font(); f.setBold(True); est_item.setFont(f)
            self._table.setItem(i, COL_ESTADO, est_item)

            rsh_item = cell(rsh_txt)
            if rsh_raw is not None:
                rsh_item.setData(Qt.ItemDataRole.UserRole + 1, rsh_raw)
                pct = min(rsh_raw, 100)
                rsh_item.setForeground(QColor(
                    C.RED if pct <= 40 else (C.AMBER if pct <= 70 else C.TEXT2)
                ))
            self._table.setItem(i, COL_RSH,    rsh_item)
            self._table.setItem(i, COL_EXTRA,  cell(extra_txt))

            str_item = cell(str(strikes))
            str_item.setForeground(QColor(
                C.RED if strikes >= 3 else (C.AMBER if strikes > 0 else C.TEXT3)
            ))
            self._table.setItem(i, COL_STRIKES, str_item)

        self._table.setSortingEnabled(True)
        self._lbl_count.setText(
            f"{len(rows)} estudiante{'s' if len(rows) != 1 else ''}"
        )

    def _refresh_chips(self):
        info = logic.get_capacidad_info()
        counts = db.count_students()
        self._update_chip(self._chip_pae,    str(info["activos"]))
        self._update_chip(self._chip_espera, str(info["lista_espera"]))
        self._update_chip(self._chip_total,  str(counts["total"]))
        self._update_chip(self._chip_libres, str(info["disponibles"]))

    def _populate_insp(self, rows: list):
        """Modo Inspectoría: tabla con columnas Sin firmar / Total período."""
        periodo = session.viewing_period()
        pases_map = db.get_pases_por_estudiante_periodo(periodo)

        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(rows))

        for i, est in enumerate(rows):
            est      = dict(est)
            run_raw  = est["run"]
            run_fmt  = utils.run_display(run_raw)
            nombres  = est.get("nombres") or ""
            ap_pat   = est.get("apellido_paterno") or ""
            ap_mat   = est.get("apellido_materno") or ""
            apellidos = f"{ap_pat} {ap_mat}".strip()
            curso    = est.get("curso") or ""
            stats    = pases_map.get(run_raw, {"total": 0, "sin_firmar": 0})
            total    = stats["total"]
            sf       = stats["sin_firmar"]

            def cell(txt, run=run_raw):
                item = QTableWidgetItem(txt)
                item.setData(Qt.ItemDataRole.UserRole, run)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
                )
                return item

            self._table.setItem(i, COL_INS_RUN,      cell(run_fmt))
            self._table.setItem(i, COL_INS_APELLIDO,  cell(apellidos))
            self._table.setItem(i, COL_INS_NOMBRE,    cell(nombres))
            curso_display = db.display_curso(curso, self._cursos_map)
            self._table.setItem(i, COL_INS_CURSO,     cell(curso_display))

            # Sin firmar: numérico con color alerta
            sf_item = _NumericItem(sf)
            sf_item.setData(Qt.ItemDataRole.UserRole, run_raw)
            if sf >= 3:
                sf_item.setForeground(QColor(C.RED))
                f = sf_item.font(); f.setBold(True); sf_item.setFont(f)
            elif sf > 0:
                sf_item.setForeground(QColor(C.AMBER))
            else:
                sf_item.setForeground(QColor(C.TEXT3))
            self._table.setItem(i, COL_INS_SINFIRMAR, sf_item)

            # Total período
            tot_item = _NumericItem(total)
            tot_item.setData(Qt.ItemDataRole.UserRole, run_raw)
            tot_item.setForeground(QColor(C.TEXT2 if total else C.TEXT3))
            self._table.setItem(i, COL_INS_TOTAL, tot_item)

        self._table.setSortingEnabled(True)
        self._lbl_count.setText(
            f"{len(rows)} estudiante{'s' if len(rows) != 1 else ''}"
        )

    def _refresh_chips_insp(self):
        """Actualiza chips del modo inspectoría."""
        periodo = session.viewing_period()
        pases_map = db.get_pases_por_estudiante_periodo(periodo)
        total_pases = sum(v["total"] for v in pases_map.values())
        sin_firmar  = sum(v["sin_firmar"] for v in pases_map.values())
        counts = db.count_students()
        self._update_chip(self._chip_total_pases, str(total_pases))
        self._update_chip(self._chip_sin_firmar,  str(sin_firmar))
        self._update_chip(self._chip_total,       str(counts["total"]))

    def refresh_period(self):
        """Llamado por main_window cuando el usuario cambia el período visualizado."""
        self._run_search()

    # ─────────────────────────────────────────────
    #  ACTIONS
    # ─────────────────────────────────────────────

    def _selected_runs(self) -> list:
        rows = set(idx.row() for idx in self._table.selectedIndexes())
        result = []
        for row in sorted(rows):
            item = self._table.item(row, COL_RUN)
            if item:
                result.append(item.data(Qt.ItemDataRole.UserRole))
        return result

    def _apply_to_selected(self):
        runs = self._selected_runs()
        if not runs:
            self._saved_ind.show_error("✗  Selecciona al menos un estudiante")
            sound.error()
            return
        destino = self._cmb_action.currentData()
        for run in runs:
            if destino == "pae":
                db.update_student_status(run, 1, 0)
            elif destino == "espera":
                db.update_student_status(run, 1, 1)
            elif destino == "no_pae":
                db.update_student_status(run, 0, 0)
        self._run_search()
        self._saved_ind.show_saved(f"✓  {len(runs)} actualizado(s)")

    def _promover_por_rsh(self):
        run = db.promote_next_by_priority()
        if run:
            self._run_search()
            self._saved_ind.show_saved(f"✓  Promovido: {utils.run_display(run)}")
        else:
            self._saved_ind.show_error("✗  Sin cupos o lista vacía")
            sound.error()

    def _on_cell_clicked(self, item):
        """Click en celda → copia texto al portapapeles."""
        if item and item.text() and item.text() != "—":
            QApplication.clipboard().setText(item.text())
            self._saved_ind.show_saved("✓  Copiado")

    def _edit_rsh_selected(self):
        """Abre diálogo para editar RSH% de todos los seleccionados (multi-select)."""
        runs = self._selected_runs()
        if not runs:
            return
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QDialogButtonBox
        )
        dlg = QDialog(self)
        dlg.setWindowTitle(
            f"Editar RSH%  ·  {len(runs)} estudiante{'s' if len(runs) != 1 else ''}"
        )
        dlg.setFixedWidth(340)
        dlg.setStyleSheet(f"background: {C.SURFACE}; color: {C.TEXT};")
        lay = QVBoxLayout(dlg)
        lay.setSpacing(14)
        lay.setContentsMargins(20, 20, 20, 20)

        info = QLabel(
            "<b>RSH</b> — Registro Social de Hogares<br>"
            f"<small style='color:{C.TEXT2}'>"
            "0–100%  ·  menor valor = mayor vulnerabilidad = mayor prioridad en PAE<br>"
            "Rangos: 0–40 alta vulnerabilidad · 41–70 media · 71–100 baja</small>"
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {C.TEXT}; background: transparent;")
        lay.addWidget(info)

        rsh_row = QHBoxLayout()
        lbl_r = QLabel("Puntaje RSH:")
        lbl_r.setStyleSheet(f"color: {C.TEXT2}; background: transparent;")
        rsh_row.addWidget(lbl_r)
        spn_rsh = QSpinBox()
        spn_rsh.setRange(0, 100)
        spn_rsh.setSingleStep(10)
        spn_rsh.setSpecialValueText("Sin asignar")
        spn_rsh.setValue(0)
        rsh_row.addWidget(spn_rsh)
        lay.addLayout(rsh_row)

        extra_row = QHBoxLayout()
        lbl_e = QLabel("Puntos extra:")
        lbl_e.setStyleSheet(f"color: {C.TEXT2}; background: transparent;")
        extra_row.addWidget(lbl_e)
        spn_extra = QSpinBox()
        spn_extra.setRange(0, 9999)
        spn_extra.setSpecialValueText("Sin asignar")
        spn_extra.setValue(0)
        extra_row.addWidget(spn_extra)
        lay.addLayout(extra_row)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)

        if dlg.exec():
            rsh_val   = spn_rsh.value()   if spn_rsh.value()   > 0 else None
            extra_val = spn_extra.value() if spn_extra.value() > 0 else None
            for run in runs:
                db.update_student_scores(
                    run,
                    puntaje_rsh=rsh_val,
                    puntaje_extra=extra_val,
                )
            self._run_search()
            self._saved_ind.show_saved(
                f"✓  RSH% guardado  ({len(runs)} estudiante{'s' if len(runs) != 1 else ''})"
            )
            sound.save()

    def _auto_fill_waitlist(self):
        """Llena la lista de espera hasta 25 estudiantes, priorizando por RSH%."""
        counts = db.count_students()
        espera_actual = counts["espera"]
        target = 25
        needed = max(0, target - espera_actual)

        if needed == 0:
            self._saved_ind.show_error("✗  La lista ya tiene 25 o más estudiantes")
            sound.error()
            return

        candidates = db.get_candidates_for_waitlist()
        if not candidates:
            self._saved_ind.show_error("✗  Sin candidatos disponibles")
            sound.error()
            return

        to_add = list(candidates[:needed])
        for est in to_add:
            db.update_student_status(est["run"], activo=1, lista_espera=1)

        self._run_search()
        self._saved_ind.show_saved(
            f"✓  {len(to_add)} agregado{'s' if len(to_add) != 1 else ''} a lista de espera"
        )
        sound.save()

    def _context_menu(self, pos: QPoint):
        """Menú contextual click derecho — cambio de estado."""
        item = self._table.itemAt(pos)
        if item is None:
            return
        run = item.data(Qt.ItemDataRole.UserRole)
        if not run:
            return

        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: {C.SURFACE};
                border: 1px solid {C.BORDER};
                border-radius: 10px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 8px 18px;
                border-radius: 6px;
                font-size: 13px;
                color: {C.TEXT};
            }}
            QMenu::item:selected {{
                background: {C.BLUE_DIM};
                color: {C.BLUE};
            }}
            QMenu::separator {{
                height: 1px;
                background: {C.BORDER};
                margin: 4px 8px;
            }}
        """)

        import session as _sess
        rol = _sess.rol()

        # ── Estado PAE (solo admin) ──────────────────────
        if rol == "admin":
            act_pae    = QAction("✓  Beneficiario PAE",  menu)
            act_espera = QAction("↷  Lista de espera",   menu)
            act_no_pae = QAction("✗  No beneficiario",   menu)
            menu.addAction(act_pae)
            menu.addAction(act_espera)
            menu.addAction(act_no_pae)
            act_pae.triggered.connect(   lambda: self._change_status(run, "pae"))
            act_espera.triggered.connect(lambda: self._change_status(run, "espera"))
            act_no_pae.triggered.connect(lambda: self._change_status(run, "no_pae"))
            menu.addSeparator()

        # ── RSH (pae + admin, NO inspectoria) ────────────
        if rol in ("pae", "admin"):
            n_sel = len(set(idx.row() for idx in self._table.selectedIndexes()))
            lbl_rsh = f"◎  Editar RSH%…  ({n_sel} seleccionado{'s' if n_sel != 1 else ''})"
            act_rsh = QAction(lbl_rsh, menu)
            act_rsh.triggered.connect(self._edit_rsh_selected)
            menu.addAction(act_rsh)

        # ── Datos personales (inspectoria + admin, NO pae) ──
        if rol in ("inspectoria", "admin"):
            if rol == "admin":
                menu.addSeparator()
            act_curso = QAction("⊞  Cambiar curso…", menu)
            act_curso.triggered.connect(lambda: self._change_curso_dialog(run))
            menu.addAction(act_curso)

            act_nombre = QAction("✎  Editar nombre…", menu)
            act_nombre.triggered.connect(lambda: self._edit_nombre_dialog(run))
            menu.addAction(act_nombre)

            act_tel = QAction("📞  Teléfono apoderado…", menu)
            act_tel.triggered.connect(lambda: self._edit_telefono_dialog(run))
            menu.addAction(act_tel)

        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _change_curso_dialog(self, run: str):
        """Diálogo dropdown para cambiar el curso de un estudiante."""
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QDialogButtonBox, QComboBox
        )
        st = db.get_student(run)
        if not st:
            return
        st = dict(st)

        dlg = QDialog(self)
        dlg.setWindowTitle("Cambiar curso")
        dlg.setFixedWidth(340)
        dlg.setStyleSheet(f"background: {C.SURFACE}; color: {C.TEXT};")
        lay = QVBoxLayout(dlg)
        lay.setSpacing(14)
        lay.setContentsMargins(20, 20, 20, 20)

        run_fmt = utils.run_display(run)
        ap = f"{st.get('apellido_paterno','')} {st.get('apellido_materno','')}".strip()
        info = QLabel(f"<b>{run_fmt}</b>  ·  {ap}, {st.get('nombres','')}")
        info.setStyleSheet(f"color: {C.TEXT2}; background: transparent;")
        lay.addWidget(info)

        cur_raw = st.get("curso", "")
        lbl_actual = QLabel(
            f"Curso actual:  <b>{db.display_curso(cur_raw, self._cursos_map) or cur_raw or '—'}</b>"
        )
        lbl_actual.setStyleSheet(f"color: {C.TEXT2}; background: transparent;")
        lay.addWidget(lbl_actual)

        # Dropdown con los 24 cursos
        cmb = QComboBox()
        cursos_list = db.get_cursos_nombres_list()
        _LETRAS = ["A", "B", "C", "D", "E", "F"]
        _RAW_MAP = {}  # display → raw_curso_key
        for entry in cursos_list:
            n, s, nombre = entry["nivel"], entry["seccion"], entry["nombre"]
            display = f"{n}° {nombre}  ({n}° medio {s})"
            raw_val = f"{n}° medio{s}"
            cmb.addItem(display, raw_val)
            _RAW_MAP[display] = raw_val
        # Seleccionar el actual
        for i in range(cmb.count()):
            if cmb.itemData(i) == cur_raw:
                cmb.setCurrentIndex(i)
                break
        lay.addWidget(cmb)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)

        if dlg.exec():
            nuevo_raw = cmb.currentData()
            if nuevo_raw and nuevo_raw != cur_raw:
                db.update_student_curso(run, nuevo_raw)
                self._reload_courses()
                self._run_search()
                nuevo_display = db.display_curso(nuevo_raw, self._cursos_map)
                self._saved_ind.show_saved(f"✓  Curso → {nuevo_display}")
                sound.save()

    def _edit_nombre_dialog(self, run: str):
        """Diálogo para editar nombre/apellidos con registro de motivo."""
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QDialogButtonBox,
            QComboBox, QLineEdit, QLabel
        )
        st = db.get_student(run)
        if not st:
            return
        st = dict(st)

        dlg = QDialog(self)
        dlg.setWindowTitle("Editar nombre")
        dlg.setFixedWidth(420)
        dlg.setStyleSheet(f"background: {C.SURFACE}; color: {C.TEXT};")
        lay = QVBoxLayout(dlg)
        lay.setSpacing(12)
        lay.setContentsMargins(20, 20, 20, 20)

        run_fmt = utils.run_display(run)
        lbl_run = QLabel(f"RUN:  <b>{run_fmt}</b>")
        lbl_run.setStyleSheet(f"color: {C.TEXT2}; background: transparent;")
        lay.addWidget(lbl_run)

        def _field(label: str, value: str):
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setMinimumWidth(120)
            lbl.setStyleSheet(f"color: {C.TEXT2}; background: transparent;")
            inp = QLineEdit(value)
            inp.setStyleSheet(
                f"background: {C.BG}; border: 1px solid {C.BORDER}; "
                f"border-radius: 6px; padding: 6px 10px; color: {C.TEXT};"
            )
            row.addWidget(lbl)
            row.addWidget(inp)
            lay.addLayout(row)
            return inp

        inp_nombres  = _field("Nombres:",         st.get("nombres", ""))
        inp_ap_pat   = _field("Apellido paterno:", st.get("apellido_paterno", ""))
        inp_ap_mat   = _field("Apellido materno:", st.get("apellido_materno", ""))

        # Tipo de cambio
        row_tipo = QHBoxLayout()
        lbl_tipo = QLabel("Motivo del cambio:")
        lbl_tipo.setMinimumWidth(120)
        lbl_tipo.setStyleSheet(f"color: {C.TEXT2}; background: transparent;")
        cmb_tipo = QComboBox()
        for opt in [
            "Corrección ortográfica",
            "Cambio nombre social",
            "Decreto / resolución",
            "Error en importación",
            "Otro",
        ]:
            cmb_tipo.addItem(opt)
        row_tipo.addWidget(lbl_tipo)
        row_tipo.addWidget(cmb_tipo)
        lay.addLayout(row_tipo)

        # Motivo detalle
        row_motivo = QHBoxLayout()
        lbl_mot = QLabel("Detalle (opcional):")
        lbl_mot.setMinimumWidth(120)
        lbl_mot.setStyleSheet(f"color: {C.TEXT2}; background: transparent;")
        inp_motivo = QLineEdit()
        inp_motivo.setPlaceholderText("Ej: Decreto N° 123, resolución CREA…")
        inp_motivo.setStyleSheet(
            f"background: {C.BG}; border: 1px solid {C.BORDER}; "
            f"border-radius: 6px; padding: 6px 10px; color: {C.TEXT};"
        )
        row_motivo.addWidget(lbl_mot)
        row_motivo.addWidget(inp_motivo)
        lay.addLayout(row_motivo)

        aviso = QLabel("⚠  Todos los cambios quedan registrados en el log de nombres.")
        aviso.setStyleSheet(f"color: {C.AMBER}; font-size: 11px; background: transparent;")
        aviso.setWordWrap(True)
        lay.addWidget(aviso)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)

        if dlg.exec():
            db.update_student_nombre(
                run,
                nuevos_nombres  = inp_nombres.text().strip(),
                nuevo_ap_pat    = inp_ap_pat.text().strip(),
                nuevo_ap_mat    = inp_ap_mat.text().strip(),
                tipo_cambio     = cmb_tipo.currentText(),
                motivo          = inp_motivo.text().strip(),
            )
            self._run_search()
            self._saved_ind.show_saved("✓  Nombre actualizado")
            sound.save()

    def _edit_telefono_dialog(self, run: str):
        """Diálogo para editar el teléfono del apoderado."""
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QDialogButtonBox, QLabel
        )
        from ui.widgets import PhoneLineEdit
        st = db.get_student(run)
        if not st:
            return
        st = dict(st)

        dlg = QDialog(self)
        dlg.setWindowTitle("Teléfono apoderado")
        dlg.setFixedWidth(380)
        dlg.setStyleSheet(f"background: {C.SURFACE}; color: {C.TEXT};")
        lay = QVBoxLayout(dlg)
        lay.setSpacing(12)
        lay.setContentsMargins(20, 20, 20, 20)

        run_fmt = utils.run_display(run)
        ap = f"{st.get('apellido_paterno','')} {st.get('apellido_materno','')}".strip()
        info = QLabel(f"<b>{run_fmt}</b>  ·  {ap}, {st.get('nombres','')}")
        info.setStyleSheet(f"color: {C.TEXT2}; background: transparent;")
        lay.addWidget(info)

        lbl = QLabel("Teléfono apoderado:")
        lbl.setStyleSheet(f"color: {C.TEXT2}; background: transparent;")
        lay.addWidget(lbl)

        inp = PhoneLineEdit()
        inp.set_phone(st.get("telefono_apoderado", "") or "")
        inp.setStyleSheet(
            f"background: {C.BG}; border: 1px solid {C.BORDER}; "
            f"border-radius: 6px; padding: 6px 10px; color: {C.TEXT}; font-size: 15px;"
        )
        lay.addWidget(inp)

        hint = QLabel("Se usará para enviar notificaciones de atraso por WhatsApp.")
        hint.setStyleSheet(f"color: {C.TEXT3}; font-size: 11px; background: transparent;")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)

        if dlg.exec():
            tel = inp.phone_display()
            db.update_student_telefono_apoderado(run, tel)
            self._saved_ind.show_saved("✓  Teléfono apoderado guardado")
            sound.save()

    def _change_status(self, run: str, destino: str):
        if destino == "pae":
            db.update_student_status(run, 1, 0)
        elif destino == "espera":
            db.update_student_status(run, 1, 1)
        elif destino == "no_pae":
            db.update_student_status(run, 0, 0)
        self._run_search()
        self._saved_ind.show_saved(f"✓  Estado actualizado")

    def showEvent(self, event):
        super().showEvent(event)
        self._reload_courses()
        self._run_search()

    def _get_selected_run_and_student(self) -> tuple:
        """Retorna (run, student_dict) del primer item seleccionado, o (None, None)."""
        idxs = self._table.selectedIndexes()
        if not idxs:
            return None, None
        row = idxs[0].row()
        item = self._table.item(row, COL_RUN)
        if not item:
            return None, None
        run = item.data(Qt.ItemDataRole.UserRole)
        st = db.get_student(run)
        return run, (dict(st) if st else None)


# ─────────────────────────────────────────────
#  HELPERS LOCALES (no dependen de imports externos extra)
# ─────────────────────────────────────────────

class _NumericItem(QTableWidgetItem):
    """QTableWidgetItem con sort numérico."""
    def __init__(self, value: int, display: str = ""):
        super().__init__(display or (str(value) if value else "—"))
        self._value = value
        self.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)

    def __lt__(self, other):
        if isinstance(other, _NumericItem):
            return self._value < other._value
        return super().__lt__(other)


class QPushButton_tab(QFrame):
    """Botón de pestaña estilo segmented control macOS."""

    def __init__(self, label: str, idx: int, callback, parent=None):
        super().__init__(parent)
        self._idx = idx
        self._cb  = callback
        self._active = False

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        from PyQt6.QtWidgets import QPushButton
        self._btn = QPushButton(label)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.clicked.connect(lambda: self._cb(self._idx))
        self._btn.setFlat(True)
        lay.addWidget(self._btn)

        self.set_active(False)

    def set_active(self, active: bool):
        self._active = active
        if active:
            self._btn.setStyleSheet(f"""
                QPushButton {{
                    background: {C.SURFACE};
                    color: {C.BLUE};
                    border: 1px solid {C.BORDER};
                    border-radius: 8px;
                    padding: 7px 18px;
                    font-size: 13px;
                    font-weight: 600;
                }}
            """)
        else:
            self._btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {C.TEXT2};
                    border: 1px solid transparent;
                    border-radius: 8px;
                    padding: 7px 18px;
                    font-size: 13px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background: {C.SURFACE3};
                    color: {C.TEXT};
                }}
            """)


