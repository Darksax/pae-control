"""
config_screen.py — Configuración MiAppoderado 0.9 Alpha

- QTimeEdit para horarios (sin texto libre, formato siempre válido)
- QComboBox para valores categóricos
- Auto-save con debounce 1.2s + SavedIndicator inline
- Sound en save (pop/lock)
- Sin modales: confirmación inline debajo del botón
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QSpinBox, QFrame, QCheckBox, QFormLayout,
    QScrollArea, QSizePolicy, QTimeEdit, QComboBox,
    QListWidget, QListWidgetItem,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QPushButton, QMessageBox,
)
from PyQt6.QtCore import Qt, QTimer, QTime
from PyQt6.QtGui import QFont

import assistant
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
                border: none;
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
                border: none;
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

        # ── Scan screen settings card ─────────────────
        scan_card = QFrame()
        scan_card.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border: none;
                border-radius: 16px;
            }}
        """)
        scan_lay = QVBoxLayout(scan_card)
        scan_lay.setContentsMargins(20, 18, 20, 18)
        scan_lay.setSpacing(14)

        scan_lay.addWidget(SectionHeader("Pantalla de escaneo"))

        # ── Delays ────────────────────────────────────
        delay_hint = QLabel(
            "Ajusta los tiempos según la velocidad de tu lector de barras y el ritmo del comedor."
        )
        delay_hint.setStyleSheet(
            f"font-size: 11px; color: {C.TEXT3}; background: transparent;"
        )
        scan_lay.addWidget(delay_hint)

        row_delays = QHBoxLayout()
        row_delays.setSpacing(24)

        self._spin_submit_delay = self._make_spinbox(
            50, 2000, "Delay auto-submit scanner (ms)",
            suffix=" ms", tooltip="Tiempo de espera tras el último carácter del scanner antes de enviar. 150-200ms es lo habitual."
        )
        self._spin_autoreset_default = self._make_spinbox(
            0, 60, "Auto-reset pantalla por defecto (s)",
            suffix=" s", tooltip="0 = sin auto-reset. La pantalla mantiene el último resultado hasta el próximo escaneo."
        )
        for widget in self._spin_submit_delay + self._spin_autoreset_default:
            row_delays.addWidget(widget)
        row_delays.addStretch()
        scan_lay.addLayout(row_delays)

        scan_lay.addWidget(HDivider())

        # ── Toggles ────────────────────────────────────
        toggles_hint = QLabel("Activa o desactiva funciones visuales y sonoras de la pantalla de escaneo.")
        toggles_hint.setStyleSheet(
            f"font-size: 11px; color: {C.TEXT3}; background: transparent;"
        )
        scan_lay.addWidget(toggles_hint)

        chk_style = f"color: {C.TEXT2}; font-size: 13px; background: transparent;"

        self._chk_flash = QCheckBox("Flash de pantalla al escanear  (verde OK / rojo error)")
        self._chk_flash.setStyleSheet(chk_style)
        self._chk_flash.stateChanged.connect(self._on_field_changed)
        scan_lay.addWidget(self._chk_flash)

        self._chk_ausencias = QCheckBox("Mostrar alerta de ausencias previas del estudiante")
        self._chk_ausencias.setStyleSheet(chk_style)
        self._chk_ausencias.stateChanged.connect(self._on_field_changed)
        scan_lay.addWidget(self._chk_ausencias)

        self._chk_doble_sonido = QCheckBox("Doble sonido en error  (Sosumi + Basso — audible desde lejos)")
        self._chk_doble_sonido.setStyleSheet(chk_style)
        self._chk_doble_sonido.stateChanged.connect(self._on_field_changed)
        scan_lay.addWidget(self._chk_doble_sonido)

        self._chk_historial = QCheckBox("Mostrar panel de historial reciente")
        self._chk_historial.setStyleSheet(chk_style)
        self._chk_historial.stateChanged.connect(self._on_field_changed)
        scan_lay.addWidget(self._chk_historial)

        root.addWidget(scan_card)

        # ── Clima card ─────────────────────
        wx_card = QFrame()
        wx_card.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border: none;
                border-radius: 16px;
            }}
        """)
        wx_lay = QVBoxLayout(wx_card)
        wx_lay.setContentsMargins(20, 18, 20, 18)
        wx_lay.setSpacing(14)

        wx_lay.addWidget(SectionHeader("Clima (toolbar)"))

        chk_style2 = (
            f"QCheckBox {{ color: {C.TEXT2}; font-size: 13px; "
            f"background: transparent; spacing: 8px; }}"
        )

        # ── Clima ────────────────────────────────────
        self._chk_weather = QCheckBox("Mostrar clima en la barra superior")
        self._chk_weather.setStyleSheet(chk_style2)
        self._chk_weather.setToolTip("Temp actual + mañana/tarde + mín — Open-Meteo (sin API key)")
        self._chk_weather.stateChanged.connect(self._on_field_changed)
        wx_lay.addWidget(self._chk_weather)

        # Ciudad con geocoding autocomplete
        lbl_city = QLabel("Ciudad:")
        lbl_city.setStyleSheet(f"color: {C.TEXT2}; font-size: 13px; background: transparent;")
        wx_lay.addWidget(lbl_city)

        city_row = QHBoxLayout()
        self._inp_weather_city = QLineEdit()
        self._inp_weather_city.setPlaceholderText("Escriba una ciudad — sugerencias automáticas")
        self._inp_weather_city.setStyleSheet(
            f"QLineEdit {{ background: {C.SURFACE2}; border: 1.5px solid {C.BORDER}; "
            f"border-radius: 8px; padding: 6px 10px; color: {C.TEXT}; font-size: 13px; }}"
            f"QLineEdit:focus {{ border-color: {C.BLUE}; }}"
        )
        # Debounce para geocoding: 700ms
        self._geo_debounce = QTimer(self)
        self._geo_debounce.setSingleShot(True)
        self._geo_debounce.setInterval(700)
        self._geo_debounce.timeout.connect(self._search_city_suggestions)
        self._inp_weather_city.textChanged.connect(lambda t: (
            self._geo_debounce.start(),
            self._lbl_city_status.setText("Buscando…"),
            self._lbl_city_status.setStyleSheet(
                f"color: {C.TEXT3}; font-size: 11px; background: transparent;")
        ))
        city_row.addWidget(self._inp_weather_city, stretch=1)

        btn_reload_weather = AButton("⟳ Actualizar clima", sound_type="click")
        btn_reload_weather.setFixedHeight(32)
        btn_reload_weather.setStyleSheet(f"""
            QPushButton {{
                background: {C.SURFACE2}; color: {C.TEXT2};
                border: 1.5px solid {C.BORDER}; border-radius: 8px;
                padding: 0 12px; font-size: 12px;
            }}
            QPushButton:hover {{ background: {C.SURFACE3}; color: {C.TEXT}; }}
        """)
        btn_reload_weather.clicked.connect(self._reload_weather_now)
        city_row.addWidget(btn_reload_weather)
        wx_lay.addLayout(city_row)

        # Sugerencias de ciudades (popup)
        self._city_popup = QListWidget()
        self._city_popup.setFixedHeight(0)   # oculto por defecto (altura = 0)
        self._city_popup.setStyleSheet(f"""
            QListWidget {{
                background: {C.SURFACE}; border: 1.5px solid {C.BLUE};
                border-radius: 8px; font-size: 13px; color: {C.TEXT};
            }}
            QListWidget::item {{ padding: 7px 12px; }}
            QListWidget::item:selected {{ background: {C.BLUE_DIM}; color: {C.BLUE}; }}
        """)
        self._city_popup.itemClicked.connect(self._on_city_selected)
        self._city_popup.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        wx_lay.addWidget(self._city_popup)

        # Status: lat/lon confirmado o error
        self._lbl_city_status = QLabel("")
        self._lbl_city_status.setStyleSheet(
            f"color: {C.TEXT3}; font-size: 11px; background: transparent;")
        wx_lay.addWidget(self._lbl_city_status)

        # Resultado de geocoding temporal (para la opción seleccionada)
        self._pending_geo: dict = {}   # {"lat":..., "lon":..., "city":...}

        root.addWidget(wx_card)

        # ── Meal schedule card ────────────────────────
        meal_card = QFrame()
        meal_card.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border: none;
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

        # ── WhatsApp Business (solo admin) ───────────
        import session as _sess
        if _sess.is_admin():
            wa_card = QFrame()
            wa_card.setStyleSheet(f"""
                QFrame {{
                    background: {C.SURFACE};
                    border: none;
                    border-radius: 14px;
                }}
            """)
            wa_lay = QVBoxLayout(wa_card)
            wa_lay.setContentsMargins(20, 16, 20, 16)
            wa_lay.setSpacing(10)
            wa_lay.addWidget(SectionHeader("WhatsApp Business — Notificaciones de atrasos"))

            hint_wa = QLabel(
                "Ingresa las credenciales de la Meta WhatsApp Cloud API. "
                "Requiere cuenta Business verificada y plantilla aprobada."
            )
            hint_wa.setWordWrap(True)
            hint_wa.setStyleSheet(f"font-size: 11px; color: {C.TEXT3}; background: transparent;")
            wa_lay.addWidget(hint_wa)

            def _wa_field(label_txt: str, placeholder: str, echo_mode=None) -> tuple:
                lbl = QLabel(label_txt.upper())
                lbl.setStyleSheet(
                    f"font-size: 10px; font-weight: 700; letter-spacing: 0.6px; "
                    f"color: {C.TEXT2}; background: transparent;"
                )
                inp = QLineEdit()
                inp.setPlaceholderText(placeholder)
                if echo_mode:
                    inp.setEchoMode(echo_mode)
                inp.textChanged.connect(self._on_field_changed)
                return lbl, inp

            lbl_pid, self._wa_phone_id = _wa_field(
                "Phone Number ID", "Ej: 123456789012345"
            )
            lbl_tok, self._wa_token = _wa_field(
                "Access Token", "EAAxxxxxx...", QLineEdit.EchoMode.Password
            )
            lbl_plt, self._wa_plantilla = _wa_field(
                "Nombre plantilla", "notificacion_atraso"
            )
            for lbl, inp in [(lbl_pid, self._wa_phone_id),
                             (lbl_tok, self._wa_token),
                             (lbl_plt, self._wa_plantilla)]:
                wa_lay.addWidget(lbl)
                wa_lay.addWidget(inp)

            # Fila: número de prueba + botón probar
            wa_lay.addWidget(QLabel("").setStyleSheet if False else QLabel(""))
            test_row = QHBoxLayout()
            test_row.setSpacing(8)
            self._wa_test_num = QLineEdit()
            self._wa_test_num.setPlaceholderText("Número de prueba (56912345678)")
            test_row.addWidget(self._wa_test_num, stretch=1)

            btn_wa_test = AButton("Probar conexión", sound_type="click")
            btn_wa_test.setStyleSheet(f"""
                QPushButton {{
                    background: #25D366; color: white;
                    border: none; border-radius: 8px;
                    padding: 8px 16px; font-size: 12px; font-weight: 600;
                }}
                QPushButton:hover {{ background: #1DAF54; }}
                QPushButton:disabled {{ background: {C.BORDER}; color: {C.TEXT3}; }}
            """)
            btn_wa_test.clicked.connect(self._probar_whatsapp)
            test_row.addWidget(btn_wa_test)
            wa_lay.addLayout(test_row)

            self._wa_test_result = QLabel("")
            self._wa_test_result.setWordWrap(True)
            self._wa_test_result.setStyleSheet(
                f"font-size: 12px; background: transparent;"
            )
            wa_lay.addWidget(self._wa_test_result)

            root.addWidget(wa_card)

        # ── Asistente IA (Gemini) — solo admin ────────
        if _sess.is_admin():
            from PyQt6.QtWidgets import QTextEdit as _QTE

            ai_card = QFrame()
            ai_card.setStyleSheet(f"""
                QFrame {{
                    background: {C.SURFACE};
                    border: none;
                    border-radius: 14px;
                }}
            """)
            ai_lay = QVBoxLayout(ai_card)
            ai_lay.setContentsMargins(20, 16, 20, 16)
            ai_lay.setSpacing(10)
            ai_lay.addWidget(SectionHeader("Asistente IA (Gemini) — dudas de reglamento y uso de la app"))

            hint_ai = QLabel(
                "Consíguela gratis en aistudio.google.com/apikey. El reglamento "
                "que pegues abajo es lo único que el asistente usa para responder "
                "preguntas de reglas — si lo dejas vacío, avisa que falta configurarlo "
                "en vez de inventar una respuesta."
            )
            hint_ai.setWordWrap(True)
            hint_ai.setStyleSheet(f"font-size: 11px; color: {C.TEXT3}; background: transparent;")
            ai_lay.addWidget(hint_ai)

            lbl_key = QLabel("CLAVE API GEMINI")
            lbl_key.setStyleSheet(
                f"font-size: 10px; font-weight: 700; letter-spacing: 0.6px; "
                f"color: {C.TEXT2}; background: transparent;"
            )
            self._gemini_key = QLineEdit()
            self._gemini_key.setPlaceholderText("AIzaSy...")
            self._gemini_key.setEchoMode(QLineEdit.EchoMode.Password)
            self._gemini_key.textChanged.connect(self._on_field_changed)
            ai_lay.addWidget(lbl_key)
            ai_lay.addWidget(self._gemini_key)

            lbl_reg = QLabel("TEXTO DEL REGLAMENTO DEL LICEO")
            lbl_reg.setStyleSheet(
                f"font-size: 10px; font-weight: 700; letter-spacing: 0.6px; "
                f"color: {C.TEXT2}; background: transparent;"
            )
            self._gemini_reglamento = _QTE()
            self._gemini_reglamento.setFixedHeight(140)
            self._gemini_reglamento.setPlaceholderText(
                "Pega aquí el texto completo del reglamento interno / de convivencia del liceo…"
            )
            self._gemini_reglamento.setStyleSheet(f"""
                QTextEdit {{
                    background: {C.SURFACE2}; color: {C.TEXT};
                    border: 1.5px solid {C.BORDER2}; border-radius: 8px;
                    padding: 8px 10px; font-size: 12.5px;
                }}
                QTextEdit:focus {{ border-color: {C.BLUE}; }}
            """)
            self._gemini_reglamento.textChanged.connect(self._on_field_changed)
            self._gemini_reglamento.textChanged.connect(self._update_reglamento_counter)

            self._lbl_reglamento_count = QLabel("")
            self._lbl_reglamento_count.setStyleSheet(
                f"font-size: 10.5px; color: {C.TEXT2}; background: transparent;"
            )
            ai_lay.addWidget(lbl_reg)
            ai_lay.addWidget(self._gemini_reglamento)
            ai_lay.addWidget(self._lbl_reglamento_count)

            root.addWidget(ai_card)

        # ── Impresora Térmica ─────────────────────────
        printer_card = QFrame()
        printer_card.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border: none;
                border-radius: 14px;
            }}
        """)
        pl = QVBoxLayout(printer_card)
        pl.setContentsMargins(20, 16, 20, 16)
        pl.setSpacing(10)
        pl.addWidget(SectionHeader("Impresora Térmica (ESC/POS 80mm)"))

        hint_pr = QLabel(
            "Conecta cualquier impresora de boleta estándar (Epson TM, Star, Bixolon, etc.). "
            "Formatos de conexión: <b>192.168.1.100:9100</b> (red TCP), "
            "<b>CUPS:NombreImpresora</b> (cola CUPS), "
            "<b>/dev/cu.usbmodem001</b> (USB directo)."
        )
        hint_pr.setWordWrap(True)
        hint_pr.setTextFormat(Qt.TextFormat.RichText)
        hint_pr.setStyleSheet(f"font-size: 11px; color: {C.TEXT3}; background: transparent;")
        pl.addWidget(hint_pr)

        lbl_pr = QLabel("CONEXIÓN")
        lbl_pr.setStyleSheet(
            f"font-size: 10px; font-weight: 700; letter-spacing: 0.6px; "
            f"color: {C.TEXT2}; background: transparent;"
        )
        pl.addWidget(lbl_pr)

        pr_row = QHBoxLayout()
        pr_row.setSpacing(8)
        self._inp_printer = QLineEdit()
        self._inp_printer.setPlaceholderText("Ej: 192.168.1.100:9100  o  CUPS:EpsonTM  o  /dev/cu.usb...")
        self._inp_printer.textChanged.connect(self._on_field_changed)
        pr_row.addWidget(self._inp_printer, stretch=1)

        btn_pr_save = AButton("Guardar", sound_type="save")
        btn_pr_save.setStyleSheet(f"""
            QPushButton {{
                background: {C.NAVY_700}; color: {C.TEXT};
                border: none; border-radius: 8px;
                padding: 8px 14px; font-size: 12px; font-weight: 600;
            }}
            QPushButton:hover {{ background: {C.NAVY_600}; }}
        """)
        btn_pr_save.clicked.connect(self._guardar_printer)
        pr_row.addWidget(btn_pr_save)

        btn_pr_test = AButton("Probar", sound_type="click")
        btn_pr_test.setStyleSheet(f"""
            QPushButton {{
                background: {C.BLUE_DIM}; color: {C.BLUE};
                border: 1px solid {C.BLUE}44;
                border-radius: 8px;
                padding: 8px 14px; font-size: 12px; font-weight: 600;
            }}
            QPushButton:hover {{ background: {C.BLUE}22; }}
        """)
        btn_pr_test.clicked.connect(self._probar_printer)
        pr_row.addWidget(btn_pr_test)
        pl.addLayout(pr_row)

        self._lbl_pr_result = QLabel("")
        self._lbl_pr_result.setStyleSheet(
            f"font-size: 12px; background: transparent;"
        )
        pl.addWidget(self._lbl_pr_result)

        # ── Disclaimer editable ──────────────────────
        from PyQt6.QtWidgets import QTextEdit as _QTE
        pl.addWidget(HDivider())

        lbl_disc = QLabel("TEXTO DEL PIE (disclaimer)")
        lbl_disc.setStyleSheet(
            f"font-size: 10px; font-weight: 700; letter-spacing: 0.6px; "
            f"color: {C.TEXT2}; background: transparent;"
        )
        pl.addWidget(lbl_disc)

        self._inp_disclaimer = _QTE()
        self._inp_disclaimer.setFixedHeight(56)
        self._inp_disclaimer.setPlaceholderText(
            "El estudiante tiene un lapso de 5 minutos desde emitido este pase "
            "para hacer ingreso al aula."
        )
        self._inp_disclaimer.setStyleSheet(f"""
            QTextEdit {{
                background: {C.SURFACE2};
                border: 1px solid {C.BORDER};
                border-radius: 8px;
                color: {C.TEXT};
                font-size: 12px;
                padding: 6px 10px;
            }}
            QTextEdit:focus {{ border-color: {C.NAVY_400}; }}
        """)
        self._inp_disclaimer.textChanged.connect(self._on_disclaimer_changed)
        pl.addWidget(self._inp_disclaimer)

        # ── Preview del ticket ───────────────────────
        pl.addWidget(HDivider())

        lbl_prev = QLabel("VISTA PREVIA DEL TICKET")
        lbl_prev.setStyleSheet(
            f"font-size: 10px; font-weight: 700; letter-spacing: 0.6px; "
            f"color: {C.TEXT2}; background: transparent;"
        )
        pl.addWidget(lbl_prev)

        # Selector de tipo para preview
        prev_sel_row = QHBoxLayout()
        prev_sel_row.setSpacing(6)
        self._btn_prev_atraso = QPushButton("Atraso")
        self._btn_prev_inasis = QPushButton("Inasistencia")
        self._btn_prev_current = "atraso"

        _prev_btn_base = f"""
            QPushButton {{
                border-radius: 7px; padding: 4px 16px;
                font-size: 12px; font-weight: 600;
            }}
        """
        self._prev_btn_on  = _prev_btn_base + f"QPushButton {{ background: {C.BLUE}; color: white; border: none; }}"
        self._prev_btn_off = _prev_btn_base + f"QPushButton {{ background: transparent; color: {C.TEXT3}; border: 1px solid {C.BORDER}; }} QPushButton:hover {{ background: {C.SURFACE2}; }}"

        self._btn_prev_atraso.setStyleSheet(self._prev_btn_on)
        self._btn_prev_inasis.setStyleSheet(self._prev_btn_off)
        self._btn_prev_atraso.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_prev_inasis.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_prev_atraso.clicked.connect(lambda: self._switch_preview("atraso"))
        self._btn_prev_inasis.clicked.connect(lambda: self._switch_preview("inasistencia"))
        prev_sel_row.addWidget(self._btn_prev_atraso)
        prev_sel_row.addWidget(self._btn_prev_inasis)
        prev_sel_row.addStretch()
        pl.addLayout(prev_sel_row)

        self._preview_text = _QTE()
        self._preview_text.setReadOnly(True)
        self._preview_text.setFixedHeight(300)
        from PyQt6.QtGui import QFont as _QF
        _mono = _QF("Courier New")
        _mono.setPointSize(10)
        self._preview_text.setFont(_mono)
        self._preview_text.setStyleSheet(f"""
            QTextEdit {{
                background: #1a1a1a;
                color: #e0e0e0;
                border: 1px solid {C.BORDER};
                border-radius: 8px;
                padding: 10px 12px;
            }}
        """)
        pl.addWidget(self._preview_text)

        root.addWidget(printer_card)

        # ── Gestión de usuarios (solo admin) ─────────
        if _sess.is_admin():
            users_card = QFrame()
            users_card.setStyleSheet(f"""
                QFrame {{
                    background: {C.SURFACE};
                    border: none;
                    border-radius: 14px;
                }}
            """)
            ul = QVBoxLayout(users_card)
            ul.setContentsMargins(20, 16, 20, 16)
            ul.setSpacing(10)
            ul.addWidget(SectionHeader("Gestión de usuarios"))

            hint_u = QLabel(
                "El PIN por defecto del Administrador es 1234. "
                "Cámbialo desde aquí después del primer inicio de sesión."
            )
            hint_u.setWordWrap(True)
            hint_u.setStyleSheet(f"font-size: 11px; color: {C.TEXT3}; background: transparent;")
            ul.addWidget(hint_u)

            self._users_table = QTableWidget()
            self._users_table.setColumnCount(3)
            self._users_table.setHorizontalHeaderLabels(["Usuario", "Rol", "Estado"])
            self._users_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            self._users_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            self._users_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            self._users_table.verticalHeader().setVisible(False)
            self._users_table.setFixedHeight(160)
            ul.addWidget(self._users_table)
            self._load_users_table()

            # Crear usuario rápido
            new_row = QHBoxLayout()
            new_row.setSpacing(8)
            self._inp_u_nombre = QLineEdit()
            self._inp_u_nombre.setPlaceholderText("Nombre del usuario")
            self._inp_u_pin = QLineEdit()
            self._inp_u_pin.setPlaceholderText("PIN (4-6 dígitos)")
            self._inp_u_pin.setMaximumWidth(130)
            from PyQt6.QtWidgets import QComboBox as _QCB
            self._cmb_u_rol = _QCB()
            self._cmb_u_rol.addItems(["pae", "inspectoria", "admin"])
            self._cmb_u_rol.setMaximumWidth(130)
            btn_add_u = AButton("+ Crear", sound_type="save")
            btn_add_u.setStyleSheet(f"""
                QPushButton {{
                    background: {C.BLUE}; color: white;
                    border: none; border-radius: 8px;
                    padding: 8px 14px; font-size: 12px; font-weight: 600;
                }}
                QPushButton:hover {{ background: {C.NAVY_600}; }}
            """)
            btn_add_u.clicked.connect(self._crear_usuario)
            new_row.addWidget(self._inp_u_nombre, stretch=1)
            new_row.addWidget(self._inp_u_pin)
            new_row.addWidget(self._cmb_u_rol)
            new_row.addWidget(btn_add_u)
            ul.addLayout(new_row)

            root.addWidget(users_card)

        # ── Reportes de bugs → Supabase (solo admin) ──
        if _sess.is_admin():
            bug_card = QFrame()
            bug_card.setStyleSheet(f"""
                QFrame {{
                    background: {C.SURFACE};
                    border: none;
                    border-radius: 14px;
                }}
            """)
            bl = QVBoxLayout(bug_card)
            bl.setContentsMargins(20, 16, 20, 16)
            bl.setSpacing(10)
            bl.addWidget(SectionHeader("Reportes de bugs"))

            hint_bug = QLabel(
                "Los reportes se guardan localmente en ~/pae_control/bug_reports/ "
                "y además se suben a la tabla bug_reports de Supabase (mismas credenciales de arriba). "
                "Consúltalos desde el dashboard de Supabase."
            )
            hint_bug.setWordWrap(True)
            hint_bug.setStyleSheet(f"font-size: 11px; color: {C.TEXT3}; background: transparent;")
            bl.addWidget(hint_bug)

            bug_btn_row = QHBoxLayout()
            self._lbl_bug_result = QLabel("")
            self._lbl_bug_result.setStyleSheet(f"font-size: 11px; color: {C.TEXT2}; background: transparent;")
            btn_bug_test = AButton("Probar conexion", sound_type="click")
            btn_bug_test.setFixedHeight(30)
            btn_bug_test.clicked.connect(self._probar_bug_reporter)
            bug_btn_row.addWidget(self._lbl_bug_result, stretch=1)
            bug_btn_row.addWidget(btn_bug_test)
            bl.addLayout(bug_btn_row)

            root.addWidget(bug_card)

        # ── Gestión de período (solo admin) ──────────
        if _sess.is_admin():
            periodo_card = QFrame()
            periodo_card.setStyleSheet(f"""
                QFrame {{
                    background: {C.SURFACE};
                    border: 1.5px solid {C.GOLD_500}44;
                    border-radius: 14px;
                }}
            """)
            pl = QVBoxLayout(periodo_card)
            pl.setContentsMargins(20, 16, 20, 16)
            pl.setSpacing(10)
            pl.addWidget(SectionHeader("Gestión de períodos"))

            periodo_activo = db.get_periodo_activo()
            self._lbl_periodo_actual = QLabel(f"Período activo: {periodo_activo}")
            self._lbl_periodo_actual.setStyleSheet(
                f"font-size: 13px; font-weight: 600; color: {C.TEXT}; background: transparent;"
            )
            pl.addWidget(self._lbl_periodo_actual)

            hint_p = QLabel(
                "Al cerrar un período, los datos se conservan y pueden verse desde el selector "
                "del toolbar. El nuevo período empieza en blanco para attendance y pases. "
                "La nómina PAE y los estudiantes se mantienen."
            )
            hint_p.setWordWrap(True)
            hint_p.setStyleSheet(f"font-size: 11px; color: {C.TEXT3}; background: transparent;")
            pl.addWidget(hint_p)

            from PyQt6.QtWidgets import QHBoxLayout as _HBL, QLineEdit as _LE
            p_row = _HBL()
            p_row.setSpacing(8)
            nuevo_lbl = QLabel("Nombre nuevo período:")
            nuevo_lbl.setStyleSheet(f"color: {C.TEXT2}; font-size: 12px; background: transparent;")
            p_row.addWidget(nuevo_lbl)

            self._nuevo_periodo_edit = _LE()
            self._nuevo_periodo_edit.setPlaceholderText("ej. 2026-S2")
            self._nuevo_periodo_edit.setFixedWidth(120)
            self._nuevo_periodo_edit.setFixedHeight(32)
            p_row.addWidget(self._nuevo_periodo_edit)

            btn_cerrar = AButton("Cerrar período →", sound_type="save")
            btn_cerrar.setFixedHeight(32)
            btn_cerrar.setStyleSheet(f"""
                QPushButton {{
                    background: {C.GOLD_500};
                    color: white;
                    border: none; border-radius: 8px;
                    padding: 0 16px; font-size: 12px; font-weight: 700;
                }}
                QPushButton:hover {{ background: {C.GOLD_400}; }}
                QPushButton:pressed {{ background: #A87800; }}
            """)
            btn_cerrar.clicked.connect(self._cerrar_periodo)
            p_row.addWidget(btn_cerrar)
            p_row.addStretch()
            pl.addLayout(p_row)

            self._lbl_periodo_result = QLabel("")
            self._lbl_periodo_result.setStyleSheet(
                f"font-size: 11px; color: {C.TEXT3}; background: transparent;"
            )
            pl.addWidget(self._lbl_periodo_result)

            root.addWidget(periodo_card)

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

    def _make_spinbox(self, min_v: int, max_v: int, label: str,
                      suffix: str = "", tooltip: str = ""):
        """Returns [QLabel, QSpinBox] to add to a layout."""
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {C.TEXT2}; font-size: 13px; background: transparent;")
        spin = QSpinBox()
        spin.setRange(min_v, max_v)
        spin.setFixedWidth(100)
        if suffix:
            spin.setSuffix(suffix)
        if tooltip:
            spin.setToolTip(tooltip)
            lbl.setToolTip(tooltip)
        spin.valueChanged.connect(self._on_field_changed)
        return [lbl, spin]

    # ─────────────────────────────────────────────
    #  CONFIG LOAD / SAVE
    # ─────────────────────────────────────────────

    def _load_config(self):
        # Bloquear signals durante carga para no disparar debounce de guardado
        widgets = [
            self._inp_nombre, self._spin_cupos[1], self._spin_strikes[1],
            self._spin_submit_delay[1], self._spin_autoreset_default[1],
            self._chk_flash, self._chk_ausencias, self._chk_doble_sonido,
            self._chk_historial, self._chk_weather, self._inp_weather_city,
        ]
        for w in widgets:
            w.blockSignals(True)

        cfg = db.get_all_config()
        self._inp_nombre.setText(cfg.get("nombre_establecimiento", ""))
        self._spin_cupos[1].setValue(int(cfg.get("cupos_totales", "100")))
        self._spin_strikes[1].setValue(int(cfg.get("max_strikes", "3")))

        # ── Pantalla de escaneo ───────────────────────
        self._spin_submit_delay[1].setValue(
            int(cfg.get("scan_submit_delay_ms", "180")))
        self._spin_autoreset_default[1].setValue(
            int(cfg.get("scan_auto_reset_default_s", "5")))
        self._chk_flash.setChecked(
            cfg.get("scan_flash_enabled", "1") == "1")
        self._chk_ausencias.setChecked(
            cfg.get("scan_show_ausencias", "1") == "1")
        self._chk_doble_sonido.setChecked(
            cfg.get("scan_double_sound", "1") == "1")
        self._chk_historial.setChecked(
            cfg.get("scan_show_historial", "1") == "1")

        # ── Clima ──────────────────────────
        self._chk_weather.setChecked(
            cfg.get("weather_enabled", "1") == "1")
        city = cfg.get("weather_city", "Laja")
        self._inp_weather_city.setText(city)
        lat = cfg.get("weather_lat", "")
        lon = cfg.get("weather_lon", "")
        if lat and lon:
            self._lbl_city_status.setText(f"✓ {city}  ({lat}, {lon})")
            self._lbl_city_status.setStyleSheet(
                f"color: {C.GREEN}; font-size: 11px; background: transparent;")

        # ── WhatsApp (si admin y widgets existen)
        if hasattr(self, "_wa_phone_id"):
            self._wa_phone_id.blockSignals(True)
            self._wa_token.blockSignals(True)
            self._wa_plantilla.blockSignals(True)
            self._wa_phone_id.setText(cfg.get("wa_phone_id", ""))
            self._wa_token.setText(cfg.get("wa_token", ""))
            self._wa_plantilla.setText(cfg.get("wa_plantilla", ""))
            self._wa_phone_id.blockSignals(False)
            self._wa_token.blockSignals(False)
            self._wa_plantilla.blockSignals(False)

        # ── Asistente IA (si admin y widgets existen)
        if hasattr(self, "_gemini_key"):
            self._gemini_key.blockSignals(True)
            self._gemini_reglamento.blockSignals(True)
            self._gemini_key.setText(cfg.get("gemini_api_key", ""))
            self._gemini_reglamento.setPlainText(cfg.get("gemini_reglamento", ""))
            self._gemini_key.blockSignals(False)
            self._gemini_reglamento.blockSignals(False)
            self._update_reglamento_counter()

        # ── Impresora Térmica
        self._inp_printer.blockSignals(True)
        self._inp_printer.setText(cfg.get("thermal_printer", ""))
        self._inp_printer.blockSignals(False)
        self._inp_disclaimer.blockSignals(True)
        self._inp_disclaimer.setPlainText(cfg.get("thermal_disclaimer", ""))
        self._inp_disclaimer.blockSignals(False)
        self._refresh_preview()

        # (SMTP eliminado — reportes van directo a Supabase)

        # Desbloquear signals después de la carga completa
        for w in widgets:
            w.blockSignals(False)

    def _on_field_changed(self, *args):
        """Called on any field change — starts debounce timer."""
        self._debounce.start()

    def _update_reglamento_counter(self):
        n = len(self._gemini_reglamento.toPlainText())
        cap = assistant.MAX_REGLAMENTO_CHARS
        if n > cap:
            self._lbl_reglamento_count.setStyleSheet(
                f"font-size: 10.5px; color: {C.RED}; background: transparent;"
            )
            self._lbl_reglamento_count.setText(
                f"{n:,} caracteres — supera el máximo que el Agente IA puede usar "
                f"por consulta ({cap:,}); se recortará automáticamente, así que "
                f"conviene dejar solo lo más relevante acá."
            )
        else:
            self._lbl_reglamento_count.setStyleSheet(
                f"font-size: 10.5px; color: {C.TEXT2}; background: transparent;"
            )
            self._lbl_reglamento_count.setText(f"{n:,} / {cap:,} caracteres")

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

            # ── Pantalla de escaneo ───────────────────
            db.set_config("scan_submit_delay_ms",
                          str(self._spin_submit_delay[1].value()))
            db.set_config("scan_auto_reset_default_s",
                          str(self._spin_autoreset_default[1].value()))
            db.set_config("scan_flash_enabled",
                          "1" if self._chk_flash.isChecked() else "0")
            db.set_config("scan_show_ausencias",
                          "1" if self._chk_ausencias.isChecked() else "0")
            db.set_config("scan_double_sound",
                          "1" if self._chk_doble_sonido.isChecked() else "0")
            db.set_config("scan_show_historial",
                          "1" if self._chk_historial.isChecked() else "0")

            # ── Clima ──────────────────────
            db.set_config("weather_enabled",
                          "1" if self._chk_weather.isChecked() else "0")
            # Si hay un resultado confirmado de geocoding, guardarlo
            if self._pending_geo:
                db.set_config("weather_city", self._pending_geo["city"])
                db.set_config("weather_lat",  self._pending_geo["lat"])
                db.set_config("weather_lon",  self._pending_geo["lon"])
                self._pending_geo = {}
            else:
                city_val = self._inp_weather_city.text().strip()
                if city_val:
                    db.set_config("weather_city", city_val)

            # ── WhatsApp credentials (si admin y widgets existen)
            if hasattr(self, "_wa_phone_id"):
                db.set_config("wa_phone_id",   self._wa_phone_id.text().strip())
                db.set_config("wa_token",       self._wa_token.text().strip())
                db.set_config("wa_plantilla",   self._wa_plantilla.text().strip())

            # ── Asistente IA (si admin y widgets existen)
            if hasattr(self, "_gemini_key"):
                db.set_config("gemini_api_key",    self._gemini_key.text().strip())
                db.set_config("gemini_reglamento", self._gemini_reglamento.toPlainText().strip())

            # ── Impresora Térmica
            db.set_config("thermal_printer",    self._inp_printer.text().strip())
            db.set_config("thermal_disclaimer", self._inp_disclaimer.toPlainText().strip())

            # (SMTP eliminado — reportes van directo a Supabase)

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

    # ── WhatsApp ─────────────────────────────────────────────────────────────

    def _probar_whatsapp(self):
        """Prueba la conexión WA con el número ingresado (background thread)."""
        numero = self._wa_test_num.text().strip()
        if not numero:
            self._wa_test_result.setText("⚠ Ingresa un número de prueba")
            self._wa_test_result.setStyleSheet(
                f"font-size: 12px; color: {C.GOLD_500}; background: transparent;"
            )
            return
        # Leer credenciales desde los campos UI (sin pasar por DB ni _commit_save)
        phone_id  = self._wa_phone_id.text().strip()
        token     = self._wa_token.text().strip()
        plantilla = self._wa_plantilla.text().strip() or "notificacion_atraso"
        self._wa_test_result.setText("Enviando mensaje de prueba…")
        self._wa_test_result.setStyleSheet(
            f"font-size: 12px; color: {C.TEXT2}; background: transparent;"
        )
        import threading
        def _do():
            try:
                import whatsapp
                ok, msg = whatsapp.probar_conexion(numero, phone_id, token, plantilla)
                def _update():
                    if ok:
                        self._wa_test_result.setText(f"✓ {msg}")
                        self._wa_test_result.setStyleSheet(
                            f"font-size: 12px; color: {C.GREEN}; background: transparent;"
                        )
                    else:
                        self._wa_test_result.setText(f"✗ {msg}")
                        self._wa_test_result.setStyleSheet(
                            f"font-size: 12px; color: {C.RED}; background: transparent;"
                        )
                QTimer.singleShot(0, _update)
            except Exception as e:
                err = str(e)
                QTimer.singleShot(0, lambda: (
                    self._wa_test_result.setText(f"✗ Error: {err}"),
                    self._wa_test_result.setStyleSheet(
                        f"font-size: 12px; color: {C.RED}; background: transparent;"
                    )
                ))
        threading.Thread(target=_do, daemon=True, name="wa-test").start()

    # ── Impresora Térmica ─────────────────────────────────────────────────────

    def _on_disclaimer_changed(self):
        self._on_field_changed()
        self._refresh_preview()

    def _switch_preview(self, tipo: str):
        self._btn_prev_current = tipo
        if tipo == "atraso":
            self._btn_prev_atraso.setStyleSheet(self._prev_btn_on)
            self._btn_prev_inasis.setStyleSheet(self._prev_btn_off)
        else:
            self._btn_prev_atraso.setStyleSheet(self._prev_btn_off)
            self._btn_prev_inasis.setStyleSheet(self._prev_btn_on)
        self._refresh_preview()

    def _refresh_preview(self):
        """Regenera el preview en monospace del ticket actual."""
        try:
            import thermal_print
            estab     = self._inp_nombre.text().strip() or "Nombre del establecimiento"
            disc      = self._inp_disclaimer.toPlainText().strip()
            tipo      = getattr(self, "_btn_prev_current", "atraso")
            texto     = thermal_print.generar_preview_texto(
                tipo=tipo,
                establecimiento=estab,
                disclaimer=disc,
            )
            self._preview_text.setPlainText(texto)
        except Exception as exc:
            self._preview_text.setPlainText(f"[Error al generar preview: {exc}]")

    def _guardar_printer(self):
        val = self._inp_printer.text().strip()
        db.set_config("thermal_printer", val)
        sound.save()
        if val:
            self._lbl_pr_result.setText("✓ Guardado")
            self._lbl_pr_result.setStyleSheet(
                f"font-size: 12px; color: {C.GREEN}; background: transparent;"
            )
        else:
            self._lbl_pr_result.setText("Impresora desactivada (campo vacío)")
            self._lbl_pr_result.setStyleSheet(
                f"font-size: 12px; color: {C.TEXT3}; background: transparent;"
            )

    def _probar_printer(self):
        """Imprime ticket de prueba en hilo daemon."""
        import threading as _th
        val = self._inp_printer.text().strip()
        if not val:
            self._lbl_pr_result.setText("⚠ Ingresa la conexión de la impresora primero")
            self._lbl_pr_result.setStyleSheet(
                f"font-size: 12px; color: {C.GOLD_500}; background: transparent;"
            )
            return
        # Guardar primero
        db.set_config("thermal_printer", val)
        self._lbl_pr_result.setText("Enviando ticket de prueba…")
        self._lbl_pr_result.setStyleSheet(
            f"font-size: 12px; color: {C.TEXT2}; background: transparent;"
        )

        def _do():
            try:
                import thermal_print
                estab = db.get_config("nombre_establecimiento", "MiAppoderado")
                contenido = thermal_print.generar_ticket_prueba(estab)
                ok, msg = thermal_print.imprimir(contenido)

                def _update():
                    if ok:
                        self._lbl_pr_result.setText(f"✓ {msg}")
                        self._lbl_pr_result.setStyleSheet(
                            f"font-size: 12px; color: {C.GREEN}; background: transparent;"
                        )
                    else:
                        self._lbl_pr_result.setText(f"✗ {msg}")
                        self._lbl_pr_result.setStyleSheet(
                            f"font-size: 12px; color: {C.RED}; background: transparent;"
                        )
                from PyQt6.QtCore import QTimer as _QT
                _QT.singleShot(0, _update)
            except Exception as exc:
                def _upd_err():
                    self._lbl_pr_result.setText(f"✗ {exc}")
                    self._lbl_pr_result.setStyleSheet(
                        f"font-size: 12px; color: {C.RED}; background: transparent;"
                    )
                from PyQt6.QtCore import QTimer as _QT
                _QT.singleShot(0, _upd_err)

        _th.Thread(target=_do, daemon=True, name="thermal-test").start()

    def _cerrar_periodo(self):
        """Cierra el período activo y abre uno nuevo."""
        from PyQt6.QtWidgets import QMessageBox
        if not hasattr(self, "_nuevo_periodo_edit"):
            return

        nuevo = self._nuevo_periodo_edit.text().strip()
        if not nuevo:
            self._lbl_periodo_result.setText("Escribe el nombre del nuevo período (ej. 2026-S2)")
            self._lbl_periodo_result.setStyleSheet(
                f"font-size: 11px; color: {C.RED}; background: transparent;"
            )
            return

        actual = db.get_periodo_activo()
        resp = QMessageBox.question(
            self,
            "Cerrar período",
            f"¿Cerrar el período <b>{actual}</b> y abrir <b>{nuevo}</b>?<br><br>"
            "Los datos históricos se conservan y podrás verlos desde el selector del toolbar.<br>"
            "La nómina PAE y los estudiantes NO se modifican.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return

        result = db.cerrar_periodo(nuevo)
        if result["ok"]:
            import session as _sess
            _sess.set_viewing_period(nuevo)
            self._lbl_periodo_actual.setText(f"Período activo: {nuevo}")
            self._nuevo_periodo_edit.clear()
            self._lbl_periodo_result.setText(
                f"Período {result['periodo_anterior']} cerrado · {nuevo} activo"
            )
            self._lbl_periodo_result.setStyleSheet(
                f"font-size: 11px; color: {C.GREEN}; background: transparent;"
            )
        else:
            self._lbl_periodo_result.setText(f"Error: {result['error']}")
            self._lbl_periodo_result.setStyleSheet(
                f"font-size: 11px; color: {C.RED}; background: transparent;"
            )

    def _probar_bug_reporter(self):
        """Sube un reporte de prueba a Supabase para verificar la conexión."""
        if not hasattr(self, "_lbl_bug_result"):
            return
        self._lbl_bug_result.setText("Conectando a Supabase…")
        self._lbl_bug_result.setStyleSheet(
            f"font-size: 11px; color: {C.TEXT2}; background: transparent;"
        )

        import threading as _th

        def _do():
            import bug_reporter
            ok, msg = bug_reporter.probar_conexion()

            def _upd():
                if ok:
                    self._lbl_bug_result.setText(f"OK  {msg}")
                    self._lbl_bug_result.setStyleSheet(
                        f"font-size: 11px; color: {C.GREEN}; background: transparent;"
                    )
                else:
                    self._lbl_bug_result.setText(f"Error  {msg}")
                    self._lbl_bug_result.setStyleSheet(
                        f"font-size: 11px; color: {C.RED}; background: transparent;"
                    )
            from PyQt6.QtCore import QTimer as _QT
            _QT.singleShot(0, _upd)

        _th.Thread(target=_do, daemon=True, name="bugreport-test").start()

    # ── Usuarios ──────────────────────────────────────────────────────────────

    def _load_users_table(self):
        """Carga la tabla de usuarios con datos de db."""
        if not hasattr(self, "_users_table"):
            return
        users = db.get_todos_usuarios()
        self._users_table.setRowCount(len(users))
        _rol_label = {"admin": "Administrador", "pae": "PAE", "inspectoria": "Inspectoría"}
        for i, u in enumerate(users):
            self._users_table.setItem(i, 0, QTableWidgetItem(u["nombre"]))
            self._users_table.setItem(i, 1, QTableWidgetItem(_rol_label.get(u["rol"], u["rol"])))
            estado = "Activo" if u["activo"] else "Inactivo"
            item_estado = QTableWidgetItem(estado)
            from PyQt6.QtGui import QColor
            item_estado.setForeground(QColor(C.GREEN if u["activo"] else C.RED))
            self._users_table.setItem(i, 2, item_estado)
            # guardar id en item nombre para poder referenciarlo
            self._users_table.item(i, 0).setData(Qt.ItemDataRole.UserRole, u["id"])
        self._users_table.resizeColumnsToContents()
        self._users_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )

    def _crear_usuario(self):
        """Crea un nuevo usuario con los campos del formulario."""
        nombre = self._inp_u_nombre.text().strip()
        pin    = self._inp_u_pin.text().strip()
        rol    = self._cmb_u_rol.currentText()

        if not nombre:
            self._saved_ind.show_error("✗  Ingresa un nombre de usuario")
            return
        if not pin.isdigit() or not (4 <= len(pin) <= 6):
            self._saved_ind.show_error("✗  PIN debe ser 4-6 dígitos numéricos")
            return

        try:
            db.create_usuario(nombre, pin, rol)
            self._inp_u_nombre.clear()
            self._inp_u_pin.clear()
            self._load_users_table()
            self._saved_ind.show_saved(f"✓  Usuario '{nombre}' creado")
        except Exception as e:
            self._saved_ind.show_error(f"✗  {e}")

    def _search_city_suggestions(self):
        """Fetch sugerencias de ciudad desde Open-Meteo geocoding. Background."""
        import threading, urllib.request, urllib.parse, json, ssl
        query = self._inp_weather_city.text().strip()
        if len(query) < 2:
            self._city_popup.clear()
            self._city_popup.setFixedHeight(0)
            return

        def _ssl():
            return ssl._create_unverified_context()

        def _do():
            try:
                url = (
                    f"https://geocoding-api.open-meteo.com/v1/search"
                    f"?name={urllib.parse.quote(query)}&count=6&language=es&format=json"
                )
                with urllib.request.urlopen(url, timeout=8, context=_ssl()) as r:
                    data = json.loads(r.read().decode())
                results = data.get("results", [])
                QTimer.singleShot(0, lambda: self._show_city_suggestions(results))
            except Exception as e:
                msg = str(e)
                QTimer.singleShot(0, lambda m=msg: (
                    self._lbl_city_status.setText(f"⚠ {m}"),
                    self._lbl_city_status.setStyleSheet(
                        f"color: {C.RED}; font-size: 11px; background: transparent;")
                ))

        threading.Thread(target=_do, daemon=True, name="pae-geocode").start()

    def _show_city_suggestions(self, results: list):
        self._city_popup.clear()
        if not results:
            self._city_popup.setFixedHeight(0)
            self._lbl_city_status.setText("Ciudad no encontrada")
            self._lbl_city_status.setStyleSheet(
                f"color: {C.RED}; font-size: 11px; background: transparent;")
            return

        for r in results:
            name    = r.get("name", "")
            admin1  = r.get("admin1", "")
            country = r.get("country", "")
            lat     = round(r.get("latitude",  0), 4)
            lon     = round(r.get("longitude", 0), 4)
            label   = name
            if admin1:
                label += f", {admin1}"
            if country:
                label += f" — {country}"
            label += f"  ({lat}, {lon})"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, {
                "city": name, "lat": str(lat), "lon": str(lon)
            })
            self._city_popup.addItem(item)

        rows = min(len(results), 5)
        self._city_popup.setFixedHeight(rows * 34)
        self._lbl_city_status.setText("↑ Selecciona una ciudad de la lista")
        self._lbl_city_status.setStyleSheet(
            f"color: {C.TEXT3}; font-size: 11px; background: transparent;")

    def _on_city_selected(self, item: QListWidgetItem):
        geo = item.data(Qt.ItemDataRole.UserRole)
        if not geo:
            return
        self._inp_weather_city.blockSignals(True)
        self._inp_weather_city.setText(geo["city"])
        self._inp_weather_city.blockSignals(False)
        self._city_popup.clear()
        self._city_popup.setFixedHeight(0)
        self._lbl_city_status.setText(
            f"✓ {geo['city']}  ({geo['lat']}, {geo['lon']})"
        )
        self._lbl_city_status.setStyleSheet(
            f"color: {C.GREEN}; font-size: 11px; background: transparent;")
        # Guardar coordenadas inmediatamente en DB
        db.set_config("weather_city", geo["city"])
        db.set_config("weather_lat",  geo["lat"])
        db.set_config("weather_lon",  geo["lon"])

    def _reload_weather_now(self):
        mw = self.window()
        if hasattr(mw, "reload_weather"):
            mw.reload_weather()

    def _geocode_city(self, city: str):
        pass  # reemplazado por autocomplete

    def showEvent(self, event):
        super().showEvent(event)
        self._load_config()
