"""
bootstrap_client.py — Carga la config inicial (Supabase, Gemini, reglamento)
desde un servidor de bootstrap propio (ver miappoderado-bootstrap-server),
para no tener que teclearla a mano en cada PC nuevo.

No tiene nada que ver con GitHub/manifest.json (eso son parches de código,
público) — este es un servidor privado del liceo, con usuario/clave por PC,
que sirve credenciales reales. Por eso NO usa la clave de Gemini/Supabase
compartida vía sync.py (esa sync ni siquiera está activa todavía).
"""

import base64
import json
import urllib.error
import urllib.request


def fetch_bootstrap(url: str, username: str, password: str, timeout: int = 10) -> tuple[bool, dict | str]:
    """
    Descarga la config desde el endpoint de bootstrap.
    Retorna (True, config_dict) o (False, mensaje_de_error).

    A diferencia de whatsapp.py/assistant.py, acá NO se usa un contexto SSL
    sin verificar: este request manda usuario/clave (Basic Auth) y recibe
    claves reales de Supabase/Gemini de vuelta — saltarse la verificación
    del certificado dejaría eso interceptable por cualquiera en el camino
    (MITM). Se usa la verificación TLS por defecto de Python, y se exige
    https:// explícito para no mandar Basic Auth en texto plano por error.
    """
    url = url.strip()
    if not url:
        return False, "Falta la URL del servidor."
    if not url.lower().startswith("https://"):
        return False, "La URL debe empezar con https:// — por http:// la clave viajaría sin cifrar."

    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Basic {token}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return True, data
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False, "Usuario o clave incorrectos para este servidor."
        return False, f"Error del servidor ({e.code})."
    except urllib.error.URLError as e:
        return False, f"No se pudo conectar al servidor: {e.reason}"
    except Exception as exc:
        return False, f"Respuesta inválida del servidor: {exc}"
