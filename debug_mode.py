"""
debug_mode.py — Registro de diagnóstico de MiAppoderado.

SIEMPRE activo (costo cero):
  · faulthandler  →  ~/pae_control/logs/fault.log    (crashes nativos: SIGSEGV, etc.)
  · excepthook    →  ~/pae_control/logs/errors.log   (excepciones Python no manejadas)

MODO DEBUG (lanzar con --debug o PAE_DEBUG=1):
  · logging nivel DEBUG de toda la app  →  logs/debug_AAAAMMDD_HHMMSS.log
  · mensajes internos de Qt (qInstallMessageHandler) al mismo log

Uso en cualquier módulo de la app:
    from debug_mode import logger
    logger.debug("mensaje")
"""

import datetime
import faulthandler
import logging
import os
import sys
import traceback

LOG_DIR = os.path.join(os.path.expanduser("~"), "pae_control", "logs")

logger = logging.getLogger("pae")

# faulthandler exige que el archivo siga abierto durante toda la sesión
_fault_fh = None


def is_debug() -> bool:
    return "--debug" in sys.argv or os.environ.get("PAE_DEBUG") == "1"


def log_exception(context: str) -> None:
    """
    Escribe el traceback COMPLETO de la excepción actual a errors.log,
    siempre — a diferencia de logger.exception(), que en modo normal (sin
    --debug/PAE_DEBUG=1) no tiene ningún handler con archivo detrás y no
    deja rastro. Pensado para excepciones que se atrapan localmente (un
    try/except que solo muestra str(exc) al usuario) y por eso nunca llegan
    al excepthook global de más arriba — sin esto, un error real solo se ve
    como un mensaje corto en la UI, sin traceback, imposible de diagnosticar
    a distancia.
    """
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(os.path.join(LOG_DIR, "errors.log"), "a", encoding="utf-8") as f:
            f.write(f"\n=== {datetime.datetime.now():%Y-%m-%d %H:%M:%S} — {context} ===\n")
            traceback.print_exc(file=f)
    except Exception:
        pass


def init() -> None:
    """Llamar ANTES de importar PyQt6 (captura crashes durante el import)."""
    global _fault_fh
    os.makedirs(LOG_DIR, exist_ok=True)

    # ── 1. Crashes nativos ──────────────────────────────────────────────────
    _fault_fh = open(os.path.join(LOG_DIR, "fault.log"), "a", encoding="utf-8")
    _fault_fh.write(
        f"\n=== sesión {datetime.datetime.now():%Y-%m-%d %H:%M:%S} "
        f"(pid {os.getpid()}, frozen={getattr(sys, 'frozen', False)}, "
        f"debug={is_debug()}) ===\n"
    )
    _fault_fh.flush()
    faulthandler.enable(file=_fault_fh, all_threads=True)

    # ── 2. Excepciones Python no manejadas ──────────────────────────────────
    def _hook(tp, val, tb):
        with open(os.path.join(LOG_DIR, "errors.log"), "a", encoding="utf-8") as f:
            f.write(f"\n=== {datetime.datetime.now():%Y-%m-%d %H:%M:%S} ===\n")
            traceback.print_exception(tp, val, tb, file=f)
        traceback.print_exception(tp, val, tb)  # también a stderr
        # Auto-reporte de crash en background (no bloquea el proceso)
        try:
            import bug_reporter
            bug_reporter.auto_report_crash(tp, val, tb)
        except Exception:
            pass

    sys.excepthook = _hook

    # ── 3. Logging de la app ────────────────────────────────────────────────
    if is_debug():
        logfile = os.path.join(
            LOG_DIR, f"debug_{datetime.datetime.now():%Y%m%d_%H%M%S}.log"
        )
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
            handlers=[
                logging.FileHandler(logfile, encoding="utf-8"),
                logging.StreamHandler(sys.stderr),
            ],
        )
        logger.info("MODO DEBUG activo — log: %s", logfile)
        logger.info("Python %s", sys.version)
        logger.info("Ejecutable: %s", sys.executable)
        logger.info("argv: %s", sys.argv)
    else:
        logging.basicConfig(level=logging.WARNING)


def attach_qt() -> None:
    """Llamar DESPUÉS de crear QApplication: redirige mensajes internos de Qt."""
    if not is_debug():
        return
    try:
        from PyQt6.QtCore import QtMsgType, qInstallMessageHandler

        _levels = {
            QtMsgType.QtDebugMsg:    logging.DEBUG,
            QtMsgType.QtInfoMsg:     logging.INFO,
            QtMsgType.QtWarningMsg:  logging.WARNING,
            QtMsgType.QtCriticalMsg: logging.ERROR,
            QtMsgType.QtFatalMsg:    logging.CRITICAL,
        }

        def _qt_handler(msg_type, _ctx, msg):
            logging.getLogger("qt").log(_levels.get(msg_type, logging.INFO), msg)

        qInstallMessageHandler(_qt_handler)
        logger.debug("Handler de mensajes Qt instalado")
    except Exception as exc:
        logger.warning("No se pudo instalar handler Qt: %s", exc)
