"""
login_screen.py — Pantalla de login con PIN para MiAppoderado.

Diseño dark navy profesional:
  · Panel oscuro con gradiente de profundidad
  · Tarjetas de usuario con barra de color por rol
  · Dots PIN usando QFrame styled (no unicode)
  · Numpad limpio con bordes sutiles
"""

from __future__ import annotations

import os
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QPoint
from PyQt6.QtGui import QPixmap

import db
import session
from ui.theme import C, sound


# ── Roles ─────────────────────────────────────────────────────────────────
_ROL_LABEL = {"admin": "Administrador", "pae": "PAE", "inspectoria": "Inspectoría"}
_ROL_COLOR = {"admin": C.GOLD_500, "pae": C.BLUE, "inspectoria": C.GREEN}

# ── Paleta login ───────────────────────────────────────────────────────────
_BG      = "#0F172A"
_PANEL   = "#1E293B"
_BTN     = "#293548"
_BTN_HVR = "#334565"
_BTN_PRS = "#1E293B"
_BORDER  = "#2D3F58"
_TEXT    = "#F1F5FF"
_TEXT2   = "#6B90B0"
_TEXT3   = "#4A6A88"
_ACCENT  = "#4F8EF7"


class LoginScreen(QDialog):
    """
    Diálogo modal de login.
    Llámalo con .exec() antes de mostrar la MainWindow.
    Al aceptar, session.get() ya contiene el usuario autenticado.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MiAppoderado — Iniciar sesión")
        self.setMinimumSize(460, 560)
        self.resize(480, 600)
        self.setModal(True)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.CustomizeWindowHint
        )

        self._selected_user: dict | None = None
        self._pin_digits: list[str] = []
        self._shake_anim = None
        self._dot_frames: list[QFrame] = []

        self._build_ui()
        self._load_users()

    # ── Construcción UI ──────────────────────────────────────────────────────

    def _build_ui(self):
        self.setStyleSheet(f"QDialog {{ background: {_BG}; }}")
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 32, 36, 28)
        root.setSpacing(0)

        # ── Header ───────────────────────────────────────
        hdr = QVBoxLayout()
        hdr.setSpacing(4)
        hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)

        _escudo = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "assets", "escudo.png"
        )
        if os.path.exists(_escudo):
            logo = QLabel()
            pix = QPixmap(_escudo).scaled(
                52, 60,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            logo.setPixmap(pix)
            logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logo.setStyleSheet("background: transparent;")
            hdr.addWidget(logo)
            hdr.addSpacing(8)

        title = QLabel("MiAppoderado")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: {_TEXT}; background: transparent;"
        )
        hdr.addWidget(title)

        sub = QLabel("Liceo Bicentenario · Héroes de la Concepción · Laja")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(
            f"font-size: 10px; color: {_TEXT3}; background: transparent; letter-spacing: 0.3px;"
        )
        hdr.addWidget(sub)
        root.addLayout(hdr)
        root.addSpacing(20)

        # ── Instrucción dinámica ──────────────────────
        self._inst = QLabel("Selecciona tu usuario")
        self._inst.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._inst.setStyleSheet(
            f"font-size: 12px; color: {_TEXT2}; background: transparent;"
        )
        root.addWidget(self._inst)
        root.addSpacing(12)

        # ── Panel usuarios ────────────────────────────
        self._users_panel = QWidget()
        self._users_panel.setStyleSheet("background: transparent;")
        self._users_lay = QVBoxLayout(self._users_panel)
        self._users_lay.setSpacing(8)
        self._users_lay.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._users_panel)

        # ── Panel PIN ─────────────────────────────────
        self._pin_panel = QFrame()
        self._pin_panel.setStyleSheet(f"""
            QFrame {{
                background: {_PANEL};
                border: 1.5px solid {_BORDER};
                border-radius: 18px;
            }}
        """)
        pin_lay = QVBoxLayout(self._pin_panel)
        pin_lay.setSpacing(0)
        pin_lay.setContentsMargins(24, 20, 24, 18)

        # Chip usuario seleccionado
        self._user_chip = QLabel()
        self._user_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._user_chip.setFixedHeight(44)
        self._user_chip.setStyleSheet(f"""
            font-size: 14px; font-weight: 600; color: {_TEXT};
            background: {_BTN};
            border-radius: 10px;
            padding: 0 20px;
            border: 1px solid {_BORDER};
        """)
        pin_lay.addWidget(self._user_chip)
        pin_lay.addSpacing(20)

        # Dots PIN
        dots_row = QHBoxLayout()
        dots_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dots_row.setSpacing(14)
        self._dot_frames = []
        for _ in range(6):
            dot = QFrame()
            dot.setFixedSize(14, 14)
            dot.setStyleSheet(f"QFrame {{ background: {_TEXT3}; border-radius: 7px; border: none; }}")
            dots_row.addWidget(dot)
            self._dot_frames.append(dot)
        pin_lay.addLayout(dots_row)
        pin_lay.addSpacing(6)

        # Error label
        self._err = QLabel("")
        self._err.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._err.setStyleSheet(f"font-size: 11px; color: {C.RED}; background: transparent;")
        self._err.setFixedHeight(18)
        pin_lay.addWidget(self._err)
        pin_lay.addSpacing(14)

        # Numpad
        for row_keys in [["1","2","3"], ["4","5","6"], ["7","8","9"], ["←","0","↩"]]:
            row_w = QHBoxLayout()
            row_w.setSpacing(10)
            for k in row_keys:
                btn = QPushButton(k)
                btn.setFixedSize(86, 58)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                if k in ("←", "↩"):
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background: {_BTN};
                            color: {_TEXT2};
                            border: 1px solid {_BORDER};
                            border-radius: 12px;
                            font-size: 18px;
                            font-weight: 500;
                        }}
                        QPushButton:hover   {{ background: {_BTN_HVR}; color: {_TEXT}; }}
                        QPushButton:pressed {{ background: {_BTN_PRS}; }}
                    """)
                else:
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background: {_BTN};
                            color: {_TEXT};
                            border: 1px solid {_BORDER};
                            border-radius: 12px;
                            font-size: 22px;
                            font-weight: 300;
                        }}
                        QPushButton:hover   {{ background: {_BTN_HVR}; border-color: {_ACCENT}55; }}
                        QPushButton:pressed {{ background: {_BTN_PRS}; }}
                    """)
                btn.clicked.connect(lambda _, key=k: self._key(key))
                row_w.addWidget(btn)
            pin_lay.addLayout(row_w)
            pin_lay.addSpacing(8)

        # Botón volver
        back = QPushButton("‹  Cambiar usuario")
        back.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {_ACCENT};
                border: none;
                font-size: 12px;
                font-weight: 500;
                padding: 4px;
            }}
            QPushButton:hover {{ color: #7AADFF; }}
        """)
        back.setCursor(Qt.CursorShape.PointingHandCursor)
        back.clicked.connect(self._show_users)
        pin_lay.addWidget(back, alignment=Qt.AlignmentFlag.AlignCenter)

        self._pin_panel.hide()
        root.addWidget(self._pin_panel)
        root.addStretch()

    # ── Carga de usuarios ────────────────────────────────────────────────────

    def _load_users(self):
        while self._users_lay.count():
            item = self._users_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        users = db.get_usuarios_activos()
        for u in users:
            color = _ROL_COLOR.get(u["rol"], _TEXT2)
            label = _ROL_LABEL.get(u["rol"], u["rol"])

            btn = QPushButton(f"  {u['nombre']}   ·   {label}")
            btn.setFixedHeight(52)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {_PANEL};
                    color: {_TEXT};
                    border: 1.5px solid {_BORDER};
                    border-left: 4px solid {color};
                    border-radius: 12px;
                    font-size: 14px;
                    font-weight: 500;
                    text-align: left;
                    padding: 0 20px;
                }}
                QPushButton:hover {{
                    background: {_BTN_HVR};
                    border-color: {_BORDER};
                    border-left-color: {color};
                }}
                QPushButton:pressed {{ background: {_BTN_PRS}; }}
            """)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, user=u: self._select(user))
            self._users_lay.addWidget(btn)

    # ── Lógica selección y PIN ───────────────────────────────────────────────

    def _select(self, user: dict):
        self._selected_user = user
        self._pin_digits = []
        self._err.setText("")
        self._update_dots()

        label = _ROL_LABEL.get(user["rol"], user["rol"])
        color = _ROL_COLOR.get(user["rol"], _TEXT2)
        self._user_chip.setText(f"{user['nombre']}   ·   {label}")
        self._user_chip.setStyleSheet(f"""
            font-size: 14px; font-weight: 600; color: {_TEXT};
            background: {_BTN};
            border-radius: 10px;
            padding: 0 20px;
            border: 1px solid {_BORDER};
            border-left: 4px solid {color};
        """)

        self._users_panel.hide()
        self._pin_panel.show()
        self._inst.setText("Ingresa tu PIN de acceso")
        sound.click()

    def _show_users(self):
        self._pin_panel.hide()
        self._users_panel.show()
        self._inst.setText("Selecciona tu usuario")
        self._selected_user = None
        self._pin_digits = []

    def _key(self, k: str):
        if k == "←":
            if self._pin_digits:
                self._pin_digits.pop()
                self._err.setText("")
                self._update_dots()
        elif k == "↩":
            self._submit()
        elif k.isdigit() and len(self._pin_digits) < 6:
            self._pin_digits.append(k)
            self._update_dots()
            self._err.setText("")
            if len(self._pin_digits) == 6:
                QTimer.singleShot(120, self._submit)

    def _update_dots(self):
        for i, dot in enumerate(self._dot_frames):
            if i < len(self._pin_digits):
                dot.setStyleSheet(
                    f"QFrame {{ background: {_ACCENT}; border-radius: 7px; border: none; }}"
                )
            else:
                dot.setStyleSheet(
                    f"QFrame {{ background: {_TEXT3}; border-radius: 7px; border: none; }}"
                )

    def _submit(self):
        if not self._pin_digits or not self._selected_user:
            return
        pin = "".join(self._pin_digits)
        if db.verificar_pin(self._selected_user["id"], pin):
            sound.scan_ok()
            user = db.get_usuario(self._selected_user["id"])
            session.set_user(user)
            self.accept()
        else:
            sound.scan_error(double=False)
            self._err.setText("PIN incorrecto · Intenta de nuevo")
            self._pin_digits = []
            self._update_dots()
            self._shake()

    def _shake(self):
        pos = self._pin_panel.pos()
        anim = QPropertyAnimation(self._pin_panel, b"pos", self)
        anim.setDuration(320)
        anim.setKeyValueAt(0.00, pos)
        anim.setKeyValueAt(0.15, QPoint(pos.x() - 14, pos.y()))
        anim.setKeyValueAt(0.30, QPoint(pos.x() + 14, pos.y()))
        anim.setKeyValueAt(0.45, QPoint(pos.x() - 9,  pos.y()))
        anim.setKeyValueAt(0.60, QPoint(pos.x() + 9,  pos.y()))
        anim.setKeyValueAt(0.75, QPoint(pos.x() - 4,  pos.y()))
        anim.setKeyValueAt(0.90, QPoint(pos.x() + 4,  pos.y()))
        anim.setKeyValueAt(1.00, pos)
        anim.start()
        self._shake_anim = anim

    # ── Teclado físico ───────────────────────────────────────────────────────

    def keyPressEvent(self, event):
        if not self._selected_user or self._pin_panel.isHidden():
            super().keyPressEvent(event)
            return
        k = event.text()
        if k.isdigit():
            self._key(k)
        elif event.key() == Qt.Key.Key_Backspace:
            self._key("←")
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._key("↩")
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        event.ignore()
