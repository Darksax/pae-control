"""
config_screen.py — Configuración PAE Control 0.9 Alpha

- QTimeEdit para horarios (sin texto libre, formato siempre válido)
- QComboBox para valores categóricos
- Auto-save con debounce 1.2s + SavedIndicator inline
- Sound en save (pop/lock)
- Sin modales: confirmación inline debajo del botón
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QSpinBox, QFrame, QCheckBox, QFormLayout,
    QScrollArea, QSizePolicy, QTimeEdit
)
from PyQt6.QtCore import Qt, QTimer, QTime
from PyQt6.QtGui import QFont

import db
from ui.theme   import C, sound
from ui.widgets import AButton, HDivider, SectionHeader, SavedIndicator


class MealRow(QFrame):
    """
    One meal config row: name | start QTimeEdit → end QTimeEdit | active checkbox.
    Emits change signal for auto-save debounce.
    """

    def __init__(self, comida: dict, on_change, parent=None):
        super().__init__(parent)
        self._id        = comida["id"]
        self._on_change = on_change
        self.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE2};
                border: 1.5px solid {C.BORDER};
                border-radius: 12px;
            }}
        """)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(16)

        # Meal name (editable)
        self._inp_nombre = QLineEdit(comida["nombre"])
        self._inp_nombre.setFixedWidth(120)
        self._inp_nombre.setStyleSheet(
            f"font-size: 14px; font-weight: 600; color: {C.TEXT};"
        )
        self._inp_nombre.textChanged.connect(self._on_change)
        lay.addWidget(self._inp_nombre)

        lay.addWidget(self._sep("Inicio"))

        # QTimeEdit — no text libre, siempre formato HH:MM válido
        self._time_inicio = QTimeEdit()
        self._time_inicio.setDisplayFormat("HH:mm")
        self._time_inicio.setTime(self._parse_time(comida["hora_inicio"]))
        self._time_inicio.setFixedWidth(80)
        self._time_inicio.setStyleSheet(f"""
            QTimeEdit {{
                font-size: 14px; font-weight: 600;
                color: {C.GOLD_500};
                background: {C.SURFACE};
                border: 1.5px solid {C.BORDER};
                border-radius: 8px;
                padding: 6px 10px;
            }}
            QTimeEdit:focus {{ border-color: {C.NAVY_400}; }}
            QTimeEdit::up-button, QTimeEdit::down-button {{
                background: {C.SURFACE3}; border: none; width: 18px; border-radius: 4px;
            }}
        """)
        self._time_inicio.timeChanged.connect(self._on_change)
        lay.addWidget(self._time_inicio)

        arrow = QLabel("→")
        arrow.setStyleSheet(f"color: {C.TEXT3}; background: transparent; font-size: 16px;")
        lay.addWidget(arrow)

        self._time_fin = QTimeEdit()
        self._time_fin.setDisplayFormat("HH:mm")
        self._time_fin.setTime(self._parse_time(comida["hora_fin"]))
        self._time_fin.setFixedWidth(80)
        self._time_fin.setStyleSheet(self._time_inicio.styleSheet())
        self._time_fin.timeChanged.connect(self._on_change)
        lay.addWidget(self._time_fin)

        lay.addStretch()

        # Active toggle
        self._chk = QCheckBox("Activa")
        self._chk.setChecked(bool(comida["activa"]))
        self._chk.setStyleSheet(f"color: {C.TEXT2}; background: transparent;")
        self._chk.stateChanged.connect(self._on_change)
        lay.addWidget(self._chk)

    def _sep(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setStyleSheet(
            f"font-size: 11px; color: {C.TEXT3}; background: transparent; font-weight: 600;"
        )
        return l

    @staticmethod
    def _parse_time(hhmm: str) -> QTime:
        try:
            h, m = hhmm.split(":")
            return QTime(int(h), int(m))
        except Exception:
            return QTime(0, 0)

    def get_data(self) -> dict:
        return {
            "id":          self._id,
            "nombre":      self._inp_nombre.text().strip(),
            "hora_inicio": self._time_inicio.time().toString("HH:mm"),
            "hora_fin":    self._time_fin.time().toString("HH:mm"),
            "activa":      1 if self._chk.isChecked() else 0,
        }


class ConfigScreen(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._meal_rows: list = []
        self._debounce  = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(1200)   # 1.2s after last change → auto-save
        self._debounce.timeout.connect(self._auto_save)
        self._build_ui()
        self._load_config()

    def _build_ui(self):
        self.setStyleSheet(f"background: {C.BG};")

        # Outer scroll wrapper
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"background: {C.BG}; border: none;")
        outer.addWidget(scroll)

        container = QWidget()
        container.setStyleSheet(f"background: {C.BG};")
        scroll.setWidget(container)

        root = QVBoxLayout(container)
        root.setContentsMargins(28, 24, 28, 32)
        root.setSpacing(20)

        # ── Title ────────────────────────────────────
        title = QLabel("Configuración")
        title.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: {C.TEXT}; background: transparent;"
        )
        root.addWidget(title)

        sub = QLabel(
            "Los cambios se guardan automáticamente 1.2s después de la última modificación."
        )
        sub.setStyleSheet(f"font-size: 12px; color: {C.TEXT3}; background: transparent;")
        root.addWidget(sub)
        root.addSpacing(4)

        # ── General card ─────────────────────────────
        gen_card = QFrame()
        gen_card.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border: 1.5px solid {C.BORDER};
                border-radius: 16px;
            }}
        """)
        gen_lay = QVBoxLayout(gen_card)
        gen_lay.setContentsMargins(20, 18, 20, 18)
        gen_lay.setSpacing(14)

        gen_lay.addWidget(SectionHeader("General"))

        # Nombre establecimiento
        row_nombre = QHBoxLayout()
        lbl_n = QLabel("Nombre del establecimiento")
        lbl_n.setStyleSheet(f"color: {C.TEXT2}; font-size: 13px; background: transparent;")
        lbl_n.setFixedWidth(220)
        self._inp_nombre = QLineEdit()
        self._inp_nombre.setPlaceholderText("Ej: Liceo Bicentenario Héroes de la Concepción")
        self._inp_nombre.textChanged.connect(self._on_field_changed)
        row_nombre.addWidget(lbl_n)
        row_nombre.addWidget(self._inp_nombre, stretch=1)
        gen_lay.addLayout(row_nombre)

        gen_lay.addWidget(HDivider())

        # Cupos + max strikes (inline)
        row_nums = QHBoxLayout()
        row_nums.setSpacing(24)

        self._spin_cupos   = self._make_spinbox(1, 9999, "Cupos totales PAE")
        self._spin_strikes = self._make_spinbox(1, 20,   "Máximo de strikes")

        for widget in self._spin_cupos + self._spin_strikes:
            row_nums.addWidget(widget)
        row_nums.addStretch()
        gen_lay.addLayout(row_nums)

        root.addWidget(gen_card)

        # ── Meal schedule card ────────────────────────
        meal_card = QFrame()
        meal_card.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border: 1.5px solid {C.BORDER};
                border-radius: 16px;
            }}
        """)
        meal_lay = QVBoxLayout(meal_card)
        meal_lay.setContentsMargins(20, 18, 20, 18)
        meal_lay.setSpacing(10)

        meal_lay.addWidget(SectionHeader("Horarios de comidas"))

        hint = QLabel("Usa las flechas ↑↓ o escribe directamente la hora. Formato 24h.")
        hint.setStyleSheet(f"font-size: 11px; color: {C.TEXT3}; background: transparent;")
        meal_lay.addWidget(hint)
        meal_lay.addSpacing(4)

        comidas = db.get_all_comidas()
        self._meal_rows = []
        for c in comidas:
            row = MealRow(c, on_change=self._on_field_changed)
            meal_lay.addWidget(row)
            self._meal_rows.append(row)

        root.addWidget(meal_card)

        # ── Save bar ─────────────────────────────────
        save_row = QHBoxLayout()
        save_row.addStretch()

        btn_save = AButton("Guardar ahora", sound_type="save")
        btn_save.setStyleSheet(f"""
            QPushButton {{
                background: {C.NAVY_700};
                color: {C.TEXT};
                border: none; border-radius: 10px;
                padding: 10px 28px;
                font-size: 13px; font-weight: 600;
            }}
            QPushButton:hover {{ background: {C.NAVY_600}; }}
            QPushButton:pressed {{ background: {C.NAVY_800}; }}
        """)
        btn_save.clicked.connect(self._manual_save)
        save_row.addWidget(btn_save)

        root.addLayout(save_row)

        # Saved indicator (inline, non-blocking)
        self._saved_ind = SavedIndicator()
        ind_row = QHBoxLayout()
        ind_row.addStretch()
        ind_row.addWidget(self._saved_ind)
        root.addLayout(ind_row)

        root.addStretch()

    def _make_spinbox(self, min_v: int, max_v: int, label: str):
        """Returns [QLabel, QSpinBox] to add to a layout."""
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {C.TEXT2}; font-size: 13px; background: transparent;")
        spin = QSpinBox()
        spin.setRange(min_v, max_v)
        spin.setFixedWidth(90)
        spin.valueChanged.connect(self._on_field_changed)
        return [lbl, spin]

    # ─────────────────────────────────────────────
    #  CONFIG LOAD / SAVE
    # ─────────────────────────────────────────────

    def _load_config(self):
        cfg = db.get_all_config()
        self._inp_nombre.setText(cfg.get("nombre_establecimiento", ""))
        self._spin_cupos[1].setValue(int(cfg.get("cupos_totales", "100")))
        self._spin_strikes[1].setValue(int(cfg.get("max_strikes", "3")))

    def _on_field_changed(self, *args):
        """Called on any field change — starts debounce timer."""
        self._debounce.start()

    def _auto_save(self):
        """Called 1.2s after last change — saves silently."""
        self._commit_save()

    def _manual_save(self):
        """Called by 'Guardar ahora' button."""
        self._debounce.stop()
        self._commit_save()

    def _commit_save(self):
        try:
            db.set_config("nombre_establecimiento",
                          self._inp_nombre.text().strip())
            db.set_config("cupos_totales", str(self._spin_cupos[1].value()))
            db.set_config("max_strikes",   str(self._spin_strikes[1].value()))

            for row in self._meal_rows:
                d = row.get_data()
                db.update_comida(
                    comida_id   = d["id"],
                    nombre      = d["nombre"],
                    hora_inicio = d["hora_inicio"],
                    hora_fin    = d["hora_fin"],
                    activa      = d["activa"],
                )

            sound.save()
            self._saved_ind.show_saved()

        except Exception as e:
            sound.error()
            self._saved_ind.show_error(f"✗  Error: {e}")

    def showEvent(self, event):
        super().showEvent(event)
        self._load_config()
