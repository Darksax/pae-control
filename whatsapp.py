"""
whatsapp.py — Notificaciones WhatsApp Business para MiAppoderado.

Usa la Meta WhatsApp Cloud API (oficial).
Credenciales configuradas en la tabla config de SQLite (nunca hardcodeadas).

Flujo:
  1. inspectoria_screen registra un atraso
  2. Llama a enviar_atraso(run, hora)
  3. Si hay conexión → POST a Meta API
  4. Si no hay conexión → encola en whatsapp_pendientes
  5. Timer en background reintenta cada 60s
"""

from __future__ import annotations

import json
import threading
import urllib.request
import urllib.error
import ssl
from datetime import datetime
from typing import Optional

import db


# ── SSL context sin verificación (mismo patrón usado para APIs públicas de solo lectura)
def _ssl_ctx():
    return ssl._create_unverified_context()


def _get_config() -> tuple[str, str, str]:
    """
    Retorna (phone_id, token, nombre_plantilla).
    Vacíos si no están configurados.
    """
    phone_id  = db.get_config("wa_phone_id", "").strip()
    token     = db.get_config("wa_token", "").strip()
    plantilla = db.get_config("wa_plantilla", "notificacion_atraso").strip()
    return phone_id, token, plantilla


def esta_configurado() -> bool:
    """True si las credenciales Meta están ingresadas."""
    phone_id, token, _ = _get_config()
    return bool(phone_id and token)


def _formatear_numero(numero: str) -> str:
    """
    Convierte número chileno al formato E.164 sin '+':
    '912345678' → '56912345678'
    '56912345678' → '56912345678'
    '+56912345678' → '56912345678'
    """
    n = numero.strip().replace(" ", "").replace("-", "")
    if n.startswith("+"):
        n = n[1:]
    if n.startswith("56"):
        return n
    if n.startswith("9") and len(n) == 9:
        return "56" + n
    return n


def _post_mensaje(numero: str, nombre_estudiante: str,
                   hora: str, phone_id: str,
                   token: str, plantilla: str,
                   atrasos_mes: int = 0,
                   pases_sin_firmar: int = 0) -> tuple[bool, str]:
    """
    Envía el mensaje vía Meta Graph API.
    Retorna (ok, error_msg).
    Parámetros de plantilla:
      {{1}} nombre_estudiante  {{2}} hora
      {{3}} atrasos_mes        {{4}} pases_sin_firmar
    """
    url = f"https://graph.facebook.com/v19.0/{phone_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": _formatear_numero(numero),
        "type": "template",
        "template": {
            "name": plantilla,
            "language": {"code": "es"},
            "components": [{
                "type": "body",
                "parameters": [
                    {"type": "text", "text": nombre_estudiante},
                    {"type": "text", "text": hora},
                    {"type": "text", "text": str(atrasos_mes)},
                    {"type": "text", "text": str(pases_sin_firmar)},
                ]
            }]
        }
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10, context=_ssl_ctx()) as r:
            return True, ""
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        return False, f"HTTP {e.code}: {body}"
    except Exception as exc:
        return False, str(exc)


def enviar_atraso(run: str, hora: Optional[str] = None) -> tuple[bool, str]:
    """
    Envía notificación de atraso al apoderado del estudiante.
    Retorna (ok, mensaje_estado).
    'ok' puede ser True (enviado) o False (encolado o sin número).
    """
    if hora is None:
        hora = datetime.now().strftime("%H:%M")

    estudiante = db.get_student(run)
    if not estudiante:
        return False, "Estudiante no encontrado"

    numero = (estudiante.get("telefono_apoderado") or "").strip()
    if not numero:
        return False, "Sin número de apoderado registrado"

    nombre = (
        f"{estudiante.get('nombres', '')} "
        f"{estudiante.get('apellido_paterno', '')}"
    ).strip()

    # Obtener conteos para el mensaje enriquecido
    try:
        stats = db.get_pases_estudiante(run)
        atrasos_mes      = stats.get("mes", 0)
        pases_sin_firmar = stats.get("sin_firmar", 0)
    except Exception:
        atrasos_mes      = 0
        pases_sin_firmar = 0

    if not esta_configurado():
        _encolar(run, numero, nombre, hora, atrasos_mes, pases_sin_firmar)
        return False, "WhatsApp no configurado — guardado en cola"

    phone_id, token, plantilla = _get_config()
    ok, err = _post_mensaje(numero, nombre, hora, phone_id, token, plantilla,
                            atrasos_mes, pases_sin_firmar)

    if ok:
        _registrar_enviado(run, numero)
        return True, "Enviado"
    else:
        _encolar(run, numero, nombre, hora, atrasos_mes, pases_sin_firmar, error_inicial=err)
        return False, f"Sin conexión — encolado ({err[:60]})"


def _encolar(run: str, numero: str, nombre: str, hora: str,
             atrasos_mes: int = 0, pases_sin_firmar: int = 0,
             error_inicial: str = ""):
    payload = json.dumps({
        "nombre":           nombre,
        "hora":             hora,
        "atrasos_mes":      atrasos_mes,
        "pases_sin_firmar": pases_sin_firmar,
    })
    conn = db.get_conn()
    db._ensure_whatsapp_table(conn)
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute("""
        INSERT INTO whatsapp_pendientes
            (run, tipo, numero, payload, ultimo_error, creado_en)
        VALUES (?, 'atraso', ?, ?, ?, ?)
    """, (run, numero, payload, error_inicial[:300], now))
    conn.commit()
    conn.close()


def _registrar_enviado(run: str, numero: str):
    """Registra el mensaje como enviado en el historial."""
    conn = db.get_conn()
    db._ensure_whatsapp_table(conn)
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute("""
        INSERT INTO whatsapp_pendientes
            (run, tipo, numero, payload, enviado, creado_en)
        VALUES (?, 'atraso', ?, '{}', 1, ?)
    """, (run, numero, now))
    conn.commit()
    conn.close()


# ── Retry en background ────────────────────────────────────────────────────

def _retry_loop():
    """Intenta reenviar mensajes pendientes. Llamar en hilo background."""
    if not esta_configurado():
        return

    phone_id, token, plantilla = _get_config()
    pendientes = db.get_pendientes_whatsapp()
    if not pendientes:
        return

    for msg in pendientes:
        try:
            payload = json.loads(msg["payload"])
            nombre           = payload.get("nombre", "")
            hora             = payload.get("hora", "")
            atrasos_mes      = payload.get("atrasos_mes", 0)
            pases_sin_firmar = payload.get("pases_sin_firmar", 0)
            ok, err = _post_mensaje(
                msg["numero"], nombre, hora, phone_id, token, plantilla,
                atrasos_mes, pases_sin_firmar
            )
            if ok:
                db.marcar_whatsapp_enviado(msg["id"])
            else:
                db.marcar_whatsapp_error(msg["id"], err)
        except Exception as exc:
            db.marcar_whatsapp_error(msg["id"], str(exc))


def iniciar_retry_timer(interval_ms: int = 60_000):
    """
    Llama a esta función desde MainWindow para iniciar el timer de reintentos.
    Corre en el hilo de Qt, lanza _retry_loop en un thread daemon.
    """
    from PyQt6.QtCore import QTimer

    def _tick():
        t = threading.Thread(target=_retry_loop, daemon=True, name="wa-retry")
        t.start()

    timer = QTimer()
    timer.setInterval(interval_ms)
    timer.timeout.connect(_tick)
    timer.start()
    return timer  # caller must keep reference


def probar_conexion(numero_test: str,
                    phone_id: str = "",
                    token: str = "",
                    plantilla: str = "") -> tuple[bool, str]:
    """
    Envía un mensaje de prueba. Para usar desde ConfigScreen.
    Si se pasan credenciales explícitas las usa; si no, lee de DB.
    """
    if not phone_id or not token:
        if not esta_configurado():
            return False, "Credenciales no configuradas"
        phone_id, token, plantilla = _get_config()
    if not plantilla:
        plantilla = db.get_config("wa_plantilla", "notificacion_atraso").strip()
    ok, err = _post_mensaje(
        numero_test, "Estudiante Prueba", "08:30", phone_id, token, plantilla
    )
    if ok:
        return True, "Mensaje de prueba enviado correctamente"
    # Distinguir error de plantilla vs error de auth/conexión
    if "132001" in err or "does not exist" in err.lower():
        return False, "Conexión OK — plantilla aún no aprobada por Meta"
    return False, err
