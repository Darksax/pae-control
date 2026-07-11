"""
utils.py — Utilidades: normalización RUN, validación dígito verificador,
           helpers de fecha y formato de nombres.
"""

import re
from datetime import datetime, time


# ─────────────────────── RUN ───────────────────────

def normalizar_run(raw: str) -> str:
    """
    Acepta cualquier formato de RUN y retorna "12345678-9" o "12345678-K".
    Formatos de entrada soportados:
      - "12.345.678-9"
      - "12345678-9"
      - "123456789"        (9 dígitos = 8 cuerpo + 1 dv)
      - "12345678 9"
      - "12345678K"
    """
    if not raw:
        return ""
    raw = raw.strip().upper().replace(".", "").replace(" ", "")

    # Si tiene guion, separar directamente
    if "-" in raw:
        partes = raw.split("-")
        if len(partes) == 2:
            cuerpo = partes[0].strip()
            dv = partes[1].strip()
            if cuerpo.isdigit() and (dv.isdigit() or dv == "K"):
                return f"{cuerpo}-{dv}"

    # Sin guion: los últimos 1-2 chars son el DV
    digits_k = re.sub(r"[^0-9K]", "", raw)
    if len(digits_k) >= 2:
        # DV es el último char
        cuerpo = digits_k[:-1]
        dv = digits_k[-1]
        if cuerpo.isdigit() and (dv.isdigit() or dv == "K"):
            return f"{cuerpo}-{dv}"

    return raw  # fallback: devolver tal cual


def validar_run(run: str) -> bool:
    """
    Valida dígito verificador de RUN chileno.
    Recibe RUN normalizado "12345678-9".
    """
    try:
        partes = run.split("-")
        if len(partes) != 2:
            return False
        cuerpo = int(partes[0])
        dv = partes[1].upper()

        suma = 0
        multiplo = 2
        n = cuerpo
        while n > 0:
            suma += (n % 10) * multiplo
            n //= 10
            multiplo = (multiplo - 1) % 6 + 2  # cicla 2→3→4→5→6→7→2→...

        resto = 11 - (suma % 11)
        if resto == 11:
            esperado = "0"
        elif resto == 10:
            esperado = "K"
        else:
            esperado = str(resto)

        return dv == esperado
    except Exception:
        return False


def run_display(run: str) -> str:
    """Formatea RUN con puntos para mostrar: "12.345.678-9"."""
    try:
        cuerpo, dv = run.split("-")
        cuerpo_int = int(cuerpo)
        return f"{cuerpo_int:,}".replace(",", ".") + f"-{dv}"
    except Exception:
        return run


# ─────────────────────── NOMBRES ───────────────────────

def nombre_completo(estudiante) -> str:
    """Retorna 'APELLIDO1 APELLIDO2, Nombres' desde un sqlite3.Row."""
    ap = (estudiante["apellido_paterno"] or "").strip()
    am = (estudiante["apellido_materno"] or "").strip()
    nm = (estudiante["nombres"] or "").strip()
    apellidos = " ".join(filter(None, [ap, am]))
    if apellidos:
        return f"{apellidos}, {nm}"
    return nm


def nombre_corto(estudiante) -> str:
    """Retorna 'Nombres Apellido1' para mostrar en pantalla."""
    ap = (estudiante["apellido_paterno"] or "").strip()
    nm = (estudiante["nombres"] or "").strip()
    # Si nombres tiene múltiples palabras, tomar solo la primera
    primer_nombre = nm.split()[0] if nm else ""
    return f"{primer_nombre} {ap}".strip()


# ─────────────────────── TIEMPO ───────────────────────

def parse_hora(h: str) -> time:
    """Parsea "HH:MM" a datetime.time."""
    partes = h.strip().split(":")
    return time(int(partes[0]), int(partes[1]))


def comida_actual(comidas: list):
    """
    Retorna la comida activa según hora actual.
    Si no hay ninguna activa en este momento, retorna la más cercana
    (para mostrar "próxima comida" en pantalla — NO usar para registrar
    asistencia, ver comida_activa_ahora).
    """
    ahora = datetime.now().time()
    # Primero buscar una que esté activa ahora mismo
    for c in comidas:
        inicio = parse_hora(c["hora_inicio"])
        fin    = parse_hora(c["hora_fin"])
        if inicio <= ahora <= fin:
            return c
    # Si no hay ninguna activa, retornar la próxima
    for c in comidas:
        inicio = parse_hora(c["hora_inicio"])
        if ahora < inicio:
            return c
    # Si ya pasaron todas, retornar la última
    return comidas[-1] if comidas else None


def comida_activa_ahora(comidas: list):
    """
    Retorna la comida solo si HAY UNA realmente activa ahora mismo
    (hora_inicio <= ahora <= hora_fin). Retorna None si no hay ninguna.

    A diferencia de comida_actual(), no hace fallback a la próxima comida:
    esto evita que un escaneo fuera de horario se registre por error en
    la comida siguiente y deje al estudiante marcado "ya registrado"
    cuando llegue a comer de verdad.
    """
    ahora = datetime.now().time()
    for c in comidas:
        inicio = parse_hora(c["hora_inicio"])
        fin    = parse_hora(c["hora_fin"])
        if inicio <= ahora <= fin:
            return c
    return None


def comida_anterior(comidas: list, comida_actual_id: int):
    """Retorna la comida inmediatamente anterior a la actual."""
    ids = [c["id"] for c in comidas]
    try:
        idx = ids.index(comida_actual_id)
        if idx > 0:
            return comidas[idx - 1]
    except ValueError:
        pass
    return None  # Es la primera comida del día


def format_fecha_display(fecha_iso: str) -> str:
    """Convierte "2024-06-08" → "Sábado 08 Jun 2024"."""
    meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
             "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    dias  = ["Lunes", "Martes", "Miércoles", "Jueves",
             "Viernes", "Sábado", "Domingo"]
    try:
        d = datetime.fromisoformat(fecha_iso)
        return f"{dias[d.weekday()]} {d.day:02d} {meses[d.month-1]} {d.year}"
    except Exception:
        return fecha_iso


def es_viernes() -> bool:
    return datetime.today().weekday() == 4
