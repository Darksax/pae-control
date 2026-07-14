"""
assistant.py — Asistente IA (Gemini) para dudas de reglamento del liceo y uso de la app.

Usa la API REST de Gemini directo por HTTP (sin dependencia nueva de pip),
igual de simple que sync.py/whatsapp.py. La clave y el texto del reglamento
viven en la tabla config (igual que las credenciales de Supabase/WhatsApp) —
nunca se sincronizan a Supabase (ver sync.py, la tabla config no se sube).
"""

import json
import socket
import ssl
import urllib.request
import urllib.error

import db
import session

# Mismo patrón que whatsapp.py: en algunos equipos (típicamente Windows sin
# certificados CA actualizados, o macOS con el Python embebido de
# PyInstaller) el urlopen por default revienta con CERTIFICATE_VERIFY_FAILED,
# que es un URLError — indistinguible de una caída real de internet si no se
# usa un contexto SSL propio. Sin esto, un problema de certificados se
# reportaba como "Sin conexión a internet" aunque el equipo sí tuviera red.
def _ssl_ctx():
    return ssl._create_unverified_context()

GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)

# Descripción de la app — se le da a Gemini como conocimiento de base para
# que pueda GUIAR a los usuarios (qué pantalla usar, qué hace cada botón),
# no solo responder "sí, se puede hacer X" sin decir cómo.
APP_KNOWLEDGE = """\
PANTALLAS (según rol del usuario logueado):
- Escaneo (roles: pae, admin) — pantalla principal de operación. Escanea el \
RUN (cédula) del estudiante con lector de código de barras o lo escribe a \
mano, y registra su asistencia a la comida activa según el horario \
configurado. Estados posibles al escanear: OK (verde, ingreso registrado), \
YA REGISTRADO (naranja, ya comió esta comida), STRIKE (rojo, faltó a una \
comida anterior), FUERA DE HORARIO (gris, no hay comida activa ahora mismo \
— no registra nada, evita que un escaneo de prueba consuma la comida real), \
NO BENEFICIADO / NO ENCONTRADO / RUN INVÁLIDO (rojo), SIN SERVICIO HOY \
(gris, día suspendido/feriado).
- Cupos por día (pae, admin) — define el cupo total de raciones, la fecha \
de inicio del servicio, excepciones por fecha (feriados sin servicio, días \
de ración fría, suspensión de varios días de una vez).
- Estudiantes (pae, inspectoria, admin) — ficha de cada estudiante: estado \
(activo / en lista de espera / inactivo). El rol pae solo ve el puntaje \
RSH; inspectoria ve nombre/curso/teléfono pero NO el RSH.
- Inspectoría (inspectoria, admin) — atrasos, pases, licencias médicas y \
suspensiones escolares.
- Reportes (todos los roles) — resumen semanal/mensual de asistencia, top \
de inasistencias.
- Importar (solo admin) — carga la nómina de estudiantes desde archivos \
SIGE (.xls).
- Sync Supabase (solo admin) — respaldo en la nube: sube estudiantes, \
registros, strikes y usuarios; baja estudiantes actualizados. Se ejecuta \
manualmente con el botón "Sincronizar ahora".
- Configuración (solo admin) — cupos, horarios de comidas, gestión de \
usuarios (crear/cambiar PIN), credenciales de Supabase/WhatsApp/Gemini, \
impresora térmica.

ROLES Y PERMISOS:
- admin: acceso a todo.
- pae: Escaneo, Cupos por día, Estudiantes (solo ficha RSH), Reportes.
- inspectoria: Inspectoría (atrasos/pases/licencias), Estudiantes (sin \
RSH), Reportes.

LOGIN: por PIN — el usuario elige su nombre de una lista y escribe su PIN, \
no hay usuario/contraseña de texto. El PIN se cambia desde Configuración → \
Gestión de usuarios (solo admin).

REGLAS DE NEGOCIO:
- Strikes: se genera un strike por faltar a una comida anterior que sí \
operó ese día, o al día completo anterior. El contador de strikes se \
reinicia cuando se cierra el período/semestre (Configuración) — no es un \
acumulado histórico de todo el año.
- Cupo diario: si un escaneo supera el cupo configurado, igual se registra \
(no se le niega comida a nadie) pero se muestra una advertencia visual.
"""


# Tope de caracteres del reglamento que se manda en CADA consulta a Gemini.
# El campo en Configuración no tiene límite (alguien puede pegar un PDF
# completo ahí), pero reenviar un texto de cientos de miles de caracteres
# como system_instruction en TODA pregunta agota el cupo gratuito de tokens
# por minuto de un plan free en la primera consulta del día — no hace falta
# mandar preguntas seguidas para que pase.
MAX_REGLAMENTO_CHARS = 24_000


def is_configured() -> bool:
    return bool(db.get_config("gemini_api_key", "").strip())


def _system_prompt() -> str:
    reglamento = db.get_config("gemini_reglamento", "").strip()
    reglamento_truncado = False
    if len(reglamento) > MAX_REGLAMENTO_CHARS:
        reglamento = reglamento[:MAX_REGLAMENTO_CHARS]
        reglamento_truncado = True
    nombre_est = db.get_config("nombre_establecimiento", "el establecimiento")
    rol_usuario = session.rol() or "desconocido"

    partes = [
        f"El usuario que te está hablando ahora tiene el rol '{rol_usuario}' "
        f"en la app. Ten esto en cuenta al explicar qué puede hacer — si "
        f"pregunta por una pantalla que su rol no puede ver, dile que esa "
        f"función está reservada a otro rol en vez de explicar cómo llegar "
        f"a algo que no verá en su menú.",
        f"Te llamas Liceín, el asistente de MiAppoderado, la app de gestión "
        f"del comedor escolar (Programa de Alimentación Escolar) de "
        f"{nombre_est}. Preséntate como Liceín solo si te preguntan tu "
        f"nombre o al inicio de la conversación — no lo repitas en cada "
        f"respuesta. Respondes en español, de forma breve y concreta, SOLO sobre dos temas: "
        f"(1) cómo usar la app MiAppoderado — para esto tienes el conocimiento "
        f"detallado de la app más abajo, úsalo para dar instrucciones "
        f"concretas (qué pantalla abrir, qué botón usar), no respuestas "
        f"vagas, y "
        f"(2) el reglamento interno / de convivencia del liceo, entregado "
        f"abajo (NO es específico del programa PAE — es el reglamento "
        f"general del establecimiento). "
        f"Si preguntan algo fuera de esos dos temas, dilo y redirige la "
        f"conversación. Si no sabes algo o no está en el reglamento entregado, "
        f"dilo claramente en vez de inventar una respuesta — son reglas "
        f"reales del liceo, no las inventes ni las supongas.",
        f"\n--- CONOCIMIENTO DE LA APP ---\n{APP_KNOWLEDGE}--- FIN CONOCIMIENTO DE LA APP ---",
    ]
    if reglamento:
        aviso_corte = (
            "\n(NOTA: este es solo un extracto — el documento completo es "
            "más largo. Si la pregunta parece requerir una sección no "
            "incluida acá, dilo en vez de asumir que esto es todo el "
            "reglamento.)" if reglamento_truncado else ""
        )
        partes.append(
            f"\n--- REGLAMENTO DEL LICEO ---{aviso_corte}\n{reglamento}\n--- FIN REGLAMENTO ---"
        )
    else:
        partes.append(
            "\n(Todavía no se cargó el texto del reglamento en Configuración. "
            "Si preguntan sobre reglas específicas del programa, indica que "
            "falta configurarlo y que consulten con administración mientras tanto.)"
        )
    return "\n".join(partes)


def ask(pregunta: str, historial: list[dict] | None = None) -> tuple[bool, str]:
    """
    Envía una pregunta a Gemini. Retorna (ok, respuesta_o_mensaje_error).
    historial: lista de {"role": "user"|"model", "text": str} para dar contexto
               de turnos anteriores de la misma conversación.
    """
    api_key = db.get_config("gemini_api_key", "").strip()
    if not api_key:
        return False, (
            "El asistente no está configurado todavía. Pide al administrador "
            "que agregue la clave de Gemini en Configuración → Asistente IA."
        )

    contents = []
    for turno in (historial or []):
        role = "user" if turno.get("role") == "user" else "model"
        contents.append({"role": role, "parts": [{"text": turno.get("text", "")}]})
    contents.append({"role": "user", "parts": [{"text": pregunta}]})

    payload = {
        "system_instruction": {"parts": [{"text": _system_prompt()}]},
        "contents": contents,
    }

    req = urllib.request.Request(
        f"{GEMINI_URL}?key={api_key}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=25, context=_ssl_ctx()) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        texto = (
            data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
                .strip()
        )
        if not texto:
            return False, "El asistente no devolvió una respuesta. Intenta de nuevo."
        return True, texto
    except urllib.error.HTTPError as e:
        if e.code == 429:
            body = e.read().decode("utf-8", errors="replace")
            # OJO: shared_config (sync de la clave de Gemini entre
            # instalaciones, ver sync.py) requiere una migración manual de
            # SQL en Supabase que puede no haberse corrido nunca — no asumir
            # que la clave está compartida solo porque el código lo permite.
            # Gemini distingue el motivo en el body (PerDay vs PerMinute):
            # con una clave gratuita nueva, un 429 en la primera consulta
            # suele ser cupo DIARIO ya gastado (o de tokens, si el
            # reglamento cargado es largo), no ráfaga de pedidos.
            if "PerDay" in body or "per day" in body.lower():
                return False, (
                    "Se agotó el cupo diario gratuito de la clave de Gemini. "
                    "Vuelve a intentar mañana, o revisa el plan/cupo de esa "
                    "clave en Configuración → Asistente IA."
                )
            return False, (
                "Se alcanzó el límite de consultas del plan gratuito de "
                "Gemini para esta clave. Espera un momento y vuelve a "
                "intentar; si vuelve a pasar seguido, revisa el cupo de la "
                "clave en Configuración → Asistente IA."
            )
        if e.code in (401, 403):
            return False, "La clave de Gemini no es válida. Revísala en Configuración."
        return False, f"Error del servicio de IA ({e.code}). Intenta más tarde."
    except (socket.timeout, TimeoutError):
        return False, "El servicio de IA demoró demasiado en responder. Intenta de nuevo."
    except urllib.error.URLError as e:
        # Solo un DNS/socket real que no resuelve o rechaza conexión implica
        # falta de internet — cualquier otro motivo (proxy, firewall, cert)
        # se reporta aparte para no confundir al usuario ni ocultar la causa real.
        if isinstance(e.reason, socket.gaierror) or isinstance(e.reason, ConnectionRefusedError):
            return False, "Sin conexión a internet — el asistente necesita internet para responder."
        return False, f"No se pudo conectar con el asistente: {e.reason}"
    except Exception as exc:
        return False, f"No se pudo conectar con el asistente: {exc}"
