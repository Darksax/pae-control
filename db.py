"""
db.py — Capa de base de datos para PAE Control
SQLite con WAL mode para máximo rendimiento en escaneo.
"""

import sqlite3
import os
from datetime import datetime, date, timedelta
from typing import Optional

# Ruta de la DB en ~/pae_control/pae.db
DB_DIR = os.path.join(os.path.expanduser("~"), "pae_control")
DB_PATH = os.path.join(DB_DIR, "pae.db")


def _dict_factory(cursor, row):
    """Convierte cada fila en dict para que .get() funcione en toda la app."""
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def get_conn() -> sqlite3.Connection:
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = _dict_factory
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA cache_size=-16000")  # 16MB cache
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS config (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS students (
        run              TEXT PRIMARY KEY,
        nombres          TEXT NOT NULL,
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
        fecha_importacion TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_students_curso   ON students(curso);
    CREATE INDEX IF NOT EXISTS idx_students_activo  ON students(activo, lista_espera);

    CREATE TABLE IF NOT EXISTS comidas (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre       TEXT NOT NULL,
        hora_inicio  TEXT NOT NULL,
        hora_fin     TEXT NOT NULL,
        activa       INTEGER DEFAULT 1,
        orden        INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS registros (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        run_estudiante  TEXT NOT NULL,
        fecha           TEXT NOT NULL,
        comida_id       INTEGER NOT NULL,
        comida_nombre   TEXT NOT NULL,
        timestamp       TEXT NOT NULL,
        metodo          TEXT DEFAULT 'scan',
        UNIQUE(run_estudiante, fecha, comida_id)
    );
    CREATE INDEX IF NOT EXISTS idx_reg_run_fecha   ON registros(run_estudiante, fecha);
    CREATE INDEX IF NOT EXISTS idx_reg_fecha_comida ON registros(fecha, comida_id);

    CREATE TABLE IF NOT EXISTS strikes (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        run_estudiante  TEXT NOT NULL,
        fecha           TEXT NOT NULL,
        comida_id       INTEGER NOT NULL,
        comida_nombre   TEXT NOT NULL,
        tipo            TEXT DEFAULT 'individual',
        timestamp       TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_strikes_run ON strikes(run_estudiante);

    CREATE TABLE IF NOT EXISTS status_log (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        run        TEXT NOT NULL,
        estado_ant TEXT NOT NULL,
        estado_new TEXT NOT NULL,
        timestamp  TEXT NOT NULL,
        motivo     TEXT DEFAULT ''
    );
    CREATE INDEX IF NOT EXISTS idx_statuslog_run ON status_log(run);
    CREATE INDEX IF NOT EXISTS idx_statuslog_ts  ON status_log(timestamp);
    """)

    # Configuración por defecto
    defaults = {
        "max_strikes":           "3",
        "cupos_totales":         "100",
        "nombre_establecimiento": "Liceo Bicentenario Héroes de la Concepción",
        "alerta_semana_activa":  "1",
    }
    for k, v in defaults.items():
        c.execute("INSERT OR IGNORE INTO config VALUES (?,?)", (k, v))

    # Comidas por defecto
    c.execute("SELECT COUNT(*) AS n FROM comidas")
    if c.fetchone()["n"] == 0:
        c.executemany(
            "INSERT INTO comidas (nombre, hora_inicio, hora_fin, orden) VALUES (?,?,?,?)",
            [
                ("Desayuno", "07:30", "09:30", 1),
                ("Almuerzo", "12:00", "14:30", 2),
                ("Cena",     "17:30", "20:00", 3),
            ]
        )

    # Migración para DBs existentes: agregar columnas si no existen
    migration_cols = [
        ("students",  "genero",           "TEXT DEFAULT ''"),
        ("students",  "fecha_nacimiento", "TEXT DEFAULT ''"),
        ("students",  "direccion",        "TEXT DEFAULT ''"),
        ("students",  "comuna",           "TEXT DEFAULT ''"),
        ("students",  "telefono",         "TEXT DEFAULT ''"),
        ("students",  "email",            "TEXT DEFAULT ''"),
        ("students",  "vulnerabilidad",   "TEXT DEFAULT ''"),
        ("students",  "residencia",       "TEXT DEFAULT ''"),
        ("students",  "puntaje_rsh",      "INTEGER DEFAULT NULL"),   # Registro Social de Hogares
        ("students",  "puntaje_extra",    "INTEGER DEFAULT NULL"),   # Puntaje auxiliar / otro criterio
        ("students",  "prioridad",        "INTEGER DEFAULT 0"),      # Prioridad manual (mayor = antes)
        ("registros", "comida_fria",      "INTEGER DEFAULT 0"),
    ]
    for table, col_name, col_def in migration_cols:
        try:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
        except Exception:
            pass  # Columna ya existe

    conn.commit()
    conn.close()


# ─────────────────────── CONFIG ───────────────────────

def get_config(key: str, default: str = "") -> str:
    conn = get_conn()
    row = conn.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_config(key: str, value: str):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO config VALUES (?,?)", (key, value))
    conn.commit()
    conn.close()


def get_all_config() -> dict:
    conn = get_conn()
    rows = conn.execute("SELECT key, value FROM config").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


# ─────────────────────── ESTUDIANTES ───────────────────────

def get_student(run: str) -> Optional[sqlite3.Row]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM students WHERE run=?", (run,)).fetchone()
    conn.close()
    return row


def get_all_students(include_inactive: bool = True) -> list:
    conn = get_conn()
    if include_inactive:
        rows = conn.execute(
            "SELECT * FROM students ORDER BY apellido_paterno, nombres"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM students WHERE activo=1 ORDER BY apellido_paterno, nombres"
        ).fetchall()
    conn.close()
    return rows


def search_students(query: str, limit: int = 20) -> list:
    """Búsqueda por RUN, nombre o curso."""
    conn = get_conn()
    q = f"%{query}%"
    rows = conn.execute("""
        SELECT * FROM students
        WHERE run LIKE ? OR nombres LIKE ? OR apellido_paterno LIKE ?
              OR apellido_materno LIKE ? OR curso LIKE ?
        ORDER BY apellido_paterno, nombres
        LIMIT ?
    """, (q, q, q, q, q, limit)).fetchall()
    conn.close()
    return rows


def get_students_by_curso(curso: str) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM students WHERE curso=? ORDER BY apellido_paterno, nombres",
        (curso,)
    ).fetchall()
    conn.close()
    return rows


def get_cursos() -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT curso FROM students WHERE curso!='' ORDER BY curso"
    ).fetchall()
    conn.close()
    return [r["curso"] for r in rows]


def _estado_label(activo: int, lista_espera: int) -> str:
    if activo and not lista_espera:
        return "beneficiario"
    if lista_espera:
        return "espera"
    return "no_beneficiario"


def update_student_status(run: str, activo: int, lista_espera: int,
                          motivo: str = ""):
    conn = get_conn()
    current = conn.execute(
        "SELECT activo, lista_espera FROM students WHERE run=?", (run,)
    ).fetchone()
    conn.execute(
        "UPDATE students SET activo=?, lista_espera=? WHERE run=?",
        (activo, lista_espera, run)
    )
    if current:
        estado_ant = _estado_label(current["activo"], current["lista_espera"])
        estado_new = _estado_label(activo, lista_espera)
        if estado_ant != estado_new:
            conn.execute("""
                INSERT INTO status_log (run, estado_ant, estado_new, timestamp, motivo)
                VALUES (?,?,?,?,?)
            """, (run, estado_ant, estado_new,
                  datetime.now().isoformat(timespec="seconds"), motivo))
    conn.commit()
    conn.close()


def update_student_scores(run: str, puntaje_rsh: Optional[int] = None,
                          puntaje_extra: Optional[int] = None,
                          prioridad: Optional[int] = None):
    """Actualiza puntajes y/o prioridad manual de un estudiante."""
    conn = get_conn()
    updates = {}
    if puntaje_rsh is not None:
        updates["puntaje_rsh"] = puntaje_rsh
    if puntaje_extra is not None:
        updates["puntaje_extra"] = puntaje_extra
    if prioridad is not None:
        updates["prioridad"] = prioridad
    if updates:
        set_clause = ", ".join(f"{k}=?" for k in updates)
        conn.execute(f"UPDATE students SET {set_clause} WHERE run=?",
                     list(updates.values()) + [run])
        conn.commit()
    conn.close()


def get_candidates_for_waitlist() -> list:
    """
    Retorna estudiantes que NO son PAE ni están en lista de espera,
    ordenados por prioridad para llenar la lista:
    1. puntaje_rsh ASC NULLS LAST  (menor RSH = más vulnerable = mayor prioridad)
    2. puntaje_extra DESC NULLS LAST
    3. apellido_paterno ASC (desempate)
    """
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM students
        WHERE activo = 0 AND lista_espera = 0
        ORDER BY
            CASE WHEN puntaje_rsh IS NULL THEN 1 ELSE 0 END,
            puntaje_rsh ASC,
            CASE WHEN puntaje_extra IS NULL THEN 1 ELSE 0 END,
            puntaje_extra DESC,
            apellido_paterno ASC
    """).fetchall()
    conn.close()
    return rows


def get_waitlist_sorted() -> list:
    """
    Retorna estudiantes en lista de espera ordenados por:
      1. prioridad DESC (mayor prioridad manual primero)
      2. puntaje_rsh ASC NULLS LAST (menor RSH = más vulnerable = primero)
      3. puntaje_extra DESC NULLS LAST
      4. apellido_paterno ASC (desempate alfabético)
    """
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM students
        WHERE lista_espera=1
        ORDER BY
            prioridad DESC,
            CASE WHEN puntaje_rsh IS NULL THEN 1 ELSE 0 END,
            puntaje_rsh ASC,
            CASE WHEN puntaje_extra IS NULL THEN 1 ELSE 0 END,
            puntaje_extra DESC,
            apellido_paterno ASC
    """).fetchall()
    conn.close()
    return rows


def promote_next_by_priority() -> Optional[str]:
    """
    Promueve al estudiante con mayor prioridad de la lista de espera.
    Retorna el RUN promovido, o None si la lista está vacía o no hay cupos.
    """
    conn = get_conn()
    cupos_cfg = conn.execute("SELECT value FROM config WHERE key='cupos_totales'").fetchone()
    cupos_total = int(cupos_cfg["value"]) if cupos_cfg else 100
    activos = conn.execute(
        "SELECT COUNT(*) AS n FROM students WHERE activo=1 AND lista_espera=0"
    ).fetchone()["n"]
    conn.close()

    if activos >= cupos_total:
        return None  # Sin cupos disponibles

    rows = get_waitlist_sorted()
    if not rows:
        return None

    next_run = rows[0]["run"]
    update_student_status(next_run, activo=1, lista_espera=0)
    return next_run


def upsert_student(run: str, nombres: str, apellido_paterno: str,
                   apellido_materno: str, curso: str = '', nivel: str = '',
                   programa: str = '', activo: int = 0,
                   genero: str = '', fecha_nacimiento: str = '',
                   direccion: str = '', comuna: str = '',
                   telefono: str = '', email: str = '',
                   vulnerabilidad: str = '', residencia: str = ''):
    """
    Upsert con merge inteligente:
    - Si el estudiante no existe → inserta con todos los campos
    - Si ya existe → actualiza SOLO los campos que vienen con valor
      (no pisa datos buenos de una fuente con vacíos de otra)
    """
    conn = get_conn()
    existing = conn.execute("SELECT * FROM students WHERE run=?", (run,)).fetchone()

    if not existing:
        conn.execute("""
            INSERT INTO students
                (run, nombres, apellido_paterno, apellido_materno, curso, nivel,
                 programa, activo, genero, fecha_nacimiento, direccion, comuna,
                 telefono, email, vulnerabilidad, residencia, fecha_importacion)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (run, nombres, apellido_paterno, apellido_materno, curso, nivel,
              programa, activo, genero, fecha_nacimiento, direccion, comuna,
              telefono, email, vulnerabilidad, residencia, date.today().isoformat()))
    else:
        # Actualizar solo campos con valor; nunca pisar con vacío
        updates = {}
        # Campos de identidad: siempre actualizar
        updates['nombres']          = nombres or existing['nombres']
        updates['apellido_paterno'] = apellido_paterno or existing['apellido_paterno']
        updates['apellido_materno'] = apellido_materno or existing['apellido_materno']
        updates['curso']            = curso or existing['curso']
        updates['nivel']            = nivel or existing['nivel']
        # programa: solo actualiza si viene con valor
        if programa:
            updates['programa'] = programa
        # activo: actualiza si la nueva fuente lo marca como activo (1 gana sobre 0)
        if activo == 1:
            updates['activo'] = 1
        # Campos enriquecimiento: solo pisa si vienen con valor
        for field, val in [('genero', genero), ('fecha_nacimiento', fecha_nacimiento),
                           ('direccion', direccion), ('comuna', comuna),
                           ('telefono', telefono), ('email', email),
                           ('vulnerabilidad', vulnerabilidad), ('residencia', residencia)]:
            if val:
                updates[field] = val
        updates['fecha_importacion'] = date.today().isoformat()

        set_clause = ', '.join(f"{k}=?" for k in updates)
        vals = list(updates.values()) + [run]
        conn.execute(f"UPDATE students SET {set_clause} WHERE run=?", vals)

    conn.commit()
    conn.close()


def get_status_log(limit: int = 200) -> list:
    """Log de altas/bajas: cambios de estado de estudiantes."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT sl.id, sl.run, sl.estado_ant, sl.estado_new, sl.timestamp, sl.motivo,
               st.nombres, st.apellido_paterno, st.apellido_materno, st.curso
        FROM status_log sl
        LEFT JOIN students st ON st.run = sl.run
        ORDER BY sl.timestamp DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return rows


def search_students_by_name(query: str, limit: int = 10) -> list:
    """Busca estudiantes activos por nombre o apellido (LIKE %query%)."""
    conn = get_conn()
    q = f"%{query}%"
    rows = conn.execute("""
        SELECT run, nombres, apellido_paterno, apellido_materno, curso, lista_espera
        FROM students
        WHERE activo = 1
          AND (nombres LIKE ? OR apellido_paterno LIKE ? OR apellido_materno LIKE ?)
        ORDER BY apellido_paterno, nombres
        LIMIT ?
    """, (q, q, q, limit)).fetchall()
    conn.close()
    return rows


def count_students() -> dict:
    conn = get_conn()
    total   = conn.execute("SELECT COUNT(*) AS n FROM students").fetchone()["n"]
    activos = conn.execute("SELECT COUNT(*) AS n FROM students WHERE activo=1 AND lista_espera=0").fetchone()["n"]
    espera  = conn.execute("SELECT COUNT(*) AS n FROM students WHERE lista_espera=1").fetchone()["n"]
    conn.close()
    return {"total": total, "activos": activos, "espera": espera}


# ─────────────────────── COMIDAS ───────────────────────

def get_comidas() -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM comidas WHERE activa=1 ORDER BY orden"
    ).fetchall()
    conn.close()
    return rows


def get_all_comidas() -> list:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM comidas ORDER BY orden").fetchall()
    conn.close()
    return rows


def update_comida(comida_id: int, nombre: str, hora_inicio: str,
                  hora_fin: str, activa: int):
    conn = get_conn()
    conn.execute(
        "UPDATE comidas SET nombre=?, hora_inicio=?, hora_fin=?, activa=? WHERE id=?",
        (nombre, hora_inicio, hora_fin, activa, comida_id)
    )
    conn.commit()
    conn.close()


# ─────────────────────── REGISTROS ───────────────────────

def registrar_asistencia(run: str, comida_id: int, comida_nombre: str,
                          metodo: str = "scan", comida_fria: int = 0) -> bool:
    """Registra asistencia. Retorna False si ya estaba registrado."""
    conn = get_conn()
    hoy = date.today().isoformat()
    now = datetime.now().isoformat(timespec="seconds")
    try:
        conn.execute("""
            INSERT INTO registros
                (run_estudiante, fecha, comida_id, comida_nombre, timestamp, metodo, comida_fria)
            VALUES (?,?,?,?,?,?,?)
        """, (run, hoy, comida_id, comida_nombre, now, metodo, comida_fria))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # Ya registrado
    finally:
        conn.close()


def get_registros_estudiante(run: str, fecha: str) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM registros WHERE run_estudiante=? AND fecha=? ORDER BY comida_id",
        (run, fecha)
    ).fetchall()
    conn.close()
    return rows


def get_registros_comida(fecha: str, comida_id: int) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM registros WHERE fecha=? AND comida_id=? ORDER BY timestamp",
        (fecha, comida_id)
    ).fetchall()
    conn.close()
    return rows


def count_registros_comida(fecha: str, comida_id: int) -> int:
    conn = get_conn()
    n = conn.execute(
        "SELECT COUNT(*) AS n FROM registros WHERE fecha=? AND comida_id=?",
        (fecha, comida_id)
    ).fetchone()["n"]
    conn.close()
    return n


def ya_registrado(run: str, comida_id: int, fecha: str) -> bool:
    conn = get_conn()
    n = conn.execute(
        "SELECT COUNT(*) AS n FROM registros WHERE run_estudiante=? AND comida_id=? AND fecha=?",
        (run, comida_id, fecha)
    ).fetchone()["n"]
    conn.close()
    return n > 0


# ─────────────────────── STRIKES ───────────────────────

def registrar_strike(run: str, comida_id: int, comida_nombre: str,
                     tipo: str = "individual"):
    conn = get_conn()
    now = datetime.now().isoformat(timespec="seconds")
    hoy = date.today().isoformat()
    conn.execute("""
        INSERT INTO strikes (run_estudiante, fecha, comida_id, comida_nombre, tipo, timestamp)
        VALUES (?,?,?,?,?,?)
    """, (run, hoy, comida_id, comida_nombre, tipo, now))
    conn.commit()
    conn.close()


def count_strikes(run: str) -> int:
    conn = get_conn()
    n = conn.execute(
        "SELECT COUNT(*) AS n FROM strikes WHERE run_estudiante=? AND tipo='individual'",
        (run,)
    ).fetchone()["n"]
    conn.close()
    return n


def get_strikes_estudiante(run: str) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM strikes WHERE run_estudiante=? ORDER BY timestamp DESC",
        (run,)
    ).fetchall()
    conn.close()
    return rows


# ─────────────────────── REPORTES ───────────────────────

def get_top_ausentes_semana(limit: int = 25) -> list:
    """Top estudiantes con más strikes esta semana (lunes a hoy)."""
    conn = get_conn()
    hoy = date.today()
    lunes = (hoy - timedelta(days=hoy.weekday())).isoformat()
    rows = conn.execute("""
        SELECT s.run_estudiante,
               st.nombres, st.apellido_paterno, st.apellido_materno, st.curso,
               COUNT(*) AS total_strikes
        FROM strikes s
        JOIN students st ON st.run = s.run_estudiante
        WHERE s.fecha >= ? AND s.tipo='individual'
        GROUP BY s.run_estudiante
        ORDER BY total_strikes DESC
        LIMIT ?
    """, (lunes, limit)).fetchall()
    conn.close()
    return rows


def get_top_ausentes_mes(limit: int = 25) -> list:
    conn = get_conn()
    hoy = date.today()
    primer_dia = date(hoy.year, hoy.month, 1).isoformat()
    rows = conn.execute("""
        SELECT s.run_estudiante,
               st.nombres, st.apellido_paterno, st.apellido_materno, st.curso,
               COUNT(*) AS total_strikes
        FROM strikes s
        JOIN students st ON st.run = s.run_estudiante
        WHERE s.fecha >= ? AND s.tipo='individual'
        GROUP BY s.run_estudiante
        ORDER BY total_strikes DESC
        LIMIT ?
    """, (primer_dia, limit)).fetchall()
    conn.close()
    return rows


def get_resumen_semana() -> dict:
    """Resumen para el alerta de fin de semana."""
    conn = get_conn()
    hoy = date.today()
    lunes = (hoy - timedelta(days=hoy.weekday())).isoformat()

    total_registros = conn.execute(
        "SELECT COUNT(*) AS n FROM registros WHERE fecha >= ?", (lunes,)
    ).fetchone()["n"]
    total_strikes = conn.execute(
        "SELECT COUNT(*) AS n FROM strikes WHERE fecha >= ? AND tipo='individual'",
        (lunes,)
    ).fetchone()["n"]
    estudiantes_con_strikes = conn.execute(
        "SELECT COUNT(DISTINCT run_estudiante) AS n FROM strikes WHERE fecha >= ? AND tipo='individual'",
        (lunes,)
    ).fetchone()["n"]
    conn.close()
    return {
        "total_registros": total_registros,
        "total_strikes": total_strikes,
        "estudiantes_con_strikes": estudiantes_con_strikes,
        "desde": lunes,
        "hasta": hoy.isoformat(),
    }


# ─────────────────────── REGISTRO MASIVO ───────────────────────

# ─────────────────────── CUPOS POR DÍA ───────────────────────

def _ensure_quota_table(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS quota_exceptions (
            fecha            TEXT PRIMARY KEY,
            cupos_dia        INTEGER,            -- NULL → usa cupos_totales de config
            suspendido       INTEGER DEFAULT 0,  -- 1 = sin servicio ese día
            motivo           TEXT DEFAULT '',
            comida_fria      INTEGER DEFAULT 0,  -- 1 = ración fría (no cocida)
            descripcion_fria TEXT DEFAULT ''     -- descripción de la ración fría
        )
    """)
    # Migración segura para DBs existentes
    for col, dflt in [("comida_fria", "INTEGER DEFAULT 0"),
                      ("descripcion_fria", "TEXT DEFAULT ''")]:
        try:
            conn.execute(f"ALTER TABLE quota_exceptions ADD COLUMN {col} {dflt}")
        except Exception:
            pass


def get_quota_for_date(fecha: str) -> tuple[int, bool, str]:
    """
    Retorna (cupos_efectivos, suspendido, motivo) para una fecha dada.
    Si no hay excepción, retorna (cupos_totales_config, False, '').
    """
    conn = get_conn()
    _ensure_quota_table(conn)
    row = conn.execute(
        "SELECT cupos_dia, suspendido, motivo FROM quota_exceptions WHERE fecha=?",
        (fecha,)
    ).fetchone()
    default_cupos = int(conn.execute(
        "SELECT value FROM config WHERE key='cupos_totales'"
    ).fetchone()["value"] or 100)
    conn.close()

    if row is None:
        return default_cupos, False, ''

    cupos = row["cupos_dia"] if row["cupos_dia"] is not None else default_cupos
    return cupos, bool(row["suspendido"]), row["motivo"] or ''


def get_comida_fria_for_date(fecha: str) -> tuple[bool, str]:
    """
    Retorna (comida_fria, descripcion_fria) para la fecha dada.
    """
    conn = get_conn()
    _ensure_quota_table(conn)
    row = conn.execute(
        "SELECT comida_fria, descripcion_fria FROM quota_exceptions WHERE fecha=?",
        (fecha,)
    ).fetchone()
    conn.close()
    if row is None:
        return False, ''
    return bool(row["comida_fria"]), row["descripcion_fria"] or ''


def set_quota_exception(fecha: str, cupos_dia: Optional[int],
                         suspendido: int, motivo: str,
                         comida_fria: int = 0, descripcion_fria: str = ''):
    conn = get_conn()
    _ensure_quota_table(conn)
    conn.execute("""
        INSERT OR REPLACE INTO quota_exceptions
            (fecha, cupos_dia, suspendido, motivo, comida_fria, descripcion_fria)
        VALUES (?,?,?,?,?,?)
    """, (fecha, cupos_dia, suspendido, motivo, comida_fria, descripcion_fria))
    conn.commit()
    conn.close()


def delete_quota_exception(fecha: str):
    conn = get_conn()
    _ensure_quota_table(conn)
    conn.execute("DELETE FROM quota_exceptions WHERE fecha=?", (fecha,))
    conn.commit()
    conn.close()


def get_upcoming_exceptions(from_date: str, limit: int = 60) -> list:
    conn = get_conn()
    _ensure_quota_table(conn)
    rows = conn.execute("""
        SELECT fecha, cupos_dia, suspendido, motivo, comida_fria, descripcion_fria
        FROM quota_exceptions
        WHERE fecha >= ?
        ORDER BY fecha
        LIMIT ?
    """, (from_date, limit)).fetchall()
    conn.close()
    return rows


# ─────────────────────── SUSPENSIONES INDIVIDUALES ───────────────────────

def _ensure_suspension_table(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS student_suspensions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            run          TEXT NOT NULL,
            fecha_inicio TEXT NOT NULL,
            fecha_fin    TEXT NOT NULL,
            motivo       TEXT DEFAULT '',
            creado_en    TEXT NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_susp_run ON student_suspensions(run)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_susp_fecha "
        "ON student_suspensions(fecha_inicio, fecha_fin)"
    )


def is_student_suspended(run: str, fecha: str) -> tuple[bool, str]:
    """
    Retorna (True, motivo) si el estudiante tiene una suspensión activa ese día,
    (False, '') en caso contrario.
    """
    conn = get_conn()
    _ensure_suspension_table(conn)
    row = conn.execute("""
        SELECT motivo FROM student_suspensions
        WHERE run=? AND fecha_inicio <= ? AND fecha_fin >= ?
        ORDER BY fecha_inicio DESC
        LIMIT 1
    """, (run, fecha, fecha)).fetchone()
    conn.close()
    if row:
        return True, row["motivo"] or ''
    return False, ''


def add_student_suspension(run: str, fecha_inicio: str,
                            fecha_fin: str, motivo: str):
    conn = get_conn()
    _ensure_suspension_table(conn)
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute("""
        INSERT INTO student_suspensions (run, fecha_inicio, fecha_fin, motivo, creado_en)
        VALUES (?,?,?,?,?)
    """, (run, fecha_inicio, fecha_fin, motivo, now))
    conn.commit()
    conn.close()


def delete_student_suspension(suspension_id: int):
    conn = get_conn()
    _ensure_suspension_table(conn)
    conn.execute("DELETE FROM student_suspensions WHERE id=?", (suspension_id,))
    conn.commit()
    conn.close()


def get_suspensions_for_student(run: str) -> list:
    conn = get_conn()
    _ensure_suspension_table(conn)
    rows = conn.execute("""
        SELECT id, run, fecha_inicio, fecha_fin, motivo, creado_en
        FROM student_suspensions
        WHERE run=?
        ORDER BY fecha_inicio DESC
    """, (run,)).fetchall()
    conn.close()
    return rows


def get_active_and_upcoming_suspensions(from_date: str, limit: int = 60) -> list:
    """Suspensiones activas o futuras desde from_date."""
    conn = get_conn()
    _ensure_suspension_table(conn)
    rows = conn.execute("""
        SELECT ss.id, ss.run, ss.fecha_inicio, ss.fecha_fin, ss.motivo, ss.creado_en,
               st.nombres, st.apellido_paterno, st.apellido_materno, st.curso
        FROM student_suspensions ss
        JOIN students st ON st.run = ss.run
        WHERE ss.fecha_fin >= ?
        ORDER BY ss.fecha_inicio, st.apellido_paterno
        LIMIT ?
    """, (from_date, limit)).fetchall()
    conn.close()
    return rows


def _ensure_bulk_tables(conn: sqlite3.Connection):
    """Crea tabla bulk_operations y migra columna operacion_id si no existen."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bulk_operations (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            operacion_id   TEXT UNIQUE NOT NULL,
            fecha          TEXT NOT NULL,
            comida_id      INTEGER NOT NULL,
            comida_nombre  TEXT NOT NULL,
            curso          TEXT NOT NULL,
            total_curso    INTEGER NOT NULL,
            nuevos         INTEGER NOT NULL,
            ya_registrados INTEGER NOT NULL,
            omitidos       INTEGER NOT NULL,
            timestamp      TEXT NOT NULL,
            notas          TEXT DEFAULT ''
        )
    """)
    try:
        conn.execute("ALTER TABLE registros ADD COLUMN operacion_id TEXT DEFAULT NULL")
    except Exception:
        pass  # ya existe


def get_students_bulk_preview(curso: str, comida_id: int,
                               fecha: str) -> list:
    """
    Retorna estudiantes activos del curso con estado para el preview:
    estado: 'pendiente' | 'ya_registrado' | 'lista_espera'
    """
    conn = get_conn()
    _ensure_bulk_tables(conn)
    students = conn.execute("""
        SELECT run, nombres, apellido_paterno, apellido_materno,
               activo, lista_espera
        FROM students
        WHERE curso=? AND activo=1
        ORDER BY apellido_paterno, nombres
    """, (curso,)).fetchall()

    result = []
    for s in students:
        ya_reg = conn.execute("""
            SELECT COUNT(*) AS n FROM registros
            WHERE run_estudiante=? AND comida_id=? AND fecha=?
        """, (s["run"], comida_id, fecha)).fetchone()["n"] > 0

        if s["lista_espera"]:
            estado = "lista_espera"
        elif ya_reg:
            estado = "ya_registrado"
        else:
            estado = "pendiente"

        result.append({
            "run":              s["run"],
            "nombres":          s["nombres"],
            "apellido_paterno": s["apellido_paterno"],
            "apellido_materno": s["apellido_materno"],
            "lista_espera":     s["lista_espera"],
            "estado":           estado,
        })
    conn.close()
    return result


def bulk_register(operacion_id: str, curso: str,
                   comida_id: int, comida_nombre: str,
                   fecha: str, students: list) -> dict:
    """
    Registra asistencia masiva para la lista dada.
    Solo registra los en estado 'pendiente' (no lista_espera, no ya_registrado).
    Retorna resumen: {nuevos, ya_registrados, omitidos, total}.
    """
    conn = get_conn()
    _ensure_bulk_tables(conn)
    now = datetime.now().isoformat(timespec="seconds")

    nuevos         = 0
    ya_registrados = 0
    omitidos       = 0

    for s in students:
        if s["estado"] == "ya_registrado":
            ya_registrados += 1
            continue
        if s["estado"] == "lista_espera":
            omitidos += 1
            continue
        try:
            conn.execute("""
                INSERT INTO registros
                    (run_estudiante, fecha, comida_id, comida_nombre,
                     timestamp, metodo, operacion_id)
                VALUES (?,?,?,?,?,?,?)
            """, (s["run"], fecha, comida_id, comida_nombre,
                  now, "bulk", operacion_id))
            nuevos += 1
        except sqlite3.IntegrityError:
            ya_registrados += 1

    # Guardar registro de operación
    conn.execute("""
        INSERT OR REPLACE INTO bulk_operations
            (operacion_id, fecha, comida_id, comida_nombre, curso,
             total_curso, nuevos, ya_registrados, omitidos, timestamp)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (operacion_id, fecha, comida_id, comida_nombre, curso,
          len(students), nuevos, ya_registrados, omitidos, now))

    conn.commit()
    conn.close()
    return {
        "nuevos":          nuevos,
        "ya_registrados":  ya_registrados,
        "omitidos":        omitidos,
        "total":           len(students),
    }


def get_bulk_operations(limit: int = 30) -> list:
    """Historial de operaciones masivas para trazabilidad."""
    conn = get_conn()
    _ensure_bulk_tables(conn)
    rows = conn.execute("""
        SELECT * FROM bulk_operations
        ORDER BY timestamp DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return rows
