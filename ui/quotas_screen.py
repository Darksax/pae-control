"""
quotas_screen.py — Cupos variables por día · PAE Control 0.9 Alpha

Permite:
  - Ver cupos efectivos por fecha (override o default de config)
  - Marcar un día como suspendido (sin servicio)
  - Establecer cupo específico para una fecha
  - Ver y eliminar excepciones próximas

Sin QMessageBox: todo feedback via SavedIndicator.
"""

from datetime import date
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QAbstractItemView, QCalendarWidget,
    QSpinBox, QCheckBox, QLineEdit, QSizePolicy
)
from PyQt6.QtCore import Qt, QDate, QTimer
from PyQt6.QtGui import QColor, QTextCharFormat, QFont

import db
import utils
from ui.theme   import C, sound
from ui.widgets import AButton, HDivider, SectionHeader, SavedIndicator


class QuotasScreen(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_date: str = date.today().isoformat()
        self._exceptions_cache: dict[str, dict] = {}
        self._build_ui()
        self._load_screen()

    def _build_ui(self):
        self.setStyleSheet(f"background: {C.BG};")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # ── Title ────────────────────────────────────
        title = QLabel("Cupos por día")
        title.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: {C.TEXT}; background: transparent;"
        )
        root.addWidget(title)

        sub = QLabel(
            "Establece cupos específicos por fecha o marca días sin servicio. "
            "Sin excepción, se usa el cupo base de Configuración."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet(
            f"font-size: 12px; color: {C.TEXT3}; background: transparent;"
        )
        root.addWidget(sub)

        # ── Default cupo chip ─────────────────────────
        default_row = QHBoxLayout()
        self._lbl_default = QLabel("")
        self._lbl_default.setStyleSheet(
            f"font-size: 12px; color: {C.TEXT2}; background: transparent;"
        )
        default_row.addWidget(self._lbl_default)
        default_row.addStretch()
        root.addLayout(default_row)

        # ── Two-column layout: Calendar | Edit panel ──
        cols = QHBoxLayout()
        cols.setSpacing(16)

        # Left: Calendar
        cal_card = QFrame()
        cal_card.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border: 1.5px solid {C.BORDER};
                border-radius: 14px;
            }}
        """)
        cal_lay = QVBoxLayout(cal_card)
        cal_lay.setContentsMargins(12, 12, 12, 12)
        cal_lay.setSpacing(8)

        cal_lay.addWidget(SectionHeader("Selecciona una fecha"))

        self._calendar = QCalendarWidget()
        self._calendar.setGridVisible(False)
        self._calendar.setVerticalHeaderFormat(
            QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader
        )
        self._calendar.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
        self._calendar.setMinimumDate(QDate(2020, 1, 1))
        self._calendar.setSelectedDate(QDate.currentDate())
        self._calendar.setStyleSheet(f"""
            QCalendarWidget QWidget {{
                background: {C.SURFACE};
                color: {C.TEXT};
                border: none;
            }}
            QCalendarWidget QAbstractItemView {{
                background: {C.SURFACE};
                color: {C.TEXT};
                selection-background-color: {C.NAVY_600};
                selection-color: {C.TEXT};
                border: none;
                outline: none;
            }}
            QCalendarWidget QAbstractItemView:disabled {{
                color: {C.TEXT3};
            }}
            QCalendarWidget QToolButton {{
                background: {C.SURFACE2};
                color: {C.TEXT};
                border: none;
                border-radius: 6px;
                padding: 5px 10px;
                font-weight: 600;
            }}
            QCalendarWidget QToolButton:hover {{
                background: {C.NAVY_700};
            }}
            QCalendarWidget QMenu {{
                background: {C.SURFACE2};
                color: {C.TEXT};
                border: 1px solid {C.BORDER};
            }}
            QCalendarWidget QSpinBox {{
                background: {C.SURFACE2};
                color: {C.TEXT};
                border: 1px solid {C.BORDER};
                border-radius: 5px;
            }}
            #qt_calendar_navigationbar {{
                background: {C.SURFACE2};
                border-radius: 8px;
                margin-bottom: 4px;
            }}
        """)
        self._calendar.clicked.connect(self._on_date_selected)
        cal_lay.addWidget(self._calendar)

        # Legend
        legend_row = QHBoxLayout()
        legend_row.setSpacing(12)
        for txt, color in [("Sin excepción", C.TEXT3),
                            ("Cupo modificado", C.GOLD_500),
                            ("Suspendido", C.RED),
                            ("Ración fría", "#60A5FA")]:
            dot = QLabel(f"● {txt}")
            dot.setStyleSheet(
                f"font-size: 11px; color: {color}; background: transparent;"
            )
            legend_row.addWidget(dot)
        legend_row.addStretch()
        cal_lay.addLayout(legend_row)

        cols.addWidget(cal_card)

        # Right: Edit panel
        edit_card = QFrame()
        edit_card.setFixedWidth(320)
        edit_card.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border: 1.5px solid {C.BORDER};
                border-radius: 14px;
            }}
        """)
        edit_lay = QVBoxLayout(edit_card)
        edit_lay.setContentsMargins(20, 18, 20, 18)
        edit_lay.setSpacing(14)

        self._lbl_date_header = QLabel("—")
        self._lbl_date_header.setStyleSheet(
            f"font-size: 16px; font-weight: 700; color: {C.TEXT}; background: transparent;"
        )
        edit_lay.addWidget(self._lbl_date_header)

        self._lbl_current = QLabel("")
        self._lbl_current.setWordWrap(True)
        self._lbl_current.setStyleSheet(
            f"font-size: 12px; color: {C.TEXT3}; background: transparent;"
        )
        edit_lay.addWidget(self._lbl_current)

        edit_lay.addWidget(HDivider())

        # Suspendido checkbox
        self._chk_suspend = QCheckBox("Día suspendido (sin servicio)")
        self._chk_suspend.setStyleSheet(
            f"font-size: 13px; color: {C.TEXT}; background: transparent; font-weight: 500;"
        )
        self._chk_suspend.stateChanged.connect(self._on_suspend_changed)
        edit_lay.addWidget(self._chk_suspend)

        # Cupo override
        cupo_row = QHBoxLayout()
        cupo_row.setSpacing(10)
        lbl_cupo = QLabel("Cupo del día")
        lbl_cupo.setStyleSheet(
            f"font-size: 13px; color: {C.TEXT2}; background: transparent;"
        )
        cupo_row.addWidget(lbl_cupo)
        self._spin_cupo = QSpinBox()
        self._spin_cupo.setRange(0, 9999)
        self._spin_cupo.setSpecialValueText("Sin override")
        self._spin_cupo.setValue(0)
        self._spin_cupo.setFixedWidth(120)
        self._spin_cupo.setEnabled(True)
        cupo_row.addWidget(self._spin_cupo)
        edit_lay.addLayout(cupo_row)

        # Motivo
        lbl_motivo = QLabel("Motivo (opcional)")
        lbl_motivo.setStyleSheet(
            f"font-size: 12px; color: {C.TEXT3}; background: transparent;"
        )
        edit_lay.addWidget(lbl_motivo)
        self._inp_motivo = QLineEdit()
        self._inp_motivo.setPlaceholderText("Ej: Paro docente, Visita liceo, Feriado…")
        edit_lay.addWidget(self._inp_motivo)

        edit_lay.addWidget(HDivider())

        # Comida fría
        self._chk_fria = QCheckBox("Comida fría (ración sin cocción)")
        self._chk_fria.setStyleSheet(
            f"font-size: 13px; color: #60A5FA; background: transparent; font-weight: 500;"
        )
        edit_lay.addWidget(self._chk_fria)

        lbl_desc_fria = QLabel("Descripción ración fría (opcional)")
        lbl_desc_fria.setStyleSheet(
            f"font-size: 12px; color: {C.TEXT3}; background: transparent;"
        )
        edit_lay.addWidget(lbl_desc_fria)
        self._inp_desc_fria = QLineEdit()
        self._inp_desc_fria.setPlaceholderText("Ej: Pan + queso + jugo + fruta")
        edit_lay.addWidget(self._inp_desc_fria)

        edit_lay.addSpacing(4)

        # Botones
        btn_save = AButton("Guardar excepción", sound_type="save")
        btn_save.setStyleSheet(f"""
            QPushButton {{
                background: {C.NAVY_700};
                color: {C.TEXT};
                border: none; border-radius: 10px;
                padding: 10px 20px;
                font-size: 13px; font-weight: 600;
            }}
            QPushButton:hover {{ background: {C.NAVY_600}; }}
        """)
        btn_save.clicked.connect(self._save_exception)
        edit_lay.addWidget(btn_save)

        btn_del = AButton("Eliminar excepción", sound_type="click")
        btn_del.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {C.RED};
                border: 1.5px solid {C.RED}66;
                border-radius: 10px;
                padding: 9px 20px;
                font-size: 13px; font-weight: 600;
            }}
            QPushButton:hover {{ background: {C.RED_DIM}; }}
        """)
        btn_del.clicked.connect(self._delete_exception)
        edit_lay.addWidget(btn_del)

        self._saved_ind = SavedIndicator()
        edit_lay.addWidget(self._saved_ind)

        edit_lay.addStretch()
        cols.addWidget(edit_card)
        root.addLayout(cols)

        # ── Upcoming exceptions table ─────────────────
        tbl_hdr = QHBoxLayout()
        tbl_hdr.addWidget(SectionHeader("Próximas excepciones"))
        tbl_hdr.addStretch()
        root.addLayout(tbl_hdr)

        self._tbl = QTableWidget()
        self._tbl.setColumnCount(4)
        self._tbl.setHorizontalHeaderLabels(["Fecha", "Cupo", "Estado", "Motivo"])
        self._tbl.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tbl.verticalHeader().setVisible(False)
        self._tbl.setAlternatingRowColors(True)
        self._tbl.setShowGrid(False)
        self._tbl.setMaximumHeight(200)
        self._tbl.verticalHeader().setDefaultSectionSize(36)
        self._tbl.setStyleSheet(f"""
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
        """)
        self._tbl.clicked.connect(self._on_table_clicked)
        root.addWidget(self._tbl)

    # ─────────────────────────────────────────────
    #  DATA
    # ─────────────────────────────────────────────

    def _load_screen(self):
        # Default cupo label
        default = db.get_config("cupos_totales", "100")
        self._lbl_default.setText(
            f"Cupo base (configuración): {default} estudiantes"
        )
        self._load_exceptions()
        self._refresh_calendar_markers()
        self._load_date(self._selected_date)

    def _load_exceptions(self):
        rows = db.get_upcoming_exceptions(date.today().isoformat(), limit=90)
        self._exceptions_cache = {r["fecha"]: dict(r) for r in rows}
        self._fill_table(rows)

    def _fill_table(self, rows):
        default_cupo = int(db.get_config("cupos_totales", "100"))
        self._tbl.setColumnCount(4)
        self._tbl.setHorizontalHeaderLabels(["Fecha", "Cupo", "Estado", "Motivo / Descripción"])
        self._tbl.setRowCount(len(rows))
        for i, row in enumerate(rows):
            susp = bool(row["suspendido"])
            fria = bool(row.get("comida_fria", 0))
            cupo = row["cupos_dia"] if row["cupos_dia"] is not None else default_cupo
            if susp:
                estado_txt = "Suspendido"
                color = C.RED
            elif fria:
                estado_txt = "Ración fría"
                color = "#60A5FA"
            else:
                estado_txt = "Cupo modificado"
                color = C.GOLD_500

            motivo_display = (
                row.get("descripcion_fria", "") or row.get("motivo", "")
            ) if fria else (row.get("motivo", "") or "")

            values = [
                utils.format_fecha_display(row["fecha"]),
                "—" if susp else str(cupo),
                estado_txt,
                motivo_display,
            ]
            for col, txt in enumerate(values):
                item = QTableWidgetItem(txt)
                item.setData(Qt.ItemDataRole.UserRole, row["fecha"])
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
                )
                if col == 2:
                    item.setForeground(QColor(color))
                    f = item.font(); f.setBold(True); item.setFont(f)
                self._tbl.setItem(i, col, item)

    def _refresh_calendar_markers(self):
        """Colorea fechas con excepción en el calendario."""
        default_fmt = QTextCharFormat()
        default_fmt.setForeground(QColor(C.TEXT))

        susp_fmt = QTextCharFormat()
        susp_fmt.setForeground(QColor(C.RED))
        susp_fmt.setFontWeight(QFont.Weight.Bold)
        susp_fmt.setBackground(QColor(C.RED_DIM))

        override_fmt = QTextCharFormat()
        override_fmt.setForeground(QColor(C.GOLD_500))
        override_fmt.setFontWeight(QFont.Weight.Bold)

        fria_fmt = QTextCharFormat()
        fria_fmt.setForeground(QColor("#60A5FA"))
        fria_fmt.setFontWeight(QFont.Weight.Bold)

        for fecha, exc in self._exceptions_cache.items():
            try:
                y, m, d = fecha.split("-")
                qdate = QDate(int(y), int(m), int(d))
                if bool(exc["suspendido"]):
                    self._calendar.setDateTextFormat(qdate, susp_fmt)
                elif bool(exc.get("comida_fria", 0)):
                    self._calendar.setDateTextFormat(qdate, fria_fmt)
                else:
                    self._calendar.setDateTextFormat(qdate, override_fmt)
            except Exception:
                pass

    def _load_date(self, fecha: str):
        self._selected_date = fecha
        exc = self._exceptions_cache.get(fecha)
        default_cupo = int(db.get_config("cupos_totales", "100"))

        # Update header
        self._lbl_date_header.setText(utils.format_fecha_display(fecha))

        _style_normal   = f"font-size: 12px; color: {C.TEXT3}; background: transparent;"
        _style_override = f"font-size: 12px; font-weight: 600; color: {C.TEXT2}; background: transparent;"
        _style_susp     = f"font-size: 12px; font-weight: 700; color: {C.RED}; background: transparent;"
        _style_fria     = f"font-size: 12px; font-weight: 600; color: #60A5FA; background: transparent;"

        if exc is None:
            susp = False
            self._lbl_current.setText(f"Sin excepción  ·  cupo base: {default_cupo}")
            self._lbl_current.setStyleSheet(_style_normal)
            self._chk_suspend.setChecked(False)
            self._spin_cupo.setValue(0)
            self._inp_motivo.clear()
            self._chk_fria.setChecked(False)
            self._inp_desc_fria.clear()
        else:
            susp = bool(exc["suspendido"])
            cupos_ef  = exc["cupos_dia"] if exc["cupos_dia"] is not None else default_cupo
            motivo    = exc["motivo"] or ""
            fria      = bool(exc.get("comida_fria", 0))
            desc_fria = exc.get("descripcion_fria", "") or ""
            if susp:
                self._lbl_current.setText(f"Suspendido  ·  {motivo}" if motivo else "Suspendido")
                self._lbl_current.setStyleSheet(_style_susp)
            elif fria:
                self._lbl_current.setText(f"Ración fría  ·  {desc_fria}" if desc_fria else "Ración fría")
                self._lbl_current.setStyleSheet(_style_fria)
            else:
                self._lbl_current.setText(
                    f"Cupo override: {cupos_ef}  ·  {motivo}" if motivo
                    else f"Cupo override: {cupos_ef}"
                )
                self._lbl_current.setStyleSheet(_style_override)
            self._chk_suspend.setChecked(susp)
            self._spin_cupo.setValue(0 if susp or exc["cupos_dia"] is None else exc["cupos_dia"])
            self._inp_motivo.setText(motivo)
            self._chk_fria.setChecked(fria)
            self._inp_desc_fria.setText(desc_fria)

        self._spin_cupo.setEnabled(not susp)

    # ─────────────────────────────────────────────
    #  EVENTS
    # ─────────────────────────────────────────────

    def _on_date_selected(self, qdate: QDate):
        fecha = qdate.toString("yyyy-MM-dd")
        self._load_date(fecha)

    def _on_suspend_changed(self, state: int):
        checked = bool(state)
        self._spin_cupo.setEnabled(not checked)

    def _on_table_clicked(self, index):
        item = self._tbl.item(index.row(), 0)
        if item:
            fecha = item.data(Qt.ItemDataRole.UserRole)
            if fecha:
                y, m, d = fecha.split("-")
                self._calendar.setSelectedDate(QDate(int(y), int(m), int(d)))
                self._load_date(fecha)

    # ─────────────────────────────────────────────
    #  ACTIONS
    # ─────────────────────────────────────────────

    def _save_exception(self):
        fecha      = self._selected_date
        suspendido = 1 if self._chk_suspend.isChecked() else 0
        cupo_val   = self._spin_cupo.value()
        cupos_dia  = None if (suspendido or cupo_val == 0) else cupo_val
        motivo     = self._inp_motivo.text().strip()
        comida_fria      = 1 if (not suspendido and self._chk_fria.isChecked()) else 0
        descripcion_fria = self._inp_desc_fria.text().strip() if comida_fria else ""

        db.set_quota_exception(fecha, cupos_dia, suspendido, motivo,
                               comida_fria, descripcion_fria)
        sound.save()
        self._saved_ind.show_saved("✓  Excepción guardada")
        self._load_exceptions()
        self._refresh_calendar_markers()
        self._load_date(fecha)

    def _delete_exception(self):
        fecha = self._selected_date
        if fecha not in self._exceptions_cache:
            self._saved_ind.show_error("✗  Sin excepción para esta fecha")
            sound.error()
            return
        db.delete_quota_exception(fecha)
        sound.save()
        self._saved_ind.show_saved("✓  Excepción eliminada")
        self._load_exceptions()
        self._refresh_calendar_markers()
        self._load_date(fecha)

    def showEvent(self, event):
        super().showEvent(event)
        self._load_screen()
