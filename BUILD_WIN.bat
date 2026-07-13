@echo off
REM BUILD_WIN.bat — Compila MiAppoderado como .exe para Windows
REM Doble clic para ejecutar (requiere Python 3.10+ instalado en Windows).

title MiAppoderado — Build Windows
cd /d "%~dp0"

echo.
echo  ==========================================
echo    MiAppoderado ^— Build Windows
echo    Liceo Bicentenario Hereos de la Concepcion
echo  ==========================================
echo.

REM ── 1. Verificar Python ────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no encontrado.
    echo Descarga Python 3.12 desde https://www.python.org/downloads/
    echo Asegurate de marcar "Add Python to PATH" durante la instalacion.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version') do echo Python: %%i
echo.

REM ── 2. Generar icono .ico ──────────────────────────────────────────────
if not exist "assets\AppIcon.ico" (
    echo Generando AppIcon.ico...
    python make_AppIcon_win.py
    if errorlevel 1 (
        echo WARN: No se pudo generar el icono. Continuando sin icono...
    ) else (
        echo OK  AppIcon.ico creado
    )
)

REM ── 3. Instalar dependencias ───────────────────────────────────────────
echo Instalando / actualizando dependencias...
python -m pip install --upgrade pip --quiet
python -m pip install --upgrade PyQt6 PyQt6-WebEngine pyinstaller supabase --quiet
if errorlevel 1 (
    echo ERROR: Fallo la instalacion de dependencias.
    pause
    exit /b 1
)
echo OK  Dependencias listas
echo.

REM ── 4. Limpiar builds anteriores y caché de Python ───────────────────
echo Limpiando build anterior y cache...
if exist "build" rmdir /s /q "build"
if exist "dist\MiAppoderado.exe" del /q "dist\MiAppoderado.exe"
REM Eliminar __pycache__ para forzar recompilación del fuente actualizado
for /d /r . %%d in (__pycache__) do (
    if exist "%%d" rmdir /s /q "%%d"
)
echo OK  Limpio
echo.

REM ── 5. Compilar ───────────────────────────────────────────────────────
echo Compilando .exe (puede tardar 3-8 minutos)...
echo.
python -m PyInstaller MiAppoderado_win.spec --clean --noconfirm

if not exist "dist\MiAppoderado.exe" (
    echo.
    echo ERROR: No se genero el .exe. Revisa los mensajes de error arriba.
    pause
    exit /b 1
)

echo.
echo OK  Compilacion exitosa
echo.

REM ── 6. Resultado ──────────────────────────────────────────────────────
echo  ==========================================
echo    BUILD COMPLETADO
echo  ==========================================
echo.
echo   .exe  -^>  dist\MiAppoderado.exe
echo.
echo  Para distribuir: copia 'MiAppoderado.exe' y la carpeta 'dist\'
echo  completa al equipo destino (o usa Inno Setup para crear un instalador).
echo.

REM Abrir carpeta dist
explorer dist\

pause
