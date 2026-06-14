"""
theme.py — Sistema de diseño PAE Control
Palette: Liceo Bicentenario Héroes de la Concepción
Style:   macOS Sonoma dark · institutional navy + gold
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
    # ── macOS Light Mode System Colors
    BG        = "#F2F2F7"   # systemGroupedBackground
    SURFACE   = "#FFFFFF"   # systemBackground (cards, panels)
    SURFACE2  = "#F2F2F7"   # secondarySystemBackground
    SURFACE3  = "#E5E5EA"   # tertiarySystemBackground / hover
    BORDER    = "#D1D1D6"   # separator
    BORDER2   = "#C7C7CC"   # opaqueSeparator

    # ── Text
    TEXT      = "#1C1C1E"   # label (near black)
    TEXT2     = "#6C6C70"   # secondaryLabel
    TEXT3     = "#AEAEB2"   # tertiaryLabel / placeholder

    # ── Semantic — macOS standard
    GREEN     = "#34C759"   # systemGreen
    GREEN_DIM = "#D9F2E0"
    RED       = "#FF3B30"   # systemRed
    RED_DIM   = "#FFE8E6"
    AMBER     = "#FF9500"   # systemOrange
    BLUE      = "#007AFF"   # systemBlue (interactive)
    BLUE_DIM  = "#EAF2FF"

    # ── Blue scale (replaces navy for actions/buttons)
    NAVY_950  = "#001A40"
    NAVY_900  = "#002966"
    NAVY_800  = "#003D8F"
    NAVY_700  = "#007AFF"   # primary action → systemBlue
    NAVY_600  = "#0066CC"   # hover
    NAVY_400  = "#4DA6FF"   # accent / info
    NAVY_300  = "#80BDFF"

    # ── Institutional gold (branding, logo only)
    GOLD_500  = "#C9960C"   # slightly darker for legibility on white
    GOLD_400  = "#E8A800"
    GOLD_300  = "#F5C842"

    # ── Sidebar
    SIDEBAR_BG        = "#FFFFFF"
    SIDEBAR_ACTIVE    = "#E8F0FE"   # light blue tint
    SIDEBAR_HOVER     = "#F5F5F7"
    SIDEBAR_INDICATOR = "#007AFF"   # blue bar


# ═══════════════════════════════════════════════
#  GLOBAL STYLESHEET
# ═══════════════════════════════════════════════

def global_stylesheet() -> str:
    return f"""
    /* ── App base ── */
    QMainWindow, QWidget {{
        background: {C.BG};
        color: {C.TEXT};
        font-family: -apple-system, "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
        font-size: 13px;
    }}

    /* ── Scrollbars ── */
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {C.BORDER2};
        border-radius: 4px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {C.TEXT3};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 8px;
    }}
    QScrollBar::handle:horizontal {{
        background: {C.BORDER2};
        border-radius: 4px;
        min-width: 30px;
    }}

    /* ── QLineEdit / QTextEdit ── */
    QLineEdit, QTextEdit, QPlainTextEdit {{
        background: {C.SURFACE};
        border: 1px solid {C.BORDER};
        border-radius: 8px;
        padding: 8px 12px;
        color: {C.TEXT};
        selection-background-color: {C.BLUE};
        selection-color: white;
    }}
    QLineEdit:focus, QTextEdit:focus {{
        border-color: {C.BLUE};
        border-width: 2px;
    }}
    QLineEdit:disabled {{
        color: {C.TEXT3};
        background: {C.SURFACE2};
        border-color: {C.BORDER};
    }}

    /* ── QComboBox ── */
    QComboBox {{
        background: {C.SURFACE};
        border: 1px solid {C.BORDER};
        border-radius: 8px;
        padding: 7px 12px;
        color: {C.TEXT};
        min-height: 34px;
    }}
    QComboBox:hover {{
        border-color: {C.TEXT3};
    }}
    QComboBox:focus {{
        border-color: {C.BLUE};
        border-width: 2px;
    }}
    QComboBox::drop-down {{
        border: none;
        width: 28px;
    }}
    QComboBox::down-arrow {{
        image: none;
        width: 10px;
        height: 6px;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 6px solid {C.TEXT2};
    }}
    QComboBox QAbstractItemView {{
        background: {C.SURFACE};
        border: 1px solid {C.BORDER};
        border-radius: 8px;
        selection-background-color: {C.BLUE_DIM};
        selection-color: {C.TEXT};
        color: {C.TEXT};
        padding: 4px;
        outline: none;
    }}
    QComboBox QAbstractItemView::item {{
        padding: 8px 12px;
        border-radius: 6px;
        min-height: 30px;
    }}

    /* ── QTimeEdit / QDateEdit / QSpinBox ── */
    QTimeEdit, QDateEdit, QSpinBox, QDoubleSpinBox {{
        background: {C.SURFACE};
        border: 1px solid {C.BORDER};
        border-radius: 8px;
        padding: 7px 12px;
        color: {C.TEXT};
        min-height: 34px;
    }}
    QTimeEdit:focus, QDateEdit:focus, QSpinBox:focus {{
        border-color: {C.BLUE};
        border-width: 2px;
    }}
    QTimeEdit::up-button, QDateEdit::up-button, QSpinBox::up-button,
    QTimeEdit::down-button, QDateEdit::down-button, QSpinBox::down-button {{
        background: {C.SURFACE2};
        border: none;
        width: 20px;
        border-radius: 4px;
    }}
    QTimeEdit::up-button:hover, QDateEdit::up-button:hover, QSpinBox::up-button:hover,
    QTimeEdit::down-button:hover, QDateEdit::down-button:hover, QSpinBox::down-button:hover {{
        background: {C.BORDER};
    }}

    /* ── QGroupBox ── */
    QGroupBox {{
        border: 1px solid {C.BORDER};
        border-radius: 12px;
        margin-top: 20px;
        padding: 16px 12px 12px 12px;
        font-weight: 600;
        color: {C.TEXT2};
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 12px;
        padding: 0 6px;
        background: {C.BG};
    }}

    /* ── QTableWidget ── */
    QTableWidget {{
        background: {C.SURFACE};
        border: 1px solid {C.BORDER};
        border-radius: 10px;
        gridline-color: {C.BORDER};
        outline: none;
        alternate-background-color: {C.SURFACE2};
    }}
    QTableWidget::item {{
        padding: 10px 12px;
        border: none;
    }}
    QTableWidget::item:selected {{
        background: {C.BLUE_DIM};
        color: {C.TEXT};
    }}
    QTableWidget::item:hover {{
        background: {C.SURFACE3};
    }}
    QHeaderView::section {{
        background: {C.SURFACE2};
        color: {C.TEXT2};
        padding: 10px 12px;
        border: none;
        border-bottom: 1px solid {C.BORDER};
        font-weight: 600;
        font-size: 11px;
        letter-spacing: 0.4px;
    }}
    QHeaderView::section:hover {{
        background: {C.SURFACE3};
    }}

    /* ── QProgressBar ── */
    QProgressBar {{
        background: {C.SURFACE2};
        border: none;
        border-radius: 5px;
        height: 6px;
        text-align: center;
    }}
    QProgressBar::chunk {{
        background: {C.BLUE};
        border-radius: 5px;
    }}

    /* ── QLabel ── */
    QLabel {{
        color: {C.TEXT};
        background: transparent;
    }}

    /* ── QCheckBox ── */
    QCheckBox {{
        color: {C.TEXT};
        spacing: 8px;
    }}
    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border-radius: 5px;
        border: 1.5px solid {C.BORDER2};
        background: {C.SURFACE};
    }}
    QCheckBox::indicator:checked {{
        background: {C.BLUE};
        border-color: {C.BLUE};
    }}
    QCheckBox::indicator:hover {{
        border-color: {C.BLUE};
    }}

    /* ── QTabWidget ── */
    QTabWidget::pane {{
        border: 1px solid {C.BORDER};
        border-radius: 10px;
        background: {C.SURFACE};
        top: -1px;
    }}
    QTabBar::tab {{
        background: transparent;
        color: {C.TEXT2};
        padding: 8px 20px;
        border: none;
        border-radius: 8px;
        margin: 2px;
        font-weight: 500;
    }}
    QTabBar::tab:selected {{
        background: {C.SURFACE};
        color: {C.BLUE};
        font-weight: 600;
    }}
    QTabBar::tab:hover:!selected {{
        background: {C.SURFACE3};
        color: {C.TEXT};
    }}

    /* ── QMessageBox ── */
    QMessageBox {{
        background: {C.SURFACE};
    }}
    QMessageBox QLabel {{
        color: {C.TEXT};
    }}
    """


# ═══════════════════════════════════════════════
#  BUTTON STYLES
# ═══════════════════════════════════════════════

def btn_primary(danger: bool = False, small: bool = False) -> str:
    bg      = C.RED  if danger else C.BLUE
    bg_h    = "#CC2F26" if danger else C.NAVY_600
    pad     = "7px 16px" if small else "10px 22px"
    radius  = "8px"      if small else "10px"
    font    = "12px"     if small else "13px"
    return f"""
    QPushButton {{
        background: {bg};
        color: white;
        border: none;
        border-radius: {radius};
        padding: {pad};
        font-size: {font};
        font-weight: 600;
    }}
    QPushButton:hover {{ background: {bg_h}; }}
    QPushButton:pressed {{ background: {C.NAVY_800}; }}
    QPushButton:disabled {{ background: {C.BORDER}; color: {C.TEXT3}; }}
    """

def btn_secondary(small: bool = False) -> str:
    pad    = "7px 16px" if small else "10px 22px"
    radius = "8px"      if small else "10px"
    font   = "12px"     if small else "13px"
    return f"""
    QPushButton {{
        background: {C.SURFACE};
        color: {C.TEXT};
        border: 1px solid {C.BORDER};
        border-radius: {radius};
        padding: {pad};
        font-size: {font};
        font-weight: 500;
    }}
    QPushButton:hover {{ background: {C.SURFACE2}; border-color: {C.BORDER2}; }}
    QPushButton:pressed {{ background: {C.SURFACE3}; }}
    QPushButton:disabled {{ color: {C.TEXT3}; border-color: {C.BORDER}; background: {C.SURFACE2}; }}
    """

def btn_ghost(small: bool = False) -> str:
    pad    = "6px 14px" if small else "9px 18px"
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
    QPushButton:hover {{ background: {C.BLUE_DIM}; }}
    QPushButton:pressed {{ background: {C.SURFACE3}; }}
    """

def btn_gold(small: bool = False) -> str:
    pad = "7px 16px" if small else "10px 22px"
    return f"""
    QPushButton {{
        background: {C.GOLD_500};
        color: white;
        border: none;
        border-radius: 10px;
        padding: {pad};
        font-size: 13px;
        font-weight: 700;
    }}
    QPushButton:hover {{ background: {C.GOLD_400}; }}
    QPushButton:pressed {{ background: #A87800; }}
    QPushButton:disabled {{ background: {C.BORDER}; color: {C.TEXT3}; }}
    """


# ═══════════════════════════════════════════════
#  SOUND ENGINE
# ═══════════════════════════════════════════════

class SoundEngine:
    """Platform-native sounds — no extra dependencies."""

    @staticmethod
    def click():
        """Short click — confirms a UI interaction."""
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
        """Deeper 'lock' click — confirms data was saved."""
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
                    ['afplay', '/System/Library/Sounds/Basso.aiff'],
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
                    ['afplay', '/System/Library/Sounds/Glass.aiff'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            elif sys.platform == 'win32':
                import winsound
                winsound.MessageBeep(0)
        except Exception:
            pass

    @staticmethod
    def scan_error():
        SoundEngine.error()


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
    """Slide widget in from right — used for screen transitions."""
    start_x = widget.parent().width() if widget.parent() else 400
    anim = QPropertyAnimation(widget, b"pos", widget)
    anim.setDuration(duration)
    anim.setStartValue(widget.pos().__class__(start_x, widget.y()))
    anim.setEndValue(widget.pos())
    anim.setEasingCurve(QEasingCurve.Type.OutExpo)
    return anim


# ═══════════════════════════════════════════════
#  SAVED INDICATOR  (inline, non-blocking)
# ═══════════════════════════════════════════════

from PyQt6.QtWidgets import QLabel, QHBoxLayout

class SavedIndicator(QLabel):
    """
    A small '✓ Guardado' label that fades in, holds 1.2s, fades out.
    Drop it below any save button. Call .show_saved() to trigger.
    """

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
        if text != "✓  Guardado":
            self.setText(text)
        else:
            self.setText("✓  Guardado")
        self.setStyleSheet(f"""
            QLabel {{
                color: {C.GREEN};
                font-size: 12px; font-weight: 600;
                padding: 4px 0; background: transparent;
            }}
        """)
        self.show()
        self._out_anim.stop()
        self._hold_timer.stop()
        self._in_anim.start()
        self._hold_timer.start(hold_ms)

    def show_error(self, text: str = "✗  Error al guardar"):
        self.setText(text)
        self.setStyleSheet(f"""
            QLabel {{
                color: {C.RED};
                font-size: 12px;
                font-weight: 600;
                padding: 4px 0;
                background: transparent;
            }}
        """)
        self.show_saved(hold_ms=2000)
        # Reset text after
        QTimer.singleShot(2500, lambda: self.setText("✓  Guardado"))
        QTimer.singleShot(2500, lambda: self.setStyleSheet(f"""
            QLabel {{
                color: {C.GREEN};
                font-size: 12px;
                font-weight: 600;
                padding: 4px 0;
                background: transparent;
            }}
        """))


# ═══════════════════════════════════════════════
#  CARD WIDGET  (reusable panel with border)
# ═══════════════════════════════════════════════

from PyQt6.QtWidgets import QFrame, QVBoxLayout

class Card(QFrame):
    """Rounded surface panel — use as container for form sections."""

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
#  APPLY PALETTE  (called once in main.py)
# ═══════════════════════════════════════════════

def apply_theme(app: QApplication):
    app.setStyle("Fusion")
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window,          QColor(C.BG))
    p.setColor(QPalette.ColorRole.WindowText,      QColor(C.TEXT))
    p.setColor(QPalette.ColorRole.Base,            QColor(C.SURFACE))
    p.setColor(QPalette.ColorRole.AlternateBase,   QColor(C.SURFACE2))
    p.setColor(QPalette.ColorRole.Text,            QColor(C.TEXT))
    p.setColor(QPalette.ColorRole.BrightText,      QColor(C.TEXT))
    p.setColor(QPalette.ColorRole.Button,          QColor(C.SURFACE2))
    p.setColor(QPalette.ColorRole.ButtonText,      QColor(C.TEXT))
    p.setColor(QPalette.ColorRole.Highlight,       QColor(C.BLUE))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    p.setColor(QPalette.ColorRole.ToolTipBase,     QColor(C.SURFACE))
    p.setColor(QPalette.ColorRole.ToolTipText,     QColor(C.TEXT))
    p.setColor(QPalette.ColorRole.PlaceholderText, QColor(C.TEXT3))
    p.setColor(QPalette.ColorRole.Mid,             QColor(C.BORDER))
    p.setColor(QPalette.ColorRole.Midlight,        QColor(C.SURFACE3))
    p.setColor(QPalette.ColorRole.Dark,            QColor(C.BORDER2))
    p.setColor(QPalette.ColorRole.Shadow,          QColor(C.BORDER2))
    app.setPalette(p)
    app.setStyleSheet(global_stylesheet())
