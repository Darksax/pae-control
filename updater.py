"""
updater.py — Sistema de parches sin recompilar para MiAppoderado.

Cómo funciona:
  1. Los parches son archivos .py que sobreescriben módulos del bundle.
  2. Se almacenan en ~/pae_control/patches/ (misma carpeta que la DB).
  3. Al iniciar, apply_local_patches() agrega patches/ al frente de sys.path.
     Python carga primero los archivos de ahí → el bundle queda sobreescrito.
  4. En background, check_for_updates_async() descarga manifest.json desde
     GitHub y compara versiones. Si hay update, descarga los .py nuevos.
  5. El usuario reinicia la app → parches activos.

Formato manifest.json (subir al repo GitHub):
  {
    "version": "1.1.0",
    "date": "2026-07-15",
    "notes": ["Fix X", "Mejora Y"],
    "patches": [
      {
        "path": "db.py",
        "url":  "https://raw.githubusercontent.com/TU_USUARIO/pae-control/main/db.py",
        "sha256": "abc123..."   <- opcional pero recomendado
      },
      {
        "path": "ui/students_screen.py",
        "url":  "https://raw.githubusercontent.com/..."
      }
    ]
  }
"""

import os
import sys
import json
import hashlib
import threading
from pathlib import Path
from typing import Optional, Callable

# Directorio de parches: ~/pae_control/patches/
# (mismo árbol que pae.db para facilitar backup)
PATCHES_DIR = Path.home() / "pae_control" / "patches"


# ─────────────────────── PATHS ────────────────────────────────────────────

def get_patches_dir() -> Path:
    PATCHES_DIR.mkdir(parents=True, exist_ok=True)
    return PATCHES_DIR


def apply_local_patches():
    """
    Prepend patches/ a sys.path para que los .py descargados sobreescriban
    los módulos del bundle PyInstaller.

    DEBE llamarse en main.py ANTES de cualquier import de la app.
    """
    pd = get_patches_dir()
    paths_to_add = [str(pd)]

    # Agregar subdirectorios (ui/, etc.)
    if pd.exists():
        for sub in sorted(pd.iterdir()):
            if sub.is_dir():
                paths_to_add.append(str(sub))

    for p in paths_to_add:
        if p not in sys.path:
            sys.path.insert(0, p)


# ─────────────────────── NETWORK ──────────────────────────────────────────

def _fetch_json(url: str, timeout: int = 6) -> dict:
    """Lanza la excepción de red/parseo tal cual — check_manifest() la deja
    pasar para que check_for_updates_async() pueda distinguir "no hay
    update" (None) de "no se pudo comprobar" (on_error), algo que antes se
    perdía acá al tragarse cualquier excepción y devolver None en ambos
    casos por igual."""
    import urllib.request
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _version_tuple(v: str):
    try:
        return tuple(int(x) for x in str(v).split("."))
    except Exception:
        return (0,)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ─────────────────────── MANIFEST CHECK ───────────────────────────────────

def check_manifest(url: str, current_version: str) -> Optional[dict]:
    """
    Descarga manifest.json y comprueba si hay versión más nueva.
    Retorna el dict del manifest si hay update disponible, None si no.
    """
    if not url or "TU_USUARIO" in url:
        return None  # URL no configurada todavía

    data = _fetch_json(url)
    if not data or "version" not in data:
        return None

    if _version_tuple(data["version"]) <= _version_tuple(current_version):
        return None  # Ya está en la última versión

    return data


# ─────────────────────── DOWNLOAD ─────────────────────────────────────────

def download_patch_files(manifest: dict) -> tuple:
    """
    Descarga todos los archivos listados en manifest['patches'] al
    directorio patches/.

    Retorna:
        (ok: bool, errors: list[str])

    Errores típicos: red caída, hash incorrecto, permisos.
    """
    import urllib.request

    pd = get_patches_dir()
    errors = []

    for patch in manifest.get("patches", []):
        url      = patch.get("url", "").strip()
        rel_path = patch.get("path", "").strip()
        expected = patch.get("sha256", "").strip().lower()

        if not url or not rel_path:
            continue

        dest = pd / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)

        try:
            with urllib.request.urlopen(url, timeout=15) as r:
                data = r.read()
        except Exception as e:
            errors.append(f"{rel_path}: error de red — {e}")
            continue

        if expected and _sha256_bytes(data) != expected:
            errors.append(f"{rel_path}: hash SHA256 no coincide (corrupto)")
            continue

        dest.write_bytes(data)

    if not errors:
        # Guardar versión instalada para no descargar de nuevo
        (pd / "installed_version.txt").write_text(
            manifest.get("version", "0.0.0"), encoding="utf-8"
        )

    return (len(errors) == 0), errors


# ─────────────────────── ASYNC HELPER ─────────────────────────────────────

def check_for_updates_async(
    manifest_url: str,
    current_version: str,
    on_update_found: Callable,
    on_no_update: Optional[Callable] = None,
    on_error: Optional[Callable] = None,
):
    """
    Comprueba updates en un thread daemon para no bloquear la UI.

    Callbacks (se ejecutan en el thread, usar QTimer.singleShot para UI):
        on_update_found(manifest: dict)
        on_no_update()
        on_error(exception: str)
    """
    def _worker():
        try:
            manifest = check_manifest(manifest_url, current_version)
            if manifest:
                on_update_found(manifest)
            elif on_no_update:
                on_no_update()
        except Exception as e:
            if on_error:
                on_error(str(e))

    t = threading.Thread(target=_worker, daemon=True, name="pae-update-check")
    t.start()


# ─────────────────────── INSTALLED VERSION ────────────────────────────────

def get_installed_patch_version() -> Optional[str]:
    """Versión del último parche instalado (None si patches/ está vacío)."""
    p = get_patches_dir() / "installed_version.txt"
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    return None


def clear_patches():
    """Elimina todos los parches instalados (rollback manual)."""
    import shutil
    if PATCHES_DIR.exists():
        shutil.rmtree(PATCHES_DIR)
    PATCHES_DIR.mkdir(parents=True, exist_ok=True)
