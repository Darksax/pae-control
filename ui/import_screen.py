"""
import_screen.py — Importación PAE / SIGE · PAE Control 0.9 Alpha

Flujo:
  1. Drag-and-drop o botón → selección de archivo
  2. Auto-detect formato (PAE .xlsx / SIGE .xls)
  3. Preview en tabla (primeras 10 filas)
  4. Botón Importar → ImportWorker (QThread) → progress bar + log inline
  5. Resultado: resumen sin modales, SavedIndicator

Nota: importar PAE primero, luego SIGE.
"""

import os
import html.parser
from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QProgressBar, QFrame, QAbstractItemView, QTextEdit,
    QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QDragEnterEvent, QDropEvent

try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

import db
import utils
from ui.theme   import C, sound
from ui.widgets import AButton, HDivider, SectionHeader, SavedIndicator


# ═══════════════════════════════════════════════
#  FILE PARSERS
# ═══════════════════════════════════════════════

class _HTMLTableParser(html.parser.HTMLParser):
    """SAX-style parser for SIGE .xls files (which are HTML in disguise)."""
    def __init__(self):
        super().__init__()
        self.rows = []
        self._current_row = []
        self._current_cell = []
        self._in_cell = False

    def handle_starttag(self, tag, attrs):
        if tag in ('tr',):
            self._current_row = []
        elif tag in ('td', 'th'):
            self._in_cell = True
            self._current_cell = []

    def handle_endtag(self, tag):
        if tag in ('td', 'th'):
            self._in_cell = False
            self._current_row.append(''.join(self._current_cell).strip())
        elif tag == 'tr':
            if any(c.strip() for c in self._current_row):
                self.rows.append(self._current_row)

    def handle_data(self, data):
        if self._in_cell:
            self._current_cell.append(data)


def parse_html_table(filepath: str) -> tuple:
    """Read SIGE .xls (HTML). Returns (headers, rows_as_dicts)."""
    with open(filepath, 'r', encoding='latin-1', errors='replace') as f:
        content = f.read()
    parser = _HTMLTableParser()
    parser.feed(content)
    if not parser.rows:
        return [], []
    raw_headers = [h.lower().strip() for h in parser.rows[0]]
    data = []
    for raw in parser.rows[1:]:
        row = {}
        for i, h in enumerate(raw_headers):
            row[h] = raw[i].strip() if i < len(raw) else ''
        data.append(row)
    return raw_headers, data


def parse_xlsx(filepath: str) -> tuple:
    """Read PAE .xlsx with openpyxl. Returns (headers, rows_as_dicts)."""
    if not HAS_OPENPYXL:
        return [], []
    wb = openpyxl.load_workbook(filepath, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return [], []
    raw_headers = [str(c).lower().strip() if c is not None else '' for c in rows[0]]
    data = []
    for raw in rows[1:]:
        row = {}
        for i, h in enumerate(raw_headers):
            val = raw[i]
            row[h] = str(val).strip() if val is not None else ''
        data.append(row)
    return raw_headers, data


def detect_format(headers: list) -> str:
    """Returns 'SIGE', 'PAE', or 'DESCONOCIDO'."""
    hl = [h.lower() for h in headers]
    has_run    = any('run' in h for h in hl)
    has_digito = any('dígito' in h or 'digito' in h for h in hl)
    has_rbd    = any('rbd' in h for h in hl)
    has_vuln   = any('vulnerabilidad' in h for h in hl)
    if has_rbd or (has_run and has_digito):
        return 'SIGE'
    if has_run and has_vuln:
        return 'PAE'
    return 'DESCONOCIDO'


def procesar_fila_sige(row: dict) -> Optional[dict]:
    """Build a normalized student dict from a SIGE row."""
    run_raw = ''
    dv_raw  = ''
    for k, v in row.items():
        kl = k.lower()
        if kl == 'run':
            run_raw = v
        elif 'dígito' in kl or 'digito' in kl:
            dv_raw = v

    run_digits = ''.join(c for c in run_raw if c.isdigit())
    if not run_digits:
        return None
    run_full = f"{run_digits}-{dv_raw.strip()}" if dv_raw.strip() else run_digits

    grado = ''
    letra = ''
    nombres = ''
    ap_pat  = ''
    ap_mat  = ''
    for k, v in row.items():
        kl = k.lower()
        if 'grado' in kl:
            grado = v.strip()
        elif 'letra' in kl:
            letra = v.strip()
        elif 'nombre' in kl and 'estab' not in kl:
            nombres = v.strip()
        elif 'paterno' in kl:
            ap_pat = v.strip()
        elif 'materno' in kl:
            ap_mat = v.strip()

    curso = f"{grado}{letra}".strip()

    # Telefono apoderado — columnas posibles en SIGE
    tel_apoderado = ''
    for k, v in row.items():
        kl = k.lower()
        if any(p in kl for p in ('apoderado', 'tel_apod', 'celular_apod', 'fono_apod')):
            tel_apoderado = str(v).strip()
            break

    return {
        'run':                utils.normalizar_run(run_full),
        'nombres':            nombres,
        'apellido_paterno':   ap_pat,
        'apellido_materno':   ap_mat,
        'curso':              curso,
        'activo':             0,
        'programa':           '',
        'telefono_apoderado': tel_apoderado,
    }


def procesar_fila_pae(row: dict) -> Optional[dict]:
    """Build a normalized student dict from a PAE row."""
    run_raw = ''
    for k, v in row.items():
        if 'run' in k.lower():
            run_raw = v
            break
    if not run_raw:
        return None

    nombres = ''
    ap_pat  = ''
    ap_mat  = ''
    curso   = ''
    vuln    = ''
    for k, v in row.items():
        kl = k.lower()
        if 'nombre' in kl:
            nombres = v
        elif 'paterno' in kl:
            ap_pat = v
        elif 'materno' in kl:
            ap_mat = v
        elif 'curso' in kl or 'grado' in kl:
            curso = v
        elif 'vulnerabilidad' in kl:
            vuln = v

    run_norm = utils.normalizar_run(run_raw)
    if not run_norm or not utils.validar_run(run_norm):
        return None

    # Telefono apoderado — columnas posibles en distintos formatos PAE
    tel_apoderado = ''
    for k, v in row.items():
        kl = k.lower()
        if any(p in kl for p in ('apoderado', 'tel_apod', 'celular_apod', 'fono_apod')):
            tel_apoderado = str(v).strip()
            break

    return {
        'run':                 run_norm,
        'nombres':             nombres.strip(),
        'apellido_paterno':    ap_pat.strip(),
        'apellido_materno':    ap_mat.strip(),
        'curso':               curso.strip(),
        'activo':              1,
        'programa':            'PAE',
        'vulnerabilidad':      vuln.strip(),
        'telefono_apoderado':  tel_apoderado,
    }


# ═══════════════════════════════════════════════
#  IMPORT WORKER  (non-blocking)
# ═══════════════════════════════════════════════

class ImportWorker(QThread):
    progress  = pyqtSignal(int, int)      # (processed, total)
    log       = pyqtSignal(str, str)      # (message, level)
    finished  = pyqtSignal(int, int, int) # (ok, skip, error)

    def __init__(self, rows: list, fmt: str):
        super().__init__()
        self._rows = rows
        self._fmt  = fmt

    def run(self):
        total = len(self._rows)
        ok = skip = error = 0
        for i, row in enumerate(self._rows, 1):
            try:
                if self._fmt == 'PAE':
                    est = procesar_fila_pae(row)
                elif self._fmt == 'SIGE':
                    est = procesar_fila_sige(row)
                else:
                    est = None

                if est is None:
                    skip += 1
                    self.log.emit(f"Fila {i}: RUN inválido o sin datos — omitida", "warn")
                else:
                    db.upsert_student(
                        run               = est['run'],
                        nombres           = est.get('nombres', ''),
                        apellido_paterno  = est.get('apellido_paterno', ''),
                        apellido_materno  = est.get('apellido_materno', ''),
                        curso             = est.get('curso', ''),
                        programa          = est.get('programa', ''),
                        activo            = est.get('activo', 0),
                        vulnerabilidad    = est.get('vulnerabilidad', ''),
                    )
                    tel = est.get('telefono_apoderado', '').strip()
                    if tel:
                        db.update_student_telefono_apoderado(est['run'], tel)
                    ok += 1
            except Exception as e:
                error += 1
                self.log.emit(f"Fila {i}: {e}", "error")

            self.progress.emit(i, total)

        self.finished.emit(ok, skip, error)


# ═══════════════════════════════════════════════
#  DROP ZONE
# ═══════════════════════════════════════════════

class DropZone(QFrame):
    file_dropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(130)
        self._set_idle()

        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(6)

        self._icon = QLabel("⬆")
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon.setStyleSheet(
            f"font-size: 28px; color: {C.NAVY_400}; background: transparent;"
        )
        lay.addWidget(self._icon)

        self._lbl = QLabel("Arrastra un archivo aquí")
        self._lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl.setStyleSheet(
            f"font-size: 14px; font-weight: 600; color: {C.TEXT2}; background: transparent;"
        )
        lay.addWidget(self._lbl)

        self._sub = QLabel("PAE (.xlsx) o SIGE (.xls)")
        self._sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sub.setStyleSheet(
            f"font-size: 12px; color: {C.TEXT3}; background: transparent;"
        )
        lay.addWidget(self._sub)

    def _set_idle(self):
        self.setStyleSheet(f"""
            QFrame {{
                background: {C.SURFACE};
                border: 2px dashed {C.BORDER2};
                border-radius: 16px;
            }}
        """)

    def _set_hover(self):
        self.setStyleSheet(f"""
            QFrame {{
                background: {C.NAVY_800}33;
                border: 2px dashed {C.NAVY_400};
                border-radius: 16px;
            }}
        """)

    def set_loaded(self, filename: str):
        self._lbl.setText(filename)
        self._sub.setText("Archivo cargado  ✓")
        self._icon.setText("✓")
        self._icon.setStyleSheet(
            f"font-size: 28px; color: {C.GREEN}; background: transparent;"
        )
        self.setStyleSheet(f"""
            QFrame {{
                background: {C.GREEN_DIM};
                border: 2px solid {C.GREEN}66;
                border-radius: 16px;
            }}
        """)

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._set_hover()

    def dragLeaveEvent(self, e):
        self._set_idle()

    def dropEvent(self, e: QDropEvent):
        self._set_idle()
        urls = e.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            self.file_dropped.emit(path)


# ═══════════════════════════════════════════════
#  MAIN SCREEN
# ═══════════════════════════════════════════════

FORMAT_BADGE = {
    'PAE':          (C.GREEN,     "PAE  ·  .xlsx"),
    'SIGE':         (C.NAVY_400,  "SIGE  ·  .xls"),
    'DESCONOCIDO':  (C.AMBER,     "Formato desconocido"),
}

class ImportScreen(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filepath  = None
        self._fmt       = None
        self._all_rows  = []
        self._worker    = None
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet(f"background: {C.BG};")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # ── Title ────────────────────────────────────
        title = QLabel("Importación de estudiantes")
        title.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: {C.TEXT}; background: transparent;"
        )
        root.addWidget(title)

        hint = QLabel(
            "Importa primero el archivo PAE (.xlsx), "
            "luego el SIGE (.xls) para enriquecer los datos."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(
            f"font-size: 12px; color: {C.GOLD_500}; background: transparent;"
        )
        root.addWidget(hint)

        # ── Top row: drop zone + actions ─────────────
        top_row = QHBoxLayout()
        top_row.setSpacing(14)

        self._drop = DropZone()
        self._drop.file_dropped.connect(self._on_file)
        top_row.addWidget(self._drop, stretch=1)

        right_col = QVBoxLayout()
        right_col.setSpacing(10)
        right_col.setAlignment(Qt.AlignmentFlag.AlignTop)

        btn_open = AButton("Seleccionar archivo…", sound_type="click")
        btn_open.setStyleSheet(f"""
            QPushButton {{
                background: {C.NAVY_700};
                color: {C.TEXT};
                border: none; border-radius: 10px;
                padding: 11px 22px;
                font-size: 13px; font-weight: 600;
            }}
            QPushButton:hover {{ background: {C.NAVY_600}; }}
        """)
        btn_open.clicked.connect(self._open_dialog)
        right_col.addWidget(btn_open)

        self._fmt_badge = QLabel("Sin archivo")
        self._fmt_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._fmt_badge.setStyleSheet(f"""
            QLabel {{
                background: {C.SURFACE2};
                color: {C.TEXT3};
                border: 1.5px solid {C.BORDER};
                border-radius: 10px;
                padding: 8px 16px;
                font-size: 12px; font-weight: 600;
            }}
        """)
        right_col.addWidget(self._fmt_badge)
        right_col.addStretch()
        top_row.addLayout(right_col)
        root.addLayout(top_row)

        # ── Preview ───────────────────────────────────
        prev_hdr = QHBoxLayout()
        prev_hdr.addWidget(SectionHeader("Vista previa"))
        prev_hdr.addStretch()
        self._lbl_rowcount = QLabel("")
        self._lbl_rowcount.setStyleSheet(
            f"font-size: 11px; color: {C.TEXT3}; background: transparent;"
        )
        prev_hdr.addWidget(self._lbl_rowcount)
        root.addLayout(prev_hdr)

        self._preview = QTableWidget()
        self._preview.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._preview.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._preview.verticalHeader().setVisible(False)
        self._preview.setAlternatingRowColors(True)
        self._preview.setShowGrid(False)
        self._preview.setMaximumHeight(210)
        self._preview.setStyleSheet(f"""
            QTableWidget {{
                background: {C.SURFACE};
                border: 1.5px solid {C.BORDER};
                border-radius: 10px;
                outline: none;
            }}
            QTableWidget::item {{
                padding: 7px 12px;
                border: none;
                color: {C.TEXT2};
                font-size: 12px;
            }}
            QTableWidget::item:selected {{
                background: {C.NAVY_700};
                color: {C.TEXT};
            }}
            QTableWidget::item:alternate {{ background: {C.SURFACE2}; }}
        """)
        root.addWidget(self._preview)

        # ── Import button + progress ──────────────────
        import_row = QHBoxLayout()
        import_row.setSpacing(14)

        self._btn_import = AButton("Importar estudiantes", sound_type="save")
        self._btn_import.setEnabled(False)
        self._btn_import.setStyleSheet(self._import_btn_style(enabled=False))
        self._btn_import.clicked.connect(self._run_import)
        import_row.addWidget(self._btn_import)

        self._progress = QProgressBar()
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(6)
        self._progress.setVisible(False)
        import_row.addWidget(self._progress, stretch=1)
        root.addLayout(import_row)

        # ── Log ──────────────────────────────────────
        log_hdr = QHBoxLayout()
        log_hdr.addWidget(SectionHeader("Log de importación"))
        log_hdr.addStretch()

        btn_clear = AButton("Limpiar", sound_type="click")
        btn_clear.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT3};
                border: none; font-size: 11px; padding: 2px 8px;
            }}
            QPushButton:hover {{ color: {C.TEXT2}; }}
        """)
        btn_clear.clicked.connect(lambda: self._log.clear())
        log_hdr.addWidget(btn_clear)
        root.addLayout(log_hdr)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(160)
        self._log.setStyleSheet(f"""
            QTextEdit {{
                background: {C.SURFACE};
                border: 1.5px solid {C.BORDER};
                border-radius: 10px;
                color: {C.TEXT2};
                font-size: 11px;
                font-family: 'SF Mono', 'Consolas', monospace;
                padding: 8px 12px;
            }}
        """)
        root.addWidget(self._log)

        self._saved_ind = SavedIndicator()
        root.addWidget(self._saved_ind)

    # ─────────────────────────────────────────────
    #  FILE HANDLING
    # ─────────────────────────────────────────────

    def _open_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo de estudiantes",
            "", "Archivos de datos (*.xlsx *.xls)"
        )
        if path:
            self._on_file(path)

    def _on_file(self, path: str):
        self._filepath = path
        ext = os.path.splitext(path)[1].lower()
        filename = os.path.basename(path)
        try:
            if ext == '.xls':
                headers, self._all_rows = parse_html_table(path)
            elif ext == '.xlsx':
                headers, self._all_rows = parse_xlsx(path)
            else:
                self._log_line(f"Extensión no soportada: {ext}", "error")
                return

            self._fmt = detect_format(headers)
            self._drop.set_loaded(filename)
            self._update_fmt_badge()
            self._fill_preview(headers, self._all_rows[:10])

            total = len(self._all_rows)
            self._lbl_rowcount.setText(
                f"{total} filas detectadas · mostrando primeras 10"
            )
            self._log_line(
                f"Archivo cargado: {filename}  ({total} filas, formato {self._fmt})", "ok"
            )

            enabled = self._fmt in ('PAE', 'SIGE') and total > 0
            self._btn_import.setEnabled(enabled)
            self._btn_import.setStyleSheet(self._import_btn_style(enabled=enabled))
            sound.click()

        except Exception as e:
            self._log_line(f"Error al leer archivo: {e}", "error")
            sound.error()

    def _update_fmt_badge(self):
        color, label = FORMAT_BADGE.get(self._fmt, (C.AMBER, self._fmt))
        self._fmt_badge.setText(label)
        self._fmt_badge.setStyleSheet(f"""
            QLabel {{
                background: {color}22;
                color: {color};
                border: 1.5px solid {color}66;
                border-radius: 10px;
                padding: 8px 16px;
                font-size: 12px; font-weight: 600;
            }}
        """)

    def _fill_preview(self, headers: list, rows: list):
        self._preview.setColumnCount(len(headers))
        self._preview.setHorizontalHeaderLabels(headers)
        self._preview.setRowCount(len(rows))
        for r_idx, row in enumerate(rows):
            for c_idx, h in enumerate(headers):
                item = QTableWidgetItem(row.get(h, ''))
                self._preview.setItem(r_idx, c_idx, item)
        self._preview.resizeColumnsToContents()

    # ─────────────────────────────────────────────
    #  IMPORT
    # ─────────────────────────────────────────────

    def _run_import(self):
        if not self._all_rows or self._fmt not in ('PAE', 'SIGE'):
            return
        self._btn_import.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setMaximum(len(self._all_rows))
        self._progress.setValue(0)
        self._log.clear()
        self._log_line(
            f"Iniciando importación {self._fmt}  ({len(self._all_rows)} filas)…", "info"
        )
        self._worker = ImportWorker(self._all_rows, self._fmt)
        self._worker.progress.connect(self._on_progress)
        self._worker.log.connect(self._log_line)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, done: int, total: int):
        self._progress.setValue(done)

    def _on_finished(self, ok: int, skip: int, error: int):
        self._progress.setVisible(False)
        self._btn_import.setEnabled(True)
        self._btn_import.setStyleSheet(self._import_btn_style(enabled=True))
        msg = f"Completado — {ok} importados · {skip} omitidos · {error} errores"
        self._log_line(msg, "ok" if error == 0 else "warn")
        if error == 0:
            self._saved_ind.show_saved(f"✓  {ok} estudiantes importados")
            sound.save()
        else:
            self._saved_ind.show_error(f"⚠  {ok} ok  ·  {error} con error")
            sound.error()

    # ─────────────────────────────────────────────
    #  HELPERS
    # ─────────────────────────────────────────────

    LOG_COLORS = {
        "ok":    C.GREEN,
        "warn":  C.AMBER,
        "error": C.RED,
        "info":  C.TEXT2,
    }

    def _log_line(self, text: str, level: str = "info"):
        color = self.LOG_COLORS.get(level, C.TEXT2)
        self._log.append(
            f'<span style="color:{color}; font-size:11px;">{text}</span>'
        )

    @staticmethod
    def _import_btn_style(enabled: bool) -> str:
        if enabled:
            return f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 {C.NAVY_700}, stop:1 {C.NAVY_800});
                    color: {C.TEXT};
                    border: none; border-radius: 10px;
                    padding: 11px 28px;
                    font-size: 13px; font-weight: 700;
                }}
                QPushButton:hover {{ background: {C.NAVY_600}; }}
                QPushButton:pressed {{ background: {C.NAVY_800}; }}
            """
        return f"""
            QPushButton {{
                background: {C.SURFACE2};
                color: {C.TEXT3};
                border: none; border-radius: 10px;
                padding: 11px 28px;
                font-size: 13px; font-weight: 700;
            }}
        """
