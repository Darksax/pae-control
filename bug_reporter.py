"""
bug_reporter.py — Sistema de reporte de bugs para MiAppoderado.

Flujo:
  · Manual : usuario abre diálogo → describe el problema → Enviar
  · Auto   : crash no manejado → excepthook → auto_report_crash()

Cada reporte se guarda en ~/pae_control/bug_reports/<timestamp>.json
Y además se sube a la tabla `bug_reports` de Supabase (mismas credenciales
que el resto de la app). Así Marcelo puede consultarlos desde el dashboard.
"""

from __future__ import annotations

import json
import os
import platform
import socket
import sys
import traceback
from datetime import datetime

import db

# ── Directorios ───────────────────────────────────────────────────────────────

REPORTS_DIR = os.path.join(os.path.expanduser("~"), "pae_control", "bug_reports")
LOG_DIR     = os.path.join(os.path.expanduser("~"), "pae_control", "logs")


# ── Recolección de contexto ───────────────────────────────────────────────────

def _tail_file(path: str, n: int = 60) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return "".join(lines[-n:]).strip()
    except FileNotFoundError:
        return "(no encontrado)"
    except Exception as e:
        return f"(error: {e})"


def _collect_context(
    descripcion: str = "",
    tipo: str = "bug",
    traceback_str: str = "",
) -> dict:
    try:
        import patchnotes
        version = patchnotes.VERSION
    except Exception:
        version = "desconocida"

    try:
        import session as _sess
        usuario = f"{_sess.nombre()} ({_sess.rol()})"
    except Exception:
        usuario = "no disponible"

    return {
        "ts":          datetime.now().isoformat(timespec="seconds"),
        "tipo":        tipo,
        "descripcion": descripcion.strip(),
        "version":     version,
        "usuario":     usuario,
        "os_info":     f"{platform.system()} {platform.release()} {platform.machine()}",
        "python_v":    sys.version.split()[0],
        "hostname":    socket.gethostname(),
        "traceback":   traceback_str.strip(),
        "errors_log":  _tail_file(os.path.join(LOG_DIR, "errors.log")),
        "fault_log":   _tail_file(os.path.join(LOG_DIR, "fault.log"), 20),
    }


# ── Guardado local ────────────────────────────────────────────────────────────

def _save_local(report: dict) -> str:
    os.makedirs(REPORTS_DIR, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    tipo = report.get("tipo", "bug")[:6]
    path = os.path.join(REPORTS_DIR, f"{tipo}_{ts}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return path


# ── Envío a Supabase ──────────────────────────────────────────────────────────

def _send_supabase(report: dict) -> tuple[bool, str]:
    """
    Inserta el reporte en la tabla bug_reports de Supabase.
    Usa las mismas credenciales configuradas en la app (supabase_url / supabase_key).
    """
    try:
        from supabase import create_client  # type: ignore
        from supabase.lib.client_options import SyncClientOptions
    except ImportError:
        return False, "supabase-py no instalado"

    try:
        url = db.get_config("supabase_url", "").strip()
        key = db.get_config("supabase_key", "").strip()
    except Exception:
        return False, "No se pudo leer configuración local"

    if not url or not key:
        return False, "Sin credenciales Supabase — configúralas en Configuración"

    try:
        # Mismo motivo que sync.py: el default de supabase-py es 120s, y
        # esto corre en background pero el diálogo se queda mostrando
        # "Enviando..." todo ese tiempo si hay cualquier problema de red.
        client = create_client(url, key, options=SyncClientOptions(postgrest_client_timeout=15))
        client.table("bug_reports").insert(report).execute()
        return True, "Reporte subido a Supabase"
    except Exception as e:
        return False, f"Error Supabase: {str(e)[:120]}"


# ── API pública ───────────────────────────────────────────────────────────────

def enviar_reporte(
    descripcion: str,
    tipo: str = "bug",
    traceback_str: str = "",
) -> tuple[bool, str, str]:
    """
    Recolecta, guarda localmente y sube a Supabase.
    Retorna (supabase_ok, mensaje, ruta_local).
    """
    report = _collect_context(descripcion, tipo, traceback_str)
    ruta   = _save_local(report)
    ok, msg = _send_supabase(report)
    return ok, msg, ruta


def auto_report_crash(tp, val, tb) -> None:
    """Llamar desde sys.excepthook para reportar crashes automáticamente."""
    tb_str = "".join(traceback.format_exception(tp, val, tb))

    import threading

    def _do():
        try:
            desc = f"Crash automático: {tp.__name__}: {val}"
            enviar_reporte(desc, tipo="crash", traceback_str=tb_str)
        except Exception:
            pass

    threading.Thread(target=_do, daemon=True, name="crash-report").start()


def probar_conexion() -> tuple[bool, str]:
    """Prueba la conexión a Supabase. Usado desde Configuración."""
    ok, msg = _send_supabase({
        "ts":          datetime.now().isoformat(timespec="seconds"),
        "tipo":        "prueba",
        "descripcion": "Prueba de conexión desde Configuración",
        "version":     "—",
        "usuario":     "admin",
        "os_info":     f"{platform.system()} {platform.release()}",
        "python_v":    sys.version.split()[0],
        "hostname":    socket.gethostname(),
        "traceback":   "",
        "errors_log":  "",
        "fault_log":   "",
    })
    return ok, msg
