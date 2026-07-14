"""
db.py — Capa de base de datos para MiAppoderado
SQLite con WAL mode para máximo rendimiento en escaneo.
"""

import sqlite3
import os
import unicodedata
from datetime import datetime, date, timedelta
from typing import Optional


def _normalize_str(s: str) -> str:
    """Normaliza texto para búsqueda: minúsculas + sin tildes/diacríticos.
    Ejemplo: 'Tomás' → 'tomas', 'López' → 'lopez'.
    """
    if not s:
        return ''
    nfd = unicodedata.normalize('NFD', s.lower())
    return ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')

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
    # Función SQL para búsqueda sin tildes (buscar "tomas" encuentra "Tomás")
    conn.create_function('normalize', 1, _normalize_str)
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

    CREATE TABLE IF NOT EXISTS cursos_nombres (
        nivel    INTEGER NOT NULL,
        seccion  TEXT    NOT NULL,
        nombre   TEXT    NOT NULL,
        PRIMARY KEY (nivel, seccion)
    );

    CREATE TABLE IF NOT EXISTS name_change_log (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        run          TEXT NOT NULL,
        campo        TEXT NOT NULL,
        valor_ant    TEXT NOT NULL,
        valor_nuevo  TEXT NOT NULL,
        tipo_cambio  TEXT NOT NULL,
        motivo       TEXT NOT NULL,
        timestamp    TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_namelog_run ON name_change_log(run);
    """)

    # Seed opcional de credenciales para builds privados (Supabase, Gemini,
    # etc.) — ver config_default.example.json. NUNCA se sube al repo (está
    # en .gitignore); solo existe en un build armado a mano para uso propio,
    # instalado desde fuera de GitHub. Corre ANTES que los defaults de abajo
    # a propósito: para una clave que está en ambos (ej. nombre_establecimiento)
    # el INSERT OR IGNORE del seed gana porque llega primero — si fuera al
    # revés, el default genérico ya habría ocupado la fila y el valor real
    # del seed se ignoraría en silencio.
    import sys as _sys
    import json as _json
    if getattr(_sys, "frozen", False):
        _seed_dir = os.path.dirname(_sys.executable)
    else:
        _seed_dir = os.path.dirname(os.path.abspath(__file__))
    _seed_path = os.path.join(_seed_dir, "config_default.json")
    if os.path.exists(_seed_path):
        try:
            with open(_seed_path, "r", encoding="utf-8") as f:
                _seed = _json.load(f)
            for k, v in _seed.items():
                if v:
                    c.execute("INSERT OR IGNORE INTO config VALUES (?,?)", (k, str(v)))
        except Exception:
            pass

    # Configuración por defecto
    defaults = {
        "max_strikes":             "3",
        "cupos_totales":           "100",
        "nombre_establecimiento":  "Liceo Bicentenario Héroes de la Concepción",
        "alerta_semana_activa":    "1",
        "weather_enabled":         "1",
        "weather_city":            "Laja",
        "weather_lat":             "-37.3572",
        "weather_lon":             "-72.7013",
        "theme_mode":              "dark",
        # Primer arranque real del servicio — se sella con la fecha de HOY
        # la primera vez que corre esta versión (INSERT OR IGNORE no toca
        # instalaciones que ya tengan un valor guardado). Antes de esta
        # fecha, detectar_ausencias_previas() no genera strikes.
        "servicio_fecha_inicio":   date.today().isoformat(),
    }
    for k, v in defaults.items():
        c.execute("INSERT OR IGNORE INTO config VALUES (?,?)", (k, v))

    # Cursos — seed inicial (solo si la tabla está vacía)
    c.execute("SELECT COUNT(*) AS n FROM cursos_nombres")
    if c.fetchone()["n"] == 0:
        _CURSOS_SEED = [
            (1, "A", "CAB"), (1, "B", "GAB"), (1, "C", "JOP"),
            (1, "D", "CLE"), (1, "E", "JUD"), (1, "F", "CAT"),
            (2, "A", "LFA"), (2, "B", "GEF"), (2, "C", "JOS"),
            (2, "D", "NIC"), (2, "E", "MAS"), (2, "F", "NAR"),
            (3, "A", "PAG"), (3, "B", "FAB"), (3, "C", "NAT"),
            (3, "D", "YMS"), (3, "E", "EMO"), (3, "F", "CMU"),
            (4, "A", "BBA"), (4, "B", "LFE"), (4, "C", "SEP"),
            (4, "D", "YAS"), (4, "E", "HGO"), (4, "F", "JAS"),
        ]
        c.executemany(
            "INSERT OR IGNORE INTO cursos_nombres (nivel, seccion, nombre) VALUES (?,?,?)",
            _CURSOS_SEED
        )

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

    # ── Tabla de usuarios con PIN ───────────────────────────────────────────
    c.executescript("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre    TEXT NOT NULL,
        pin_hash  TEXT NOT NULL,
        rol       TEXT NOT NULL DEFAULT 'pae',
        activo    INTEGER DEFAULT 1,
        creado_en TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_usuarios_rol ON usuarios(rol);
    """)
    # Seed: admin por defecto si la tabla está vacía
    if c.execute("SELECT COUNT(*) AS n FROM usuarios").fetchone()["n"] == 0:
        import hashlib as _hl
        _admin_hash = _hl.sha256("123456".encode()).hexdigest()
        c.execute("""
            INSERT INTO usuarios (nombre, pin_hash, rol, activo, creado_en)
            VALUES ('Administrador', ?, 'admin', 1, ?)
        """, (_admin_hash, datetime.now().isoformat(timespec="seconds")))

    # ── Tabla suspensiones/Inspectoría ──────────────────────────────────────
    _ensure_suspension_table(conn)

    # ── Tabla WhatsApp pendientes ────────────────────────────────────────────
    _ensure_whatsapp_table(conn)

    # Migración para DBs existentes: agregar columnas si no existen
    migration_cols = [
        ("students",  "genero",               "TEXT DEFAULT ''"),
        ("students",  "fecha_nacimiento",     "TEXT DEFAULT ''"),
        ("students",  "direccion",            "TEXT DEFAULT ''"),
        ("students",  "comuna",               "TEXT DEFAULT ''"),
        ("students",  "telefono",             "TEXT DEFAULT ''"),
        ("students",  "email",                "TEXT DEFAULT ''"),
        ("students",  "vulnerabilidad",       "TEXT DEFAULT ''"),
        ("students",  "residencia",           "TEXT DEFAULT ''"),
        ("students",  "puntaje_rsh",          "INTEGER DEFAULT NULL"),
        ("students",  "puntaje_extra",        "INTEGER DEFAULT NULL"),
        ("students",  "prioridad",            "INTEGER DEFAULT 0"),
        ("students",  "telefono_apoderado",   "TEXT DEFAULT ''"),   # WhatsApp apoderado
        ("registros", "comida_fria",          "INTEGER DEFAULT 0"),
    ]
    for table, col_name, col_def in migration_cols:
        try:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
        except Exception:
            pass  # Columna ya existe

    # ── Migración de período ─────────────────────────────────────────────────
    # Agrega columna 'periodo' a las tablas transaccionales.
    # Los registros existentes reciben período derivado de su fecha.
    periodo_migration = [
        ("registros",           "periodo", "TEXT DEFAULT ''"),
        ("student_suspensions", "periodo", "TEXT DEFAULT ''"),
        ("strikes",             "periodo", "TEXT DEFAULT ''"),
    ]
    for table, col_name, col_def in periodo_migration:
        try:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
        except Exception:
            pass

    # Tag registros existentes sin período asignado
    def _fecha_to_periodo(fecha_str: str) -> str:
        try:
            from datetime import date as _date
            d = _date.fromisoformat(fecha_str[:10])
            return f"{d.year}-S{'1' if d.month <= 6 else '2'}"
        except Exception:
            return _periodo_default()

    # registros: campo fecha
    sin_periodo = c.execute(
        "SELECT DISTINCT fecha FROM registros WHERE periodo IS NULL OR periodo = ''"
    ).fetchall()
    for row in sin_periodo:
        p = _fecha_to_periodo(row["fecha"])
        c.execute(
            "UPDATE registros SET periodo=? WHERE fecha=? AND (periodo IS NULL OR periodo='')",
            (p, row["fecha"])
        )

    # student_suspensions: campo fecha_inicio
    sin_periodo_ss = c.execute(
        "SELECT DISTINCT fecha_inicio FROM student_suspensions WHERE periodo IS NULL OR periodo = ''"
    ).fetchall()
    for row in sin_periodo_ss:
        p = _fecha_to_periodo(row["fecha_inicio"])
        c.execute(
            "UPDATE student_suspensions SET periodo=? "
            "WHERE fecha_inicio=? AND (periodo IS NULL OR periodo='')",
            (p, row["fecha_inicio"])
        )

    # strikes: campo fecha
    sin_periodo_str = c.execute(
        "SELECT DISTINCT fecha FROM strikes WHERE periodo IS NULL OR periodo = ''"
    ).fetchall()
    for row in sin_periodo_str:
        p = _fecha_to_periodo(row["fecha"])
        c.execute(
            "UPDATE strikes SET periodo=? WHERE fecha=? AND (periodo IS NULL OR periodo='')",
            (p, row["fecha"])
        )

    # Asegura que periodo_activo esté en config
    c.execute("INSERT OR IGNORE INTO config VALUES ('periodo_activo', ?)", (_periodo_default(),))

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


def es_ascii_valido(valor: str) -> bool:
    """
    True si `valor` es puro ASCII. Pensado para credenciales tipo URL/JWT
    que DEBEN ser ASCII — un caracter como una "ñ" metido por un copy-paste
    con problemas no rompe nada al guardarlo, pero revienta bien adentro de
    httpx (headers deben ser ASCII) con un traceback incomprensible varias
    pantallas después. Mejor rechazarlo al momento de guardar.
    """
    return all(ord(c) < 128 for c in valor)


def get_all_config() -> dict:
    conn = get_conn()
    rows = conn.execute("SELECT key, value FROM config").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


# ─────────────────────── GESTIÓN DE PERÍODOS ──────────────────────────────

def _periodo_default() -> str:
    """Retorna el período correspondiente a hoy: 'YYYY-SN'."""
    d = date.today()
    return f"{d.year}-S{'1' if d.month <= 6 else '2'}"


def get_periodo_activo() -> str:
    """Período donde se escriben datos nuevos (ej. '2026-S2')."""
    return get_config("periodo_activo", _periodo_default())


def set_periodo_activo(periodo: str):
    set_config("periodo_activo", periodo)


def get_periodos_disponibles() -> list:
    """
    Lista de períodos únicos presentes en la DB, más el activo.
    Incluye entradas de año completo ('2026') cuando hay ≥2 semestres ese año.
    Ordenado del más reciente al más antiguo.
    """
    conn = get_conn()
    periodos = set()
    periodos.add(get_periodo_activo())

    for tabla in ("registros", "student_suspensions"):
        try:
            rows = conn.execute(
                f"SELECT DISTINCT periodo FROM {tabla} WHERE periodo IS NOT NULL AND periodo != ''"
            ).fetchall()
            for r in rows:
                periodos.add(r["periodo"])
        except Exception:
            pass

    conn.close()

    # Filtrar solo periodos bien formados 'YYYY-SN'
    semestral = sorted(
        [p for p in periodos if len(p) == 7 and p[4] == '-'],
        reverse=True
    )
    # Añadir vista anual cuando hay más de un semestre de ese año
    años = {}
    for p in semestral:
        yr = p[:4]
        años[yr] = años.get(yr, 0) + 1

    result = []
    seen_yr = set()
    for p in semestral:
        result.append(p)
        yr = p[:4]
        if años[yr] >= 1 and yr not in seen_yr:
            # Siempre ofrecemos la vista anual, aunque haya un solo semestre
            result.append(yr)
            seen_yr.add(yr)

    return result if result else [_periodo_default()]


def _periodo_where(periodo: str) -> tuple[str, list]:
    """
    Retorna (fragmento_SQL, params) para filtrar por período.
    'YYYY-SN' → exact match
    'YYYY'    → LIKE 'YYYY-%' (año completo)
    ''        → sin filtro (todos)
    """
    if not periodo:
        return ("", [])
    if len(periodo) == 4 and periodo.isdigit():
        return ("AND periodo LIKE ?", [f"{periodo}-%"])
    return ("AND periodo = ?", [periodo])


def cerrar_periodo(nuevo_nombre: str) -> dict:
    """
    Crea un nuevo período activo sin eliminar datos.
    - Valida que nuevo_nombre sea 'YYYY-SN' (ej. '2026-S2').
    - Cambia periodo_activo en config.
    - Retorna {'ok': True, 'periodo_anterior': ..., 'periodo_nuevo': ...}
      o {'ok': False, 'error': str}
    """
    import re
    if not re.match(r'^\d{4}-S[12]$', nuevo_nombre):
        return {"ok": False, "error": f"Formato inválido '{nuevo_nombre}'. Debe ser YYYY-SN (ej. 2026-S2)"}

    anterior = get_periodo_activo()
    if anterior == nuevo_nombre:
        return {"ok": False, "error": "El período nuevo es igual al actual"}

    set_periodo_activo(nuevo_nombre)
    return {"ok": True, "periodo_anterior": anterior, "periodo_nuevo": nuevo_nombre}


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
    """Búsqueda por RUN, nombre o curso. Ignora tildes y mayúsculas."""
    conn = get_conn()
    q_raw  = f"%{query}%"
    q_norm = f"%{_normalize_str(query)}%"
    rows = conn.execute("""
        SELECT * FROM students
        WHERE run LIKE ?
              OR normalize(nombres) LIKE ?
              OR normalize(apellido_paterno) LIKE ?
              OR normalize(apellido_materno) LIKE ?
              OR curso LIKE ?
        ORDER BY apellido_paterno, nombres
        LIMIT ?
    """, (q_raw, q_norm, q_norm, q_norm, q_raw, limit)).fetchall()
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
    """Busca estudiantes activos por nombre o apellido. Ignora tildes y mayúsculas."""
    conn = get_conn()
    q = f"%{_normalize_str(query)}%"
    rows = conn.execute("""
        SELECT run, nombres, apellido_paterno, apellido_materno, curso, lista_espera
        FROM students
        WHERE activo = 1
          AND (normalize(nombres) LIKE ?
               OR normalize(apellido_paterno) LIKE ?
               OR normalize(apellido_materno) LIKE ?)
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
    periodo = get_periodo_activo()
    try:
        conn.execute("""
            INSERT INTO registros
                (run_estudiante, fecha, comida_id, comida_nombre, timestamp, metodo, comida_fria, periodo)
            VALUES (?,?,?,?,?,?,?,?)
        """, (run, hoy, comida_id, comida_nombre, now, metodo, comida_fria, periodo))
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
    periodo = get_periodo_activo()
    conn.execute("""
        INSERT INTO strikes (run_estudiante, fecha, comida_id, comida_nombre, tipo, timestamp, periodo)
        VALUES (?,?,?,?,?,?,?)
    """, (run, hoy, comida_id, comida_nombre, tipo, now, periodo))
    conn.commit()
    conn.close()


def count_strikes(run: str) -> int:
    """Cuenta strikes SOLO del período activo — se reinicia al cerrar período."""
    conn = get_conn()
    periodo = get_periodo_activo()
    n = conn.execute(
        "SELECT COUNT(*) AS n FROM strikes WHERE run_estudiante=? AND tipo='individual' AND periodo=?",
        (run, periodo)
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
            tipo         TEXT DEFAULT 'suspension',
            creado_en    TEXT NOT NULL,
            firmado      INTEGER DEFAULT 0,
            firmado_en   TEXT DEFAULT '',
            firmado_por  TEXT DEFAULT ''
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_susp_run ON student_suspensions(run)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_susp_fecha "
        "ON student_suspensions(fecha_inicio, fecha_fin)"
    )
    # Migraciones seguras para DBs existentes
    for col, defn in [
        ("tipo",        "TEXT DEFAULT 'suspension'"),
        ("firmado",     "INTEGER DEFAULT 0"),
        ("firmado_en",  "TEXT DEFAULT ''"),
        ("firmado_por", "TEXT DEFAULT ''"),
        ("periodo",     "TEXT DEFAULT ''"),
    ]:
        try:
            conn.execute(f"ALTER TABLE student_suspensions ADD COLUMN {col} {defn}")
        except Exception:
            pass


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
                            fecha_fin: str, motivo: str,
                            tipo: str = 'suspension'):
    conn = get_conn()
    _ensure_suspension_table(conn)
    now = datetime.now().isoformat(timespec="seconds")
    periodo = get_periodo_activo()
    conn.execute("""
        INSERT INTO student_suspensions (run, fecha_inicio, fecha_fin, motivo, tipo, creado_en, periodo)
        VALUES (?,?,?,?,?,?,?)
    """, (run, fecha_inicio, fecha_fin, motivo, tipo, now, periodo))
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


def get_active_and_upcoming_suspensions(from_date: str, limit: int = 60,
                                         tipo: Optional[str] = None) -> list:
    """Suspensiones/licencias/retiros/atrasos activos o futuros desde from_date."""
    conn = get_conn()
    _ensure_suspension_table(conn)
    if tipo:
        rows = conn.execute("""
            SELECT ss.id, ss.run, ss.fecha_inicio, ss.fecha_fin, ss.motivo,
                   ss.tipo, ss.creado_en,
                   st.nombres, st.apellido_paterno, st.apellido_materno, st.curso
            FROM student_suspensions ss
            JOIN students st ON st.run = ss.run
            WHERE ss.fecha_fin >= ? AND ss.tipo = ?
            ORDER BY ss.fecha_inicio, st.apellido_paterno
            LIMIT ?
        """, (from_date, tipo, limit)).fetchall()
    else:
        rows = conn.execute("""
            SELECT ss.id, ss.run, ss.fecha_inicio, ss.fecha_fin, ss.motivo,
                   COALESCE(ss.tipo, 'suspension') AS tipo, ss.creado_en,
                   st.nombres, st.apellido_paterno, st.apellido_materno, st.curso
            FROM student_suspensions ss
            JOIN students st ON st.run = ss.run
            WHERE ss.fecha_fin >= ?
            ORDER BY ss.fecha_inicio, st.apellido_paterno
            LIMIT ?
        """, (from_date, limit)).fetchall()
    conn.close()
    return rows


# ─────────────────────── PASES INSPECTORÍA ───────────────────────────────

def get_pases_estudiante(run: str, periodo: str = "") -> dict:
    """
    Retorna stats de pases del estudiante en el período dado.
    Si periodo='', usa el período activo.
    periodo='YYYY' → agrega todos los semestres de ese año (vista anual).
    Solo tipos: atraso, inasistencia, retiro.
    """
    conn = get_conn()
    _ensure_suspension_table(conn)

    # Período a consultar
    if not periodo:
        periodo = get_periodo_activo()
    p_frag, p_params = _periodo_where(periodo)

    hoy = date.today()
    inicio_mes = hoy.replace(day=1).isoformat()

    def _count(extra_where="", params=()):
        sql = f"""
            SELECT COUNT(*) AS n FROM student_suspensions
            WHERE run=? AND tipo IN ('atraso','inasistencia','retiro')
            {p_frag} {extra_where}
        """
        return conn.execute(sql, (run, *p_params, *params)).fetchone()["n"]

    total      = _count()
    firmados   = _count("AND firmado=1")
    sin_firmar = _count("AND firmado=0")
    mes        = _count("AND fecha_inicio >= ?", (inicio_mes,))

    # Lista completa de pases filtrada por período
    pases = conn.execute(f"""
        SELECT id, run, fecha_inicio, fecha_fin, motivo, tipo,
               firmado, firmado_en, firmado_por, creado_en, periodo
        FROM student_suspensions
        WHERE run=? AND tipo IN ('atraso','inasistencia','retiro')
        {p_frag}
        ORDER BY fecha_inicio DESC
    """, (run, *p_params)).fetchall()

    conn.close()
    return {
        "total":      total,       # total en el período visualizado
        "semestre":   total,       # alias para compatibilidad con _StudentCard
        "firmados":   firmados,
        "sin_firmar": sin_firmar,
        "mes":        mes,
        "periodo":    periodo,
        "pases":      pases,
    }


def get_pases_periodo(desde: str, hasta: str,
                       tipo: Optional[str] = None,
                       periodo: str = "") -> list:
    """
    Pases entre dos fechas con datos del estudiante.
    tipo   : 'atraso'|'inasistencia'|'retiro'|None (todos).
    periodo: filtra además por período ('YYYY-SN' exacto o 'YYYY' para año completo).
             Si está vacío, solo filtra por rango de fechas.
    """
    conn = get_conn()
    _ensure_suspension_table(conn)
    p_frag, p_params = _periodo_where(periodo)
    tipo_clause = "AND ss.tipo = ?" if tipo else "AND ss.tipo IN ('atraso','inasistencia','retiro')"
    tipo_params  = [tipo] if tipo else []
    rows = conn.execute(f"""
        SELECT ss.id, ss.run, ss.fecha_inicio, ss.tipo, ss.motivo,
               ss.firmado, ss.firmado_en, ss.firmado_por, ss.creado_en,
               st.nombres, st.apellido_paterno, st.apellido_materno,
               st.curso, st.telefono_apoderado
        FROM student_suspensions ss
        JOIN students st ON st.run = ss.run
        WHERE ss.fecha_inicio BETWEEN ? AND ?
          {tipo_clause}
          {p_frag}
        ORDER BY ss.fecha_inicio DESC, st.apellido_paterno
    """, (desde, hasta, *tipo_params, *p_params)).fetchall()
    conn.close()
    return rows


def get_pases_stats_hoy() -> dict:
    """
    Stats de pases para el chip de toolbar de Inspectoría:
      pases_hoy  : total pases del día (atraso + inasistencia + retiro)
      sin_firmar : pases pendientes de firma en el período activo
    """
    conn = get_conn()
    _ensure_suspension_table(conn)
    hoy = date.today().isoformat()
    periodo = get_periodo_activo()
    p_frag, p_params = _periodo_where(periodo)

    pases_hoy = conn.execute(
        f"SELECT COUNT(*) AS n FROM student_suspensions "
        f"WHERE tipo IN ('atraso','inasistencia','retiro') AND fecha_inicio = ? {p_frag}",
        (hoy, *p_params)
    ).fetchone()["n"]
    sin_firmar = conn.execute(
        f"SELECT COUNT(*) AS n FROM student_suspensions "
        f"WHERE tipo IN ('atraso','inasistencia','retiro') AND firmado = 0 {p_frag}",
        (*p_params,)
    ).fetchone()["n"]
    conn.close()
    return {"pases_hoy": pases_hoy, "sin_firmar": sin_firmar}


def get_pases_por_estudiante_periodo(periodo: str = "") -> dict:
    """
    Retorna dict {run: {"sin_firmar": N, "total": N}} para todos los
    estudiantes con ≥1 pase en el período dado.
    Si periodo == '' usa get_periodo_activo().
    """
    if not periodo:
        periodo = get_periodo_activo()
    p_frag, p_params = _periodo_where(periodo)
    conn = get_conn()
    _ensure_suspension_table(conn)
    rows = conn.execute(
        f"""
        SELECT run,
               COUNT(*) AS total,
               SUM(CASE WHEN firmado = 0 THEN 1 ELSE 0 END) AS sin_firmar
        FROM student_suspensions
        WHERE tipo IN ('atraso','inasistencia','retiro')
          {p_frag}
        GROUP BY run
        """,
        (*p_params,)
    ).fetchall()
    conn.close()
    return {r["run"]: {"total": r["total"], "sin_firmar": r["sin_firmar"]} for r in rows}


def firmar_pase(pase_id: int, firmado_por: str = "Inspectoría"):
    """Marca un pase como firmado por el apoderado."""
    conn = get_conn()
    _ensure_suspension_table(conn)
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute("""
        UPDATE student_suspensions
        SET firmado=1, firmado_en=?, firmado_por=?
        WHERE id=?
    """, (now, firmado_por, pase_id))
    conn.commit()
    conn.close()


def justificar_strikes_por_pase(run: str, fecha: str,
                                  tipo: str, hora: str = ""):
    """
    Elimina strikes retroactivos del estudiante en esa fecha
    según el tipo de pase y la hora:
      - inasistencia → elimina TODOS los strikes del día
      - retiro (hora H) → elimina strikes de comidas con hora_inicio >= H
      - atraso (hora H) → elimina strikes de comidas con hora_fin <= H
    """
    conn = get_conn()
    comidas = conn.execute(
        "SELECT id, nombre, hora_inicio, hora_fin FROM comidas WHERE activa=1"
    ).fetchall()

    ids_a_borrar: list[int] = []

    if tipo == "inasistencia":
        ids_a_borrar = [c["id"] for c in comidas]
    elif hora:
        for c in comidas:
            if tipo == "retiro" and c["hora_inicio"] >= hora:
                ids_a_borrar.append(c["id"])
            elif tipo == "atraso" and c["hora_fin"] <= hora:
                ids_a_borrar.append(c["id"])

    for cid in ids_a_borrar:
        conn.execute("""
            DELETE FROM strikes
            WHERE run_estudiante=? AND fecha=? AND comida_id=?
        """, (run, fecha, cid))

    conn.commit()
    conn.close()
    return len(ids_a_borrar)


def get_top_pases_mes(limit: int = 30) -> list:
    """
    Ranking de estudiantes con más pases (atraso+inasistencia+retiro) este mes,
    desglosado por tipo.
    """
    conn = get_conn()
    _ensure_suspension_table(conn)
    inicio_mes = date.today().replace(day=1).isoformat()
    rows = conn.execute("""
        SELECT ss.run,
               st.nombres, st.apellido_paterno, st.apellido_materno, st.curso,
               SUM(CASE WHEN ss.tipo='atraso'       THEN 1 ELSE 0 END) AS atrasos,
               SUM(CASE WHEN ss.tipo='inasistencia' THEN 1 ELSE 0 END) AS inasistencias,
               SUM(CASE WHEN ss.tipo='retiro'       THEN 1 ELSE 0 END) AS retiros,
               COUNT(*) AS total
        FROM student_suspensions ss
        JOIN students st ON st.run = ss.run
        WHERE ss.tipo IN ('atraso','inasistencia','retiro')
          AND ss.fecha_inicio >= ?
        GROUP BY ss.run
        ORDER BY total DESC
        LIMIT ?
    """, (inicio_mes, limit)).fetchall()
    conn.close()
    return rows


def tiene_licencia_activa(run: str, fecha: str) -> bool:
    """True si hay una licencia médica registrada que cubre 'fecha'."""
    conn = get_conn()
    _ensure_suspension_table(conn)
    n = conn.execute("""
        SELECT COUNT(*) FROM student_suspensions
        WHERE run=? AND tipo='licencia'
          AND fecha_inicio <= ? AND fecha_fin >= ?
    """, (run, fecha, fecha)).fetchone()[0]
    conn.close()
    return n > 0


def get_licencias_estudiante(run: str) -> list:
    """Todas las licencias (activas y vencidas) de un estudiante, más recientes primero."""
    conn = get_conn()
    _ensure_suspension_table(conn)
    hoy = date.today().isoformat()
    rows = conn.execute("""
        SELECT id, fecha_inicio, fecha_fin, motivo,
               CASE WHEN fecha_fin >= ? THEN 1 ELSE 0 END AS activa,
               creado_en
        FROM student_suspensions
        WHERE run=? AND tipo='licencia'
        ORDER BY fecha_inicio DESC
    """, (hoy, run)).fetchall()
    conn.close()
    return rows


# ─────────────────────── JUSTIFICACIÓN DE COMIDAS ───────────────────────

def _ensure_justificacion_col(conn: sqlite3.Connection):
    """Agrega columna justificacion a registros si no existe."""
    try:
        conn.execute("ALTER TABLE registros ADD COLUMN justificacion TEXT DEFAULT NULL")
    except Exception:
        pass


def justify_meals_bulk(run: str, fechas: list, comidas: list,
                        tipo_justif: str, texto_justif: str) -> int:
    """
    Justifica comidas de un estudiante: inserta en registros con
    metodo='justificado'. Solo inserta si no hay registro previo.
    Retorna cantidad de comidas justificadas.
    fechas: list[str] de 'YYYY-MM-DD'
    comidas: list[dict] con 'id' y 'nombre'
    """
    conn = get_conn()
    _ensure_justificacion_col(conn)
    now = datetime.now().isoformat(timespec="seconds")
    justif_txt = f"[{tipo_justif}] {texto_justif}".strip()
    count = 0
    for fecha in fechas:
        for c in comidas:
            try:
                conn.execute("""
                    INSERT INTO registros
                        (run_estudiante, fecha, comida_id, comida_nombre,
                         timestamp, metodo, justificacion)
                    VALUES (?,?,?,?,?,?,?)
                """, (run, fecha, c["id"], c["nombre"], now, "justificado", justif_txt))
                count += 1
            except sqlite3.IntegrityError:
                pass  # Ya existe registro para ese día/comida
    conn.commit()
    conn.close()
    return count


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


# ══════════════════════════════════════════════════════
#  REPORTES DE ASISTENCIA
# ══════════════════════════════════════════════════════

def get_asistencia_diaria(fecha: str) -> list:
    """
    Lista de todos los registros del día especificado.
    Retorna filas con run, apellidos, nombres, curso, comida, hora.
    """
    conn = get_conn()
    rows = conn.execute("""
        SELECT
            r.run_estudiante        AS run,
            e.apellido_paterno,
            e.apellido_materno,
            e.nombres,
            e.curso,
            c.nombre                AS comida,
            r.timestamp
        FROM registros r
        JOIN estudiantes e ON e.run = r.run_estudiante
        JOIN comidas     c ON c.id  = r.comida_id
        WHERE r.fecha = ?
        ORDER BY r.timestamp
    """, (fecha,)).fetchall()
    conn.close()
    return rows


def get_asistencia_periodo(desde: str, hasta: str) -> list:
    """
    Resumen de asistencia por estudiante en un rango de fechas.
    Retorna run, apellidos, nombres, curso, total_comidas, dias_distintos.
    """
    conn = get_conn()
    rows = conn.execute("""
        SELECT
            r.run_estudiante        AS run,
            e.apellido_paterno,
            e.apellido_materno,
            e.nombres,
            e.curso,
            COUNT(*)                AS total_comidas,
            COUNT(DISTINCT r.fecha) AS dias_distintos
        FROM registros r
        JOIN estudiantes e ON e.run = r.run_estudiante
        WHERE r.fecha BETWEEN ? AND ?
        GROUP BY r.run_estudiante
        ORDER BY total_comidas DESC
    """, (desde, hasta)).fetchall()
    conn.close()
    return rows


def get_asistencia_mensual(anio: int, mes: int) -> list:
    """
    Resumen de asistencia por estudiante para un mes dado.
    """
    desde = f"{anio:04d}-{mes:02d}-01"
    # Último día del mes
    import calendar
    ultimo = calendar.monthrange(anio, mes)[1]
    hasta  = f"{anio:04d}-{mes:02d}-{ultimo:02d}"
    return get_asistencia_periodo(desde, hasta)


def get_top_asistentes(desde: str, hasta: str, limit: int = 25) -> list:
    """Top estudiantes más responsables (mayor asistencia) en el período."""
    return get_asistencia_periodo(desde, hasta)[:limit]


def get_dias_con_registros(desde: str, hasta: str) -> list:
    """Lista de fechas distintas que tuvieron al menos un registro."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT DISTINCT fecha
        FROM registros
        WHERE fecha BETWEEN ? AND ?
        ORDER BY fecha
    """, (desde, hasta)).fetchall()
    conn.close()
    return [r["fecha"] for r in rows]


def get_resumen_dia(fecha: str) -> dict:
    """KPIs rápidos de un día: total registros, estudiantes únicos, por comida."""
    conn = get_conn()
    total = conn.execute(
        "SELECT COUNT(*) AS n FROM registros WHERE fecha=?", (fecha,)
    ).fetchone()["n"]
    unicos = conn.execute(
        "SELECT COUNT(DISTINCT run_estudiante) AS n FROM registros WHERE fecha=?", (fecha,)
    ).fetchone()["n"]
    por_comida = conn.execute("""
        SELECT c.nombre AS comida, COUNT(*) AS n
        FROM registros r JOIN comidas c ON c.id = r.comida_id
        WHERE r.fecha = ?
        GROUP BY r.comida_id
        ORDER BY c.id
    """, (fecha,)).fetchall()
    conn.close()
    return {
        "total":     total,
        "unicos":    unicos,
        "por_comida": [dict(r) for r in por_comida],
    }


# ─────────────────────── CURSOS NOMBRES ───────────────────────

def get_cursos_nombres_map() -> dict:
    """Retorna {(nivel: int, seccion: str): nombre: str} — p.ej. {(1,'A'): 'CAB'}."""
    conn = get_conn()
    rows = conn.execute("SELECT nivel, seccion, nombre FROM cursos_nombres").fetchall()
    conn.close()
    return {(r["nivel"], r["seccion"].upper()): r["nombre"] for r in rows}


def get_cursos_nombres_list() -> list:
    """Lista completa ordenada: [{"nivel":1, "seccion":"A", "nombre":"CAB"}, ...]."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT nivel, seccion, nombre FROM cursos_nombres ORDER BY nivel, seccion"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_curso_nombre(nivel: int, seccion: str, nombre: str):
    """Actualiza el nombre corto de un curso (jefe de curso)."""
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO cursos_nombres (nivel, seccion, nombre) VALUES (?,?,?)",
        (nivel, seccion.upper(), nombre.upper().strip())
    )
    conn.commit()
    conn.close()


def display_curso(raw: str, cursos_map: dict) -> str:
    """
    Convierte el valor raw de la DB al formato de display.
    '1° medioA' → '1° CAB'   |   '2° medioB' → '2° GEF'
    Si no hay mapping devuelve el raw sin cambios.
    """
    import re
    if not raw:
        return raw
    m = re.match(r'(\d+)[°º\s]*medio\s*([A-Fa-f])', raw)
    if not m:
        m = re.match(r'(\d+)[°º\s]+\s*([A-Fa-f])\b', raw)
    if not m:
        return raw
    nivel = int(m.group(1))
    sec   = m.group(2).upper()
    nombre = cursos_map.get((nivel, sec))
    if nombre:
        return f"{nivel}° {nombre}"
    return raw


# ─────────────────────── NOMBRE ESTUDIANTES ───────────────────────

def update_student_nombre(run: str, nuevos_nombres: str, nuevo_ap_pat: str,
                           nuevo_ap_mat: str, tipo_cambio: str, motivo: str):
    """Actualiza nombre/apellidos con registro en name_change_log."""
    conn = get_conn()
    actual = conn.execute(
        "SELECT nombres, apellido_paterno, apellido_materno FROM students WHERE run=?",
        (run,)
    ).fetchone()
    if not actual:
        conn.close()
        return
    now = datetime.now().isoformat(timespec="seconds")
    cambios = []
    if nuevos_nombres and nuevos_nombres != actual["nombres"]:
        cambios.append(("nombres", actual["nombres"], nuevos_nombres))
    if nuevo_ap_pat and nuevo_ap_pat != actual["apellido_paterno"]:
        cambios.append(("apellido_paterno", actual["apellido_paterno"], nuevo_ap_pat))
    if nuevo_ap_mat and nuevo_ap_mat != actual["apellido_materno"]:
        cambios.append(("apellido_materno", actual["apellido_materno"], nuevo_ap_mat))

    if cambios:
        set_parts = []
        vals = []
        for campo, _, nuevo in cambios:
            set_parts.append(f"{campo}=?")
            vals.append(nuevo)
        vals.append(run)
        conn.execute(f"UPDATE students SET {', '.join(set_parts)} WHERE run=?", vals)
        for campo, ant, nuevo in cambios:
            conn.execute("""
                INSERT INTO name_change_log
                    (run, campo, valor_ant, valor_nuevo, tipo_cambio, motivo, timestamp)
                VALUES (?,?,?,?,?,?,?)
            """, (run, campo, ant, nuevo, tipo_cambio, motivo, now))
        conn.commit()
    conn.close()


def update_student_curso(run: str, nuevo_curso: str):
    """Actualiza el campo curso de un estudiante."""
    conn = get_conn()
    conn.execute("UPDATE students SET curso=? WHERE run=?", (nuevo_curso, run))
    conn.commit()
    conn.close()


def update_student_telefono_apoderado(run: str, telefono: str):
    """Actualiza el teléfono del apoderado para WhatsApp."""
    conn = get_conn()
    conn.execute("UPDATE students SET telefono_apoderado=? WHERE run=?", (telefono, run))
    conn.commit()
    conn.close()


def get_name_change_log(run: str = None, limit: int = 200) -> list:
    """Log de cambios de nombre. Si run=None retorna todos."""
    conn = get_conn()
    if run:
        rows = conn.execute("""
            SELECT * FROM name_change_log WHERE run=?
            ORDER BY timestamp DESC LIMIT ?
        """, (run, limit)).fetchall()
    else:
        rows = conn.execute("""
            SELECT ncl.*, s.nombres, s.apellido_paterno
            FROM name_change_log ncl
            LEFT JOIN students s ON s.run = ncl.run
            ORDER BY timestamp DESC LIMIT ?
        """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─────────────────────── USUARIOS ───────────────────────

def get_usuarios_activos() -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, nombre, rol FROM usuarios WHERE activo=1 ORDER BY nombre"
    ).fetchall()
    conn.close()
    return rows


def get_todos_usuarios() -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, nombre, rol, activo FROM usuarios ORDER BY nombre"
    ).fetchall()
    conn.close()
    return rows


def verificar_pin(usuario_id: int, pin: str) -> bool:
    import hashlib
    pin_hash = hashlib.sha256(pin.encode()).hexdigest()
    conn = get_conn()
    row = conn.execute(
        "SELECT id FROM usuarios WHERE id=? AND pin_hash=? AND activo=1",
        (usuario_id, pin_hash)
    ).fetchone()
    conn.close()
    return row is not None


def get_usuario(usuario_id: int) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute(
        "SELECT id, nombre, rol, activo FROM usuarios WHERE id=?",
        (usuario_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def create_usuario(nombre: str, pin: str, rol: str) -> int:
    import hashlib
    pin_hash = hashlib.sha256(pin.encode()).hexdigest()
    conn = get_conn()
    now = datetime.now().isoformat(timespec="seconds")
    cursor = conn.execute(
        "INSERT INTO usuarios (nombre, pin_hash, rol, activo, creado_en) VALUES (?,?,?,1,?)",
        (nombre.strip(), pin_hash, rol, now)
    )
    conn.commit()
    uid = cursor.lastrowid
    conn.close()
    return uid


def update_usuario_pin(usuario_id: int, nuevo_pin: str):
    import hashlib
    pin_hash = hashlib.sha256(nuevo_pin.encode()).hexdigest()
    conn = get_conn()
    conn.execute("UPDATE usuarios SET pin_hash=? WHERE id=?", (pin_hash, usuario_id))
    conn.commit()
    conn.close()


def toggle_usuario_activo(usuario_id: int, activo: bool):
    conn = get_conn()
    conn.execute("UPDATE usuarios SET activo=? WHERE id=?", (int(activo), usuario_id))
    conn.commit()
    conn.close()


# ─────────────────────── WHATSAPP ───────────────────────

def _ensure_whatsapp_table(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS whatsapp_pendientes (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            run          TEXT NOT NULL,
            tipo         TEXT DEFAULT 'atraso',
            numero       TEXT NOT NULL,
            payload      TEXT NOT NULL DEFAULT '{}',
            intentos     INTEGER DEFAULT 0,
            ultimo_error TEXT DEFAULT '',
            enviado      INTEGER DEFAULT 0,
            creado_en    TEXT NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_wa_enviado "
        "ON whatsapp_pendientes(enviado, intentos)"
    )


def get_pendientes_whatsapp(limit: int = 50) -> list:
    conn = get_conn()
    _ensure_whatsapp_table(conn)
    rows = conn.execute("""
        SELECT * FROM whatsapp_pendientes
        WHERE enviado=0 AND intentos < 5
        ORDER BY creado_en
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return rows


def marcar_whatsapp_enviado(msg_id: int):
    conn = get_conn()
    conn.execute("UPDATE whatsapp_pendientes SET enviado=1 WHERE id=?", (msg_id,))
    conn.commit()
    conn.close()


def marcar_whatsapp_error(msg_id: int, error: str):
    conn = get_conn()
    conn.execute("""
        UPDATE whatsapp_pendientes
        SET intentos = intentos + 1, ultimo_error = ?
        WHERE id=?
    """, (error[:500], msg_id))
    conn.commit()
    conn.close()


def get_whatsapp_stats(desde: str = None) -> dict:
    """Estadísticas de mensajes WhatsApp para reportes."""
    conn = get_conn()
    _ensure_whatsapp_table(conn)
    q_filter = "WHERE creado_en >= ?" if desde else ""
    params   = (desde,) if desde else ()
    total    = conn.execute(f"SELECT COUNT(*) AS n FROM whatsapp_pendientes {q_filter}", params).fetchone()["n"]
    enviados = conn.execute(f"SELECT COUNT(*) AS n FROM whatsapp_pendientes {q_filter} {'AND' if desde else 'WHERE'} enviado=1", params).fetchone()["n"] if desde else conn.execute("SELECT COUNT(*) AS n FROM whatsapp_pendientes WHERE enviado=1").fetchone()["n"]
    conn.close()
    return {"total": total, "enviados": enviados, "pendientes": total - enviados}
