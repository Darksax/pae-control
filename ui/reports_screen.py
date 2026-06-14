"""
reports_screen.py — Reportes PAE Control 0.9 Alpha

- KPI cards: registros / strikes / estudiantes afectados
- Tabs: Top 25 semana / Top 25 mes / Lista de espera / Log altas-bajas
- Rank pills con gradiente de color
- Exportar CSV por tab
- Auto-refresh al entrar a la pantalla
- Sin QMessageBox — todo inline
"""

import csv
import os
import subprocess
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QTabWidget, QAbstractItemView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont

import db
import utils
from ui.theme   import C, sound
from ui.widgets import AButton, SectionHeader, StatCard


def _rank_color(rank: int) -> str:
    if rank <= 5:   return C.RED
    if rank <= 10:  return C.AMBER
    if rank <= 15:  return C.GOLD_500
    return C.TEXT3


class ReportsScreen(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        self.setStyleSheet(f"background: {C.BG};")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # ── Header ──────────────────────────────────
        hdr = QHBoxLayout()

        title = QLabel("Reportes")
        title.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: {C.TEXT}; background: transparent;"
        )
        hdr.addWidget(title)
        hdr.addStretch()

        self._lbl_range = QLabel("")
        self._lbl_range.setStyleSheet(
            f"font-size: 12px; color: {C.TEXT3}; background: transparent;"
        )
        hdr.addWidget(self._lbl_range)
        hdr.addSpacing(12)

        _btn_style = f"""
            QPushButton {{
                background: transparent;
                color: {C.TEXT2};
                border: 1.5px solid {C.BORDER};
                border-radius: 8px;
                padding: 7px 14px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: {C.SURFACE2}; color: {C.TEXT}; }}
        """

        btn_export = AButton("↓  Exportar CSV", sound_type="click")
        btn_export.setStyleSheet(_btn_style)
        btn_export.clicked.connect(self._export_current_tab)
        hdr.addWidget(btn_export)
        hdr.addSpacing(6)

        btn_refresh = AButton("↻  Actualizar", sound_type="click")
        btn_refresh.setStyleSheet(_btn_style)
        btn_refresh.clicked.connect(self._load_data)
        hdr.addWidget(btn_refresh)
        root.addLayout(hdr)

        # ── KPI row ──────────────────────────────────
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(12)

        self._kpi_regs    = StatCard("Registros semana",  "—", accent=C.NAVY_400)
        self._kpi_strikes = StatCard("Strikes semana",    "—", accent=C.RED)
        self._kpi_afect   = StatCard("Con strikes",       "—", accent=C.AMBER)

        for card in (self._kpi_regs, self._kpi_strikes, self._kpi_afect):
            card.setMinimumHeight(88)
            kpi_row.addWidget(card)

        root.addLayout(kpi_row)

        # ── Tabs ─────────────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1.5px solid {C.BORDER};
                border-radius: 12px;
                background: {C.SURFACE};
                top: -1px;
            }}
            QTabBar::tab {{
                background: transparent;
                color: {C.TEXT2};
                padding: 9px 22px;
                border: none;
                border-radius: 8px;
                margin: 2px;
                font-weight: 500;
                font-size: 13px;
            }}
            QTabBar::tab:selected {{
                background: {C.BLUE_DIM};
                color: {C.BLUE};
                font-weight: 700;
                border-bottom: 2px solid {C.BLUE};
            }}
            QTabBar::tab:hover:!selected {{
                background: {C.SURFACE};
                color: {C.TEXT};
            }}
        """)

        self._tbl_semana = self._make_table()
        self._tbl_mes    = self._make_table()
        self._tbl_espera = self._make_espera_table()
        self._tbl_log    = self._make_log_table()

        self._tabs.addTab(self._tbl_semana, "Top 25 — Semana")
        self._tabs.addTab(self._tbl_mes,    "Top 25 — Mes")
        self._tabs.addTab(self._tbl_espera, "Lista de espera")
        self._tabs.addTab(self._tbl_log,    "Log altas/bajas")

        root.addWidget(self._tabs, stretch=1)

    def _make_table(self) -> QTableWidget:
        t = QTableWidget()
        t.setColumnCount(6)
        t.setHorizontalHeaderLabels(["#", "RUN", "Nombre", "Curso", "Strikes", "Riesgo"])
        t.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        t.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        t.verticalHeader().setVisible(False)
        t.setAlternatingRowColors(True)
        t.setShowGrid(False)
        t.verticalHeader().setDefaultSectionSize(40)
        t.setStyleSheet(f"""
            QTableWidget {{
                background: {C.SURFACE};
                border: none;
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
            QTableWidget::item:alternate {{
                background: {C.SURFACE2};
            }}
        """)
        return t

    def _make_espera_table(self) -> QTableWidget:
        t = QTableWidget()
        t.setColumnCount(6)
        t.setHorizontalHeaderLabels(["#", "RUN", "Apellidos", "Nombres", "Curso", "RSH %"])
        t.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        t.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        t.verticalHeader().setVisible(False)
        t.setAlternatingRowColors(True)
        t.setShowGrid(False)
        t.verticalHeader().setDefaultSectionSize(40)
        t.setStyleSheet(self._make_table().styleSheet())
        return t

    def _make_log_table(self) -> QTableWidget:
        t = QTableWidget()
        t.setColumnCount(6)
        t.setHorizontalHeaderLabels(["Fecha/Hora", "RUN", "Nombre", "Curso", "Antes", "Ahora"])
        t.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        t.verticalHeader().setVisible(False)
        t.setAlternatingRowColors(True)
        t.setShowGrid(False)
        t.verticalHeader().setDefaultSectionSize(40)
        t.setStyleSheet(self._make_table().styleSheet())
        return t

    def _load_data(self):
        # KPIs
        res = db.get_resumen_semana()
        self._kpi_regs.set_value(str(res.get("total_registros", 0)))
        self._kpi_regs.flash()
        self._kpi_strikes.set_value(str(res.get("total_strikes", 0)))
        self._kpi_strikes.flash(C.RED)
        self._kpi_afect.set_value(str(res.get("estudiantes_con_strikes", 0)))
        self._kpi_afect.flash(C.AMBER)

        # Date range label
        desde = utils.format_fecha_display(res["desde"])
        hasta = utils.format_fecha_display(res["hasta"])
        self._lbl_range.setText(f"{desde}  →  {hasta}")

        # Tabs
        self._fill_table(self._tbl_semana, db.get_top_ausentes_semana(25))
        self._fill_table(self._tbl_mes,    db.get_top_ausentes_mes(25))
        self._fill_espera(db.get_waitlist_sorted())
        self._fill_log(db.get_status_log(200))

    def _fill_table(self, tabla: QTableWidget, rows: list):
        tabla.setRowCount(len(rows))

        for i, row in enumerate(rows):
            rank    = i + 1
            color   = _rank_color(rank)
            run_fmt = utils.run_display(row["run_estudiante"])
            nombre  = (
                f"{row.get('apellido_paterno','') or ''} "
                f"{row.get('apellido_materno','') or ''}, "
                f"{row.get('nombres','') or ''}"
            ).strip(", ")
            curso   = row.get("curso", "") or ""
            strikes = row["total_strikes"]

            # Risk label
            if rank <= 5:    riesgo = "Crítico"
            elif rank <= 10: riesgo = "Alto"
            elif rank <= 15: riesgo = "Medio"
            else:            riesgo = "Bajo"

            values = [str(rank), run_fmt, nombre, curso, str(strikes), riesgo]

            for col, txt in enumerate(values):
                item = QTableWidgetItem(txt)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
                )

                if col == 0:   # Rank number
                    item.setForeground(QColor(color))
                    f = item.font(); f.setBold(True); item.setFont(f)
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter
                    )
                elif col == 4:  # Strikes
                    item.setForeground(QColor(color))
                    f = item.font(); f.setBold(True); item.setFont(f)
                elif col == 5:  # Risk
                    item.setForeground(QColor(color))

                tabla.setItem(i, col, item)

        tabla.resizeRowsToContents()

    def _fill_espera(self, rows: list):
        """Llena la tab Lista de espera con estudiantes priorizados por RSH."""
        _ESTADO = {
            "beneficiario":    ("Beneficiario PAE", C.GREEN),
            "espera":          ("Lista de espera",  C.AMBER),
            "no_beneficiario": ("No beneficiario",  C.TEXT3),
        }
        self._tbl_espera.setRowCount(len(rows))
        for i, r in enumerate(rows):
            run_fmt   = utils.run_display(r["run"])
            apellidos = f"{r.get('apellido_paterno','') or ''} {r.get('apellido_materno','') or ''}".strip()
            nombres   = r.get("nombres", "") or ""
            curso     = r.get("curso", "") or ""
            rsh       = r.get("puntaje_rsh")
            rsh_txt   = str(rsh) if rsh is not None else "—"

            for col, txt in enumerate([str(i + 1), run_fmt, apellidos, nombres, curso, rsh_txt]):
                item = QTableWidgetItem(txt)
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                if col == 5 and rsh is not None:
                    item.setForeground(QColor(
                        C.RED if rsh <= 40 else (C.AMBER if rsh <= 70 else C.TEXT2)
                    ))
                self._tbl_espera.setItem(i, col, item)

    def _fill_log(self, rows: list):
        """Llena la tab Log altas/bajas."""
        _LABELS = {
            "beneficiario":    ("Beneficiario PAE", C.GREEN),
            "espera":          ("Lista de espera",  C.AMBER),
            "no_beneficiario": ("No beneficiario",  C.TEXT3),
        }
        self._tbl_log.setRowCount(len(rows))
        for i, r in enumerate(rows):
            ts_raw = r.get("timestamp", "")
            try:
                ts_fmt = datetime.fromisoformat(ts_raw).strftime("%d/%m/%Y %H:%M")
            except Exception:
                ts_fmt = ts_raw
            run_fmt   = utils.run_display(r["run"])
            ap        = r.get("apellido_paterno", "") or ""
            nom       = r.get("nombres", "") or ""
            nombre    = f"{ap}, {nom}".strip(", ")
            curso     = r.get("curso", "") or ""
            ant_lbl, ant_clr = _LABELS.get(r["estado_ant"], (r["estado_ant"], C.TEXT3))
            new_lbl, new_clr = _LABELS.get(r["estado_new"], (r["estado_new"], C.TEXT3))

            values = [ts_fmt, run_fmt, nombre, curso, ant_lbl, new_lbl]
            for col, txt in enumerate(values):
                item = QTableWidgetItem(txt)
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                if col == 4:
                    item.setForeground(QColor(ant_clr))
                elif col == 5:
                    item.setForeground(QColor(new_clr))
                    f = item.font(); f.setBold(True); item.setFont(f)
                self._tbl_log.setItem(i, col, item)

    def _export_current_tab(self):
        """Exporta la tabla del tab activo como CSV a ~/pae_control/exports/."""
        tab_idx = self._tabs.currentIndex()
        tabla = [self._tbl_semana, self._tbl_mes, self._tbl_espera, self._tbl_log][tab_idx]
        tab_name = ["top25_semana", "top25_mes", "lista_espera", "log_altas_bajas"][tab_idx]

        export_dir = os.path.join(os.path.expanduser("~"), "pae_control", "exports")
        os.makedirs(export_dir, exist_ok=True)

        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(export_dir, f"{tab_name}_{ts}.csv")

        headers = [
            tabla.horizontalHeaderItem(c).text()
            for c in range(tabla.columnCount())
        ]

        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for row in range(tabla.rowCount()):
                writer.writerow([
                    (tabla.item(row, col).text() if tabla.item(row, col) else "")
                    for col in range(tabla.columnCount())
                ])

        # Abrir con la app por defecto del sistema (macOS: open, Windows: start)
        try:
            subprocess.Popen(["open", path])
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        self._load_data()
