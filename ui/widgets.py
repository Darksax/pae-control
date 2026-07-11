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

import re as _re

# RUN completo: cuerpo con puntos + guión + 1 dígito o K
_RUN_COMPLETO_RE = _re.compile(r'^\d[\d\.]*-[\dkK]$', _re.I)


def _fmt_run_live(raw: str) -> str:
    """
    Formatea un RUN parcial o completo para mostrar mientras se escribe.

    Reglas:
    - Guión explícito → respeta la separación cuerpo/DV
    - K al final (sin guión) → K es el DV
    - 9+ dígitos puros (sin guión, sin K) → último dígito = DV
      RUNs 20M-28M: cuerpo 8 dígitos + DV = 9 dígitos del scanner.
      RUNs 100M+:   cuerpo 9 dígitos + DV = 10 dígitos del scanner.
    - < 9 dígitos puros → solo formatea el cuerpo con puntos, sin DV todavía
      (el scanner aún no ha enviado el DV)

    Ejemplos:
        "2379946"       → "2.379.946"        (7 dígitos, sin DV aún)
        "23799462"      → "23.799.462"       (8 dígitos, sin DV aún — esperar 9no)
        "237994620"     → "23.799.462-0"     (9 dígitos → último = DV) ← caso normal
        "1000000001"    → "100.000.000-1"    (10 dígitos → RUN provisorio)
        "23799462-0"    → "23.799.462-0"     (guión explícito)
        "23799462K"     → "23.799.462-K"     (K = DV)
    """
    has_dash = '-' in raw
    upper = raw.upper()

    # ── Caso 1: K al final sin guión ─────────────────
    if not has_dash and upper.endswith('K'):
        num_raw = ''.join(c for c in upper[:-1] if c.isdigit())
        dv = 'K'
        has_dash = True

    # ── Caso 2: guión explícito ───────────────────────
    elif has_dash:
        parts = upper.replace('.', '').replace(' ', '').split('-', 1)
        num_raw = ''.join(c for c in parts[0] if c.isdigit())
        dv = parts[1][:1] if parts[1] else ''

    # ── Caso 3: solo dígitos ──────────────────────────
    else:
        digits = ''.join(c for c in upper if c.isdigit())
        if len(digits) >= 9:
            # Lector de barras: RUNs 20M-28M tienen 8 dígitos de cuerpo + 1 DV
            # → el scanner envía 9 dígitos en total.
            # RUNs provisorios (100M+) tienen 9 cuerpo + 1 DV = 10 dígitos.
            # Regla: último dígito = DV, el resto = cuerpo.
            num_raw  = digits[:-1]
            dv       = digits[-1]
            has_dash = True
        else:
            # Menos de 9 dígitos puros → todavía puede faltar el DV
            # (el scanner aún no terminó). Mostrar solo el cuerpo sin guión.
            num_raw = digits
            dv = ''

    # ── Formatear cuerpo con puntos ───────────────────
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

    - Inserta puntos y guión automáticamente mientras se escribe
    - Con 9+ dígitos sin guión, el último es el DV (lector de barras)
    - Auto-envía con debounce de 180ms: cuando el campo deja de cambiar y
      el RUN está completo (formato XX.XXX.XXX-X), emite scan_ready.
      Funciona para scanner (todos los chars en <100ms) y tecleo manual
      (se envía 180ms después del último carácter, o con Enter inmediato).

    Uso en scan_screen:
        self._input = RUNLineEdit()
        self._input.returnPressed.connect(self._on_scan)
        self._input.scan_ready.connect(self._on_scan)
    """
    from PyQt6.QtCore import pyqtSignal as _sig
    scan_ready = _sig()   # RUN completo detectado → auto-submit

    def __init__(self, parent=None):
        super().__init__(parent)
        self._busy = False

        # Debounce: reinicia con cada cambio de texto.
        # Cuando el campo para de cambiar (180ms) → verifica si hay RUN completo.
        # Scanner: envía 9 chars en ~50ms → timer dispara ~180ms después del último.
        # Teclado: el usuario también puede esperar o presionar Enter directamente.
        self._scan_timer = QTimer(self)
        self._scan_timer.setSingleShot(True)
        self._scan_timer.setInterval(180)
        self._scan_timer.timeout.connect(self._check_auto_submit)
        self.textChanged.connect(self._on_changed)

    def _on_changed(self, text: str):
        if self._busy:
            return

        # ── Formatear en vivo ───────────────────────────
        formatted = _fmt_run_live(text)
        if formatted != text:
            self._busy = True
            self.setText(formatted)
            self.setCursorPosition(len(formatted))
            self._busy = False

        # ── Debounce: reiniciar timer en cada cambio ────
        if text.strip():
            self._scan_timer.start()   # reinicia el timer de 180ms
        else:
            self._scan_timer.stop()

    def set_submit_delay(self, ms: int):
        """Cambia el intervalo de debounce del auto-submit (mínimo 50ms)."""
        self._scan_timer.setInterval(max(50, int(ms)))

    def _check_auto_submit(self):
        """Emite scan_ready si el campo contiene un RUN completo (formato correcto)."""
        if _RUN_COMPLETO_RE.match(self.text()):
            self.scan_ready.emit()


# ══════════════════════════════════════════════════════
#  PHONE LINE EDIT — formato chileno +56 9 XXXX XXXX
# ══════════════════════════════════════════════════════

import re as _re

def _fmt_phone(raw: str) -> str:
    """
    Convierte cualquier entrada a formato '+56 9 XXXX XXXX'.
    Acepta: '912345678', '56912345678', '+56 9 1234 5678', '9 1234 5678', etc.
    Retorna cadena vacía si no hay dígitos útiles.
    """
    digits = _re.sub(r'\D', '', raw)
    if not digits:
        return ""

    # Normalizar: extraer los 8 dígitos del número local (sin 56 ni 9)
    if digits.startswith('569'):
        core = digits[3:]
    elif digits.startswith('56'):
        # puede faltar el 9 si el usuario lo omitió
        rest = digits[2:]
        core = rest[1:] if rest.startswith('9') else rest
    elif digits.startswith('9'):
        core = digits[1:]
    else:
        core = digits

    core = core[:8]  # máximo 8 dígitos

    # Construir +56 9 [XXXX] [XXXX]
    result = "+56 9"
    if core:
        result += " " + core[:4]
    if len(core) > 4:
        result += " " + core[4:8]
    return result


class PhoneLineEdit(QLineEdit):
    """
    QLineEdit con auto-formato de número celular chileno.

    Comportamiento:
    - El usuario escribe solo los dígitos del número (ej: 912345678)
    - El campo formatea en vivo → '+56 9 XXXX XXXX'
    - También acepta pegar un número ya formateado o con código de país
    - Si el campo queda vacío se limpia sin prefijo
    - phone_e164() retorna '+56XXXXXXXXX' para la API de WhatsApp
    - phone_display() retorna '+56 9 XXXX XXXX' (lo que muestra el campo)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("+56 9 XXXX XXXX")
        self.setMaxLength(15)   # '+56 9 XXXX XXXX' = 15 chars
        self._busy = False
        self.textEdited.connect(self._reformat)

    def _reformat(self, text: str):
        if self._busy:
            return
        formatted = _fmt_phone(text)
        if formatted == text:
            return
        self._busy = True
        self.setText(formatted)
        self.setCursorPosition(len(formatted))
        self._busy = False

    def set_phone(self, value: str):
        """Carga un número existente y lo formatea."""
        formatted = _fmt_phone(value) if value else ""
        self._busy = True
        self.setText(formatted)
        self.setCursorPosition(len(formatted))
        self._busy = False

    def phone_e164(self) -> str:
        """'+56XXXXXXXXX' — formato para Meta WhatsApp API."""
        digits = _re.sub(r'\D', '', self.text())
        if not digits:
            return ""
        if digits.startswith('569') and len(digits) == 11:
            return '+' + digits
        if digits.startswith('56') and len(digits) == 11:
            return '+' + digits
        return ""

    def phone_display(self) -> str:
        """'+56 9 XXXX XXXX' — formato legible."""
        return self.text().strip()

    def is_valid(self) -> bool:
        """True si tiene exactamente 8 dígitos locales (11 con 56)."""
        return len(_re.sub(r'\D', '', self.text())) == 11


# ══════════════════════════════════════════════════════
#  COPY-ON-CLICK  — helper para tablas
# ══════════════════════════════════════════════════════

def make_table_copyable(table, copy_cols: list[int] | None = None,
                        tooltip_ms: int = 1200):
    """
    Conecta cellClicked a la tabla para copiar al portapapeles al hacer
    click izquierdo en una celda (o solo en las columnas de `copy_cols`).
    Muestra un QToolTip breve de "✓ Copiado" como feedback visual.

    Uso:
        make_table_copyable(self._tabla, copy_cols=[1])  # solo columna RUN
    """
    from PyQt6.QtWidgets import QToolTip, QApplication
    from PyQt6.QtGui import QCursor
    from PyQt6.QtCore import QRect

    def _on_cell_click(row: int, col: int):
        if copy_cols is not None and col not in copy_cols:
            return
        item = table.item(row, col)
        if item and item.text():
            QApplication.clipboard().setText(item.text())
            QToolTip.showText(
                QCursor.pos(),
                "✓  Copiado",
                table,
                QRect(),
                tooltip_ms,
            )

    table.cellClicked.connect(_on_cell_click)
    # Cambiar cursor al pasar sobre la tabla — indica que es copiable
    table.setMouseTracking(True)


# ══════════════════════════════════════════════════════
#  TOAST BANNER — notificación breve flotante
# ══════════════════════════════════════════════════════

class ToastBanner(QFrame):
    """
    Notificación flotante posicionada arriba de la pantalla.
    Se muestra brevemente y se desvanece sola.

    Uso:
        self._toast = ToastBanner(self)   # child del screen
        self._toast.show_toast("✓ 3 estudiantes dados de baja", "ok")
    """

    _TIPOS = {
        "ok":    (C.GREEN,       "#052e16"),
        "error": (C.RED,         "#2d0707"),
        "info":  (C.BLUE,        "#0c1929"),
        "warn":  (C.AMBER,       C.AMBER_DIM),
    }

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setFixedHeight(56)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 0, 20, 0)
        lay.setSpacing(12)

        self._icon = QLabel("✓")
        self._icon.setStyleSheet("font-size: 18px; background: transparent;")
        lay.addWidget(self._icon)

        self._msg = QLabel("")
        self._msg.setStyleSheet(
            "font-size: 14px; font-weight: 600; background: transparent;"
        )
        lay.addWidget(self._msg, stretch=1)

        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._effect.setOpacity(0.0)
        self._anim: QPropertyAnimation | None = None
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._fade_out)
        self.hide()

    def show_toast(self, msg: str, tipo: str = "ok", duracion_ms: int = 3500):
        color, bg = self._TIPOS.get(tipo, self._TIPOS["ok"])
        self._icon.setText("✓" if tipo == "ok" else ("✗" if tipo == "error" else "ℹ"))
        self._icon.setStyleSheet(f"font-size: 18px; color: {color}; background: transparent;")
        self._msg.setText(msg)
        self._msg.setStyleSheet(
            f"font-size: 14px; font-weight: 600; color: {color}; background: transparent;"
        )
        self.setStyleSheet(f"""
            QFrame {{
                background: {bg};
                border: 1.5px solid {color}55;
                border-radius: 14px;
            }}
        """)
        self._reposition()
        self.show()
        self.raise_()

        # Stop any ongoing animation
        if self._anim and self._anim.state() == QPropertyAnimation.State.Running:
            self._anim.stop()
        self._hide_timer.stop()

        # Fade in
        self._anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._anim.setDuration(180)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.start()

        self._hide_timer.start(duracion_ms)

    def _fade_out(self):
        self._anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._anim.setDuration(400)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._anim.finished.connect(self.hide)
        self._anim.start()

    def _reposition(self):
        p = self.parent()
        if not p:
            return
        w = min(560, p.width() - 48)
        x = (p.width() - w) // 2
        self.setGeometry(x, 16, w, 56)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition()


# ══════════════════════════════════════════════════════
#  CONFIRM PANEL — confirmación inline (sin QDialog)
# ══════════════════════════════════════════════════════

class ConfirmPanel(QFrame):
    """
    Panel de confirmación que aparece en la parte inferior de la pantalla.
    No es un QDialog — es un widget hijo que se muestra/oculta.

    Uso:
        self._confirm = ConfirmPanel(self)
        self._confirm.pedir_confirmacion(
            accion   = "Dar de baja",
            color    = C.RED,
            items    = [{"run": run, "nombre": "García, Juan"}, ...],
            on_ok    = lambda runs: self._ejecutar_baja(runs),
        )
    """

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setFixedHeight(130)
        self.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border-top: 2px solid {C.BORDER2};
                border-radius: 0px;
            }}
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 12, 24, 12)
        lay.setSpacing(8)

        # Fila superior: ícono + texto
        top = QHBoxLayout()
        top.setSpacing(10)

        self._lbl_icon = QLabel("⚠")
        self._lbl_icon.setStyleSheet("font-size: 20px; background: transparent;")
        top.addWidget(self._lbl_icon)

        self._lbl_accion = QLabel("")
        self._lbl_accion.setStyleSheet(
            f"font-size: 14px; font-weight: 700; color: {C.TEXT}; background: transparent;"
        )
        top.addWidget(self._lbl_accion)
        top.addStretch()

        self._btn_cancel = AButton("Cancelar", sound_type="click")
        self._btn_cancel.setFixedHeight(34)
        self._btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background: {C.SURFACE2}; color: {C.TEXT2};
                border: 1px solid {C.BORDER}; border-radius: 8px;
                padding: 0 18px; font-size: 13px; font-weight: 600;
            }}
            QPushButton:hover {{ background: {C.SURFACE3}; color: {C.TEXT}; }}
        """)
        self._btn_cancel.clicked.connect(self._on_cancel)
        top.addWidget(self._btn_cancel)

        self._btn_confirm = AButton("Confirmar", sound_type="save")
        self._btn_confirm.setFixedHeight(34)
        top.addWidget(self._btn_confirm)
        self._btn_confirm.clicked.connect(self._on_confirm)

        lay.addLayout(top)

        # Nombres (resumen)
        self._lbl_nombres = QLabel("")
        self._lbl_nombres.setWordWrap(True)
        self._lbl_nombres.setStyleSheet(
            f"font-size: 12px; color: {C.TEXT3}; background: transparent;"
        )
        lay.addWidget(self._lbl_nombres)

        self._runs: list[str] = []
        self._on_ok = None
        self.hide()

    def pedir_confirmacion(self, accion: str, color: str,
                           items: list[dict], on_ok):
        """
        accion: texto de la operación ("Dar de baja a N estudiantes")
        color:  color del botón confirmar
        items:  [{"run": str, "nombre": str}, ...]
        on_ok:  callable(runs: list[str]) — se llama con los RUNs si confirma
        """
        self._runs  = [it["run"] for it in items]
        self._on_ok = on_ok

        self._lbl_accion.setText(accion)
        self._btn_confirm.setStyleSheet(f"""
            QPushButton {{
                background: {color}22; color: {color};
                border: 1.5px solid {color}66; border-radius: 8px;
                padding: 0 18px; font-size: 13px; font-weight: 700;
            }}
            QPushButton:hover {{ background: {color}44; }}
        """)

        nombres = [it["nombre"] for it in items]
        preview = ", ".join(nombres[:5])
        if len(nombres) > 5:
            preview += f" … y {len(nombres)-5} más"
        self._lbl_nombres.setText(preview)

        self._reposition()
        self.show()
        self.raise_()

    def _on_cancel(self):
        self.hide()

    def _on_confirm(self):
        runs = list(self._runs)
        cb   = self._on_ok
        self.hide()
        if cb:
            cb(runs)

    def _reposition(self):
        p = self.parent()
        if p:
            self.setGeometry(0, p.height() - self.height(), p.width(), self.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition()
