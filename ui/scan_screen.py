"""
scan_screen.py — Pantalla de escaneo PAE Control 0.9 Alpha
macOS Sonoma dark · Liceo Bicentenario palette

Features:
  - Input siempre enfocado (pistola de código de barras como HID keyboard)
  - Result card con fade-in animado al escanear
  - Flash verde suave (OK) / rojo (strike/error) en el card
  - Meal chips: qué comidas tuvo el estudiante hoy
  - Stat cards con flash al actualizar
  - Sound: Glass (ok), Basso (error), Tink (ya reg)
  - Auto-reset 4s con fade-out
"""

from datetime import datetime, date
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QSizePolicy, QGraphicsOpacityEffect,
    QLineEdit, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal, QPoint
from PyQt6.QtGui import QFont, QKeyEvent, QColor

import logic
import utils
import db
from ui.theme   import C, sound, fade_in, fade_out
from ui.widgets import AButton, StatCard, HDivider, VDivider, SectionHeader, Badge, RUNLineEdit


# ══════════════════════════════════════════════════════
#  MEAL CHIP  — shows one meal with done/pending state
# ══════════════════════════════════════════════════════

class MealChip(QFrame):
    def __init__(self, nombre: str, parent=None):
        super().__init__(parent)
        self.nombre = nombre
        self.setFixedHeight(34)
        self.setMinimumWidth(100)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(6)

        self._icon = QLabel("—")
        self._icon.setStyleSheet("font-size: 14px; background: transparent;")

        self._lbl = QLabel(nombre)
        self._lbl.setStyleSheet(
            f"font-size: 12px; font-weight: 600; background: transparent; color: {C.TEXT2};"
        )

        lay.addWidget(self._icon)
        lay.addWidget(self._lbl)

        self._set_pending()

    def _set_pending(self):
        self.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE2};
                border: 1.5px solid {C.BORDER};
                border-radius: 17px;
            }}
        """)
        self._icon.setText("—")
        self._icon.setStyleSheet(f"font-size: 13px; background: transparent; color: {C.TEXT3};")
        self._lbl.setStyleSheet(
            f"font-size: 12px; font-weight: 600; background: transparent; color: {C.TEXT3};"
        )

    def set_done(self):
        self.setStyleSheet(f"""
            QFrame {{
                background: {C.GREEN_DIM};
                border: 1.5px solid {C.GREEN};
                border-radius: 17px;
            }}
        """)
        self._icon.setText("✓")
        self._icon.setStyleSheet(f"font-size: 13px; background: transparent; color: {C.GREEN};")
        self._lbl.setStyleSheet(
            f"font-size: 12px; font-weight: 600; background: transparent; color: {C.GREEN};"
        )

    def reset(self):
        self._set_pending()


# ══════════════════════════════════════════════════════
#  RESULT CARD  — the big center piece
# ══════════════════════════════════════════════════════

class ResultCard(QFrame):
    """
    Animated card showing scan result.
    Fades in on each scan, fades out on reset.
    """
    autorizar_solicitado = pyqtSignal(str)   # emite run del estudiante

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border: 1.5px solid {C.BORDER};
                border-radius: 20px;
            }}
        """)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._effect.setOpacity(0.3)

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 36, 40, 36)
        root.setSpacing(0)

        # ── Waiting label (shown when idle)
        self._waiting = QLabel("Esperando escaneo…")
        self._waiting.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._waiting.setStyleSheet(
            f"font-size: 22px; font-weight: 400; color: {C.TEXT3}; background: transparent;"
        )
        root.addWidget(self._waiting)

        # ── Student info (hidden when idle)
        self._info_block = QWidget()
        self._info_block.hide()
        info_lay = QVBoxLayout(self._info_block)
        info_lay.setContentsMargins(0, 0, 0, 0)
        info_lay.setSpacing(10)

        # Name
        self._lbl_nombre = QLabel("")
        self._lbl_nombre.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_nombre.setWordWrap(True)
        self._lbl_nombre.setStyleSheet(
            f"font-size: 36px; font-weight: 700; color: {C.TEXT}; background: transparent;"
        )
        info_lay.addWidget(self._lbl_nombre)

        # RUN + curso
        self._lbl_detalle = QLabel("")
        self._lbl_detalle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_detalle.setStyleSheet(
            f"font-size: 16px; color: {C.TEXT2}; background: transparent;"
        )
        info_lay.addWidget(self._lbl_detalle)
        info_lay.addSpacing(16)

        # Status pill
        self._pill = QLabel("")
        self._pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pill.setFixedHeight(52)
        self._pill.setStyleSheet(f"""
            font-size: 20px; font-weight: 700;
            border-radius: 14px; padding: 0 20px;
            background: {C.SURFACE2}; color: {C.TEXT};
        """)
        info_lay.addWidget(self._pill)
        info_lay.addSpacing(8)

        # Sub-message
        self._lbl_msg = QLabel("")
        self._lbl_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_msg.setWordWrap(True)
        self._lbl_msg.setStyleSheet(
            f"font-size: 14px; color: {C.TEXT2}; background: transparent;"
        )
        info_lay.addWidget(self._lbl_msg)
        info_lay.addSpacing(20)

        # Meal chips row
        chips_row = QHBoxLayout()
        chips_row.setSpacing(8)
        chips_row.addStretch()
        self._chips: dict[int, MealChip] = {}
        self._chips_row = chips_row
        info_lay.addLayout(chips_row)

        # Strike counter
        self._lbl_strikes = QLabel("")
        self._lbl_strikes.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_strikes.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {C.RED}; background: transparent;"
        )
        info_lay.addSpacing(6)
        info_lay.addWidget(self._lbl_strikes)

        # Botón "Autorizar esta vez" — solo visible cuando no_activo
        info_lay.addSpacing(10)
        self._btn_autorizar = AButton("↑  Autorizar esta vez", sound_type="save")
        self._btn_autorizar.setStyleSheet(f"""
            QPushButton {{
                background: {C.BLUE};
                color: white;
                border: none;
                border-radius: 10px;
                padding: 10px 28px;
                font-size: 14px;
                font-weight: 700;
            }}
            QPushButton:hover {{ background: {C.NAVY_600}; }}
        """)
        self._btn_autorizar.hide()
        self._btn_autorizar.clicked.connect(self._on_autorizar_clicked)
        self._last_run: str = ""

        auth_row = QHBoxLayout()
        auth_row.addStretch()
        auth_row.addWidget(self._btn_autorizar)
        auth_row.addStretch()
        info_lay.addLayout(auth_row)

        root.addWidget(self._info_block)

    def _on_autorizar_clicked(self):
        if self._last_run:
            self._btn_autorizar.hide()
            self.autorizar_solicitado.emit(self._last_run)

    def build_chips(self, comidas: list):
        """Build meal chips once we know the comida list."""
        # Clear existing
        for chip in self._chips.values():
            self._chips_row.removeWidget(chip)
            chip.deleteLater()
        self._chips.clear()

        for c in comidas:
            chip = MealChip(c["nombre"])
            self._chips[c["id"]] = chip
            self._chips_row.addWidget(chip)

        # trailing stretch
        self._chips_row.addStretch()

    def reset_chips(self):
        for chip in self._chips.values():
            chip.reset()

    def mark_chip_done(self, comida_id: int):
        if comida_id in self._chips:
            self._chips[comida_id].set_done()

    def show_result(self, r: dict, comidas: list):
        estado = r["estado"]
        est    = r.get("estudiante")
        comida = r.get("comida")

        # Siempre resetear estado del botón de autorización
        self._btn_autorizar.hide()
        self._last_run = est["run"] if est else ""

        self._waiting.hide()
        self._info_block.show()

        # Student info
        if est:
            self._lbl_nombre.setText(utils.nombre_completo(est))
            self._lbl_detalle.setText(
                f"{utils.run_display(est['run'])}   ·   {est.get('curso', '')}"
            )
        else:
            self._lbl_nombre.setText("—")
            self._lbl_detalle.setText("")

        # Reset chips
        self.reset_chips()

        # Mark today's meals for this student
        if est:
            hoy = date.today().isoformat()
            registros = db.get_registros_estudiante(est["run"], hoy)
            for reg in registros:
                self.mark_chip_done(reg["comida_id"])

        # Status pill + card flash
        if estado == "ok":
            nombre_comida = comida["nombre"].upper() if comida else ""
            es_fria   = r.get("comida_fria", False)
            desc_fria = r.get("descripcion_fria", "")

            if es_fria:
                pill_txt = f"✓   INGRESO · {nombre_comida}  ·  RACIÓN FRÍA"
                BLUE = "#60A5FA"
                BLUE_DIM = "#172554"
                self._pill.setText(pill_txt)
                self._pill.setStyleSheet(f"""
                    font-size: 18px; font-weight: 700;
                    border-radius: 14px; padding: 0 20px;
                    background: {BLUE_DIM}; color: {BLUE};
                    border: 1.5px solid {BLUE};
                """)
                msg = desc_fria if desc_fria else "Servicio activo con ración fría"
                self._lbl_msg.setText(msg)
                self._flash_border(BLUE)
            else:
                self._pill.setText(f"✓   INGRESO · {nombre_comida}")
                self._pill.setStyleSheet(f"""
                    font-size: 20px; font-weight: 700;
                    border-radius: 14px; padding: 0 20px;
                    background: {C.GREEN_DIM}; color: {C.GREEN};
                    border: 1.5px solid {C.GREEN};
                """)
                self._lbl_msg.setText(r.get("mensaje", ""))
                self._flash_border(C.GREEN)

            self._lbl_strikes.setText("")

        elif estado == "strike":
            strikes = r["strikes_total"]
            maxs    = r["max_strikes"]
            self._pill.setText(f"⚠   FALTA REGISTRADA · {strikes}/{maxs} STRIKES")
            self._pill.setStyleSheet(f"""
                font-size: 18px; font-weight: 700;
                border-radius: 14px; padding: 0 20px;
                background: {C.RED_DIM}; color: {C.RED};
                border: 1.5px solid {C.RED};
            """)
            faltadas = r.get("comidas_faltadas", [])
            msgs = [f"Faltó a {cf['comida_nombre']}" for cf in faltadas]
            self._lbl_msg.setText("   ·   ".join(msgs) if msgs else r.get("mensaje", ""))
            color_s = C.RED if strikes >= maxs else C.AMBER
            self._lbl_strikes.setText(
                f"Total acumulado: {strikes} strikes de {maxs} permitidos"
            )
            self._lbl_strikes.setStyleSheet(
                f"font-size: 13px; font-weight: 600; color: {color_s}; background: transparent;"
            )
            self._flash_border(C.RED)

        elif estado == "ya_reg":
            nombre_comida = comida["nombre"].upper() if comida else ""
            self._pill.setText(f"→   YA REGISTRADO · {nombre_comida}")
            self._pill.setStyleSheet(f"""
                font-size: 18px; font-weight: 700;
                border-radius: 14px; padding: 0 20px;
                background: #2D2000; color: {C.AMBER};
                border: 1.5px solid {C.AMBER};
            """)
            self._lbl_msg.setText(r.get("mensaje", ""))
            self._lbl_strikes.setText("")
            self._flash_border(C.AMBER)

        elif estado == "suspendido":
            self._pill.setText("⊘   SIN SERVICIO HOY")
            self._pill.setStyleSheet(f"""
                font-size: 20px; font-weight: 700;
                border-radius: 14px; padding: 0 20px;
                background: {C.SURFACE2}; color: {C.TEXT3};
                border: 1.5px solid {C.BORDER2};
            """)
            self._lbl_msg.setText(r.get("mensaje", "Sin servicio programado para hoy"))
            self._lbl_strikes.setText("")
            self._flash_border(C.BORDER2)

        elif estado in ("no_activo", "no_existe", "run_inv"):
            msgs = {
                "no_activo": ("✗   NO HABILITADO",   C.TEXT3, C.BORDER2),
                "no_existe": ("✗   NO ENCONTRADO",   C.RED,   C.RED_DIM),
                "run_inv":   ("✗   RUN INVÁLIDO",    C.RED,   C.RED_DIM),
            }
            txt, col, bg = msgs[estado]
            self._pill.setText(txt)
            self._pill.setStyleSheet(f"""
                font-size: 20px; font-weight: 700;
                border-radius: 14px; padding: 0 20px;
                background: {bg}; color: {col};
                border: 1.5px solid {col};
            """)
            self._lbl_msg.setText(r.get("mensaje", ""))
            self._lbl_strikes.setText("")
            self._flash_border(C.RED if estado != "no_activo" else C.BORDER2)

            # Botón "Autorizar esta vez" solo para estudiantes inhabilitados
            if estado == "no_activo" and self._last_run:
                self._btn_autorizar.show()

        # Animate in
        anim = QPropertyAnimation(self._effect, b"opacity", self)
        anim.setDuration(200)
        anim.setStartValue(self._effect.opacity())
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        self._anim_in = anim  # keep reference

    def _flash_border(self, color: str):
        """Briefly highlight card border with result color."""
        self.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border: 2px solid {color};
                border-radius: 20px;
            }}
        """)
        QTimer.singleShot(600, lambda: self.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border: 1.5px solid {C.BORDER};
                border-radius: 20px;
            }}
        """))

    def reset(self):
        """Fade back to idle state."""
        anim = QPropertyAnimation(self._effect, b"opacity", self)
        anim.setDuration(300)
        anim.setStartValue(1.0)
        anim.setEndValue(0.3)
        anim.setEasingCurve(QEasingCurve.Type.InCubic)
        anim.finished.connect(self._go_idle)
        anim.start()
        self._anim_out = anim

    def _go_idle(self):
        self._info_block.hide()
        self._waiting.show()
        self._pill.setText("")
        self._lbl_nombre.setText("")
        self._lbl_detalle.setText("")
        self._lbl_msg.setText("")
        self._lbl_strikes.setText("")
        self._btn_autorizar.hide()
        self._last_run = ""
        self.reset_chips()
        self.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border: 1.5px solid {C.BORDER};
                border-radius: 20px;
            }}
        """)


# ══════════════════════════════════════════════════════
#  NAME SEARCH BAR — búsqueda progresiva por nombre
# ══════════════════════════════════════════════════════

class _NamePopup(QListWidget):
    """Lista flotante de resultados de búsqueda por nombre."""
    run_chosen = pyqtSignal(str)

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.Tool |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedWidth(520)
        self.setStyleSheet(f"""
            QListWidget {{
                background: {C.SURFACE};
                border: 1.5px solid {C.BORDER2};
                border-radius: 10px;
                padding: 4px;
                outline: none;
            }}
            QListWidget::item {{
                border-radius: 7px;
                padding: 6px 10px;
                color: {C.TEXT};
                font-size: 13px;
            }}
            QListWidget::item:hover, QListWidget::item:selected {{
                background: {C.BLUE_DIM};
                color: {C.BLUE};
            }}
        """)
        self.itemClicked.connect(
            lambda item: self.run_chosen.emit(item.data(Qt.ItemDataRole.UserRole))
        )

    def show_below(self, widget: QWidget):
        pos = widget.mapToGlobal(QPoint(0, widget.height() + 4))
        self.move(pos)
        self.show()
        self.raise_()


class _NameSearchBar(QFrame):
    """Barra de búsqueda por nombre con autocomplete progresivo."""
    run_selected = pyqtSignal(str)   # emite el RUN elegido

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(56)
        self.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border: 1.5px solid {C.BORDER};
                border-radius: 14px;
            }}
        """)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 14, 0)
        lay.setSpacing(10)

        icon = QLabel("🔍")
        icon.setStyleSheet("font-size: 16px; background: transparent;")
        lay.addWidget(icon)

        self._field = QLineEdit()
        self._field.setPlaceholderText("Buscar por nombre o apellido…")
        self._field.setStyleSheet(f"""
            QLineEdit {{
                background: transparent;
                border: none;
                font-size: 15px;
                font-weight: 400;
                color: {C.TEXT};
            }}
            QLineEdit::placeholder {{ color: {C.TEXT3}; }}
        """)
        lay.addWidget(self._field, stretch=1)

        lbl = QLabel("Búsqueda manual")
        lbl.setStyleSheet(
            f"font-size: 10px; color: {C.TEXT3}; background: transparent; padding-right: 4px;"
        )
        lay.addWidget(lbl)

        self._popup = _NamePopup()
        self._popup.run_chosen.connect(self._on_chosen)

        self._debounce = QTimer()
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(220)
        self._debounce.timeout.connect(self._do_search)

        self._field.textChanged.connect(self._on_text_changed)
        self._field.focusOutEvent = self._on_focus_out

    def _on_text_changed(self, text: str):
        if len(text) < 2:
            self._popup.hide()
            return
        self._debounce.start()

    def _do_search(self):
        query = self._field.text().strip()
        if len(query) < 2:
            self._popup.hide()
            return

        rows = db.search_students_by_name(query, limit=10)
        if not rows:
            self._popup.hide()
            return

        self._popup.clear()
        for r in rows:
            apellidos = f"{r.get('apellido_paterno','') or ''} {r.get('apellido_materno','') or ''}".strip()
            nombre    = r.get("nombres", "") or ""
            curso     = r.get("curso", "") or ""
            espera    = r.get("lista_espera", 0)
            tag       = " · En espera" if espera else ""
            texto     = f"{apellidos}, {nombre}  —  {curso}{tag}"

            item = QListWidgetItem(texto)
            item.setData(Qt.ItemDataRole.UserRole, r["run"])
            self._popup.addItem(item)

        self._popup.setFixedHeight(min(len(rows), 8) * 38 + 10)
        self._popup.show_below(self._field)

    def _on_chosen(self, run: str):
        self._popup.hide()
        self._field.clear()
        self.run_selected.emit(run)

    def _on_focus_out(self, event):
        QTimer.singleShot(180, self._popup.hide)
        QLineEdit.focusOutEvent(self._field, event)

    def clear(self):
        self._field.clear()
        self._popup.hide()


# ══════════════════════════════════════════════════════
#  SCAN SCREEN
# ══════════════════════════════════════════════════════

class ScanScreen(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer_reset  = QTimer(self)
        self._timer_reset.setSingleShot(True)
        self._timer_reset.timeout.connect(self._do_reset)

        self._timer_clock  = QTimer(self)
        self._timer_clock.timeout.connect(self._tick_clock)
        self._timer_clock.start(1000)

        self._timer_stats  = QTimer(self)
        self._timer_stats.timeout.connect(self._refresh_stats)
        self._timer_stats.start(30_000)   # refresh stats every 30s

        # Timer auto-reset configurable: ms (0 = infinito)
        self._auto_reset_ms: int = 5000

        # Historial últimos 10 escaneos
        self._recent: list = []

        self._comidas      = []
        self._build_ui()
        self._refresh_stats()
        self._tick_clock()

    # ─────────────────────────────────────────────
    #  UI BUILD
    # ─────────────────────────────────────────────

    def _build_ui(self):
        self.setStyleSheet(f"background: {C.BG};")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header bar ──────────────────────────────
        header = QFrame()
        header.setFixedHeight(62)
        header.setStyleSheet(
            f"background: {C.SURFACE}; border-bottom: 1px solid {C.BORDER};"
        )
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(24, 0, 24, 0)
        h_lay.setSpacing(0)

        self._lbl_school = QLabel(
            db.get_config("nombre_establecimiento", "PAE Control")
        )
        self._lbl_school.setStyleSheet(
            f"font-size: 15px; font-weight: 600; color: {C.TEXT}; background: transparent;"
        )
        h_lay.addWidget(self._lbl_school)
        h_lay.addStretch()

        # Active meal pill
        self._lbl_meal_pill = QLabel("")
        self._lbl_meal_pill.setStyleSheet(f"""
            font-size: 12px; font-weight: 700;
            color: {C.NAVY_900}; background: {C.GOLD_500};
            border-radius: 12px; padding: 4px 14px;
        """)
        h_lay.addWidget(self._lbl_meal_pill)
        h_lay.addSpacing(16)

        self._lbl_clock = QLabel("00:00:00")
        self._lbl_clock.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: {C.TEXT}; "
            f"font-variant-numeric: tabular-nums; background: transparent;"
        )
        h_lay.addWidget(self._lbl_clock)

        root.addWidget(header)

        # ── Body ─────────────────────────────────────
        body = QHBoxLayout()
        body.setContentsMargins(20, 20, 20, 20)
        body.setSpacing(16)
        root.addLayout(body, stretch=1)

        # Left: result card + input
        left = QVBoxLayout()
        left.setSpacing(14)
        body.addLayout(left, stretch=1)

        self._result_card = ResultCard()
        self._result_card.autorizar_solicitado.connect(self._autorizar_esta_vez)
        left.addWidget(self._result_card, stretch=1)

        # Input area
        input_card = QFrame()
        input_card.setFixedHeight(110)
        input_card.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border: 1.5px solid {C.BORDER};
                border-radius: 16px;
            }}
        """)
        in_lay = QVBoxLayout(input_card)
        in_lay.setContentsMargins(0, 0, 0, 0)
        in_lay.setSpacing(0)

        # Fila superior: dot + input + botón
        top_row = QHBoxLayout()
        top_row.setContentsMargins(16, 12, 16, 8)
        top_row.setSpacing(10)

        # Indicador de foco (punto pulsante)
        self._focus_dot = QFrame()
        self._focus_dot.setFixedSize(10, 10)
        self._focus_dot.setStyleSheet(
            f"background: {C.GREEN}; border-radius: 5px; border: none;"
        )
        top_row.addWidget(self._focus_dot)

        self._input = RUNLineEdit()
        self._input.setPlaceholderText("Escanear cédula o escribir RUN…")
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: transparent;
                border: none;
                font-size: 20px;
                font-weight: 500;
                color: {C.TEXT};
                letter-spacing: 1px;
            }}
            QLineEdit::placeholder {{
                color: {C.TEXT3};
            }}
        """)
        self._input.returnPressed.connect(self._on_scan)
        top_row.addWidget(self._input, stretch=1)

        btn_enter = AButton("Ingresar  ↵", sound_type="click")
        btn_enter.setStyleSheet(f"""
            QPushButton {{
                background: {C.NAVY_700};
                color: {C.TEXT};
                border: none;
                border-radius: 10px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: {C.NAVY_600}; }}
            QPushButton:pressed {{ background: {C.NAVY_800}; }}
        """)
        btn_enter.clicked.connect(self._on_scan)
        top_row.addWidget(btn_enter)
        in_lay.addLayout(top_row)

        # Fila inferior: selector de timer
        timer_row = QHBoxLayout()
        timer_row.setContentsMargins(16, 0, 16, 8)
        timer_row.setSpacing(4)

        timer_lbl = QLabel("Auto-reset:")
        timer_lbl.setStyleSheet(
            f"font-size: 11px; color: {C.TEXT3}; background: transparent;"
        )
        timer_row.addWidget(timer_lbl)
        timer_row.addSpacing(4)

        self._timer_btns: list = []
        _TIMER_OPTIONS = [("5s", 5000), ("10s", 10000), ("20s", 20000), ("∞", 0)]

        for lbl, ms in _TIMER_OPTIONS:
            from PyQt6.QtWidgets import QPushButton
            btn = QPushButton(lbl)
            btn.setFixedSize(32, 22)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty("timer_ms", ms)
            btn.clicked.connect(lambda checked, v=ms: self._set_auto_reset(v))
            timer_row.addWidget(btn)
            self._timer_btns.append(btn)

        timer_row.addStretch()
        in_lay.addLayout(timer_row)

        left.addWidget(input_card)

        # Aplicar estilo inicial a botones timer y arrancar pulso
        QTimer.singleShot(50, self._init_timer_btns)
        self._start_pulse()

        # Pulse check timer (actualiza color del dot según foco)
        self._dot_timer = QTimer(self)
        self._dot_timer.timeout.connect(self._update_focus_dot)
        self._dot_timer.start(400)

        # ── Name search bar ──────────────────────────
        self._name_bar = _NameSearchBar()
        self._name_bar.run_selected.connect(self._on_name_selected)
        left.addWidget(self._name_bar)

        # Right: stats panel
        right = QFrame()
        right.setFixedWidth(240)
        right.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border: 1.5px solid {C.BORDER};
                border-radius: 16px;
            }}
        """)
        r_lay = QVBoxLayout(right)
        r_lay.setContentsMargins(16, 20, 16, 20)
        r_lay.setSpacing(14)

        # ── Comida activa
        r_lay.addWidget(SectionHeader("Comida activa"))

        self._stat_meal_name = QLabel("—")
        self._stat_meal_name.setStyleSheet(
            f"font-size: 20px; font-weight: 700; color: {C.GOLD_500}; background: transparent;"
        )
        r_lay.addWidget(self._stat_meal_name)

        self._stat_meal_time = QLabel("")
        self._stat_meal_time.setStyleSheet(
            f"font-size: 12px; color: {C.TEXT3}; background: transparent;"
        )
        r_lay.addWidget(self._stat_meal_time)

        r_lay.addWidget(HDivider())

        # ── Stat cards
        r_lay.addWidget(SectionHeader("Capacidad"))

        self._card_activos = StatCard("Activos",        "—", accent=C.NAVY_400)
        self._card_disp    = StatCard("Almuerzos hoy", "—", accent=C.GREEN)
        self._card_espera  = StatCard("En espera",     "—", accent=C.AMBER)

        for card in (self._card_activos, self._card_disp, self._card_espera):
            r_lay.addWidget(card)

        r_lay.addWidget(HDivider())

        # ── Registros comida actual
        r_lay.addWidget(SectionHeader("Registros hoy"))

        self._card_regs = StatCard("Esta comida", "—", accent=C.GOLD_500)
        r_lay.addWidget(self._card_regs)

        r_lay.addWidget(HDivider())

        # ── Últimos 10 escaneos
        r_lay.addWidget(SectionHeader("Últimos registros"))

        from PyQt6.QtWidgets import QListWidget as _LW, QAbstractItemView as _AIV
        self._recent_list = _LW()
        self._recent_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._recent_list.setEditTriggers(_AIV.EditTrigger.NoEditTriggers)
        self._recent_list.setSelectionMode(_AIV.SelectionMode.NoSelection)
        self._recent_list.setSpacing(1)
        self._recent_list.setStyleSheet(f"""
            QListWidget {{
                background: transparent;
                border: none;
                outline: none;
            }}
            QListWidget::item {{
                border-radius: 6px;
                padding: 4px 6px;
                color: {C.TEXT2};
                font-size: 11px;
            }}
            QListWidget::item:hover {{
                background: {C.SURFACE2};
            }}
        """)
        r_lay.addWidget(self._recent_list, stretch=1)

        btn_refresh = AButton("↻  Actualizar", small=True, sound_type="click")
        btn_refresh.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {C.TEXT3};
                border: 1px solid {C.BORDER};
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 11px;
            }}
            QPushButton:hover {{ background: {C.SURFACE2}; color: {C.TEXT2}; }}
        """)
        btn_refresh.clicked.connect(self._refresh_stats)
        r_lay.addWidget(btn_refresh)

        body.addWidget(right)

        # Focus input
        QTimer.singleShot(120, self._input.setFocus)

    # ─────────────────────────────────────────────
    #  SCAN LOGIC
    # ─────────────────────────────────────────────

    def _autorizar_esta_vez(self, run: str):
        """
        Registra la comida actual para un estudiante no habilitado,
        sin modificar su estado en la base de datos.
        """
        comidas   = db.get_comidas()
        comida    = utils.comida_actual(comidas)
        if not comida:
            return
        hoy = date.today().isoformat()
        if not db.ya_registrado(run, comida["id"], hoy):
            db.registrar_asistencia(run, comida["id"], comida["nombre"])
        est = db.get_student(run)
        if not est:
            return
        r_fake = {
            "estado":            "ok",
            "estudiante":        dict(est),
            "comida":            dict(comida),
            "mensaje":           "Autorizado manualmente · sin afectar beneficio",
            "strikes_total":     0,
            "max_strikes":       int(db.get_config("max_strikes", "3")),
            "comidas_faltadas":  [],
            "comida_fria":       False,
            "descripcion_fria":  "",
        }
        self._result_card.show_result(r_fake, comidas)
        self._refresh_stats()
        sound.scan_ok()
        if self._auto_reset_ms > 0:
            self._timer_reset.stop()
            self._timer_reset.start(self._auto_reset_ms)

    def _on_name_selected(self, run: str):
        """Recibe RUN desde la barra de nombre y lanza scan."""
        import utils as _utils
        self._input.setText(_utils.run_display(run))
        self._on_scan()
        # Devolver foco al input principal para el próximo escaneo
        QTimer.singleShot(400, self._input.setFocus)

    def _on_scan(self):
        raw = self._input.text().strip()
        if not raw:
            return
        self._input.clear()

        resultado = logic.procesar_scan(raw)
        self._play_sound(resultado["estado"])
        self._result_card.show_result(resultado, self._comidas)
        self._refresh_stats()

        # Guardar en historial reciente
        self._push_recent(resultado)

        # Auto-reset configurable (0 = infinito)
        self._timer_reset.stop()
        if self._auto_reset_ms > 0:
            self._timer_reset.start(self._auto_reset_ms)

        QTimer.singleShot(60, self._input.setFocus)

    def _play_sound(self, estado: str):
        if estado == "ok":
            sound.scan_ok()
        elif estado in ("strike", "no_existe", "run_inv"):
            sound.scan_error()
        elif estado == "suspendido":
            sound.error()
        else:
            sound.click()

    def _do_reset(self):
        self._result_card.reset()
        QTimer.singleShot(320, self._input.setFocus)

    # ─────────────────────────────────────────────
    #  STATS REFRESH
    # ─────────────────────────────────────────────

    def _refresh_stats(self):
        # Capacity
        info = logic.get_capacidad_info()
        self._card_activos.set_value(str(info["activos"]))
        self._card_activos.flash()

        disp = info["disponibles"]
        self._card_disp.set_value(str(disp))
        self._card_disp._accent = C.GREEN if disp > 0 else C.RED
        self._card_disp.flash(C.GREEN if disp > 0 else C.RED)

        self._card_espera.set_value(str(info["lista_espera"]))
        self._card_espera.flash()

        # Active meal
        self._comidas = db.get_comidas()
        if not self._comidas:
            return
        comida = utils.comida_actual(self._comidas)
        if comida:
            self._stat_meal_name.setText(comida["nombre"])
            self._stat_meal_time.setText(
                f"{comida['hora_inicio']} – {comida['hora_fin']}"
            )
            self._lbl_meal_pill.setText(comida["nombre"].upper())
            n = db.count_registros_comida(date.today().isoformat(), comida["id"])
            self._card_regs.set_value(str(n))
            self._card_regs.flash()

            # Rebuild meal chips if needed
            self._result_card.build_chips(self._comidas)

    # ─────────────────────────────────────────────
    #  CLOCK
    # ─────────────────────────────────────────────

    def _tick_clock(self):
        self._lbl_clock.setText(datetime.now().strftime("%H:%M:%S"))

    # ─────────────────────────────────────────────
    #  GLOBAL KEY CAPTURE  (barcode scanner as HID)
    # ─────────────────────────────────────────────

    # ─────────────────────────────────────────────
    #  TIMER SELECTOR
    # ─────────────────────────────────────────────

    def _init_timer_btns(self):
        """Aplica estilos iniciales a los botones de timer (5s activo por defecto)."""
        for btn in self._timer_btns:
            self._style_timer_btn(btn, btn.property("timer_ms") == self._auto_reset_ms)

    def _set_auto_reset(self, ms: int):
        self._auto_reset_ms = ms
        for btn in self._timer_btns:
            self._style_timer_btn(btn, btn.property("timer_ms") == ms)

    def _style_timer_btn(self, btn, active: bool):
        if active:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {C.BLUE_DIM};
                    color: {C.BLUE};
                    border: 1px solid {C.BLUE}44;
                    border-radius: 6px;
                    font-size: 10px;
                    font-weight: 700;
                }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {C.TEXT3};
                    border: 1px solid {C.BORDER};
                    border-radius: 6px;
                    font-size: 10px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background: {C.SURFACE2};
                    color: {C.TEXT2};
                }}
            """)

    # ─────────────────────────────────────────────
    #  FOCUS DOT
    # ─────────────────────────────────────────────

    def _start_pulse(self):
        """Arranca animación de pulso en el punto de foco."""
        from PyQt6.QtWidgets import QGraphicsOpacityEffect
        self._dot_effect = QGraphicsOpacityEffect(self._focus_dot)
        self._focus_dot.setGraphicsEffect(self._dot_effect)
        anim = QPropertyAnimation(self._dot_effect, b"opacity", self)
        anim.setDuration(800)
        anim.setStartValue(0.3)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.SineCurve)
        anim.setLoopCount(-1)
        anim.start()
        self._pulse_anim = anim

    def _update_focus_dot(self):
        """Actualiza color del punto según si el input tiene foco."""
        if self._input.hasFocus():
            self._focus_dot.setStyleSheet(
                f"background: {C.GREEN}; border-radius: 5px; border: none;"
            )
        else:
            self._focus_dot.setStyleSheet(
                f"background: {C.TEXT3}; border-radius: 5px; border: none;"
            )

    # ─────────────────────────────────────────────
    #  ÚLTIMOS 10 ESCANEOS
    # ─────────────────────────────────────────────

    def _push_recent(self, resultado: dict):
        """Añade resultado al historial y actualiza la lista."""
        from datetime import datetime as _dt
        estado = resultado["estado"]
        est    = resultado.get("estudiante")
        hora   = _dt.now().strftime("%H:%M")

        # Icono por estado
        iconos = {
            "ok":          "✓",
            "ya_reg":      "→",
            "strike":      "⚠",
            "suspendido":  "⊘",
            "no_activo":   "✗",
            "no_existe":   "✗",
            "run_inv":     "✗",
        }
        icono = iconos.get(estado, "?")

        if est:
            ap  = est.get("apellido_paterno", "") or ""
            nom = est.get("nombres", "") or ""
            nombre = f"{ap}, {nom}".strip(", ")
        else:
            nombre = resultado.get("run_raw", "—")

        entry = {
            "icono":  icono,
            "nombre": nombre,
            "estado": estado,
            "hora":   hora,
        }

        self._recent.insert(0, entry)
        if len(self._recent) > 10:
            self._recent = self._recent[:10]

        self._render_recent()

    def _render_recent(self):
        from PyQt6.QtWidgets import QListWidgetItem
        self._recent_list.clear()
        colores = {
            "ok":         C.GREEN,
            "ya_reg":     C.AMBER,
            "strike":     C.RED,
            "suspendido": C.TEXT3,
            "no_activo":  C.TEXT3,
            "no_existe":  C.RED,
            "run_inv":    C.RED,
        }
        for entry in self._recent:
            color  = colores.get(entry["estado"], C.TEXT3)
            texto  = f"{entry['icono']}  {entry['nombre']}  ·  {entry['hora']}"
            item   = QListWidgetItem(texto)
            item.setForeground(QColor(color))
            self._recent_list.addItem(item)

    # ─────────────────────────────────────────────
    #  GLOBAL KEY CAPTURE  (barcode scanner as HID)
    # ─────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent):
        if not self._input.hasFocus():
            self._input.setFocus()
            self._input.event(event)
        else:
            super().keyPressEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(80, self._input.setFocus)
