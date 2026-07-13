"""
assistant.py — Asistente IA (Gemini) para dudas de reglamento del liceo y uso de la app.

Usa la API REST de Gemini directo por HTTP (sin dependencia nueva de pip),
igual de simple que sync.py/whatsapp.py. La clave y el texto del reglamento
viven en la tabla config (igual que las credenciales de Supabase/WhatsApp) —
nunca se sincronizan a Supabase (ver sync.py, la tabla config no se sube).
"""

import json
import urllib.request
import urllib.error

import db
import session

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
- Registro masivo (pae, admin) — marca asistencia de un curso completo de \
una vez, sin escanear uno por uno.
- Cupos por día (pae, admin) — define el cupo total de raciones, y \
excepciones por fecha (feriados sin servicio, días de ración fría).
- Menú JUNAEB (pae, admin) — visor del menú semanal del programa.
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
- pae: Escaneo, Registro masivo, Cupos por día, Menú JUNAEB, Estudiantes \
(solo ficha RSH), Reportes.
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


def is_configured() -> bool:
    return bool(db.get_config("gemini_api_key", "").strip())


def _system_prompt() -> str:
    reglamento = db.get_config("gemini_reglamento", "").strip()
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
        partes.append(f"\n--- REGLAMENTO DEL LICEO ---\n{reglamento}\n--- FIN REGLAMENTO ---")
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
        with urllib.request.urlopen(req, timeout=25) as resp:
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
            return False, (
                "Se alcanzó el límite de consultas por minuto del plan gratuito. "
                "Espera un momento y vuelve a intentar."
            )
        if e.code in (401, 403):
            return False, "La clave de Gemini no es válida. Revísala en Configuración."
        return False, f"Error del servicio de IA ({e.code}). Intenta más tarde."
    except urllib.error.URLError:
        return False, "Sin conexión a internet — el asistente necesita internet para responder."
    except Exception as exc:
        return False, f"No se pudo conectar con el asistente: {exc}"
