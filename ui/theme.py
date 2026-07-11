"""
theme.py — Sistema de diseño PAE Control
Palette: Liceo Bicentenario Héroes de la Concepción
Style:   macOS Sequoia dark · institutional navy + blue
"""

import sys
import os
import subprocess
from PyQt6.QtCore import (
    QPropertyAnimation, QEasingCurve, QTimer, Qt,
    QAbstractAnimation, pyqtProperty, QObject, pyqtSignal
)
from PyQt6.QtGui import QColor, QPalette, QFont
from PyQt6.QtWidgets import QGraphicsOpacityEffect, QWidget, QApplication


# ═══════════════════════════════════════════════
#  PALETTE
# ═══════════════════════════════════════════════

class C:
    # ── Dark Navy — capas de profundidad
    BG        = "#0F172A"   # fondo principal
    SURFACE   = "#1E293B"   # paneles, cards, inputs
    SURFACE2  = "#293548"   # superficie secundaria, botones
    SURFACE3  = "#334565"   # hover, pressed
    BORDER    = "#2D3F58"   # separador
    BORDER2   = "#3D5070"   # separador opaco

    # ── Text
    TEXT      = "#F1F5FF"   # primario
    TEXT2     = "#6B90B0"   # secundario
    TEXT3     = "#4A6A88"   # terciario / placeholder

    # ── Semánticos
    GREEN     = "#23D96B"
    GREEN_DIM = "#0A2218"
    RED       = "#FF4545"
    RED_DIM   = "#280A0A"
    AMBER     = "#F5A823"
    AMBER_DIM = "#251A05"
    BLUE      = "#4F8EF7"
    BLUE_DIM  = "#0E1E48"

    # ── Institutional gold (branding)
    GOLD_500  = "#D4A017"
    GOLD_400  = "#E8BC00"
    GOLD_300  = "#F5D442"

    # ── Sidebar
    SIDEBAR_BG        = "#0B1524"
    SIDEBAR_ACTIVE    = "#334565"
    SIDEBAR_HOVER     = "#293548"
    SIDEBAR_INDICATOR = "#4F8EF7"

    # ── Legacy aliases (para compatibilidad con screens existentes)
    NAVY_950  = "#001A40"
    NAVY_900  = "#002966"
    NAVY_800  = "#003D8F"
    NAVY_700  = "#4F8EF7"
    NAVY_600  = "#2D6FD9"
    NAVY_400  = "#7AADFF"
    NAVY_300  = "#A8C8FF"


# ═══════════════════════════════════════════════
#  GLOBAL STYLESHEET
# ═══════════════════════════════════════════════

def global_stylesheet() -> str:
    return f"""
    /* ══ App base ══ */
    QMainWindow, QWidget {{
        background: {C.BG};
        color: {C.TEXT};
        font-family: -apple-system, "SF Pro Text", "Helvetica Neue", "Segoe UI",
                     Arial, sans-serif;
        font-size: 13px;
        line-height: 1.4;
    }}

    /* ── Scrollbars ── */
    QScrollBar:vertical {{
        background: transparent;
        width: 5px;
        margin: 2px 1px;
    }}
    QScrollBar::handle:vertical {{
        background: {C.BORDER};
        border-radius: 3px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {C.BORDER2}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 5px;
        margin: 1px 2px;
    }}
    QScrollBar::handle:horizontal {{
        background: {C.BORDER};
        border-radius: 3px;
        min-width: 24px;
    }}
    QScrollBar::handle:horizontal:hover {{ background: {C.BORDER2}; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

    /* ── QLineEdit / QTextEdit ── */
    QLineEdit, QTextEdit, QPlainTextEdit {{
        background: {C.SURFACE};
        border: 1.5px solid {C.BORDER};
        border-radius: 10px;
        padding: 8px 12px;
        color: {C.TEXT};
        font-size: 13px;
        selection-background-color: {C.BLUE};
        selection-color: white;
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
        border-color: {C.BLUE};
        border-width: 2px;
        background: {C.SURFACE};
    }}
    QLineEdit:disabled {{
        color: {C.TEXT3};
        background: {C.SURFACE2};
        border-color: {C.BORDER};
    }}

    /* ── QComboBox ── */
    QComboBox {{
        background: {C.SURFACE};
        border: 1.5px solid {C.BORDER};
        border-radius: 10px;
        padding: 8px 12px;
        color: {C.TEXT};
        font-size: 13px;
        min-height: 36px;
    }}
    QComboBox:hover {{ border-color: {C.BORDER2}; }}
    QComboBox:focus {{ border-color: {C.BLUE}; border-width: 2px; }}
    QComboBox::drop-down {{ border: none; width: 28px; }}
    QComboBox::down-arrow {{
        image: none;
        width: 10px; height: 6px;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 6px solid {C.TEXT2};
    }}
    QComboBox QAbstractItemView {{
        background: {C.SURFACE};
        border: 1.5px solid {C.BORDER};
        border-radius: 10px;
        selection-background-color: {C.BLUE_DIM};
        selection-color: {C.TEXT};
        color: {C.TEXT};
        padding: 4px;
        outline: none;
    }}
    QComboBox QAbstractItemView::item {{
        padding: 9px 12px;
        border-radius: 6px;
        min-height: 32px;
    }}

    /* ── QTimeEdit / QDateEdit / QSpinBox ── */
    QTimeEdit, QDateEdit, QSpinBox, QDoubleSpinBox {{
        background: {C.SURFACE};
        border: 1.5px solid {C.BORDER};
        border-radius: 10px;
        padding: 4px 8px;
        color: {C.TEXT};
        font-size: 13px;
        min-height: 36px;
        qproperty-buttonSymbols: PlusMinus;
    }}
    QTimeEdit:focus, QDateEdit:focus, QSpinBox:focus {{
        border-color: {C.BLUE}; border-width: 2px;
    }}
    QTimeEdit::up-button, QDateEdit::up-button, QSpinBox::up-button,
    QTimeEdit::down-button, QDateEdit::down-button, QSpinBox::down-button {{
        background: {C.SURFACE2};
        border: none;
        width: 26px;
        border-radius: 6px;
        color: {C.TEXT};
        font-size: 17px;
        font-weight: 700;
        subcontrol-origin: border;
    }}
    QSpinBox::up-button   {{ subcontrol-position: top right;    border-bottom: 1px solid {C.BORDER}; border-top-right-radius: 8px; }}
    QSpinBox::down-button {{ subcontrol-position: bottom right; border-top:    1px solid {C.BORDER}; border-bottom-right-radius: 8px; }}
    QTimeEdit::up-button, QDateEdit::up-button   {{ subcontrol-position: top right;    border-bottom: 1px solid {C.BORDER}; border-top-right-radius: 8px; }}
    QTimeEdit::down-button, QDateEdit::down-button {{ subcontrol-position: bottom right; border-top: 1px solid {C.BORDER}; border-bottom-right-radius: 8px; }}
    QTimeEdit::up-button:hover, QDateEdit::up-button:hover, QSpinBox::up-button:hover,
    QTimeEdit::down-button:hover, QDateEdit::down-button:hover, QSpinBox::down-button:hover {{
        background: {C.BORDER};
    }}
    QTimeEdit::up-button:pressed, QDateEdit::up-button:pressed, QSpinBox::up-button:pressed,
    QTimeEdit::down-button:pressed, QDateEdit::down-button:pressed, QSpinBox::down-button:pressed {{
        background: {C.BORDER2};
    }}
    QSpinBox::up-arrow, QSpinBox::down-arrow,
    QTimeEdit::up-arrow, QTimeEdit::down-arrow,
    QDateEdit::up-arrow, QDateEdit::down-arrow {{ width: 0px; height: 0px; }}

    /* ── QPushButton (base) ── */
    QPushButton {{
        background: {C.SURFACE2};
        color: {C.TEXT};
        border: 1px solid {C.BORDER};
        border-radius: 8px;
        padding: 8px 18px;
        font-size: 13px;
        font-weight: 500;
    }}
    QPushButton:hover  {{ background: {C.SURFACE3}; border-color: {C.BORDER2}; }}
    QPushButton:pressed {{ background: {C.BORDER};   border-color: {C.BORDER2}; }}
    QPushButton:disabled {{ color: {C.TEXT3}; background: {C.SURFACE2}; border-color: {C.BORDER}; }}

    /* ── QGroupBox ── */
    QGroupBox {{
        border: 1.5px solid {C.BORDER};
        border-radius: 12px;
        margin-top: 22px;
        padding: 16px 14px 14px 14px;
        font-weight: 600;
        color: {C.TEXT2};
        font-size: 11px;
        letter-spacing: 0.6px;
        text-transform: uppercase;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 14px;
        padding: 0 6px;
        background: {C.BG};
        color: {C.TEXT3};
    }}

    /* ── QTableWidget ── */
    QTableWidget {{
        background: {C.SURFACE};
        border: 1.5px solid {C.BORDER};
        border-radius: 12px;
        gridline-color: transparent;
        outline: none;
        alternate-background-color: {C.SURFACE2};
        font-size: 13px;
    }}
    QTableWidget::item {{
        padding: 10px 14px;
        border: none;
    }}
    QTableWidget::item:selected {{
        background: {C.BLUE_DIM};
        color: {C.TEXT};
    }}
    QTableWidget::item:hover:!selected {{
        background: {C.SURFACE3};
    }}
    QHeaderView::section {{
        background: {C.SURFACE2};
        color: {C.TEXT3};
        padding: 10px 14px;
        border: none;
        border-bottom: 1.5px solid {C.BORDER};
        font-weight: 800;
        font-size: 10px;
        letter-spacing: 0.8px;
        text-transform: uppercase;
    }}
    QHeaderView::section:first  {{ border-top-left-radius:  12px; }}
    QHeaderView::section:last   {{ border-top-right-radius: 12px; }}
    QHeaderView::section:hover  {{ background: {C.SURFACE3}; color: {C.TEXT2}; }}

    /* ── QProgressBar ── */
    QProgressBar {{
        background: {C.SURFACE2};
        border: none;
        border-radius: 5px;
        height: 6px;
        text-align: center;
    }}
    QProgressBar::chunk {{ background: {C.BLUE}; border-radius: 5px; }}

    /* ── QLabel ── */
    QLabel {{ color: {C.TEXT}; background: transparent; }}

    /* ── QCheckBox ── */
    QCheckBox {{ color: {C.TEXT}; spacing: 8px; font-size: 13px; }}
    QCheckBox::indicator {{
        width: 18px; height: 18px;
        border-radius: 5px;
        border: 1.5px solid {C.BORDER2};
        background: {C.SURFACE};
    }}
    QCheckBox::indicator:checked {{
        background: {C.BLUE}; border-color: {C.BLUE};
    }}
    QCheckBox::indicator:hover {{ border-color: {C.BLUE}; }}

    /* ── QTabWidget ── */
    QTabWidget::pane {{
        border: 1.5px solid {C.BORDER};
        border-radius: 12px;
        background: {C.SURFACE};
        top: -1px;
    }}
    QTabBar::tab {{
        background: transparent;
        color: {C.TEXT2};
        padding: 8px 18px;
        border: 1.5px solid transparent;
        border-radius: 8px;
        margin: 2px;
        font-weight: 500;
        font-size: 13px;
    }}
    QTabBar::tab:selected {{
        background: {C.BLUE_DIM};
        color: {C.BLUE};
        border-color: {C.BLUE};
        font-weight: 600;
    }}
    QTabBar::tab:hover:!selected {{
        background: {C.SURFACE3};
        color: {C.TEXT};
    }}

    /* ── QToolTip ── */
    QToolTip {{
        background: {C.SURFACE3};
        color: {C.TEXT};
        border: 1px solid {C.BORDER2};
        border-radius: 6px;
        padding: 5px 10px;
        font-size: 12px;
        font-weight: 500;
    }}

    /* ── QMessageBox ── */
    QMessageBox {{
        background: {C.SURFACE};
    }}
    QMessageBox QLabel {{ color: {C.TEXT}; font-size: 13px; }}

    /* ── QSplitter ── */
    QSplitter::handle {{
        background: {C.BORDER};
        width: 1px; height: 1px;
    }}

    /* ── QListWidget ── */
    QListWidget {{
        background: {C.SURFACE};
        border: 1.5px solid {C.BORDER};
        border-radius: 10px;
        color: {C.TEXT};
        outline: none;
        padding: 4px;
    }}
    QListWidget::item {{
        padding: 8px 12px;
        border-radius: 7px;
        color: {C.TEXT};
    }}
    QListWidget::item:hover {{
        background: {C.SURFACE3};
    }}
    QListWidget::item:selected {{
        background: {C.BLUE_DIM};
        color: {C.BLUE};
    }}

    /* ── QDialog ── */
    QDialog {{
        background: {C.BG};
    }}

    /* ── QMenu ── */
    QMenu {{
        background: {C.SURFACE};
        border: 1px solid {C.BORDER};
        border-radius: 10px;
        color: {C.TEXT};
        padding: 4px;
    }}
    QMenu::item {{
        padding: 8px 20px;
        border-radius: 6px;
    }}
    QMenu::item:selected {{
        background: {C.SURFACE3};
        color: {C.TEXT};
    }}
    """


# ═══════════════════════════════════════════════
#  BUTTON STYLES
# ═══════════════════════════════════════════════

def btn_primary(danger: bool = False, small: bool = False) -> str:
    bg   = C.RED  if danger else C.BLUE
    bg_h = "#CC2F2F" if danger else C.NAVY_600
    pad  = "7px 16px" if small else "10px 22px"
    r    = "8px"      if small else "10px"
    fs   = "12px"     if small else "13px"
    return f"""
    QPushButton {{
        background: {bg};
        color: white;
        border: none;
        border-radius: {r};
        padding: {pad};
        font-size: {fs};
        font-weight: 600;
    }}
    QPushButton:hover   {{ background: {bg_h}; }}
    QPushButton:pressed {{ background: {C.NAVY_800}; }}
    QPushButton:disabled {{ background: {C.BORDER}; color: {C.TEXT3}; }}
    """

def btn_secondary(small: bool = False) -> str:
    pad = "7px 16px" if small else "10px 22px"
    r   = "8px"      if small else "10px"
    fs  = "12px"     if small else "13px"
    return f"""
    QPushButton {{
        background: {C.SURFACE};
        color: {C.TEXT};
        border: 1.5px solid {C.BORDER};
        border-radius: {r};
        padding: {pad};
        font-size: {fs};
        font-weight: 500;
    }}
    QPushButton:hover   {{ background: {C.SURFACE2}; border-color: {C.BORDER2}; }}
    QPushButton:pressed {{ background: {C.SURFACE3}; }}
    QPushButton:disabled {{ color: {C.TEXT3}; border-color: {C.BORDER}; background: {C.SURFACE2}; }}
    """

def btn_ghost(small: bool = False) -> str:
    pad = "6px 14px" if small else "9px 18px"
    return f"""
    QPushButton {{
        background: transparent;
        color: {C.BLUE};
        border: none;
        border-radius: 8px;
        padding: {pad};
        font-size: 12px;
        font-weight: 500;
    }}
    QPushButton:hover   {{ background: {C.BLUE_DIM}; }}
    QPushButton:pressed {{ background: {C.SURFACE3}; }}
    """

def btn_gold(small: bool = False) -> str:
    pad = "7px 16px" if small else "10px 22px"
    return f"""
    QPushButton {{
        background: {C.GOLD_500};
        color: #0F172A;
        border: none;
        border-radius: 10px;
        padding: {pad};
        font-size: 13px;
        font-weight: 700;
    }}
    QPushButton:hover   {{ background: {C.GOLD_400}; }}
    QPushButton:pressed {{ background: #A87800; }}
    QPushButton:disabled {{ background: {C.BORDER}; color: {C.TEXT3}; }}
    """

def btn_success(small: bool = False) -> str:
    pad = "7px 16px" if small else "10px 22px"
    r   = "8px"      if small else "10px"
    return f"""
    QPushButton {{
        background: {C.GREEN};
        color: #0F172A;
        border: none;
        border-radius: {r};
        padding: {pad};
        font-size: 13px;
        font-weight: 700;
    }}
    QPushButton:hover   {{ background: #1AB858; }}
    QPushButton:pressed {{ background: #129040; }}
    QPushButton:disabled {{ background: {C.BORDER}; color: {C.TEXT3}; }}
    """


# ═══════════════════════════════════════════════
#  SOUND ENGINE
# ═══════════════════════════════════════════════

class SoundEngine:
    """Platform-native sounds — no extra dependencies."""

    @staticmethod
    def click():
        try:
            if sys.platform == 'darwin':
                subprocess.Popen(
                    ['afplay', '/System/Library/Sounds/Tink.aiff'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            elif sys.platform == 'win32':
                import winsound
                winsound.PlaySound('SystemAsterisk',
                                   winsound.SND_ALIAS | winsound.SND_ASYNC)
        except Exception:
            pass

    @staticmethod
    def save():
        try:
            if sys.platform == 'darwin':
                subprocess.Popen(
                    ['afplay', '/System/Library/Sounds/Pop.aiff'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            elif sys.platform == 'win32':
                import winsound
                winsound.PlaySound('SystemDefault',
                                   winsound.SND_ALIAS | winsound.SND_ASYNC)
        except Exception:
            pass

    @staticmethod
    def error():
        try:
            if sys.platform == 'darwin':
                subprocess.Popen(
                    ['afplay', '-v', '1.5', '/System/Library/Sounds/Basso.aiff'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            elif sys.platform == 'win32':
                import winsound
                winsound.PlaySound('SystemHand',
                                   winsound.SND_ALIAS | winsound.SND_ASYNC)
        except Exception:
            pass

    @staticmethod
    def scan_ok():
        try:
            if sys.platform == 'darwin':
                subprocess.Popen(
                    ['afplay', '-v', '1.8', '/System/Library/Sounds/Glass.aiff'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            elif sys.platform == 'win32':
                import winsound
                winsound.MessageBeep(0)
        except Exception:
            pass

    @staticmethod
    def scan_warning():
        """Ámbar — ya registrado, strike."""
        try:
            if sys.platform == 'darwin':
                subprocess.Popen(
                    ['afplay', '-v', '1.5', '/System/Library/Sounds/Funk.aiff'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            elif sys.platform == 'win32':
                import winsound
                winsound.PlaySound('SystemExclamation',
                                   winsound.SND_ALIAS | winsound.SND_ASYNC)
        except Exception:
            pass

    @staticmethod
    def scan_error(double: bool = True):
        try:
            if sys.platform == 'darwin':
                subprocess.Popen(
                    ['afplay', '-v', '2.5', '/System/Library/Sounds/Sosumi.aiff'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                if double:
                    QTimer.singleShot(480, lambda: subprocess.Popen(
                        ['afplay', '-v', '2.0', '/System/Library/Sounds/Basso.aiff'],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    ))
            elif sys.platform == 'win32':
                import winsound
                winsound.PlaySound('SystemHand',
                                   winsound.SND_ALIAS | winsound.SND_ASYNC)
        except Exception:
            pass


sound = SoundEngine()


# ═══════════════════════════════════════════════
#  ANIMATION HELPERS
# ═══════════════════════════════════════════════

def fade_in(widget: QWidget, duration: int = 200) -> QPropertyAnimation:
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    return anim


def fade_out(widget: QWidget, duration: int = 150,
             on_done=None) -> QPropertyAnimation:
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(1.0)
    anim.setEndValue(0.0)
    anim.setEasingCurve(QEasingCurve.Type.InCubic)
    if on_done:
        anim.finished.connect(on_done)
    return anim


def slide_in_from_right(widget: QWidget, duration: int = 280):
    start_x = widget.parent().width() if widget.parent() else 400
    anim = QPropertyAnimation(widget, b"pos", widget)
    anim.setDuration(duration)
    anim.setStartValue(widget.pos().__class__(start_x, widget.y()))
    anim.setEndValue(widget.pos())
    anim.setEasingCurve(QEasingCurve.Type.OutExpo)
    return anim


# ═══════════════════════════════════════════════
#  SAVED INDICATOR
# ═══════════════════════════════════════════════

from PyQt6.QtWidgets import QLabel, QHBoxLayout

class SavedIndicator(QLabel):
    def __init__(self, parent=None, text: str = "✓  Guardado"):
        super().__init__(text, parent)
        self.setStyleSheet(f"""
            QLabel {{
                color: {C.GREEN};
                font-size: 12px;
                font-weight: 600;
                padding: 4px 0;
                background: transparent;
            }}
        """)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.hide()
        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._effect.setOpacity(0)

        self._in_anim  = QPropertyAnimation(self._effect, b"opacity", self)
        self._out_anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._hold_timer = QTimer(self)

        self._in_anim.setDuration(180)
        self._in_anim.setStartValue(0.0)
        self._in_anim.setEndValue(1.0)
        self._in_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._out_anim.setDuration(300)
        self._out_anim.setStartValue(1.0)
        self._out_anim.setEndValue(0.0)
        self._out_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._out_anim.finished.connect(self.hide)

        self._hold_timer.setSingleShot(True)
        self._hold_timer.timeout.connect(self._out_anim.start)

    def show_saved(self, text: str = "✓  Guardado", hold_ms: int = 1400):
        self.setText(text)
        self.setStyleSheet(f"QLabel {{ color: {C.GREEN}; font-size: 12px; font-weight: 600; padding: 4px 0; background: transparent; }}")
        self.show()
        self._out_anim.stop()
        self._hold_timer.stop()
        self._in_anim.start()
        self._hold_timer.start(hold_ms)

    def show_error(self, text: str = "✗  Error al guardar"):
        self.setText(text)
        self.setStyleSheet(f"QLabel {{ color: {C.RED}; font-size: 12px; font-weight: 600; padding: 4px 0; background: transparent; }}")
        self.show()
        self._out_anim.stop()
        self._hold_timer.stop()
        self._in_anim.start()
        self._hold_timer.start(2000)


# ═══════════════════════════════════════════════
#  CARD WIDGET
# ═══════════════════════════════════════════════

from PyQt6.QtWidgets import QFrame, QVBoxLayout

class Card(QFrame):
    def __init__(self, parent=None, elevated: bool = False):
        super().__init__(parent)
        bg = C.SURFACE2 if elevated else C.SURFACE
        self.setStyleSheet(f"""
            QFrame {{
                background: {bg};
                border: 1.5px solid {C.BORDER};
                border-radius: 14px;
            }}
        """)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setSpacing(10)

    def layout(self) -> QVBoxLayout:
        return self._layout


# ═══════════════════════════════════════════════
#  SCAN BAR WIDGET
#  Barra compartida PAE/Inspectoría con toggle manual
# ═══════════════════════════════════════════════

from PyQt6.QtWidgets import (
    QLineEdit, QPushButton, QHBoxLayout, QSizePolicy
)
from PyQt6.QtCore import pyqtSignal

class ScanBar(QWidget):
    """
    Barra de escaneo con auto-focus y toggle manual/escáner.

    Señales:
        scanned(str)  — emitida al presionar Enter (o al recibir texto del lector)
        text_changed(str) — cada keystroke (modo manual, para búsquedas en vivo)

    Uso:
        bar = ScanBar(parent=self)
        bar.scanned.connect(self._handle_scan)
        # Para activar/desactivar el refocus periódico:
        bar.set_auto_focus(True)
    """

    scanned      = pyqtSignal(str)
    text_changed = pyqtSignal(str)

    def __init__(self, parent=None, placeholder_scan: str = "Esperando código de barras…",
                 placeholder_manual: str = "Buscar por nombre o RUN…"):
        super().__init__(parent)
        self._locked = False
        self._ph_scan   = placeholder_scan
        self._ph_manual = placeholder_manual

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Input
        self._input = QLineEdit()
        self._input.setPlaceholderText(self._ph_scan)
        self._input.returnPressed.connect(self._on_enter)
        self._input.textChanged.connect(self.text_changed)
        layout.addWidget(self._input)

        # Toggle
        self._btn = QPushButton("✎  Buscar manual")
        self._btn.setFixedHeight(40)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.clicked.connect(self._toggle)
        layout.addWidget(self._btn)

        # Timer auto-focus
        self._timer = QTimer(self)
        self._timer.setInterval(800)
        self._timer.timeout.connect(self._maybe_focus)
        self._timer.start()

        self._apply_style()

    def _on_enter(self):
        text = self._input.text().strip()
        if text:
            self.scanned.emit(text)
            self._input.clear()

    def _toggle(self):
        self._locked = not self._locked
        self._input.clear()
        self._input.setPlaceholderText(
            self._ph_manual if self._locked else self._ph_scan
        )
        self._apply_style()
        if not self._locked:
            self._input.setFocus()
        sound.click()

    def _maybe_focus(self):
        if not self._locked and self.isVisible():
            self._input.setFocus()

    def set_auto_focus(self, enabled: bool):
        if enabled:
            self._timer.start()
        else:
            self._timer.stop()

    def clear(self):
        self._input.clear()

    def _apply_style(self):
        if self._locked:
            border = C.AMBER
            icon   = "⌗"
            label  = "Activar escaneo"
            btn_bg = C.AMBER_DIM
            btn_brd = C.AMBER
            btn_col = C.AMBER
        else:
            border = C.BLUE
            icon   = "✎"
            label  = "Buscar manual"
            btn_bg = C.SURFACE
            btn_brd = C.BORDER
            btn_col = C.TEXT2

        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: {C.SURFACE};
                border: 2px solid {border};
                border-radius: 11px;
                padding: 10px 14px;
                color: {C.TEXT};
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border-color: {border};
            }}
        """)
        self._btn.setText(f"{icon}  {label}")
        self._btn.setStyleSheet(f"""
            QPushButton {{
                background: {btn_bg};
                color: {btn_col};
                border: 1.5px solid {btn_brd};
                border-radius: 10px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {C.AMBER_DIM};
                border-color: {C.AMBER};
                color: {C.AMBER};
            }}
        """)


# ═══════════════════════════════════════════════
#  BADGE HELPER
# ═══════════════════════════════════════════════

def badge_style(color: str, bg: str) -> str:
    """Estilo para pills/badges de estado."""
    return f"""
        QLabel {{
            background: {bg};
            color: {color};
            border-radius: 100px;
            padding: 3px 10px;
            font-size: 11px;
            font-weight: 700;
        }}
    """


# ═══════════════════════════════════════════════
#  APPLY PALETTE  (llamar una vez en main.py)
# ═══════════════════════════════════════════════

def apply_theme(app: QApplication):
    app.setStyle("Fusion")
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window,          QColor(C.BG))
    p.setColor(QPalette.ColorRole.Base,            QColor(C.SURFACE))
    p.setColor(QPalette.ColorRole.AlternateBase,   QColor(C.SURFACE2))
    p.setColor(QPalette.ColorRole.Button,          QColor(C.SURFACE2))
    p.setColor(QPalette.ColorRole.Midlight,        QColor(C.SURFACE3))
    p.setColor(QPalette.ColorRole.Mid,             QColor(C.BORDER))
    p.setColor(QPalette.ColorRole.Dark,            QColor(C.BORDER2))
    p.setColor(QPalette.ColorRole.Shadow,          QColor("#000000"))
    p.setColor(QPalette.ColorRole.WindowText,      QColor(C.TEXT))
    p.setColor(QPalette.ColorRole.Text,            QColor(C.TEXT))
    p.setColor(QPalette.ColorRole.BrightText,      QColor("#FFFFFF"))
    p.setColor(QPalette.ColorRole.ButtonText,      QColor(C.TEXT))
    p.setColor(QPalette.ColorRole.PlaceholderText, QColor(C.TEXT3))
    p.setColor(QPalette.ColorRole.ToolTipBase,     QColor(C.SURFACE))
    p.setColor(QPalette.ColorRole.ToolTipText,     QColor(C.TEXT))
    p.setColor(QPalette.ColorRole.Highlight,       QColor(C.BLUE))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text,       QColor(C.TEXT3))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(C.TEXT3))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Base,       QColor(C.BG))
    app.setPalette(p)
    app.setStyleSheet(global_stylesheet())
