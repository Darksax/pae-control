"""
sync_screen.py — Pantalla de sincronización Supabase MiAppoderado

Permite configurar credenciales, verificar la conexión y lanzar sync.
El sync corre en QThread para no bloquear la UI.
Sin QMessageBox — todo inline.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QFrame, QTextEdit, QSizePolicy, QScrollArea
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QFont

import db
import sync as _sync
from ui.theme   import C, sound
from ui.widgets import AButton, HDivider, SectionHeader, SavedIndicator


# ══════════════════════════════════════════════════════
#  WORKER THREAD
# ══════════════════════════════════════════════════════

class _SyncWorker(QThread):
    finished = pyqtSignal(dict)

    def __init__(self, push_only: bool = False):
        super().__init__()
        self._push_only = push_only

    def run(self):
        result = _sync.sync_all(self._push_only)
        self.finished.emit(result)


class _CheckWorker(QThread):
    finished = pyqtSignal(bool, str)

    def run(self):
        ok, msg = _sync.check_connection()
        self.finished.emit(ok, msg)


# ══════════════════════════════════════════════════════
#  SYNC SCREEN
# ══════════════════════════════════════════════════════

class SyncScreen(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: _SyncWorker | None = None
        self._build_ui()
        self._load_credentials()

    def _build_ui(self):
        self.setStyleSheet(f"background: {C.BG};")
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 20)
        root.setSpacing(16)

        # ── Title ─────────────────────────────────────
        title_row = QHBoxLayout()
        title = QLabel("Sincronización Supabase")
        title.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: {C.TEXT}; background: transparent;"
        )
        title_row.addWidget(title)
        title_row.addStretch()

        # Estado de conexión (dot + texto)
        self._dot = QFrame()
        self._dot.setFixedSize(10, 10)
        self._dot.setStyleSheet(
            f"background: {C.TEXT3}; border-radius: 5px; border: none;"
        )
        title_row.addWidget(self._dot)
        self._lbl_status = QLabel("Sin configurar")
        self._lbl_status.setStyleSheet(
            f"font-size: 12px; color: {C.TEXT3}; background: transparent; padding-left: 6px;"
        )
        title_row.addWidget(self._lbl_status)
        root.addLayout(title_row)

        # ── Dos columnas ──────────────────────────────
        cols = QHBoxLayout()
        cols.setSpacing(16)

        # ── Columna izquierda: credenciales + botones ─
        left = QVBoxLayout()
        left.setSpacing(14)

        # Credenciales
        creds_card = QFrame()
        creds_card.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border: none;
                border-radius: 14px;
            }}
        """)
        creds_lay = QVBoxLayout(creds_card)
        creds_lay.setContentsMargins(20, 18, 20, 18)
        creds_lay.setSpacing(10)

        creds_lay.addWidget(SectionHeader("Credenciales Supabase"))

        creds_lay.addWidget(self._flabel("URL del proyecto"))
        self._inp_url = QLineEdit()
        self._inp_url.setPlaceholderText("https://xxxxxxxxxxxx.supabase.co")
        self._inp_url.setStyleSheet(self._input_style())
        creds_lay.addWidget(self._inp_url)

        creds_lay.addWidget(self._flabel("Clave (anon o service_role)"))
        self._inp_key = QLineEdit()
        self._inp_key.setPlaceholderText("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9…")
        self._inp_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._inp_key.setStyleSheet(self._input_style())
        creds_lay.addWidget(self._inp_key)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        btn_save = AButton("Guardar", sound_type="save")
        btn_save.setStyleSheet(self._btn_style(C.BLUE))
        btn_save.clicked.connect(self._save_credentials)
        btn_row.addWidget(btn_save)

        btn_test = AButton("Verificar conexión", sound_type="click")
        btn_test.setStyleSheet(self._btn_style(C.TEXT2, outline=True))
        btn_test.clicked.connect(self._check_connection)
        btn_row.addWidget(btn_test)

        btn_row.addStretch()
        creds_lay.addLayout(btn_row)

        self._saved_creds = SavedIndicator()
        creds_lay.addWidget(self._saved_creds)

        left.addWidget(creds_card)

        # Acciones de sync
        sync_card = QFrame()
        sync_card.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border: none;
                border-radius: 14px;
            }}
        """)
        sync_lay = QVBoxLayout(sync_card)
        sync_lay.setContentsMargins(20, 18, 20, 18)
        sync_lay.setSpacing(12)

        sync_lay.addWidget(SectionHeader("Sincronizar ahora"))

        self._lbl_last = QLabel("Último sync: —")
        self._lbl_last.setStyleSheet(
            f"font-size: 12px; color: {C.TEXT3}; background: transparent;"
        )
        sync_lay.addWidget(self._lbl_last)

        sync_lay.addWidget(HDivider())

        self._btn_sync_all = AButton("☁  Sincronizar todo (subir + bajar)", sound_type="save")
        self._btn_sync_all.setStyleSheet(self._btn_style(C.BLUE))
        self._btn_sync_all.clicked.connect(lambda: self._start_sync(push_only=False))
        sync_lay.addWidget(self._btn_sync_all)

        self._btn_push = AButton("↑  Solo subir (backup al cloud)", sound_type="click")
        self._btn_push.setStyleSheet(self._btn_style(C.GREEN, outline=True))
        self._btn_push.clicked.connect(lambda: self._start_sync(push_only=True))
        sync_lay.addWidget(self._btn_push)

        self._progress_lbl = QLabel("")
        self._progress_lbl.setStyleSheet(
            f"font-size: 12px; color: {C.AMBER}; background: transparent;"
        )
        sync_lay.addWidget(self._progress_lbl)

        left.addWidget(sync_card)

        # SQL schema
        sql_card = QFrame()
        sql_card.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border: none;
                border-radius: 14px;
            }}
        """)
        sql_lay = QVBoxLayout(sql_card)
        sql_lay.setContentsMargins(20, 18, 20, 18)
        sql_lay.setSpacing(8)
        sql_lay.addWidget(SectionHeader("SQL para crear tablas en Supabase"))

        hint = QLabel(
            "Pega este SQL en el Editor SQL de tu proyecto Supabase "
            "antes de hacer el primer sync."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"font-size: 12px; color: {C.TEXT3}; background: transparent;")
        sql_lay.addWidget(hint)

        btn_show_sql = AButton("Ver SQL →", sound_type="click")
        btn_show_sql.setStyleSheet(self._btn_style(C.TEXT2, outline=True))
        btn_show_sql.clicked.connect(self._toggle_sql)
        sql_lay.addWidget(btn_show_sql)

        self._sql_view = QTextEdit()
        self._sql_view.setPlainText(_sync.SCHEMA_SQL)
        self._sql_view.setReadOnly(True)
        self._sql_view.setVisible(False)
        self._sql_view.setFixedHeight(220)
        self._sql_view.setStyleSheet(f"""
            QTextEdit {{
                background: {C.SURFACE2};
                color: {C.TEXT2};
                border: 1px solid {C.BORDER};
                border-radius: 8px;
                padding: 8px;
                font-family: monospace;
                font-size: 11px;
            }}
        """)
        sql_lay.addWidget(self._sql_view)
        left.addWidget(sql_card)
        left.addStretch()

        cols.addLayout(left, stretch=1)

        # ── Columna derecha: log ───────────────────────
        right = QVBoxLayout()
        right.setSpacing(12)
        right.addWidget(SectionHeader("Log de sincronización"))

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setStyleSheet(f"""
            QTextEdit {{
                background: {C.SURFACE};
                color: {C.TEXT2};
                border: 1.5px solid {C.BORDER};
                border-radius: 12px;
                padding: 12px;
                font-family: monospace;
                font-size: 12px;
            }}
        """)
        right.addWidget(self._log, stretch=1)

        btn_clear_log = AButton("Limpiar log", sound_type="click")
        btn_clear_log.setStyleSheet(self._btn_style(C.TEXT3, outline=True))
        btn_clear_log.clicked.connect(self._log.clear)
        right.addWidget(btn_clear_log)

        cols.addLayout(right, stretch=1)
        root.addLayout(cols, stretch=1)

    # ─────────────────────────────────────────────
    #  CREDENTIALS
    # ─────────────────────────────────────────────

    def _load_credentials(self):
        url = db.get_config("supabase_url", "")
        key = db.get_config("supabase_key", "")
        self._inp_url.setText(url)
        self._inp_key.setText(key)
        last = db.get_config("supabase_last_sync", "")
        if last:
            try:
                from datetime import datetime
                ts = datetime.fromisoformat(last).strftime("%d/%m/%Y %H:%M")
                self._lbl_last.setText(f"Último sync: {ts}")
            except Exception:
                self._lbl_last.setText(f"Último sync: {last}")

    def _guardar_credenciales(self) -> bool:
        """
        Valida y guarda URL/clave de Supabase. Retorna False (sin guardar)
        si algún campo tiene un caracter no-ASCII — una URL o un JWT con
        una "ñ" (típico de un copy-paste que salió mal) no revienta acá,
        sino varias pantallas después adentro de httpx, con un traceback
        incomprensible ("'ascii' codec can't encode..."). Mejor cortarlo
        acá con un mensaje claro.
        """
        url = self._inp_url.text().strip()
        key = self._inp_key.text().strip()

        for nombre, valor in (("URL", url), ("clave", key)):
            if valor and not db.es_ascii_valido(valor):
                self._set_dot(C.RED)
                self._lbl_status.setText("Error de conexión")
                self._log_append(
                    f"✗  La {nombre} de Supabase tiene un caracter inválido "
                    f"(¿se pegó mal? revisa que no tenga tildes o ñ) — no se guardó."
                )
                return False

        db.set_config("supabase_url", url)
        db.set_config("supabase_key", key)
        return True

    def _save_credentials(self):
        if not self._guardar_credenciales():
            return
        self._saved_creds.show_saved("✓  Credenciales guardadas")
        sound.save()

    def _check_connection(self):
        if not self._guardar_credenciales():
            return
        self._set_dot(C.AMBER)
        self._lbl_status.setText("Verificando…")
        self._log_append("Verificando conexión con Supabase…")

        worker = _CheckWorker()
        worker.finished.connect(self._on_check_done)
        worker.start()
        self._check_worker = worker

    def _on_check_done(self, ok: bool, msg: str):
        if ok:
            self._set_dot(C.GREEN)
            self._lbl_status.setText("Conectado")
            self._log_append(f"✓  {msg}")
        else:
            self._set_dot(C.RED)
            self._lbl_status.setText("Error de conexión")
            self._log_append(f"✗  {msg}")

    # ─────────────────────────────────────────────
    #  SYNC
    # ─────────────────────────────────────────────

    def _start_sync(self, push_only: bool):
        if self._worker and self._worker.isRunning():
            return

        if not self._guardar_credenciales():
            return

        mode = "Solo subir" if push_only else "Sincronización completa"
        self._log_append(f"\n── {mode} iniciada ──")
        self._progress_lbl.setText("⟳  Sincronizando…")
        self._btn_sync_all.setEnabled(False)
        self._btn_push.setEnabled(False)
        self._set_dot(C.AMBER)
        self._lbl_status.setText("Sincronizando…")

        self._worker = _SyncWorker(push_only=push_only)
        self._worker.finished.connect(self._on_sync_done)
        self._worker.start()

    def _on_sync_done(self, result: dict):
        self._btn_sync_all.setEnabled(True)
        self._btn_push.setEnabled(True)
        self._progress_lbl.setText("")

        if not result.get("ok"):
            self._set_dot(C.RED)
            self._lbl_status.setText("Error")
            self._log_append(f"✗  Error: {result.get('error', '—')}")
            sound.error()
            return

        self._set_dot(C.GREEN)
        self._lbl_status.setText("Sync OK")
        sound.save()

        lines = [
            f"✓  Sync completado  ·  {result['timestamp']}",
            f"   Estudiantes subidos : {result['students_subidos']}",
            f"   Usuarios subidos    : {result.get('usuarios_subidos', 0)}",
            f"   Registros subidos   : {result['registros_subidos']}",
            f"   Strikes subidos     : {result['strikes_subidos']}",
            f"   Log subido          : {result['log_subidos']}",
        ]
        if result.get("suspensions_subidas", 0):
            lines.append(f"   Pases subidos       : {result['suspensions_subidas']}")
        if result.get("students_bajados", 0) > 0:
            lines.append(f"   Estudiantes bajados : {result['students_bajados']}")
        if result.get("usuarios_bajados", 0) > 0:
            lines.append(f"   Usuarios bajados    : {result['usuarios_bajados']}")
        self._log_append("\n".join(lines))

        # ── Warning: tabla/columna faltante en Supabase ──────────────────
        if result.get("migration_needed"):
            items = result["migration_needed"]
            warn_lines = [
                f"",
                f"⚠  Migración pendiente en Supabase ({len(items)} elemento(s))",
            ]
            for item in items:
                warn_lines.append(f"   · {item}")
            warn_lines += [
                f"",
                f"   Ejecuta el SQL siguiente en Supabase → SQL Editor,",
                f"   luego vuelve a hacer Sync para sincronizar usuarios:",
                f"",
            ]
            sql = result.get("migration_sql", "")
            for sql_line in sql.strip().splitlines():
                warn_lines.append(f"   {sql_line}")
            self._log_append("\n".join(warn_lines))
            self._set_dot(C.AMBER)
            self._lbl_status.setText("Sync OK · migración pendiente")

        try:
            from datetime import datetime
            ts = datetime.fromisoformat(result["timestamp"]).strftime("%d/%m/%Y %H:%M")
            self._lbl_last.setText(f"Último sync: {ts}")
        except Exception:
            pass

    # ─────────────────────────────────────────────
    #  SQL TOGGLE
    # ─────────────────────────────────────────────

    def _toggle_sql(self):
        vis = not self._sql_view.isVisible()
        self._sql_view.setVisible(vis)

    # ─────────────────────────────────────────────
    #  HELPERS
    # ─────────────────────────────────────────────

    def _set_dot(self, color: str):
        self._dot.setStyleSheet(
            f"background: {color}; border-radius: 5px; border: none;"
        )

    def _log_append(self, text: str):
        self._log.append(text)

    def _flabel(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: {C.TEXT3}; background: transparent;"
        )
        return l

    def _input_style(self) -> str:
        return f"""
            QLineEdit {{
                background: {C.SURFACE2};
                border: 1.5px solid {C.BORDER};
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
                color: {C.TEXT};
            }}
            QLineEdit:focus {{
                border-color: {C.BLUE};
            }}
        """

    @staticmethod
    def _btn_style(color: str, outline: bool = False) -> str:
        if outline:
            return f"""
                QPushButton {{
                    background: transparent;
                    color: {color};
                    border: 1.5px solid {color}66;
                    border-radius: 8px;
                    padding: 8px 16px;
                    font-size: 12px; font-weight: 600;
                }}
                QPushButton:hover {{ background: {color}18; }}
                QPushButton:disabled {{ opacity: 0.4; }}
            """
        return f"""
            QPushButton {{
                background: {color};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 12px; font-weight: 700;
            }}
            QPushButton:hover {{ background: {color}CC; }}
            QPushButton:disabled {{ background: {color}66; }}
        """

    def showEvent(self, event):
        super().showEvent(event)
        self._load_credentials()
