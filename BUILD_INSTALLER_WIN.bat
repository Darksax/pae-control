@echo off
setlocal EnableDelayedExpansion

REM ============================================================================
REM  BUILD_INSTALLER_WIN.bat
REM  PAE Control — Build completo: PyInstaller + Inno Setup
REM
REM  Uso: Ejecutar desde la raíz del proyecto en Windows
REM  Requiere:
REM    - Python 3.10+ con PyInstaller instalado
REM    - Inno Setup 6.x instalado (ruta estándar o definida abajo)
REM ============================================================================

echo.
echo ============================================================
echo  PAE Control — Build Pipeline (Windows)
echo  Paso 1: PyInstaller  /  Paso 2: Inno Setup
echo ============================================================
echo.

REM ── Paso 0: Verificar entorno ────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no encontrado en PATH.
    echo         Instala Python 3.10+ y asegurate de agregarlo al PATH.
    pause
    exit /b 1
)

python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] PyInstaller no instalado.
    echo         Ejecuta: pip install pyinstaller
    pause
    exit /b 1
)

REM ── Paso 1: Compilar .exe con PyInstaller ────────────────────────────────────
echo [1/2] Compilando ejecutable con PyInstaller...
echo.

python -m PyInstaller PAEControl_win.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller fallo. Revisa los mensajes anteriores.
    pause
    exit /b 1
)

echo.
echo [OK] Ejecutable generado: dist\PAEControl.exe
echo.

REM ── Paso 2: Verificar que el .exe existe ─────────────────────────────────────
if not exist "dist\PAEControl.exe" (
    echo [ERROR] No se encontro dist\PAEControl.exe
    echo         Verifica el spec file y los errores de PyInstaller.
    pause
    exit /b 1
)

REM ── Paso 3: Buscar Inno Setup ────────────────────────────────────────────────
set ISCC=""

REM Ubicaciones estándar de Inno Setup
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    goto :found_iscc
)
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"
    goto :found_iscc
)
if exist "C:\Program Files (x86)\Inno Setup 5\ISCC.exe" (
    set ISCC="C:\Program Files (x86)\Inno Setup 5\ISCC.exe"
    goto :found_iscc
)

REM Si no se encontró, buscar en PATH
where ISCC.exe >nul 2>&1
if not errorlevel 1 (
    set ISCC=ISCC.exe
    goto :found_iscc
)

echo [ERROR] Inno Setup no encontrado.
echo.
echo         Descarga e instala Inno Setup 6 desde:
echo         https://jrsoftware.org/isdl.php
echo.
echo         Luego vuelve a ejecutar este script.
pause
exit /b 1

:found_iscc
echo [2/2] Compilando instalador con Inno Setup...
echo       ISCC: %ISCC%
echo.

REM Crear directorio de salida si no existe
if not exist "dist_installer" mkdir dist_installer

%ISCC% "PAEControl_Setup.iss"

if errorlevel 1 (
    echo.
    echo [ERROR] Inno Setup fallo. Revisa el archivo PAEControl_Setup.iss.
    pause
    exit /b 1
)

REM ── Resultado ────────────────────────────────────────────────────────────────
echo.
echo ============================================================
echo  BUILD COMPLETADO EXITOSAMENTE
echo ============================================================
echo.
echo  Ejecutable:  dist\PAEControl.exe
echo  Instalador:  dist_installer\PAEControl_Setup_1.4.0-beta.exe
echo.
echo  Distribuye el archivo del instalador a los usuarios.
echo  El .exe en dist\ es solo para pruebas locales.
echo.
pause
