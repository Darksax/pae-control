"""
patchnotes.py — Fuente de verdad para versión, autoría y changelog de PAE Control.

Para publicar un update:
  1. Sube los .py modificados a tu repo GitHub
  2. Actualiza manifest.json en el repo con la nueva versión y lista de archivos
  3. Los clientes descargan automáticamente los parches al abrir la app
"""

# ── Identidad ──────────────────────────────────────────────────────────────
VERSION       = "1.0.0"
BUILD_DATE    = "2026-06-09"
AUTHOR        = "Marcelo Muñoz Lastra"
AUTHOR_TITLE  = "Profesor de Historia · Magíster en Evaluación (UNAB)"
INSTITUTION   = "Liceo Bicentenario Héroes de la Concepción"
CITY          = "Laja, Chile"

# ── URL del manifest en GitHub ─────────────────────────────────────────────
# Cambia TU_USUARIO por tu usuario de GitHub y el nombre del repo si lo renombras.
# El repo debe ser público (o usar token si es privado).
# Deja vacío ("") para deshabilitar updates automáticos.
GITHUB_MANIFEST = (
    "https://raw.githubusercontent.com/Darksax/pae-control/main/manifest.json"
)

# ── Changelog ─────────────────────────────────────────────────────────────
# Orden: más nuevo primero. El startup dialog muestra todas las versiones.
# Formato por entrada:
#   version  : str   "MAJOR.MINOR.PATCH"
#   date     : str   "YYYY-MM-DD"
#   title    : str   Título corto de la release
#   notes    : list  Cambios en frases nominales (sin infinitivo, sin punto final)
PATCHNOTES = [
    {
        "version": "1.0.0",
        "date":    "2026-06-09",
        "title":   "Lanzamiento oficial",
        "notes": [
            "Control de asistencia PAE con escaneo de cédulas (USB/Bluetooth)",
            "Nómina PAE y lista de espera con prioridad por puntaje RSH",
            "Cupos diarios con override por fecha y control de comida fría",
            "Suspensiones de cupo: cálculo automático días hábiles/corridos",
            "Auto-llenado de lista de espera por vulnerabilidad (RSH 0–40 %)",
            "Reportes de asistencia y nómina exportables",
            "Sincronización con Supabase (respaldo en nube)",
            "Importación masiva de estudiantes desde CSV/Excel",
            "Sistema de strikes por inasistencia con alerta semanal",
            "Edición de puntaje RSH con selector de paso 10 %",
            "Clic en celda → copia al portapapeles",
            "Columnas de tabla redimensionables",
            "Chips de stats en tiempo real (PAE activos / Almuerzos hoy)",
        ],
    },
]
