"""
junaeb_screen.py — Módulo JUNAEB / Menú semanal MiAppoderado 0.9 Alpha

Navegador embebido para consultar el sitio JUNAEB:
  - Acceso rápido a páginas clave (PAE, minutas, región Biobío)
  - Barra de navegación con historial + URL editable
  - Se abre en navegador del sistema si PyQt6-WebEngine no está instalado

Dependencia opcional: PyQt6-WebEngine
  pip install PyQt6-WebEngine
"""

import webbrowser
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QLineEdit, QSizePolicy, QScrollArea
)
from PyQt6.QtCore import Qt, QUrl, QTimer
from PyQt6.QtGui import QFont

from ui.theme   import C, sound
from ui.widgets import AButton, HDivider, SectionHeader

# ── Intento cargar WebEngine ─────────────────────────
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore    import QWebEnginePage
    _WEBENGINE_OK = True
except ImportError:
    _WEBENGINE_OK = False


# ── Bookmarks rápidos ─────────────────────────────────
BOOKMARKS = [
    ("Minutas PAE",   "https://minutaspublicas.junaeb.cl/minutaspub/xhtml/minutasPublicas/index.xhtml"),
    ("JUNAEB",        "https://www.junaeb.cl"),
    ("PAE",           "https://www.junaeb.cl/pae"),
    ("Biobío",        "https://www.junaeb.cl/region-del-bio-bio"),
    ("Documentos",    "https://www.junaeb.cl/documentos"),
]

DEFAULT_URL = "https://minutaspublicas.junaeb.cl/minutaspub/xhtml/minutasPublicas/index.xhtml"


# ══════════════════════════════════════════════════════
#  FALLBACK — sin WebEngine
# ══════════════════════════════════════════════════════

class _FallbackWidget(QFrame):
    """
    Se muestra cuando PyQt6-WebEngine no está instalado.
    Ofrece botones para abrir URLs en el navegador del sistema.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border: none;
                border-radius: 16px;
            }}
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 40, 40, 40)
        root.setSpacing(20)
        root.setAlignment(Qt.AlignmentFlag.AlignTop)

        icon = QLabel("⚠")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(
            f"font-size: 40px; color: {C.AMBER}; background: transparent;"
        )
        root.addWidget(icon)

        title = QLabel("PyQt6-WebEngine no instalado")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"font-size: 18px; font-weight: 700; color: {C.TEXT}; background: transparent;"
        )
        root.addWidget(title)

        msg = QLabel(
            "Para activar el navegador embebido, instala el módulo faltante:\n\n"
            "pip install PyQt6-WebEngine\n\n"
            "Mientras tanto, los enlaces se abren en tu navegador del sistema."
        )
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg.setWordWrap(True)
        msg.setStyleSheet(
            f"font-size: 13px; color: {C.TEXT2}; background: transparent;"
            f"line-height: 1.6;"
        )
        root.addWidget(msg)

        root.addWidget(HDivider())
        root.addWidget(SectionHeader("Abrir en navegador del sistema"))

        for label, url in BOOKMARKS:
            btn = AButton(f"⇗  {label}", sound_type="click")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {C.SURFACE2};
                    color: {C.TEXT};
                    border: 1.5px solid {C.BORDER};
                    border-radius: 10px;
                    padding: 10px 20px;
                    font-size: 13px; font-weight: 600;
                    text-align: left;
                }}
                QPushButton:hover {{ background: {C.NAVY_700}; border-color: {C.NAVY_400}; }}
            """)
            btn.clicked.connect(lambda checked, u=url: webbrowser.open(u))
            root.addWidget(btn)

        root.addStretch()


# ══════════════════════════════════════════════════════
#  NAV BAR
# ══════════════════════════════════════════════════════

class _NavBar(QFrame):
    """Barra de navegación: ← → ↻ | barra de URL | ⇗."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        self.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border: none;
                border-radius: 12px;
            }}
        """)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(4)

        def nav_btn(icon, tip):
            b = AButton(icon, sound_type="click")
            b.setFixedSize(34, 34)
            b.setToolTip(tip)
            b.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {C.TEXT2};
                    border: none; border-radius: 7px;
                    font-size: 15px; font-weight: 600;
                }}
                QPushButton:hover {{ background: {C.SURFACE2}; color: {C.TEXT}; }}
                QPushButton:disabled {{ color: {C.TEXT3}; }}
            """)
            return b

        self.btn_back    = nav_btn("←", "Atrás")
        self.btn_forward = nav_btn("→", "Adelante")
        self.btn_reload  = nav_btn("↻", "Recargar")

        lay.addWidget(self.btn_back)
        lay.addWidget(self.btn_forward)
        lay.addWidget(self.btn_reload)
        lay.addSpacing(6)

        # URL bar
        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("URL…")
        self.url_bar.setStyleSheet(f"""
            QLineEdit {{
                background: {C.SURFACE2};
                border: 1.5px solid {C.BORDER};
                border-radius: 8px;
                padding: 5px 12px;
                font-size: 12px;
                color: {C.TEXT};
            }}
            QLineEdit:focus {{
                border-color: {C.NAVY_400};
            }}
        """)
        lay.addWidget(self.url_bar, stretch=1)

        lay.addSpacing(6)

        self.btn_open_ext = nav_btn("⇗", "Abrir en navegador externo")
        lay.addWidget(self.btn_open_ext)


# ══════════════════════════════════════════════════════
#  JUNAEB SCREEN
# ══════════════════════════════════════════════════════

class JunaebScreen(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_url = DEFAULT_URL
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet(f"background: {C.BG};")
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(10)

        # ── Title row ────────────────────────────────
        title_row = QHBoxLayout()
        title_row.setSpacing(12)

        title = QLabel("Menú JUNAEB")
        title.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: {C.TEXT}; background: transparent;"
        )
        title_row.addWidget(title)
        title_row.addStretch()

        sub = QLabel("Sitio oficial JUNAEB — PAE Región del Biobío")
        sub.setStyleSheet(
            f"font-size: 12px; color: {C.TEXT3}; background: transparent;"
        )
        title_row.addWidget(sub)
        root.addLayout(title_row)

        # ── Bookmark bar ─────────────────────────────
        bm_frame = QFrame()
        bm_frame.setFixedHeight(44)
        bm_frame.setStyleSheet(
            f"background: {C.SURFACE}; border: 1.5px solid {C.BORDER}; border-radius: 10px;"
        )
        bm_lay = QHBoxLayout(bm_frame)
        bm_lay.setContentsMargins(8, 4, 8, 4)
        bm_lay.setSpacing(4)

        icon_lbl = QLabel("⊕")
        icon_lbl.setStyleSheet(
            f"font-size: 13px; color: {C.GOLD_500}; background: transparent; padding: 0 4px;"
        )
        bm_lay.addWidget(icon_lbl)

        for label, url in BOOKMARKS:
            btn = AButton(label, sound_type="click")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {C.TEXT2};
                    border: 1px solid {C.BORDER};
                    border-radius: 7px;
                    padding: 4px 12px;
                    font-size: 12px; font-weight: 600;
                }}
                QPushButton:hover {{
                    background: {C.NAVY_700}; color: {C.TEXT};
                    border-color: {C.NAVY_400};
                }}
            """)
            btn.clicked.connect(lambda checked, u=url: self._navigate_to(u))
            bm_lay.addWidget(btn)

        bm_lay.addStretch()
        root.addWidget(bm_frame)

        # ── Nav bar ───────────────────────────────────
        if _WEBENGINE_OK:
            self._nav = _NavBar()
            self._nav.btn_back.clicked.connect(self._go_back)
            self._nav.btn_forward.clicked.connect(self._go_forward)
            self._nav.btn_reload.clicked.connect(self._reload)
            self._nav.url_bar.returnPressed.connect(self._on_url_entered)
            self._nav.btn_open_ext.clicked.connect(
                lambda: webbrowser.open(self._current_url)
            )
            root.addWidget(self._nav)

        # ── Content area ─────────────────────────────
        if _WEBENGINE_OK:
            self._web = QWebEngineView()
            self._web.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            self._web.urlChanged.connect(self._on_url_changed)
            self._web.loadFinished.connect(self._on_load_finished)
            self._web.page().loadStarted.connect(self._on_load_started)
            self._web.setStyleSheet("border: none;")

            # Wrap in card
            web_frame = QFrame()
            web_frame.setStyleSheet(f"""
                QFrame {{
                    background: {C.SURFACE};
                    border: none;
                    border-radius: 12px;
                }}
            """)
            wf_lay = QVBoxLayout(web_frame)
            wf_lay.setContentsMargins(0, 0, 0, 0)
            wf_lay.addWidget(self._web)
            root.addWidget(web_frame, stretch=1)

            # Loading indicator
            self._lbl_loading = QLabel("")
            self._lbl_loading.setAlignment(Qt.AlignmentFlag.AlignRight)
            self._lbl_loading.setStyleSheet(
                f"font-size: 11px; color: {C.TEXT3}; background: transparent;"
            )
            root.addWidget(self._lbl_loading)

            # Initial load
            self._web.load(QUrl(DEFAULT_URL))

        else:
            self._fallback = _FallbackWidget()
            root.addWidget(self._fallback, stretch=1)

    # ─────────────────────────────────────────────
    #  NAVIGATION (solo si WebEngine disponible)
    # ─────────────────────────────────────────────

    def _navigate_to(self, url: str):
        if _WEBENGINE_OK:
            self._web.load(QUrl(url))
        else:
            webbrowser.open(url)
            sound.click()

    def _go_back(self):
        if _WEBENGINE_OK and self._web.history().canGoBack():
            self._web.back()

    def _go_forward(self):
        if _WEBENGINE_OK and self._web.history().canGoForward():
            self._web.forward()

    def _reload(self):
        if _WEBENGINE_OK:
            self._web.reload()

    def _on_url_entered(self):
        raw = self._nav.url_bar.text().strip()
        if not raw:
            return
        if not raw.startswith(("http://", "https://")):
            raw = "https://" + raw
        self._web.load(QUrl(raw))

    def _on_url_changed(self, url: QUrl):
        self._current_url = url.toString()
        self._nav.url_bar.setText(self._current_url)
        self._nav.btn_back.setEnabled(self._web.history().canGoBack())
        self._nav.btn_forward.setEnabled(self._web.history().canGoForward())

    def _on_load_started(self):
        self._lbl_loading.setText("Cargando…")

    def _on_load_finished(self, ok: bool):
        if ok:
            self._lbl_loading.setText("")
        else:
            self._lbl_loading.setText("✗  No se pudo cargar la página")
