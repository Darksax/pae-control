"""
widgets.py — Reusable custom widgets
"""

from PyQt6.QtWidgets import (
    QPushButton, QLabel, QWidget, QVBoxLayout,
    QHBoxLayout, QFrame, QSizePolicy, QStackedWidget,
    QLineEdit, QGraphicsOpacityEffect
)
from PyQt6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, QTimer,
    QRect, pyqtProperty, QSize, QPoint
)
from PyQt6.QtGui import (
    QColor, QPainter, QPen, QBrush, QFont,
    QMouseEvent, QEnterEvent
)

from ui.theme import C, sound


# ═══════════════════════════════════════════════
#  ANIMATED PUSH BUTTON
# ═══════════════════════════════════════════════

class AButton(QPushButton):
    """
    QPushButton with:
    - Press scale animation (feels physical)
    - Click sound
    - Optional auto-save debounce signal
    """

    def __init__(self, text: str = "", parent=None,
                 play_sound: bool = True, sound_type: str = "click",
                 small: bool = False):
        super().__init__(text, parent)
        self._play_sound  = play_sound
        self._sound_type  = sound_type
        self._scale       = 1.0
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if small:
            self.setFixedHeight(28)
            self.setStyleSheet(
                "font-size: 11px; font-weight: 600; padding: 0 10px;"
            )

    def mousePressEvent(self, e: QMouseEvent):
        super().mousePressEvent(e)
        if self._play_sound and self.isEnabled():
            if self._sound_type == "save":
                sound.save()
            elif self._sound_type == "error":
                sound.error()
            else:
                sound.click()

    def enterEvent(self, e):
        super().enterEvent(e)

    def leaveEvent(self, e):
        super().leaveEvent(e)


# ═══════════════════════════════════════════════
#  SIDEBAR NAV ITEM
# ═══════════════════════════════════════════════

class NavItem(QWidget):
    """
    Single sidebar navigation button.
    Shows icon (text emoji), label, and an active indicator bar.
    """

    def __init__(self, icon: str, label: str, parent=None):
        super().__init__(parent)
        self.icon_str  = icon
        self.label_str = label
        self._active   = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(52)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        # Active indicator bar
        self._indicator = QFrame()
        self._indicator.setFixedSize(3, 28)
        self._indicator.setStyleSheet(f"background: transparent; border-radius: 2px;")
        layout.addWidget(self._indicator)

        # Icon
        self._icon_lbl = QLabel(icon)
        self._icon_lbl.setFixedWidth(22)
        self._icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_lbl.setStyleSheet(f"font-size: 18px; background: transparent; color: {C.TEXT3};")
        layout.addWidget(self._icon_lbl)

        # Label
        self._label_lbl = QLabel(label)
        self._label_lbl.setStyleSheet(
            f"font-size: 13px; font-weight: 500; color: {C.TEXT2}; background: transparent;"
        )
        layout.addWidget(self._label_lbl, 1)

        self._set_hover(False)

    def set_active(self, active: bool):
        self._active = active
        self._set_hover(active)

    def _set_hover(self, active: bool):
        if active:
            self._indicator.setStyleSheet(
                f"background: {C.GOLD_500}; border-radius: 2px;"
            )
            self._icon_lbl.setStyleSheet(
                f"font-size: 18px; background: transparent; color: {C.TEXT};"
            )
            self._label_lbl.setStyleSheet(
                f"font-size: 13px; font-weight: 600; color: {C.TEXT}; background: transparent;"
            )
            self.setStyleSheet(f"background: {C.SIDEBAR_ACTIVE}; border-radius: 10px;")
        else:
            self._indicator.setStyleSheet(
                "background: transparent; border-radius: 2px;"
            )
            self._icon_lbl.setStyleSheet(
                f"font-size: 18px; background: transparent; color: {C.TEXT3};"
            )
            self._label_lbl.setStyleSheet(
                f"font-size: 13px; font-weight: 500; color: {C.TEXT2}; background: transparent;"
            )
            self.setStyleSheet("background: transparent; border-radius: 10px;")

    def enterEvent(self, e):
        if not self._active:
            self.setStyleSheet(f"background: {C.SIDEBAR_HOVER}; border-radius: 10px;")
        super().enterEvent(e)

    def leaveEvent(self, e):
        if not self._active:
            self.setStyleSheet("background: transparent; border-radius: 10px;")
        super().leaveEvent(e)


# ═══════════════════════════════════════════════
#  ANIMATED STACKED WIDGET  (screen transitions)
# ═══════════════════════════════════════════════

class AnimatedStack(QStackedWidget):
    """
    QStackedWidget with smooth fade + slide transitions.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._animating = False
        self._duration  = 220

    def slide_to(self, index: int):
        if self._animating or index == self.currentIndex():
            return

        current = self.currentWidget()
        next_w  = self.widget(index)
        if not current or not next_w:
            self.setCurrentIndex(index)
            return

        self._animating = True
        w = self.width()

        # Fade out current
        from ui.theme import fade_out, fade_in
        self._out = fade_out(current, duration=140, on_done=lambda: self._switch(index, next_w))
        self._out.start()

    def _switch(self, index: int, next_w: QWidget):
        self.setCurrentIndex(index)
        from ui.theme import fade_in
        self._in = fade_in(next_w, duration=180)
        self._in.finished.connect(lambda: setattr(self, '_animating', False))
        self._in.start()


# ═══════════════════════════════════════════════
#  STAT CARD  (used on scan screen)
# ═══════════════════════════════════════════════

class StatCard(QFrame):
    """Small KPI card: big number + label below."""

    def __init__(self, label: str, value: str = "0",
                 accent: str = C.NAVY_400, parent=None):
        super().__init__(parent)
        self._accent = accent
        self.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border: 1.5px solid {C.BORDER};
                border-radius: 12px;
                padding: 0;
            }}
        """)
        self.setMinimumWidth(100)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        self._value_lbl = QLabel(value)
        self._value_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._value_lbl.setStyleSheet(
            f"font-size: 28px; font-weight: 700; color: {accent}; background: transparent;"
        )

        self._label_lbl = QLabel(label.upper())
        self._label_lbl.setStyleSheet(
            f"font-size: 10px; font-weight: 600; color: {C.TEXT3}; "
            f"letter-spacing: 0.6px; background: transparent;"
        )

        layout.addWidget(self._value_lbl)
        layout.addWidget(self._label_lbl)

    def set_value(self, val: str):
        self._value_lbl.setText(val)

    def flash(self, color: str = None):
        """Briefly tint the card to signal a new value."""
        c = color or self._accent
        self.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE2};
                border: 1.5px solid {c};
                border-radius: 12px;
            }}
        """)
        QTimer.singleShot(400, lambda: self.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border: 1.5px solid {C.BORDER};
                border-radius: 12px;
            }}
        """))


# ═══════════════════════════════════════════════
#  SECTION HEADER
# ═══════════════════════════════════════════════

class SectionHeader(QLabel):
    """Small uppercase section title."""
    def __init__(self, text: str, parent=None):
        super().__init__(text.upper(), parent)
        self.setStyleSheet(f"""
            QLabel {{
                color: {C.TEXT3};
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 1px;
                padding: 0 4px;
                background: transparent;
            }}
        """)


# ═══════════════════════════════════════════════
#  DIVIDER
# ═══════════════════════════════════════════════

class HDivider(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFixedHeight(1)
        self.setStyleSheet(f"background: {C.BORDER}; border: none;")


class VDivider(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.VLine)
        self.setFixedWidth(1)
        self.setStyleSheet(f"background: {C.BORDER}; border: none;")


# ═══════════════════════════════════════════════
#  BADGE  (e.g., strike count)
# ═══════════════════════════════════════════════

class Badge(QLabel):
    def __init__(self, text: str = "", color: str = C.RED, parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._set_color(color)
        self.setFixedHeight(22)
        self.setMinimumWidth(22)

    def _set_color(self, color: str):
        self.setStyleSheet(f"""
            QLabel {{
                background: {color};
                color: white;
                border-radius: 11px;
                font-size: 11px;
                font-weight: 700;
                padding: 0 6px;
            }}
        """)

    def set_value(self, val: int):
        self.setText(str(val))
        if val == 0:
            self._set_color(C.TEXT3)
        elif val >= 3:
            self._set_color(C.RED)
        else:
            self._set_color(C.AMBER)


# ═══════════════════════════════════════════════
#  SAVED INDICATOR  — feedback inline sin QMessageBox
# ═══════════════════════════════════════════════

class SavedIndicator(QLabel):
    """
    Muestra un mensaje de éxito o error que aparece con fade-in,
    se mantiene 2s y desaparece con fade-out.
    No usa QMessageBox ni modales.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText("")
        self.setFixedHeight(28)
        self.setStyleSheet("background: transparent;")
        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._effect.setOpacity(0.0)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._fade_out)
        self._anim = None

    def show_saved(self, msg: str = "✓  Guardado"):
        self._show(msg, C.GREEN)

    def show_error(self, msg: str = "✗  Error"):
        self._show(msg, C.RED)

    def _show(self, msg: str, color: str):
        self.setText(msg)
        self.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: {color}; background: transparent;"
        )
        self._hide_timer.stop()
        self._anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._anim.setDuration(180)
        self._anim.setStartValue(self._effect.opacity())
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.start()
        self._hide_timer.start(2200)

    def _fade_out(self):
        self._anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._anim.setDuration(400)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._anim.finished.connect(lambda: self.setText(""))
        self._anim.start()


# ═══════════════════════════════════════════════
#  RUN LINE EDIT  (Ticket #1: live RUN formatting)
# ═══════════════════════════════════════════════

def _fmt_run_live(raw: str) -> str:
    """
    Formatea un RUN parcial o completo para mostrar mientras se escribe.
    Solo inserta puntos en el cuerpo numérico y preserva el guion si existe.
    El dígito verificador NO se infiere — se espera que el usuario o la
    lectora lo entregue con guion explícito o como 'K' al final.

    Ejemplos:
        "2379946"       → "2.379.946"
        "23799462-0"    → "23.799.462-0"
        "23799462-"     → "23.799.462-"     (guion preservado, DV aún no)
        "237994620"     → "237.994.620"     (lectora sin guion: solo puntos)
        "23799462K"     → "23.799.462-K"    (K se convierte en DV)
    """
    has_dash = '-' in raw

    # Detectar K final como DV (sin guion)
    upper = raw.upper()
    if not has_dash and upper.endswith('K'):
        num_raw = upper[:-1]
        dv = 'K'
        has_dash = True   # mostrar como separado
    elif has_dash:
        parts = raw.upper().replace('.', '').replace(' ', '').split('-', 1)
        num_raw = ''.join(c for c in parts[0] if c.isdigit())
        dv = parts[1][:1] if parts[1] else ''
    else:
        num_raw = ''.join(c for c in upper if c.isdigit())
        dv = ''

    # Formatear cuerpo con puntos (Python comma-grouping)
    if not num_raw:
        num_fmt = ''
    else:
        try:
            num_fmt = f"{int(num_raw):,}".replace(',', '.')
        except ValueError:
            num_fmt = num_raw

    if has_dash:
        return f"{num_fmt}-{dv}"
    return num_fmt


class RUNLineEdit(QLineEdit):
    """
    QLineEdit con formateo en vivo del RUN chileno.

    - Inserta puntos automáticamente mientras se escribe
    - Preserva el guion si fue escrito por el usuario
    - Compatible con lectura de código de barras (stream de chars rápido)
    - El dígito verificador se valida en el submit, no en el input

    Uso en scan_screen:
        self._input = RUNLineEdit()
        self._input.returnPressed.connect(self._on_scan)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._busy = False
        self.textChanged.connect(self._on_changed)

    def _on_changed(self, text: str):
        if self._busy:
            return
        formatted = _fmt_run_live(text)
        if formatted != text:
            self._busy = True
            self.setText(formatted)
            self.setCursorPosition(len(formatted))
            self._busy = False
