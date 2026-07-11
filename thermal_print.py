"""
thermal_print.py — Impresión silenciosa en impresora térmica 80mm.

Protocolo: ESC/POS estándar (Epson, Star, Bixolon, etc.)
Papel:     80mm — 48 caracteres por línea en modo normal.

Conexión (config DB key: "thermal_printer"):
  • "192.168.1.100:9100"   → TCP/red (lo más común; puerto 9100 en impresoras de red)
  • "CUPS:EpsonTM-T20"     → nombre CUPS; envía como raw via `lp -d`
  • "/dev/cu.usbmodem001"  → dispositivo USB directo (macOS)
  • "/dev/usb/lp0"         → dispositivo USB directo (Linux)
  • "" o "disabled"        → impresión desactivada

El módulo es thread-safe. `imprimir_async()` usa un hilo daemon para no bloquear la UI.
"""

from __future__ import annotations

import os
import socket
import subprocess
import tempfile
import threading
from datetime import datetime

import db

# ── ESC/POS — comandos básicos ────────────────────────────────────────────────

ESC = b"\x1b"
GS  = b"\x1d"

def _e(*b) -> bytes:  return ESC + bytes(b)
def _g(*b) -> bytes:  return GS  + bytes(b)

INIT         = _e(ord("@"))          # Inicializar impresora
BOLD_ON      = _e(ord("E"), 1)
BOLD_OFF     = _e(ord("E"), 0)
SIZE_NORMAL  = _e(ord("!"), 0x00)   # Normal
SIZE_2H      = _e(ord("!"), 0x10)   # Doble alto
SIZE_2W      = _e(ord("!"), 0x20)   # Doble ancho
SIZE_2H2W    = _e(ord("!"), 0x30)   # Doble alto + ancho
ALIGN_LEFT   = _e(ord("a"), 0)
ALIGN_CENTER = _e(ord("a"), 1)
ALIGN_RIGHT  = _e(ord("a"), 2)
LF           = b"\n"
CUT_FULL     = _g(ord("V"), 0)      # Corte completo
CUT_PARTIAL  = _g(ord("V"), 1)      # Corte parcial (deja tira)
FEED_3       = _e(ord("d"), 3)      # Avanzar 3 líneas

# Ancho de línea en modo normal (80mm @ ~8.5 chars/cm = 48 chars)
_WIDTH = 48


# ── Helpers de texto ──────────────────────────────────────────────────────────

def _enc(text: str) -> bytes:
    """Codifica texto a CP850 (compatible con la mayoría de térmicas)."""
    return text.encode("cp850", errors="replace")


def _rule(char: str = "-") -> str:
    return char * _WIDTH


def _ctr(text: str) -> str:
    return text.center(_WIDTH)


def _wrap(text: str, max_w: int = _WIDTH) -> list[str]:
    """Divide texto largo en líneas de max_w caracteres."""
    words = text.split()
    lines: list[str] = []
    line = ""
    for w in words:
        if line and len(line) + 1 + len(w) > max_w:
            lines.append(line)
            line = w
        else:
            line = (line + " " + w).lstrip()
    if line:
        lines.append(line)
    return lines or [""]


# ── Generación de contenido ESC/POS ──────────────────────────────────────────

def generar_pase(
    *,
    run:            str,
    nombre:         str,
    curso:          str,
    tipo:           str,              # "atraso" | "inasistencia" | "retiro"
    fecha:          str,              # "Viernes 13 de junio de 2026"
    hora:           str | None,       # "08:23"  (solo atraso)
    n_sin_firmar:   int,
    establecimiento: str,
    disclaimer:     str = "",         # texto pie, vacío = default
) -> bytes:
    """
    Genera los bytes ESC/POS para un pase de inspectoría.
    """
    tipo_label = {
        "atraso":       "PASE DE ATRASO",
        "inasistencia": "PASE DE INASISTENCIA",
        "retiro":       "AUTORIZACION DE RETIRO",
    }.get(tipo, f"PASE — {tipo.upper()}")

    buf = bytearray()

    def w(data: bytes):
        buf.extend(data)

    def line(text: str = ""):
        buf.extend(_enc(text + "\n"))

    # Inicializar
    w(INIT)

    # ── Encabezado ────────────────────────────────
    w(ALIGN_CENTER + BOLD_ON)
    # Romper el nombre del establecimiento si es muy largo
    for parte in _wrap(establecimiento.upper(), _WIDTH):
        line(parte)
    w(BOLD_OFF)
    line(_rule("="))

    # Tipo de pase (negrita grande)
    w(BOLD_ON + SIZE_2H)
    line(_ctr(tipo_label))
    w(SIZE_NORMAL + BOLD_OFF)
    line(_rule("="))

    # ── Datos del estudiante ─────────────────────
    w(ALIGN_LEFT)
    # Nombre: truncar si necesario
    nombre_display = nombre[:38] if len(nombre) > 38 else nombre
    line(f"Nombre : {nombre_display}")
    line(f"RUN    : {run}")
    if curso:
        line(f"Curso  : {curso}")
    line(f"Fecha  : {fecha}")
    line()

    # ── Hora en GRANDE (solo atraso) / fecha destacada (inasistencia) ────────
    if tipo == "atraso" and hora:
        w(ALIGN_CENTER + SIZE_2H2W + BOLD_ON)
        line(f"  {hora}  ")
        w(SIZE_NORMAL + BOLD_OFF)
        line()
    elif tipo == "inasistencia":
        w(ALIGN_CENTER + SIZE_2H + BOLD_ON)
        line(_ctr(f"Inasistencia: {fecha}"))
        w(SIZE_NORMAL + BOLD_OFF + ALIGN_LEFT)
        line()

    # ── Pases sin firmar ─────────────────────────
    if n_sin_firmar > 0:
        w(ALIGN_LEFT)
        line(_rule("-"))
        if n_sin_firmar == 1:
            line(f"  ! Tiene 1 pase sin firmar apoderado")
        else:
            line(f"  ! Tiene {n_sin_firmar} pases sin firmar apoderado")
        line(_rule("-"))
    else:
        line(_rule("-"))

    # ── Disclaimer ───────────────────────────────
    _disc = disclaimer.strip() or _DEFAULT_DISCLAIMER
    w(ALIGN_CENTER)
    for parte in _wrap(_disc, _WIDTH):
        line(parte)

    line(_rule("-"))

    # ── Pie ──────────────────────────────────────
    ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    w(ALIGN_LEFT)
    line(f"Emitido  : {ts}")
    line(f"Registro : Inspectoria")

    # Avanzar y cortar
    w(FEED_3)
    w(CUT_PARTIAL)

    return bytes(buf)


_DEFAULT_DISCLAIMER = (
    "El estudiante tiene un lapso de 5 minutos "
    "desde emitido este pase para hacer ingreso al aula."
)


def generar_preview_texto(
    *,
    tipo: str,
    establecimiento: str,
    disclaimer: str = "",
) -> str:
    """
    Representación en texto plano del ticket (para preview en ConfigScreen).
    Usa datos de ejemplo fijos.
    """
    _disc = disclaimer.strip() or _DEFAULT_DISCLAIMER

    _EJEMPLOS: dict[str, dict] = {
        "atraso": {
            "nombre": "PÉREZ SOTO, María Camila",
            "run": "15.432.987-6",
            "curso": "2° Medio B",
            "fecha": "Viernes 13 de junio de 2025",
            "hora": "08:23",
        },
        "inasistencia": {
            "nombre": "GÓMEZ ARAYA, Rodrigo Andrés",
            "run": "16.234.567-8",
            "curso": "1° Medio A",
            "fecha": "Jueves 12 de junio de 2025",
            "hora": None,
        },
    }
    ex = _EJEMPLOS.get(tipo, _EJEMPLOS["atraso"])
    tipo_label = {
        "atraso":       "PASE DE ATRASO",
        "inasistencia": "PASE DE INASISTENCIA",
    }.get(tipo, tipo.upper())

    lines: list[str] = []

    def add(t: str = ""):
        lines.append(t)

    add(_rule("="))
    for parte in _wrap(establecimiento.upper(), _WIDTH):
        add(_ctr(parte))
    add(_rule("="))
    # tipo en doble ancho simulado con espacios
    add(_ctr(f"[ {tipo_label} ]"))
    add(_rule("="))
    add(f"Nombre : {ex['nombre']}")
    add(f"RUN    : {ex['run']}")
    add(f"Curso  : {ex['curso']}")
    add(f"Fecha  : {ex['fecha']}")
    add()

    if tipo == "atraso" and ex.get("hora"):
        add(_ctr(f"*** {ex['hora']} ***"))
        add()
    elif tipo == "inasistencia":
        add(_ctr(f"Inasistencia: {ex['fecha']}"))
        add()

    add(_rule("-"))
    for parte in _wrap(_disc, _WIDTH):
        add(_ctr(parte))
    add(_rule("-"))
    add(f"Emitido  : 13/06/2025 08:23:47")
    add(f"Registro : Inspectoria")
    add(_rule("="))

    return "\n".join(lines)


def generar_ticket_prueba(establecimiento: str = "PAE Control") -> bytes:
    """Ticket mínimo para probar conexión de impresora."""
    buf = bytearray()
    buf.extend(INIT)
    buf.extend(ALIGN_CENTER + BOLD_ON)
    buf.extend(_enc("PRUEBA DE IMPRESORA\n"))
    buf.extend(BOLD_OFF)
    buf.extend(_enc(_rule("-") + "\n"))
    buf.extend(_enc(_ctr(establecimiento) + "\n"))
    ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    buf.extend(_enc(f"{_ctr(ts)}\n"))
    buf.extend(_enc(_rule("-") + "\n"))
    buf.extend(ALIGN_LEFT)
    buf.extend(_enc("Conexion OK\n"))
    buf.extend(FEED_3)
    buf.extend(CUT_PARTIAL)
    return bytes(buf)


# ── Envío a impresora ─────────────────────────────────────────────────────────

def get_printer_cfg() -> str:
    """Lee la config de impresora desde la DB. Retorna "" si no configurada."""
    try:
        val = db.get_config("thermal_printer", "")
        if val.lower() in ("", "disabled", "ninguna", "none"):
            return ""
        return val.strip()
    except Exception:
        return ""


def imprimir(contenido: bytes) -> tuple[bool, str]:
    """
    Envía bytes ESC/POS a la impresora configurada.
    Retorna (ok: bool, mensaje: str).
    """
    cfg = get_printer_cfg()
    if not cfg:
        return False, "Impresora no configurada"

    try:
        # ── TCP / Red ────────────────────────────────────────
        if ":" in cfg and not cfg.startswith("/") and not cfg.upper().startswith("CUPS:"):
            parts = cfg.rsplit(":", 1)
            host  = parts[0]
            port  = int(parts[1])
            with socket.create_connection((host, port), timeout=4) as s:
                s.sendall(contenido)
            return True, f"OK — {host}:{port}"

        # ── CUPS por nombre ──────────────────────────────────
        if cfg.upper().startswith("CUPS:"):
            printer_name = cfg[5:].strip()
            return _imprimir_cups(printer_name, contenido)

        # ── Dispositivo USB / serial (/dev/...) ──────────────
        if cfg.startswith("/"):
            with open(cfg, "wb") as f:
                f.write(contenido)
            return True, f"OK — {cfg}"

        # ── CUPS sin prefijo (solo nombre) ───────────────────
        return _imprimir_cups(cfg, contenido)

    except socket.timeout:
        return False, "Timeout — impresora no responde"
    except ConnectionRefusedError:
        return False, "Conexion rechazada — verificar IP/puerto"
    except FileNotFoundError:
        return False, f"Dispositivo no encontrado: {cfg}"
    except OSError as e:
        return False, str(e)[:80]
    except Exception as e:
        return False, str(e)[:80]


def _imprimir_cups(printer_name: str, contenido: bytes) -> tuple[bool, str]:
    """Envía raw data a una cola CUPS usando `lp -d printer_name -o raw`."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".bin")
    try:
        tmp.write(contenido)
        tmp.close()
        result = subprocess.run(
            ["lp", "-d", printer_name, "-o", "raw", tmp.name],
            capture_output=True,
            timeout=6,
        )
        if result.returncode == 0:
            return True, f"OK — CUPS:{printer_name}"
        err = result.stderr.decode(errors="replace").strip()[:80]
        return False, err or f"lp exited {result.returncode}"
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def imprimir_async(contenido: bytes, on_error=None) -> None:
    """
    Envía a impresora en hilo daemon (no bloquea la UI).
    on_error(msg: str) se llama en el hilo si hay error.
    """
    def _run():
        ok, msg = imprimir(contenido)
        if not ok and callable(on_error):
            on_error(msg)

    threading.Thread(target=_run, daemon=True, name="thermal-print").start()
