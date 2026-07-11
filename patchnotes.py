"""
patchnotes.py — Fuente de verdad para versión, autoría y changelog de PAE Control.

Para publicar un update:
  1. Sube los .py modificados a tu repo GitHub
  2. Actualiza manifest.json en el repo con la nueva versión y lista de archivos
  3. Los clientes descargan automáticamente los parches al abrir la app
"""

# ── Identidad ──────────────────────────────────────────────────────────────
VERSION       = "1.4.0-beta"
BUILD_DATE    = "2026-06-14"
AUTHOR        = "Darksax (creador)"
AUTHOR_TITLE  = "Laja · 2026"
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
        "version": "1.4.0-beta",
        "date":    "2026-06-14",
        "title":   "Sistema de períodos + UI dark navy",
        "notes": [
            "Tema dark navy en toda la interfaz: paleta unificada con la pantalla de login (fondos #0D1627 → #162035, texto #EEF2FF)",
            "Sistema de períodos (semestral): columna 'periodo' en attendance y student_suspensions, migración automática de datos existentes",
            "Selector de período en toolbar: permite ver datos de cualquier semestre o el año completo (ej. '2026') sin perder el historial",
            "Función admin 'Cerrar período': crea un nuevo período activo preservando todo el historial; disponible en Configuración",
            "session.py: nuevo concepto viewing_period separado de periodo_activo — el usuario puede navegar períodos sin afectar la escritura",
            "db.get_periodos_disponibles(): lista dinámica de períodos con opción de año completo cuando hay ≥1 semestre",
            "get_pases_stats_hoy() y get_pases_estudiante() actualizados para respetar el período activo/visualizado",
            "Registros de asistencia y pases nuevos se estampan automáticamente con el período activo",
        ],
    },
    {
        "version": "1.3.0-beta",
        "date":    "2026-06-14",
        "title":   "Pulido UI + corrección de bugs",
        "notes": [
            "Pantalla de login rediseñada: tema dark navy, tarjetas de usuario con barra de color por rol, dots PIN reales (QFrame con border-radius, no unicode), numpad con bordes sutiles",
            "Bug reporter corregido: botón 'Reportar error' ya abre el formulario (faltaban QComboBox y QTextEdit en imports)",
            "Renombrado 'Reportar error' → 'Reportar bug' para mayor claridad",
            "Dropdown de búsqueda por nombre ya no bloquea la pantalla: al cerrar sin selección devuelve el foco al campo de texto automáticamente",
            "Widget de clima eliminado del toolbar (nunca fue funcional en macOS sin certificados SSL)",
            "Iconos del sidebar renovados con set geométrico consistente",
            "Bug reporter migrado a Supabase: los reportes se suben a la tabla bug_reports con contexto completo de sistema, logs y versión",
            "Sync corregido: columna operacion_id (solo local) ya no se intenta subir a Supabase",
            "Estado del toggle 'Imprimir pase' ya se guarda y restaura entre sesiones (clave print_pase_auto)",
            "Dropdown de búsqueda en pantalla Escaneo también corregido: al cerrar sin selección devuelve el foco al campo de texto",
            "Chips del toolbar ahora muestran información según rol: Inspectoría ve 'Pases hoy' y 'Sin firmar'; PAE/Admin siguen viendo PAE activos y Almuerzos hoy",
        ],
    },
    {
        "version": "1.2.0",
        "date":    "2026-06-13",
        "title":   "Módulo Inspectoría",
        "notes": [
            "Pantalla Inspectoría con 6 tabs: Atrasos, Inasistencias, Retiros, Firma Apoderado, Licencias, Notificaciones WA",
            "Scanner de RUN en Atrasos/Inasistencias/Retiros: mismo sistema que PAE (debounce configurable, auto-reset, búsqueda por nombre)",
            "Registro de pases con stats por estudiante: total mes, semestre, total histórico, sin firma",
            "Alerta visual de umbral de pases sin firma (configurable, defecto 3): banner rojo 'Llamar al apoderado'",
            "Justificación automática de comidas al registrar pase: Retiro justifica comidas desde la hora de salida, Atraso justifica comidas ya terminadas",
            "Tab Firma de Apoderado: búsqueda por nombre o RUN, listado de pases pendientes, confirmación de firma con prompt",
            "Tab Licencias médicas: formulario con fecha de inicio y cantidad de días",
            "Tab Notificaciones WA: tabla de atrasos del día/semana con checkbox por fila, envío batch asíncrono, estado por fila (enviado/encolado/sin número)",
            "Teléfono de apoderado editable inline en la tabla de notificaciones — guarda directo en DB",
            "Selección inteligente 'Sin teléfono': marca automáticamente las filas sin número registrado",
            "Reportes Inspectoría ampliados: KPIs Atrasos/Inasistencias/Retiros/Sin firma/WA (mes)",
            "Registro de pases exportable a CSV filtrado por Hoy/Semana/Mes",
            "Top mensual de estudiantes con más pases: columnas Atrasos/Inasistencias/Retiros/Total, ordenable por clic en columna o botón",
            "Top mensual exportable a CSV",
            "Sistema de usuarios con PIN SHA-256: roles admin, pae, inspectoria con acceso diferenciado por pantalla y menú contextual",
            "Campo telefono_apoderado en importación CSV/Excel (detección automática de columna)",
            "Sync con Supabase extendido: tabla student_suspensions con firmado, firmado_en, firmado_por",
        ],
    },
    {
        "version": "1.1.0",
        "date":    "2026-06-12",
        "title":   "Escaneo masivo + UX",
        "notes": [
            "Auto-submit del scanner reescrito: debounce simple 180ms (configurable) — sin detección de velocidad, 100% fiable",
            "Formato RUN corregido para RUNs 20M-28M: threshold 9 dígitos, DV en posición correcta",
            "Botones de auto-reset de pantalla corregidos (padding/visuales)",
            "Flash rojo de pantalla corregido en macOS (paintEvent override, sin WA_TranslucentBackground)",
            "Texto 'NO BENEFICIADO' en mayúsculas, tamaño 22px, borde rojo — visible desde lejos",
            "Sonido de error: Sosumi (×2.5 volumen) + Basso 480ms después — audible a distancia",
            "Botón 'Autorizar esta vez' cambiado a rojo",
            "Alerta de ausencias previas en pantalla de escaneo: muestra comidas faltadas del día o del día anterior",
            "Toggle 'Por nombre / Por RUN' en barra de búsqueda manual — RUN con formato visual, submit en Enter",
            "Búsqueda por nombre ignora tildes y mayúsculas (buscar 'tomas' encuentra 'Tomás')",
            "Clic en celda RUN/datos → copia al portapapeles con tooltip visual",
            "Reportes semanal/mensual exportan por día (quiénes asistieron cada fecha)",
            "UI global: tipografía SF Pro, bordes 1.5px, radios 10-12px, jerarquía de headers mejorada",
            "Sección 'Pantalla de escaneo' en Configuración: delay, flash, ausencias, sonido doble, auto-reset por defecto",
        ],
    },
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
