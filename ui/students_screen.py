"""
students_screen.py — Gestión de estudiantes PAE Control

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
from ui.theme   import C, sound, btn_primary, btn_secondary
from ui.widgets import AButton, HDivider, SectionHeader, SavedIndicator


# ── Columnas de la tabla
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

    def __init__(self, curso: str, run: str, bg=None):
        super().__init__(curso)
        self.setData(Qt.ItemDataRole.UserRole, run)
        self.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        if bg:
            self.setBackground(bg)

    def __lt__(self, other):
        return _curso_sort_key(self.text()) < _curso_sort_key(other.text())


class StudentsScreen(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(300)
        self._debounce.timeout.connect(self._run_search)
        self._active_tab = TAB_TODOS
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
                border: 1px solid {C.BORDER};
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
        tab_labels = ["Todos", "Beneficiarios PAE", "Lista de espera"]
        for i, lbl in enumerate(tab_labels):
            btn = QPushButton_tab(lbl, i, self._on_tab)
            self._tab_btns.append(btn)
            tab_row.addWidget(btn)

        tab_row.addStretch()

        # Botón promover por RSH (solo visible en tab espera)
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
        tab_row.addWidget(self._btn_autofill)

        root.addLayout(tab_row)

        # ── Table ──────────────────────────────────
        self._table = QTableWidget()
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

        # Acción masiva
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
        self._btn_promover_rsh.setVisible(idx == TAB_ESPERA)
        self._btn_autofill.setVisible(idx == TAB_ESPERA)
        self._run_search()

    # ─────────────────────────────────────────────
    #  DATA
    # ─────────────────────────────────────────────

    def _reload_courses(self):
        current = self._cmb_curso.currentData()
        self._cmb_curso.blockSignals(True)
        self._cmb_curso.clear()
        self._cmb_curso.addItem("Todos los cursos", "")
        for c in db.get_cursos():
            self._cmb_curso.addItem(c, c)
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

        # Filtrar por tab
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

            # Curso con sort key personalizado (ignora "medio")
            curso_item = _CursoItem(curso, run_raw, row_color)
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
        n_sel = len(set(idx.row() for idx in self._table.selectedIndexes()))
        lbl_rsh = f"◎  Editar RSH%…  ({n_sel} seleccionado{'s' if n_sel != 1 else ''})"
        act_rsh = QAction(lbl_rsh, menu)
        act_rsh.triggered.connect(self._edit_rsh_selected)
        menu.addAction(act_rsh)

        menu.exec(self._table.viewport().mapToGlobal(pos))

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


# ─────────────────────────────────────────────
#  HELPERS LOCALES (no dependen de imports externos extra)
# ─────────────────────────────────────────────

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


