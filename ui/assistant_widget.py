"""
assistant_widget.py — Overlay flotante del asistente IA (Gemini).

Burbuja persistente (esquina inferior derecha) que se mantiene sobre
cualquier pantalla activa; click abre/cierra un panel de chat. La burbuja
tiene su propio botón para cerrarla (oculta el overlay por el resto de la
sesión — no borra el historial ni afecta la configuración).
"""

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

import assistant
from ui.theme import C

ASSISTANT_NAME = "Liceín"


class _AskThread(QThread):
    """Corre la llamada HTTP a Gemini fuera del hilo de UI."""
    done = pyqtSignal(bool, str)

    def __init__(self, pregunta: str, historial: list):
        super().__init__()
        self._pregunta = pregunta
        self._historial = historial

    def run(self):
        ok, resp = assistant.ask(self._pregunta, self._historial)
        self.done.emit(ok, resp)


class _ChatBubbleMsg(QFrame):
    """Un mensaje individual en el historial (alineado según quién lo escribió)."""

    def __init__(self, texto: str, es_usuario: bool, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)

        bubble = QLabel(texto)
        bubble.setWordWrap(True)
        bubble.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        bg = C.BLUE_DIM if es_usuario else C.SURFACE2
        bubble.setStyleSheet(f"""
            background: {bg}; color: {C.TEXT};
            border-radius: 10px; padding: 8px 12px; font-size: 12.5px;
        """)
        bubble.setMaximumWidth(250)
        bubble.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)

        if es_usuario:
            lay.addStretch(1)
            lay.addWidget(bubble)
        else:
            lay.addWidget(bubble)
            lay.addStretch(1)


class AssistantOverlay(QWidget):
    """
    Widget hijo del área central de MainWindow — se posiciona a mano
    (no participa de ningún layout) para flotar sobre el contenido activo
    sin importar qué pantalla del sidebar esté abierta.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._historial: list[dict] = []
        self._panel_abierto = False
        self._waiting = False
        self._thread: _AskThread | None = None

        self._build_bubble()
        self._build_panel()
        self._panel.hide()

    # ── BURBUJA ──────────────────────────────────────────────────────
    def _build_bubble(self):
        self._bubble = QPushButton("Agente IA", self)
        self._bubble.setFixedSize(128, 44)
        self._bubble.setCursor(Qt.CursorShape.PointingHandCursor)
        self._bubble.setStyleSheet(f"""
            QPushButton {{
                background: {C.BLUE}; color: white;
                border-radius: 22px; font-size: 13px; font-weight: 800;
                border: 2px solid {C.BG};
            }}
            QPushButton:hover {{ background: #6BA3FF; }}
        """)
        self._bubble.setToolTip(f"{ASSISTANT_NAME} — Asistente MiAppoderado")
        self._bubble.clicked.connect(self._toggle_panel)

        self._btn_close = QPushButton("×", self)
        self._btn_close.setFixedSize(20, 20)
        self._btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_close.setToolTip("Ocultar asistente")
        self._btn_close.setStyleSheet(f"""
            QPushButton {{
                background: {C.SURFACE2}; color: {C.TEXT2};
                border-radius: 10px; font-size: 13px; font-weight: 700;
                border: 1.5px solid {C.BORDER2};
            }}
            QPushButton:hover {{ background: {C.RED_DIM}; color: {C.RED}; }}
        """)
        self._btn_close.clicked.connect(self.dismiss)

    def dismiss(self):
        """Oculta la burbuja y el panel por el resto de la sesión."""
        self._panel_abierto = False
        self._panel.hide()
        self.hide()

    def restore(self):
        """Vuelve a mostrar la burbuja (p.ej. desde un menú/atajo futuro)."""
        self.show()
        self.reposition()

    # ── PANEL DE CHAT ────────────────────────────────────────────────
    def _build_panel(self):
        self._panel = QFrame(self)
        self._panel.setFixedSize(340, 440)
        self._panel.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border: 1.5px solid {C.BORDER2};
                border-radius: 16px;
            }}
        """)
        pl = QVBoxLayout(self._panel)
        pl.setContentsMargins(14, 12, 14, 12)
        pl.setSpacing(8)

        header_row = QHBoxLayout()
        title = QLabel(ASSISTANT_NAME)
        title.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {C.TEXT}; background: transparent;"
        )
        header_row.addWidget(title)
        header_row.addStretch(1)

        btn_min = QPushButton("–")
        btn_min.setFixedSize(22, 22)
        btn_min.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_min.setToolTip("Minimizar")
        btn_min.setStyleSheet(f"""
            QPushButton {{
                background: {C.SURFACE2}; color: {C.TEXT2};
                border-radius: 6px; font-size: 14px; font-weight: 700; border: none;
            }}
            QPushButton:hover {{ background: {C.SURFACE3}; }}
        """)
        btn_min.clicked.connect(self._toggle_panel)
        header_row.addWidget(btn_min)
        pl.addLayout(header_row)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {C.BORDER}; border: none;")
        pl.addWidget(sep)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet("background: transparent; border: none;")
        self._msgs_container = QWidget()
        self._msgs_container.setStyleSheet("background: transparent;")
        self._msgs_lay = QVBoxLayout(self._msgs_container)
        self._msgs_lay.setContentsMargins(2, 2, 2, 2)
        self._msgs_lay.setSpacing(4)
        self._msgs_lay.addStretch(1)
        self._scroll.setWidget(self._msgs_container)
        pl.addWidget(self._scroll, stretch=1)

        self._lbl_status = QLabel("")
        self._lbl_status.setStyleSheet(
            f"font-size: 11px; color: {C.TEXT3}; background: transparent;"
        )
        self._lbl_status.setWordWrap(True)
        pl.addWidget(self._lbl_status)

        input_row = QHBoxLayout()
        self._input = QLineEdit()
        self._input.setPlaceholderText("Escribe tu pregunta…")
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: {C.SURFACE2}; color: {C.TEXT};
                border: 1.5px solid {C.BORDER2}; border-radius: 8px;
                padding: 7px 10px; font-size: 12.5px;
            }}
            QLineEdit:focus {{ border: 1.5px solid {C.BLUE}; }}
        """)
        self._input.returnPressed.connect(self._send)
        input_row.addWidget(self._input, stretch=1)

        btn_send = QPushButton("➤")
        btn_send.setFixedSize(34, 34)
        btn_send.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_send.setStyleSheet(f"""
            QPushButton {{
                background: {C.BLUE}; color: white;
                border-radius: 8px; font-size: 14px; border: none;
            }}
            QPushButton:hover {{ background: #6BA3FF; }}
        """)
        btn_send.clicked.connect(self._send)
        input_row.addWidget(btn_send)
        pl.addLayout(input_row)

        saludo = (
            f"¡Hola! Soy {ASSISTANT_NAME}. Puedes preguntarme cómo usar "
            f"MiAppoderado o dudas del reglamento del liceo."
            if assistant.is_configured() else
            f"Hola, soy {ASSISTANT_NAME} — pero todavía no me configuraron "
            f"con una clave de Gemini. Pide al administrador que la agregue "
            f"en Configuración → Asistente IA."
        )
        self._add_msg(saludo, es_usuario=False)

    def _add_msg(self, texto: str, es_usuario: bool):
        msg = _ChatBubbleMsg(texto, es_usuario, self._msgs_container)
        self._msgs_lay.insertWidget(self._msgs_lay.count() - 1, msg)
        QTimer.singleShot(30, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        bar = self._scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _send(self):
        pregunta = self._input.text().strip()
        if not pregunta or self._waiting:
            return
        self._input.clear()
        self._add_msg(pregunta, es_usuario=True)
        self._waiting = True
        self._lbl_status.setText("Pensando…")

        self._thread = _AskThread(pregunta, list(self._historial))
        self._historial.append({"role": "user", "text": pregunta})
        self._thread.done.connect(self._on_response)
        self._thread.start()

    def _on_response(self, ok: bool, texto: str):
        self._waiting = False
        self._lbl_status.setText("")
        self._add_msg(texto, es_usuario=False)
        if ok:
            self._historial.append({"role": "model", "text": texto})
        else:
            # No dejar la pregunta fallida en el historial que se envía a Gemini
            if self._historial and self._historial[-1]["role"] == "user":
                self._historial.pop()

    # ── Toggle / posicionamiento ─────────────────────────────────────
    def _toggle_panel(self):
        self._panel_abierto = not self._panel_abierto
        self._panel.setVisible(self._panel_abierto)
        self.reposition()
        if self._panel_abierto:
            self._input.setFocus()

    def reposition(self):
        """
        Recalcula posición relativa al padre — esquina inferior derecha.

        A propósito el contenedor NO cubre toda la ventana: se dimensiona
        justo al tamaño del cluster visible (burbuja sola, o burbuja+panel),
        para no dejar ninguna región transparente-pero-clickeable tapando
        el resto de la app. Evita depender de WA_TransparentForMouseEvents,
        cuyo comportamiento con widgets hijos es inconsistente entre
        versiones de Qt/macOS y puede terminar bloqueando los clicks a la
        propia burbuja.
        """
        parent = self.parentWidget()
        if not parent:
            return

        bw, bh = self._bubble.width(), self._bubble.height()
        pad = 16  # aire extra para que el botón de cerrar (sobresale de la burbuja) no quede cortado
        gap = 12  # separación vertical entre el panel y la burbuja

        if self._panel_abierto:
            total_w = max(bw, self._panel.width()) + pad
            total_h = bh + gap + self._panel.height() + pad
        else:
            total_w = bw + pad
            total_h = bh + pad

        margin = 20
        x = max(0, parent.width()  - total_w - margin)
        y = max(0, parent.height() - total_h - margin)
        self.setGeometry(x, y, total_w, total_h)
        self.raise_()

        # Coordenadas locales — relativas a este widget, que ahora empieza en (x, y)
        bx = total_w - bw - pad // 2
        by = total_h - bh - pad // 2
        self._bubble.move(bx, by)
        self._btn_close.move(bx + bw - 10, by - 6)
        self._bubble.raise_()
        self._btn_close.raise_()

        if self._panel_abierto:
            self._panel.move(total_w - self._panel.width() - pad // 2, pad // 2)
            self._panel.raise_()
