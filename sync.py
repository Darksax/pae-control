"""
sync.py — Sincronización Supabase para PAE Control

Estrategia: Local-first con cloud backup.
  - Push: sube students (upsert), registros y strikes nuevos (incremental por fecha).
  - Pull: baja students desde Supabase y los fusiona con upsert_student().
  - Conflictos: last-write-wins basado en fecha de importación.

Instalación requerida:
    pip install supabase
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional

import db


# ─────────────────────────────────────────────────────────
#  CLIENT
# ─────────────────────────────────────────────────────────

def get_client():
    """
    Retorna (client, None) si hay credenciales y supabase-py instalado.
    Retorna (None, msg_error) en caso contrario.
    """
    try:
        from supabase import create_client  # type: ignore
    except ImportError:
        return None, (
            "El paquete supabase-py no está instalado.\n"
            "Ejecuta en Terminal:\n"
            "  pip install supabase"
        )

    url = db.get_config("supabase_url", "").strip()
    key = db.get_config("supabase_key", "").strip()

    if not url or not key:
        return None, "Ingresa la URL y la clave de Supabase en los campos de arriba."

    try:
        client = create_client(url, key)
        return client, None
    except Exception as exc:
        return None, f"Error al conectar: {exc}"


def check_connection() -> tuple:
    """Verifica conexión real con Supabase. Retorna (ok, mensaje)."""
    client, err = get_client()
    if err:
        return False, err
    try:
        client.table("students").select("run").limit(1).execute()
        return True, "Conexión exitosa con Supabase."
    except Exception as exc:
        return False, f"Sin respuesta del servidor: {exc}"


# ─────────────────────────────────────────────────────────
#  PUSH
# ─────────────────────────────────────────────────────────

def _rows_to_dicts(rows: list) -> list:
    return [dict(r) for r in rows]


def _upsert_batched(client, table: str, rows: list, batch: int = 500) -> int:
    for i in range(0, len(rows), batch):
        client.table(table).upsert(rows[i:i + batch]).execute()
    return len(rows)


def push_students(client) -> int:
    rows = _rows_to_dicts(db.get_all_students(include_inactive=True))
    return _upsert_batched(client, "students", rows)


def push_registros(client, desde: Optional[str] = None) -> int:
    conn = db.get_conn()
    if desde:
        rows = conn.execute(
            "SELECT * FROM registros WHERE fecha >= ? ORDER BY fecha, id",
            (desde,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM registros ORDER BY fecha, id"
        ).fetchall()
    conn.close()
    return _upsert_batched(client, "registros", _rows_to_dicts(rows))


def push_strikes(client, desde: Optional[str] = None) -> int:
    conn = db.get_conn()
    if desde:
        rows = conn.execute(
            "SELECT * FROM strikes WHERE fecha >= ? ORDER BY fecha, id",
            (desde,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM strikes ORDER BY fecha, id"
        ).fetchall()
    conn.close()
    return _upsert_batched(client, "strikes", _rows_to_dicts(rows))


def push_status_log(client, desde: Optional[str] = None) -> int:
    conn = db.get_conn()
    if desde:
        rows = conn.execute(
            "SELECT * FROM status_log WHERE timestamp >= ? ORDER BY id",
            (desde,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM status_log ORDER BY id").fetchall()
    conn.close()
    return _upsert_batched(client, "status_log", _rows_to_dicts(rows))


# ─────────────────────────────────────────────────────────
#  PULL
# ─────────────────────────────────────────────────────────

def pull_students(client) -> int:
    resp = client.table("students").select("*").execute()
    rows = resp.data or []
    for r in rows:
        db.upsert_student(
            run=r["run"],
            nombres=r.get("nombres", "") or "",
            apellido_paterno=r.get("apellido_paterno", "") or "",
            apellido_materno=r.get("apellido_materno", "") or "",
            curso=r.get("curso", "") or "",
            nivel=r.get("nivel", "") or "",
            programa=r.get("programa", "") or "",
            activo=int(r.get("activo", 0) or 0),
            genero=r.get("genero", "") or "",
            fecha_nacimiento=r.get("fecha_nacimiento", "") or "",
            direccion=r.get("direccion", "") or "",
            comuna=r.get("comuna", "") or "",
            telefono=r.get("telefono", "") or "",
            email=r.get("email", "") or "",
            vulnerabilidad=r.get("vulnerabilidad", "") or "",
            residencia=r.get("residencia", "") or "",
        )
        # Actualizar campos que upsert_student no toca
        rsh   = r.get("puntaje_rsh")
        extra = r.get("puntaje_extra")
        if rsh is not None or extra is not None:
            db.update_student_scores(
                r["run"],
                puntaje_rsh=rsh,
                puntaje_extra=extra,
            )
    return len(rows)


# ─────────────────────────────────────────────────────────
#  SYNC ALL
# ─────────────────────────────────────────────────────────

def sync_all(push_only: bool = False) -> dict:
    """
    Sincronización completa.
    push_only=True: sube datos sin bajar nada (backup).
    Retorna dict con stats o {"ok": False, "error": msg}.
    """
    client, err = get_client()
    if err:
        return {"ok": False, "error": err}

    try:
        last_sync = db.get_config("supabase_last_sync", "") or None

        n_stu  = push_students(client)
        n_reg  = push_registros(client, last_sync)
        n_str  = push_strikes(client, last_sync)
        n_log  = push_status_log(client, last_sync)
        n_pull = 0

        if not push_only:
            n_pull = pull_students(client)

        now = datetime.now().isoformat(timespec="seconds")
        db.set_config("supabase_last_sync", now)

        return {
            "ok": True,
            "students_subidos":  n_stu,
            "registros_subidos": n_reg,
            "strikes_subidos":   n_str,
            "log_subidos":       n_log,
            "students_bajados":  n_pull,
            "timestamp":         now,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ─────────────────────────────────────────────────────────
#  SQL PARA SUPABASE
# ─────────────────────────────────────────────────────────

SCHEMA_SQL = """\
-- ╔══════════════════════════════════════════════╗
-- ║  PAE Control — Tablas Supabase               ║
-- ║  Pega este SQL en el SQL Editor de Supabase  ║
-- ╚══════════════════════════════════════════════╝

CREATE TABLE IF NOT EXISTS students (
    run              TEXT PRIMARY KEY,
    nombres          TEXT NOT NULL DEFAULT '',
    apellido_paterno TEXT DEFAULT '',
    apellido_materno TEXT DEFAULT '',
    curso            TEXT DEFAULT '',
    nivel            TEXT DEFAULT '',
    genero           TEXT DEFAULT '',
    fecha_nacimiento TEXT DEFAULT '',
    direccion        TEXT DEFAULT '',
    comuna           TEXT DEFAULT '',
    telefono         TEXT DEFAULT '',
    email            TEXT DEFAULT '',
    activo           INTEGER DEFAULT 1,
    lista_espera     INTEGER DEFAULT 0,
    programa         TEXT DEFAULT '',
    vulnerabilidad   TEXT DEFAULT '',
    residencia       TEXT DEFAULT '',
    fecha_importacion TEXT,
    puntaje_rsh      INTEGER,
    puntaje_extra    INTEGER,
    prioridad        INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS registros (
    id             BIGINT PRIMARY KEY,
    run_estudiante TEXT NOT NULL,
    fecha          TEXT NOT NULL,
    comida_id      INTEGER NOT NULL,
    comida_nombre  TEXT NOT NULL,
    timestamp      TEXT NOT NULL,
    metodo         TEXT DEFAULT 'scan',
    comida_fria    INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS strikes (
    id             BIGINT PRIMARY KEY,
    run_estudiante TEXT NOT NULL,
    fecha          TEXT NOT NULL,
    comida_id      INTEGER NOT NULL,
    comida_nombre  TEXT NOT NULL,
    tipo           TEXT DEFAULT 'individual',
    timestamp      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS status_log (
    id         BIGINT PRIMARY KEY,
    run        TEXT NOT NULL,
    estado_ant TEXT NOT NULL,
    estado_new TEXT NOT NULL,
    timestamp  TEXT NOT NULL,
    motivo     TEXT DEFAULT ''
);

-- Desactiva RLS (ajusta políticas según tu configuración de seguridad)
ALTER TABLE students   DISABLE ROW LEVEL SECURITY;
ALTER TABLE registros  DISABLE ROW LEVEL SECURITY;
ALTER TABLE strikes    DISABLE ROW LEVEL SECURITY;
ALTER TABLE status_log DISABLE ROW LEVEL SECURITY;
"""
