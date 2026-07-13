"""
sync.py — Sincronización Supabase para MiAppoderado

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
from debug_mode import logger


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
        logger.exception("check_connection() falló")
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


def push_usuarios(client) -> int:
    """Sube la tabla de usuarios (PINs ya hasheados — no hay texto plano)."""
    conn = db.get_conn()
    rows = conn.execute(
        "SELECT id, nombre, pin_hash, rol, activo, creado_en FROM usuarios ORDER BY id"
    ).fetchall()
    conn.close()
    return _upsert_batched(client, "usuarios", _rows_to_dicts(rows))


def pull_usuarios(client) -> int:
    """Baja usuarios desde Supabase y los upsertea localmente (sin tocar admin local)."""
    resp = client.table("usuarios").select("*").execute()
    rows = resp.data or []
    if not rows:
        return 0
    conn = db.get_conn()
    for r in rows:
        existing = conn.execute(
            "SELECT id FROM usuarios WHERE id=?", (r["id"],)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE usuarios
                   SET nombre=?, pin_hash=?, rol=?, activo=?, creado_en=?
                   WHERE id=?""",
                (r["nombre"], r["pin_hash"], r["rol"],
                 int(r.get("activo", 1)), r.get("creado_en", ""), r["id"])
            )
        else:
            conn.execute(
                """INSERT INTO usuarios (id, nombre, pin_hash, rol, activo, creado_en)
                   VALUES (?,?,?,?,?,?)""",
                (r["id"], r["nombre"], r["pin_hash"], r["rol"],
                 int(r.get("activo", 1)), r.get("creado_en", ""))
            )
    conn.commit()
    conn.close()
    return len(rows)


def _supabase_has_column(client, table: str, column: str) -> bool:
    """
    Detecta si una columna existe en una tabla de Supabase haciendo un SELECT puntual.
    Retorna True si la columna existe, False si da error (columna inexistente).
    """
    try:
        client.table(table).select(column).limit(1).execute()
        return True
    except Exception:
        return False


def push_registros(client, desde: Optional[str] = None,
                   has_periodo: bool = True) -> int:
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
    # operacion_id es columna local de registro masivo — no existe en Supabase
    dicts = _rows_to_dicts(rows)
    for r in dicts:
        r.pop("operacion_id", None)
        if not has_periodo:
            r.pop("periodo", None)
    return _upsert_batched(client, "registros", dicts)


def push_strikes(client, desde: Optional[str] = None,
                 has_periodo: bool = True) -> int:
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
    dicts = _rows_to_dicts(rows)
    if not has_periodo:
        for r in dicts:
            r.pop("periodo", None)
    return _upsert_batched(client, "strikes", dicts)


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


def push_suspensions(client, desde: Optional[str] = None,
                     has_periodo: bool = True) -> int:
    """Sube registros de Inspectoría (student_suspensions) a Supabase."""
    conn = db.get_conn()
    if desde:
        rows = conn.execute(
            "SELECT * FROM student_suspensions WHERE fecha_inicio >= ? ORDER BY id",
            (desde,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM student_suspensions ORDER BY id"
        ).fetchall()
    conn.close()
    dicts = _rows_to_dicts(rows)
    if not has_periodo:
        for r in dicts:
            r.pop("periodo", None)
    return _upsert_batched(client, "student_suspensions", dicts)


# ─────────────────────────────────────────────────────────
#  CONFIG COMPARTIDA (asistente IA)
# ─────────────────────────────────────────────────────────
# A diferencia del resto de la tabla config (tokens de WhatsApp, SMTP, la
# propia clave de Supabase — nunca se sincronizan, ver push_* arriba),
# estas dos claves SÍ se comparten a propósito entre todas las instalaciones
# de MiAppoderado vía una tabla dedicada, para no tener que pegar el mismo
# reglamento/clave de Gemini a mano en cada equipo.
SHARED_CONFIG_KEYS = ["gemini_api_key", "gemini_reglamento"]


def push_shared_config(client) -> int:
    now = datetime.now().isoformat(timespec="seconds")
    rows = [
        {"key": k, "value": db.get_config(k, ""), "updated_at": now}
        for k in SHARED_CONFIG_KEYS
    ]
    return _upsert_batched(client, "shared_config", rows)


def pull_shared_config(client) -> int:
    resp = client.table("shared_config").select("*").execute()
    rows = resp.data or []
    n = 0
    for r in rows:
        if r.get("key") in SHARED_CONFIG_KEYS:
            db.set_config(r["key"], r.get("value") or "")
            n += 1
    return n


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
        tel = (r.get("telefono_apoderado") or "").strip()
        if tel:
            db.update_student_telefono_apoderado(r["run"], tel)
    return len(rows)


# ─────────────────────────────────────────────────────────
#  SYNC ALL
# ─────────────────────────────────────────────────────────

def sync_all(push_only: bool = False) -> dict:
    """
    Sincronización completa.
    push_only=True: sube datos sin bajar nada (backup).
    Retorna dict con stats o {"ok": False, "error": msg}.

    Detección automática de columna 'periodo':
      Si la columna no existe en Supabase, el push omite ese campo y
      agrega una entrada 'migration_needed' con el SQL a ejecutar.
    """
    client, err = get_client()
    if err:
        return {"ok": False, "error": err}

    try:
        last_sync = db.get_config("supabase_last_sync", "") or None

        # ── Detección de tabla 'usuarios' ────────────────────────────────
        has_usuarios_table = _supabase_has_column(client, "usuarios", "id")

        # ── Detección de tabla 'shared_config' (asistente IA) ────────────
        has_shared_config_table = _supabase_has_column(client, "shared_config", "key")

        # ── Detección de columna 'periodo' ──────────────────────────────
        reg_has_periodo = _supabase_has_column(client, "registros",           "periodo")
        sus_has_periodo = _supabase_has_column(client, "student_suspensions", "periodo")
        str_has_periodo = _supabase_has_column(client, "strikes",             "periodo")

        migration_warnings = []
        migration_sqls     = []
        if not reg_has_periodo:
            migration_warnings.append("registros (columna periodo)")
            migration_sqls.append(PERIODO_MIGRATION_SQL)
        if not sus_has_periodo:
            migration_warnings.append("student_suspensions (columna periodo)")
            if PERIODO_MIGRATION_SQL not in migration_sqls:
                migration_sqls.append(PERIODO_MIGRATION_SQL)
        if not str_has_periodo:
            migration_warnings.append("strikes (columna periodo)")
            if PERIODO_MIGRATION_SQL not in migration_sqls:
                migration_sqls.append(PERIODO_MIGRATION_SQL)
        if not has_usuarios_table:
            migration_warnings.append("usuarios (tabla nueva)")
            migration_sqls.append(USUARIOS_SCHEMA_SQL)
        if not has_shared_config_table:
            migration_warnings.append("shared_config (tabla nueva — asistente IA)")
            migration_sqls.append(SHARED_CONFIG_SCHEMA_SQL)

        # ── Push ────────────────────────────────────────────────────────
        n_stu  = push_students(client)
        n_usu  = push_usuarios(client) if has_usuarios_table else 0
        n_reg  = push_registros(client, last_sync, has_periodo=reg_has_periodo)
        n_str  = push_strikes(client, last_sync, has_periodo=str_has_periodo)
        n_log  = push_status_log(client, last_sync)
        n_sus  = push_suspensions(client, last_sync, has_periodo=sus_has_periodo)
        n_shared_push = push_shared_config(client) if has_shared_config_table else 0
        n_pull_stu = 0
        n_pull_usu = 0
        n_shared_pull = 0

        if not push_only:
            n_pull_stu = pull_students(client)
            n_pull_usu = pull_usuarios(client) if has_usuarios_table else 0
            n_shared_pull = pull_shared_config(client) if has_shared_config_table else 0

        now = datetime.now().isoformat(timespec="seconds")
        db.set_config("supabase_last_sync", now)

        result = {
            "ok": True,
            "students_subidos":      n_stu,
            "usuarios_subidos":      n_usu,
            "registros_subidos":     n_reg,
            "strikes_subidos":       n_str,
            "log_subidos":           n_log,
            "suspensions_subidas":   n_sus,
            "students_bajados":      n_pull_stu,
            "usuarios_bajados":      n_pull_usu,
            "asistente_config_subido":  n_shared_push,
            "asistente_config_bajado":  n_shared_pull,
            "timestamp":             now,
        }

        # Advertencia si falta tabla/columna en Supabase
        if migration_warnings:
            result["migration_needed"] = migration_warnings
            result["migration_sql"]    = "\n\n".join(migration_sqls)

        return result

    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ─────────────────────────────────────────────────────────
#  SQL PARA SUPABASE
# ─────────────────────────────────────────────────────────

SCHEMA_SQL = """\
-- ╔══════════════════════════════════════════════╗
-- ║  MiAppoderado — Tablas Supabase               ║
-- ║  Pega este SQL en el SQL Editor de Supabase  ║
-- ╚══════════════════════════════════════════════╝

CREATE TABLE IF NOT EXISTS usuarios (
    id        BIGINT PRIMARY KEY,
    nombre    TEXT NOT NULL,
    pin_hash  TEXT NOT NULL,
    rol       TEXT NOT NULL DEFAULT 'pae',
    activo    INTEGER DEFAULT 1,
    creado_en TEXT NOT NULL DEFAULT ''
);

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
    puntaje_rsh         INTEGER,
    puntaje_extra       INTEGER,
    prioridad           INTEGER DEFAULT 0,
    telefono_apoderado  TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS registros (
    id             BIGINT PRIMARY KEY,
    run_estudiante TEXT NOT NULL,
    fecha          TEXT NOT NULL,
    comida_id      INTEGER NOT NULL,
    comida_nombre  TEXT NOT NULL,
    timestamp      TEXT NOT NULL,
    metodo         TEXT DEFAULT 'scan',
    comida_fria    INTEGER DEFAULT 0,
    periodo        TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS strikes (
    id             BIGINT PRIMARY KEY,
    run_estudiante TEXT NOT NULL,
    fecha          TEXT NOT NULL,
    comida_id      INTEGER NOT NULL,
    comida_nombre  TEXT NOT NULL,
    tipo           TEXT DEFAULT 'individual',
    timestamp      TEXT NOT NULL,
    periodo        TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS status_log (
    id         BIGINT PRIMARY KEY,
    run        TEXT NOT NULL,
    estado_ant TEXT NOT NULL,
    estado_new TEXT NOT NULL,
    timestamp  TEXT NOT NULL,
    motivo     TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS student_suspensions (
    id           BIGINT PRIMARY KEY,
    run          TEXT NOT NULL,
    fecha_inicio TEXT NOT NULL,
    fecha_fin    TEXT NOT NULL,
    motivo       TEXT DEFAULT '',
    creado_en    TEXT DEFAULT '',
    tipo         TEXT DEFAULT 'suspension',
    firmado      INTEGER DEFAULT 0,
    firmado_en   TEXT DEFAULT '',
    firmado_por  TEXT DEFAULT '',
    periodo      TEXT DEFAULT ''
);

-- Config compartida entre instalaciones (SOLO clave de Gemini + reglamento,
-- a propósito — el resto de config, ej. tokens de WhatsApp/SMTP, nunca sube)
CREATE TABLE IF NOT EXISTS shared_config (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL DEFAULT '',
    updated_at TEXT DEFAULT ''
);

-- Desactiva RLS (ajusta políticas según tu configuración de seguridad)
ALTER TABLE students             DISABLE ROW LEVEL SECURITY;
ALTER TABLE registros            DISABLE ROW LEVEL SECURITY;
ALTER TABLE strikes              DISABLE ROW LEVEL SECURITY;
ALTER TABLE status_log           DISABLE ROW LEVEL SECURITY;
ALTER TABLE student_suspensions  DISABLE ROW LEVEL SECURITY;
ALTER TABLE shared_config        DISABLE ROW LEVEL SECURITY;
"""

# SQL para migrar un Supabase existente (tablas ya creadas, faltan columnas)
MIGRATION_SQL = """\
-- ╔══════════════════════════════════════════════════════════╗
-- ║  MiAppoderado — Migración incremental Supabase            ║
-- ║  Ejecutar en SQL Editor si las tablas ya existen         ║
-- ╚══════════════════════════════════════════════════════════╝

-- 1. students: agregar telefono_apoderado
ALTER TABLE students
    ADD COLUMN IF NOT EXISTS telefono_apoderado TEXT DEFAULT '';

-- 2. student_suspensions: agregar columnas de firma e inspectoría
ALTER TABLE student_suspensions
    ADD COLUMN IF NOT EXISTS creado_en   TEXT    DEFAULT '';
ALTER TABLE student_suspensions
    ADD COLUMN IF NOT EXISTS tipo        TEXT    DEFAULT 'suspension';
ALTER TABLE student_suspensions
    ADD COLUMN IF NOT EXISTS firmado     INTEGER DEFAULT 0;
ALTER TABLE student_suspensions
    ADD COLUMN IF NOT EXISTS firmado_en  TEXT    DEFAULT '';
ALTER TABLE student_suspensions
    ADD COLUMN IF NOT EXISTS firmado_por TEXT    DEFAULT '';

-- 3. Períodos (v1.4.0-beta)
ALTER TABLE registros
    ADD COLUMN IF NOT EXISTS periodo TEXT DEFAULT '';
ALTER TABLE student_suspensions
    ADD COLUMN IF NOT EXISTS periodo TEXT DEFAULT '';
ALTER TABLE strikes
    ADD COLUMN IF NOT EXISTS periodo TEXT DEFAULT '';
"""

# SQL específico para agregar la columna periodo (mostrado en UI cuando falta)
PERIODO_MIGRATION_SQL = """\
-- MiAppoderado v1.4.0-beta — Agregar columna periodo
-- Pega esto en el SQL Editor de Supabase y ejecuta:

ALTER TABLE registros
    ADD COLUMN IF NOT EXISTS periodo TEXT DEFAULT '';

ALTER TABLE student_suspensions
    ADD COLUMN IF NOT EXISTS periodo TEXT DEFAULT '';

ALTER TABLE strikes
    ADD COLUMN IF NOT EXISTS periodo TEXT DEFAULT '';
"""

# SQL para crear la tabla de usuarios en Supabase (mostrado en UI cuando falta)
USUARIOS_SCHEMA_SQL = """\
-- MiAppoderado v1.4.0-beta — Crear tabla usuarios
-- Pega esto en el SQL Editor de Supabase y ejecuta:

CREATE TABLE IF NOT EXISTS usuarios (
    id        BIGINT PRIMARY KEY,
    nombre    TEXT NOT NULL,
    pin_hash  TEXT NOT NULL,
    rol       TEXT NOT NULL DEFAULT 'pae',
    activo    INTEGER DEFAULT 1,
    creado_en TEXT NOT NULL DEFAULT ''
);

ALTER TABLE usuarios DISABLE ROW LEVEL SECURITY;
"""

# SQL para crear la tabla shared_config en Supabase (mostrado en UI cuando falta)
SHARED_CONFIG_SCHEMA_SQL = """\
-- MiAppoderado — Crear tabla shared_config (asistente IA)
-- Pega esto en el SQL Editor de Supabase y ejecuta:

CREATE TABLE IF NOT EXISTS shared_config (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL DEFAULT '',
    updated_at TEXT DEFAULT ''
);

ALTER TABLE shared_config DISABLE ROW LEVEL SECURITY;
"""
