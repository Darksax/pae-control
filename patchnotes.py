"""
patchnotes.py — Fuente de verdad para versión, autoría y changelog de MiAppoderado.

manifest.json se genera y publica solo — el job "publish" en
.github/workflows/build-release.yml lo arma en cada push a main (hasheando
los .py del commit) y lo sube como asset del release "latest". No hace
falta tocarlo a mano.
"""

# ── Identidad ──────────────────────────────────────────────────────────────
VERSION       = "1.5.14"
BUILD_DATE    = "2026-07-13"
AUTHOR        = "Darksax (creador)"
AUTHOR_TITLE  = "Laja · 2026"
INSTITUTION   = "Liceo Bicentenario Héroes de la Concepción"
CITY          = "Laja, Chile"

# ── URL del manifest en GitHub ─────────────────────────────────────────────
# Asset del release "latest" (no un archivo commiteado en main) — así CI lo
# regenera y publica en cada build sin necesitar un commit de vuelta al repo.
# Deja vacío ("") para deshabilitar updates automáticos.
GITHUB_MANIFEST = (
    "https://github.com/Darksax/pae-control/releases/latest/download/manifest.json"
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
        "version": "1.5.14",
        "date":    "2026-07-13",
        "title":   "Corrección crítica: foco atrapado en Escaneo, y clave de Supabase con caracteres inválidos",
        "notes": [
            "Corregido: al usar la barra de búsqueda manual (nombre/RUN) en Escaneo, el foco quedaba atrapado ahí para siempre — ni el watchdog de 5s, ni clicks, ni cambiar de pestaña lo devolvían, solo cerrar y reabrir la app. Mismo fix aplicado a la búsqueda de Inspectoría.",
            "Supabase/Gemini: la URL y la clave ahora se validan como ASCII puro antes de guardarse — un copy-paste con una tilde o ñ de más ya no revienta 2 pantallas después con un error críptico, se rechaza al momento con un mensaje claro.",
            "Los errores de conexión a Supabase ahora se suben automático a un registro para diagnóstico, sin depender de que alguien recuerde abrir 'Reportar bug'.",
            "Esta actualización se puede instalar completa desde 'Buscar actualizaciones' en la barra superior — no hace falta reinstalar ni volver a configurar Supabase/Gemini.",
        ],
    },
    {
        "version": "1.5.13",
        "date":    "2026-07-13",
        "title":   "Soporte para builds privados con config precargada",
        "notes": [
            "Nuevo: config_default.json opcional (ver config_default.example.json) para precargar Supabase/Gemini en un build armado localmente, sin depender del servidor de bootstrap ni de red al primer arranque — pensado para instaladores privados que no pasan por GitHub. Nunca se sube al repo (está en .gitignore).",
        ],
    },
    {
        "version": "1.5.12",
        "date":    "2026-07-13",
        "title":   "Corrección: 'Reportar bug' se quedaba pegado hasta 2 minutos",
        "notes": [
            "El cliente de Supabase usa 120 segundos de timeout por defecto — con cualquier problema de red (no una caída total, algo más sutil), tanto 'Probar conexión' como 'Reportar bug' se quedaban con la UI pegada hasta 2 minutos antes de mostrar cualquier error",
            "Bajado a 15 segundos en ambos casos — falla rápido y muestra el error real en vez de parecer colgado",
        ],
    },
    {
        "version": "1.5.11",
        "date":    "2026-07-13",
        "title":   "El error de 'Probar conexión' de Supabase ahora sí queda registrado",
        "notes": [
            "El error de codificación ('ascii' codec...) reportado en Sincronizar Supabase seguía pasando pese al fix de 1.5.3 — se detectó que el traceback real nunca quedaba guardado en ningún lado (el logging solo escribe a archivo en modo debug, y este error se atrapa antes de llegar al log de crashes general), así que nunca se pudo diagnosticar la causa real",
            "Ahora el traceback completo de 'Probar conexión' se guarda siempre en logs/errors.log, tenga o no modo debug activado, y 'Reportar bug' ya lo incluye — permite diagnosticar la causa real la próxima vez que pase",
        ],
    },
    {
        "version": "1.5.10",
        "date":    "2026-07-13",
        "title":   "Empaquetado: certifi explícito, referencias a pantallas eliminadas limpiadas",
        "notes": [
            "certifi (usado por el fix de certificado de 1.5.8/1.5.9) ahora se agrega explícito al build de Windows y macOS en vez de depender de que PyInstaller lo detecte solo — el import está dentro de un try/except a nivel de función, más fácil que se le escape al análisis estático",
            "Limpiadas referencias a bulk_screen/suspensions_screen/junaeb_screen (eliminadas en 1.5.7) que seguían en la lista de imports del build",
            "También sirve para probar el flujo de 'Buscar actualizaciones ahora' end-to-end desde una instancia en 1.5.9",
        ],
    },
    {
        "version": "1.5.9",
        "date":    "2026-07-13",
        "title":   "Corrección: el botón 'Buscar actualizaciones' no daba ningún resultado",
        "notes": [
            "El botón de buscar actualizaciones podía fallar en silencio (o sin mostrar el error real) por el mismo problema de certificado que ya se corrigió en la carga de config desde servidor (1.5.8) — updater.py usaba la verificación por defecto del sistema en vez del bundle propio de certifi",
            "Corregido y verificado: ahora detecta correctamente tanto 'ya estás al día' como 'hay una versión nueva disponible'",
            "URL del bootstrap precargada en Configuración, y mensaje específico cuando el servidor bloquea por intentos fallidos seguidos",
        ],
    },
    {
        "version": "1.5.8",
        "date":    "2026-07-13",
        "title":   "Corrección: la carga de config desde servidor fallaba por certificado en algunos PC",
        "notes": [
            "\"Cargar configuración desde servidor\" (nuevo en 1.5.7) podía fallar con un error de certificado en PC donde el almacén de certificados del sistema está vacío, aunque el certificado del servidor fuera válido — se detectó probando el deploy real",
            "Ahora usa el CA bundle propio de certifi en vez de depender del store del sistema operativo, igual que ya hacían las librerías de Supabase",
        ],
    },
    {
        "version": "1.5.7",
        "date":    "2026-07-13",
        "title":   "Reglamento con tope, botón de actualizar y limpieza de menú",
        "notes": [
            "El texto del reglamento no tenía límite de tamaño y se reenviaba completo en cada pregunta al Agente IA — con un reglamento largo (se detectó uno de ~300.000 caracteres), eso solo ya alcanza para agotar el cupo gratuito de Gemini en la primera consulta del día, sin necesidad de preguntar varias veces seguidas",
            "Ahora se manda como máximo un extracto de 24.000 caracteres por consulta",
            "Configuración → Asistente IA muestra el largo del reglamento pegado y avisa si supera el máximo",
            "Nuevo botón en la barra superior para buscar actualizaciones manualmente (antes solo se chequeaba solo al abrir, en silencio, sin forma de pedirlo de nuevo ni de saber si ya estabas al día)",
            "Eliminadas del menú las secciones Menú JUNAEB, Registro masivo y Pases (legacy) — quedaban sin uso, duplicadas o abandonadas",
            "Configuración → nueva tarjeta 'Cargar configuración desde servidor': en un PC nuevo, con URL + usuario + clave de un servidor de bootstrap propio (VPS del liceo, ver miappoderado-bootstrap-server), carga Supabase, Gemini y el reglamento de una vez en vez de teclear cada dato a mano",
        ],
    },
    {
        "version": "1.5.6",
        "date":    "2026-07-13",
        "title":   "Aviso más claro cuando se agota el cupo de Gemini",
        "notes": [
            "El aviso de límite de consultas del Agente IA ahora distingue cupo diario agotado de ráfaga por minuto, y sugiere revisar el cupo de la clave en Configuración en vez de decir siempre \"por minuto\"",
        ],
    },
    {
        "version": "1.5.5",
        "date":    "2026-07-13",
        "title":   "Corrección: la pantalla de Escaneo a veces desaparecía al cambiar de pantalla",
        "notes": [
            "La transición animada entre pantallas dejaba puesto (a opacidad 1) el efecto de fundido sobre la pantalla de destino después de terminar — en Escaneo, que tiene varios efectos propios (flash de resultado, sombras de tarjetas), ese efecto anidado a veces hacía que Qt renderizara la pantalla en blanco hasta el siguiente repintado grande",
            "Ahora el efecto de fundido se saca apenas termina la animación, dejando el render normal el resto del tiempo",
        ],
    },
    {
        "version": "1.5.4",
        "date":    "2026-07-13",
        "title":   "Actualizaciones automáticas en caliente",
        "notes": [
            "Al abrir, la app pregunta directo si hay una versión nueva disponible (antes solo cambiaba un botón que había que notar) — Sí la descarga e instala, y ofrece reiniciar sola para aplicarla",
            "manifest.json (la lista de archivos parcheables) ahora se genera y publica solo en cada build de CI, en vez de mantenerse a mano — quedaba desactualizado desde junio",
            "Este mecanismo cubre cambios de código Python; íconos, fuentes, dependencias nuevas o el instalador siguen requiriendo bajar el instalador completo desde Releases",
        ],
    },
    {
        "version": "1.5.3",
        "date":    "2026-07-13",
        "title":   "Corrección: error de codificación 'ascii' en Sincronizar (Windows)",
        "notes": [
            "Prueba de conexión / sincronización con Supabase: en algunos PC con Windows fallaba con 'ascii codec can't encode character...' (una ñ) en vez de conectar — se fuerza UTF-8 en stdout/stderr al iniciar la app para evitar este tipo de error de codificación",
            "El error de conexión ahora también queda registrado con su traceback completo en los logs, para poder diagnosticar más rápido si vuelve a ocurrir",
        ],
    },
    {
        "version": "1.5.2",
        "date":    "2026-07-13",
        "title":   "Corrección: íconos vacíos y falso aviso de sin conexión en el Agente IA",
        "notes": [
            "Íconos vacíos en el build compilado: icons.py no resolvía la carpeta assets/icons dentro del .exe/.app (usaba una ruta relativa a __file__ que no existe en el ejecutable empaquetado) — ahora usa el mismo mecanismo de sys._MEIPASS que el resto de la app",
            "Ícono faltante o corrupto ya no rompe la pantalla que lo pide: se muestra vacío en vez de crashear",
            "Agente IA (Liceín): ya no muestra 'Sin conexión a internet' ante fallas de certificado SSL — solo se reporta así cuando de verdad no hay red; otros errores de conexión ahora muestran su causa real",
            "Corrección de un AttributeError repetido en Inspectoría al abrir la app: el buscador por nombre instalaba su filtro de eventos antes de terminar de crear su propio popup",
        ],
    },
    {
        "version": "1.5.1",
        "date":    "2026-07-13",
        "title":   "Fecha de inicio de servicio, suspensión múltiple, cupo editable en Cupos",
        "notes": [
            "Fecha de inicio del servicio (Cupos por día): no se generan strikes por días anteriores a esta fecha — evita castigar escaneos de prueba u operación irregular antes del arranque oficial",
            "Suspender varios días de una vez: rango desde/hasta + motivo, en vez de marcar día por día",
            "Cupos totales (permanente) ahora editable directo desde Cupos por día — la persona a cargo de PAE ya no necesita acceso a Configuración (admin) para ajustarlo",
        ],
    },
    {
        "version": "1.5.0",
        "date":    "2026-07-13",
        "title":   "MiAppoderado: rebrand, rediseño visual y asistente IA",
        "notes": [
            "Renombrado de PAE Control a MiAppoderado — la app ya cubre más que solo el control PAE",
            "Ícono nuevo: glifo minimalista de apoderado/guardián sobre azul institucional",
            "Asistente IA 'Liceín' (Gemini): responde dudas de uso de la app y del reglamento del liceo; burbuja flotante cerrable; clave y reglamento se comparten entre instalaciones vía Supabase",
            "Rediseño visual: tipografía Inter, íconos Lucide reemplazando los glifos unicode, tarjetas con sombra suave en vez de bordes duros en Escaneo, Reportes, Inspectoría y el resto de las pantallas",
            "Sistema de temas: Oscuro / Claro / Pride Month, selector en la barra superior",
            "Corrección: un escaneo fuera de horario ya no registra por error en la comida siguiente (nuevo estado 'fuera_horario')",
            "Corrección: los strikes se reinician al cerrar el período/semestre en vez de acumularse para siempre",
            "Aviso visual (no bloqueante) cuando un escaneo supera el cupo diario configurado",
            "Foco de escaneo: vuelve solo al campo de RUN tras 5s de inactividad, con aviso 'vuelve a escanear' — evita que la pistola lectora mande texto a un campo equivocado",
            "Barra de noticias de educación eliminada (RSS y configuración asociada)",
            "Build automático en GitHub Actions: Windows (.exe + instalador) y macOS (.app + .dmg) en cada push, publicados juntos en un solo release",
        ],
    },
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
