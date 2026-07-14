# MiAppoderado

Sistema de control de asistencia al comedor escolar (Programa de Alimentación Escolar — PAE), desarrollado para el **Liceo Bicentenario Héroes de la Concepción**, Laja, Chile.

Registra el ingreso de cada estudiante escaneando su cédula de identidad, controla cupos diarios, inasistencias (strikes) y sincroniza los datos con Supabase como respaldo en la nube.

---

## Descarga (Windows y macOS)

Cada push a `main` compila automáticamente una versión nueva para ambas plataformas vía GitHub Actions. El link siempre apunta a la última build — no cambia entre versiones:

**➜ [github.com/Darksax/pae-control/releases/latest](https://github.com/Darksax/pae-control/releases/latest)**

Ese link siempre sigue a `main` (puede tener cambios sin probar a fondo). Para una versión fija y citable, usa la [lista de releases versionados](https://github.com/Darksax/pae-control/releases) (ej. `v1.5.0`).

**Windows** (10 de 64-bit, 1809 o superior):
- `MiAppoderado.exe` — versión portable, se ejecuta directo sin instalar.
- `MiAppoderado_Setup_*.exe` — instalador con acceso directo en Escritorio e Inicio.

**macOS**:
- `MiAppoderado_mac.dmg` — arrastra a Aplicaciones.
- `MiAppoderado_mac.zip` — alternativa si el `.dmg` no está disponible en esa build.

Ninguna requiere Python instalado.

---

## Login por defecto

Al iniciar por primera vez, la base de datos se crea vacía con un único usuario administrador:

| Usuario         | PIN      | Rol   |
|-----------------|----------|-------|
| `Administrador` | `123456` | admin |

**Cambia este PIN antes de usar el sistema con estudiantes reales.** Se cambia (o se crean más usuarios) desde **Configuración → Gestión de usuarios** una vez dentro de la app (requiere rol `admin`).

El login es solo por PIN: eliges tu nombre de una lista y escribes el PIN, no hay campo de usuario/contraseña por texto.

---

## Roles y permisos

| Rol           | Acceso                                                                 |
|---------------|-------------------------------------------------------------------------|
| `admin`       | Todo — incluye Configuración, Importar, Sync Supabase y gestión de usuarios. |
| `pae`         | Escaneo, Cupos por día, Estudiantes (solo ficha RSH), Reportes. |
| `inspectoria` | Inspectoría (atrasos/pases/licencias), Estudiantes (nombre/curso/teléfono, sin RSH), Reportes. |

---

## Funcionalidades principales

- **Escaneo** — pantalla principal de operación: lee el RUN (cédula) y registra la asistencia a la comida activa según el horario configurado.
- **Cupos por día** — define cupos totales, fecha de inicio del servicio, excepciones (feriados, raciones frías, suspensión de varios días de una vez) por fecha.
- **Estudiantes** — ficha, estado (activo/lista de espera/inactivo), puntaje RSH.
- **Inspectoría** — atrasos, pases, licencias médicas y suspensiones escolares.
- **Reportes** — resumen semanal/mensual, top de inasistencias.
- **Importar** — carga de nómina desde archivos SIGE (.xls).
- **Sync Supabase** — respaldo en la nube, push/pull incremental de estudiantes, registros, strikes y usuarios.
- **Configuración** — cupos, comidas y horarios, gestión de usuarios, credenciales Supabase, integración WhatsApp.

### Reglas de negocio clave

- **Strikes**: un strike se genera por faltar a una comida anterior operada ese día, o al día completo anterior. El contador de strikes **se reinicia al cerrar el período/semestre** (`Configuración`), no es acumulado histórico.
- **Fuera de horario**: un escaneo fuera de la ventana horaria de todas las comidas no registra nada (estado `fuera_horario`) — evita que un escaneo de prueba consuma por error la comida real del estudiante.
- **Cupo diario**: si el escaneo supera el cupo configurado, igual se registra (no se le niega comida a nadie) pero se muestra una advertencia visual en pantalla.

---

## Desarrollo

Requiere Python 3.10+.

```bash
pip install -r requirements.txt
pip install supabase          # opcional, solo si vas a usar sincronización
python3 main.py
```

La base de datos SQLite se crea automáticamente en `~/pae_control/pae.db` la primera vez que corre.

### Estructura

```
main.py         — punto de entrada
db.py           — capa de base de datos (SQLite, WAL mode)
logic.py        — lógica de negocio del escaneo (procesar_scan)
utils.py        — validación de RUN, formato, horarios
sync.py         — sincronización con Supabase
ui/             — pantallas PyQt6 (una por módulo, ver tabla de roles arriba)
tests/          — suite de carga (ver tests/README_TESTS.md)
```

### Tests de carga

```bash
cd tests
python3 stress_test_pae.py        # 9 escenarios: throughput, concurrencia, fuzz, integridad…
python3 stress_test_breakfast.py  # simulación lunes 07:30 con lógica de strikes de ayer
```

Corren contra una **copia** de la base de datos real — nunca tocan `~/pae_control/pae.db`. Detalle completo en [tests/README_TESTS.md](tests/README_TESTS.md).

---

## Compilar

**macOS**: doble clic en `BUILD_MAC.command`, o `bash build_mac.sh`.

**Windows**: doble clic en `BUILD_WIN.bat` (requiere Python instalado en esa máquina), o simplemente usa el build automático de GitHub Actions descrito arriba — no hace falta compilar a mano.

El instalador de Windows (`MiAppoderado_Setup.iss`) se compila con [Inno Setup 6](https://jrsoftware.org/isinfo.php); el workflow de CI ya lo hace solo.

---

## Sincronización Supabase

Configura URL y clave del proyecto en **Configuración → Credenciales Supabase**. El SQL de esquema/migraciones está en `sync.py` (`SCHEMA_SQL`, `MIGRATION_SQL`) y en `supabase_migration.sql` — pégalo en el SQL Editor de Supabase la primera vez o al actualizar de versión.

La sincronización nunca sube la tabla `config` (ahí viven los tokens de WhatsApp/SMTP/Supabase) — solo estudiantes, usuarios (PIN ya hasheado), registros, strikes, log de estados y suspensiones.

---

## Seguridad

- El PIN de usuarios se guarda hasheado (SHA-256), no en texto plano.
- Las credenciales de terceros (Supabase, WhatsApp Business API, SMTP) sí se guardan en texto plano en la tabla `config` de `pae.db` — es un riesgo si el archivo `.db` se comparte o se sube a algún lado. No lo subas a repositorios ni lo envíes por canales no cifrados.
- Cambia el PIN por defecto (`123456`) antes de poner el sistema en producción.
