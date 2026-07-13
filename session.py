"""
session.py — Sesión de usuario activa en MiAppoderado.
En memoria únicamente. Se pierde al cerrar la app.

Períodos:
  periodo_activo   = período donde se escriben datos nuevos  (viene de db config)
  viewing_period   = período que el usuario está visualizando ahora
                     "YYYY-SN"  → semestre específico
                     "YYYY"     → año completo (agrega todos los semestres)
"""

from __future__ import annotations

_current: dict | None = None
_viewing_period: str  = ""    # se inicializa desde db.get_periodo_activo() en main.py


def set_user(user: dict):
    global _current
    _current = user


def get() -> dict | None:
    return _current


def clear():
    global _current
    _current = None


def rol() -> str:
    return (_current or {}).get("rol", "")


def nombre() -> str:
    return (_current or {}).get("nombre", "")


def is_admin() -> bool:
    return rol() == "admin"


def can_inspectoria() -> bool:
    return rol() in ("inspectoria", "admin")


def can_pae() -> bool:
    return rol() in ("pae", "admin")


def is_logged_in() -> bool:
    return _current is not None


# ── Período visualizado ──────────────────────────────────────────────────────

def set_viewing_period(periodo: str):
    """Cambia el período que el usuario está viendo (no escribe a DB)."""
    global _viewing_period
    _viewing_period = periodo


def viewing_period() -> str:
    """
    Retorna el período actualmente seleccionado para visualización.
    Si no está inicializado, retorna el período activo de la DB.
    """
    if _viewing_period:
        return _viewing_period
    try:
        import db as _db
        return _db.get_periodo_activo()
    except Exception:
        return _default_periodo()


def is_viewing_full_year() -> bool:
    """True si el período seleccionado es un año completo (ej. '2026')."""
    p = viewing_period()
    return len(p) == 4 and p.isdigit()


def viewing_year() -> str:
    """El año del período visualizado."""
    p = viewing_period()
    return p[:4]


def _default_periodo() -> str:
    from datetime import date
    d = date.today()
    sem = "S1" if d.month <= 6 else "S2"
    return f"{d.year}-{sem}"
