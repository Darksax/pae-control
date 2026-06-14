"""
startup_screen.py — Diálogo "Novedades / Qué hay de nuevo" de PAE Control.

Se muestra automáticamente al iniciar si la versión instalada es nueva.
También abre desde el botón ? en la toolbar.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QWidget, QFrame,
)
from PyQt6.QtCore import Qt, QTimer

from ui.theme   import C
from ui.widgets import AButton, HDivider
import patchnotes as pn


class StartupDialog(QDialog):
    """
    Diálogo de bienvenida / novedades.
    Muestra versión, autor, institución y lista de cambios por release.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Novedades · PAE Control {pn.VERSION}")
        self.setMinimumWidth(660)
        self.setMaximumWidth(800)
        self.setMinimumHeight(480)
        self.setStyleSheet(f"QDialog {{ background: {C.SURFACE}; color: {C.TEXT}; }}")
        self._build()

    # ── UI ──────────────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._make_header())
        root.addWidget(self._make_scroll(), stretch=1)
        root.addWidget(self._make_footer())

    def _make_header(self) -> QFrame:
        header = QFrame()
        header.setStyleSheet(
            f"background: {C.NAVY_900}; border: none;"
        )
        lay = QVBoxLayout(header)
        lay.setContentsMargins(36, 28, 36, 24)
        lay.setSpacing(0)

        # Badge "NOVEDADES"
        badge_row = QHBoxLayout()
        badge = QLabel("NOVEDADES")
        badge.setStyleSheet(f"""
            background: {C.BLUE};
            color: white;
            font-size: 9px; font-weight: 800;
            letter-spacing: 1.2px;
            border-radius: 5px;
            padding: 3px 9px;
        """)
        badge_row.addWidget(badge)
        badge_row.addStretch()
        lay.addLayout(badge_row)
        lay.addSpacing(14)

        # Nombre app + versión
        name = QLabel("PAE Control")
        name.setStyleSheet(
            f"font-size: 30px; font-weight: 800; color: {C.TEXT}; background: transparent;"
        )
        lay.addWidget(name)

        ver_row = QHBoxLayout()
        ver_lbl = QLabel(f"Versión {pn.VERSION}")
        ver_lbl.setStyleSheet(
            f"font-size: 14px; font-weight: 600; color: {C.BLUE}; background: transparent;"
        )
        date_lbl = QLabel(f" · {pn.BUILD_DATE}")
        date_lbl.setStyleSheet(
            f"font-size: 13px; color: {C.TEXT3}; background: transparent;"
        )
        ver_row.addWidget(ver_lbl)
        ver_row.addWidget(date_lbl)
        ver_row.addStretch()
        lay.addLayout(ver_row)
        lay.addSpacing(14)

        # Autor + institución
        meta_row = QHBoxLayout()
        meta_row.setSpacing(0)

        author_lbl = QLabel(f"{pn.AUTHOR}  ·  {pn.AUTHOR_TITLE}")
        author_lbl.setStyleSheet(
            f"font-size: 11px; color: {C.TEXT3}; background: transparent;"
        )
        meta_row.addWidget(author_lbl)
        meta_row.addStretch()

        inst_lbl = QLabel(f"{pn.INSTITUTION}  ·  {pn.CITY}")
        inst_lbl.setStyleSheet(
            f"font-size: 11px; color: {C.TEXT3}; background: transparent;"
        )
        inst_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        meta_row.addWidget(inst_lbl)

        lay.addLayout(meta_row)
        return header

    def _make_scroll(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"background: {C.SURFACE}; border: none;")

        notes_w = QWidget()
        notes_w.setStyleSheet(f"background: {C.SURFACE};")
        n_lay = QVBoxLayout(notes_w)
        n_lay.setContentsMargins(36, 24, 36, 16)
        n_lay.setSpacing(0)

        for i, release in enumerate(pn.PATCHNOTES):
            if i > 0:
                n_lay.addSpacing(12)
                n_lay.addWidget(HDivider())
                n_lay.addSpacing(12)

            # Header de versión
            ver_row = QHBoxLayout()
            ver_chip = QLabel(f"v{release['version']}")
            ver_chip.setStyleSheet(f"""
                background: {C.BLUE_DIM};
                color: {C.BLUE};
                font-size: 10px; font-weight: 700;
                border-radius: 5px;
                padding: 2px 8px;
            """)
            title_lbl = QLabel(release["title"])
            title_lbl.setStyleSheet(
                f"font-size: 13px; font-weight: 700; color: {C.TEXT}; "
                f"background: transparent; padding-left: 8px;"
            )
            date_lbl = QLabel(release["date"])
            date_lbl.setStyleSheet(
                f"font-size: 11px; color: {C.TEXT3}; background: transparent;"
            )
            ver_row.addWidget(ver_chip)
            ver_row.addWidget(title_lbl)
            ver_row.addStretch()
            ver_row.addWidget(date_lbl)
            n_lay.addLayout(ver_row)
            n_lay.addSpacing(10)

            # Lista de cambios
            for note in release["notes"]:
                note_row = QHBoxLayout()
                note_row.setContentsMargins(2, 0, 0, 0)
                note_row.setSpacing(8)

                bullet = QLabel("·")
                bullet.setFixedWidth(14)
                bullet.setAlignment(
                    Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
                )
                bullet.setStyleSheet(
                    f"color: {C.BLUE}; font-size: 16px; font-weight: 700; "
                    f"background: transparent; padding-top: 1px;"
                )

                note_lbl = QLabel(note)
                note_lbl.setWordWrap(True)
                note_lbl.setStyleSheet(
                    f"color: {C.TEXT2}; font-size: 12px; background: transparent; "
                    f"line-height: 140%;"
                )

                note_row.addWidget(bullet)
                note_row.addWidget(note_lbl, stretch=1)
                n_lay.addLayout(note_row)
                n_lay.addSpacing(4)

        n_lay.addStretch()
        scroll.setWidget(notes_w)
        return scroll

    def _make_footer(self) -> QFrame:
        footer = QFrame()
        footer.setFixedHeight(56)
        footer.setStyleSheet(
            f"background: {C.SURFACE}; border-top: 1px solid {C.BORDER}; border-radius: 0;"
        )
        lay = QHBoxLayout(footer)
        lay.setContentsMargins(28, 0, 28, 0)
        lay.setSpacing(12)

        # Etiqueta de estado de update (la rellena main_window después)
        self._update_lbl = QLabel("")
        self._update_lbl.setStyleSheet(
            f"font-size: 11px; color: {C.TEXT3}; background: transparent;"
        )
        lay.addWidget(self._update_lbl)
        lay.addStretch()

        ok_btn = AButton("Entendido", sound_type="success")
        ok_btn.setFixedSize(130, 36)
        ok_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.BLUE};
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover  {{ background: {C.NAVY_600}; }}
            QPushButton:pressed {{ background: {C.NAVY_800}; }}
        """)
        ok_btn.clicked.connect(self.accept)
        lay.addWidget(ok_btn)
        return footer

    # ── API pública ─────────────────────────────────────────────────────────

    def set_update_message(self, msg: str, color: str = ""):
        """Actualizar etiqueta de estado desde main_window."""
        self._update_lbl.setText(msg)
        c = color or C.TEXT3
        self._update_lbl.setStyleSheet(
            f"font-size: 11px; color: {c}; background: transparent;"
        )
