#!/bin/bash
# BUILD_MAC.command — Compila PAE Control como .app para macOS
# Doble clic para ejecutar.

set -e
cd "$(dirname "$0")"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   PAE Control — Build macOS              ║"
echo "║   Liceo Bicentenario · Laja              ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── 1. Detectar Python ─────────────────────────────────────────────────────
PY=""
for candidate in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" &>/dev/null; then
        PY="$candidate"
        break
    fi
done

if [ -z "$PY" ]; then
    echo "ERROR: No se encontró Python 3. Instala desde python.org"
    read -p "Presiona Enter para salir..."
    exit 1
fi

echo "Python: $($PY --version)"
echo ""

# ── 2. Instalar dependencias ───────────────────────────────────────────────
echo "Instalando / actualizando dependencias..."
"$PY" -m pip install --upgrade pip --quiet
# PyInstaller siempre a última versión (los fixes de empaquetado Qt viven ahí)
"$PY" -m pip install --upgrade pyinstaller --quiet
# Qt PINNEADO a 6.9.1 — NO subir a 6.10/6.11 sin probar:
# PyInstaller reescribe los install names de Qt a formato plano (@rpath/QtCore).
# Qt >= 6.10 en macOS 26 exige que QtCore cargue desde su .framework para que
# CFBundleGetBundleWithIdentifier("org.qt-project.QtCore") lo encuentre; con el
# install name plano retorna NULL y crashea en CFBundleCopyBundleURL (SIGSEGV 0x8).
# Qt 6.9.x tolera ese layout. Ref: pyinstaller#7789.
# PyQt6-WebEngine NO se incluye en el bundle (junaeb_screen usa el browser del sistema)
"$PY" -m pip install "PyQt6==6.9.1" "PyQt6-Qt6==6.9.1" --quiet
"$PY" -m pip install --upgrade supabase --quiet
echo "OK  Dependencias listas:"
echo "    PyInstaller $("$PY" -m PyInstaller --version 2>/dev/null)"
echo "    PyQt6 $("$PY" -c 'from PyQt6.QtCore import PYQT_VERSION_STR, QT_VERSION_STR; print(PYQT_VERSION_STR, "(Qt", QT_VERSION_STR + ")")' 2>/dev/null)"
echo ""

# ── 3. Generar ícono .icns si no existe ────────────────────────────────────
if [ ! -f "assets/AppIcon.icns" ]; then
    echo "Generando AppIcon.icns..."
    "$PY" make_icon.py 2>/dev/null && echo "OK  Ícono creado" || echo "WARN  No se pudo crear ícono"
fi

# ── 4. Limpiar builds anteriores ──────────────────────────────────────────
echo "Limpiando build anterior..."
rm -rf build/ dist/ __pycache__
find . -name "*.pyc" -delete 2>/dev/null || true
echo "OK  Limpio"
echo ""

# ── 5. Compilar ───────────────────────────────────────────────────────────
echo "Compilando .app (puede tardar 2-5 minutos)..."
echo ""
"$PY" -m PyInstaller PAEControl.spec --clean --noconfirm

if [ ! -d "dist/PAE Control.app" ]; then
    echo ""
    echo "ERROR: No se generó el .app. Revisa los mensajes de error arriba."
    read -p "Presiona Enter para salir..."
    exit 1
fi

echo ""
echo "OK  Compilación exitosa"
echo ""

# ── 6. Verificación de install names de Qt (diagnóstico) ──────────────────
# Muestra cómo quedó referenciado QtCore. Formato framework
# (@rpath/QtCore.framework/Versions/A/QtCore) = correcto.
# Formato plano (@rpath/QtCore) = solo seguro con Qt <= 6.9.x.
echo "Verificando referencias a QtCore en el bundle:"
otool -L "dist/PAE Control.app/Contents/Frameworks/PyQt6/QtCore.abi3.so" 2>/dev/null \
    | grep -i qtcore || echo "WARN  No se pudo inspeccionar QtCore.abi3.so"
echo ""

# ── 7. Firmar app (ad-hoc) ─────────────────────────────────────────────────
# Requerido en Apple Silicon para ejecutar binarios. No tiene relación con el
# crash de CFBundle (ese era por install names planos + Qt >= 6.10).
# "-" = ad-hoc signature: no requiere cuenta de desarrollador Apple.
echo "Firmando app (ad-hoc, sin cuenta Apple necesaria)..."
if command -v codesign &>/dev/null; then
    codesign --force --deep --sign - "dist/PAE Control.app" 2>&1 \
        && echo "OK  App firmada (ad-hoc)" \
        || echo "WARN  codesign falló — el app puede crashear en macOS 26+"
else
    echo "WARN  codesign no encontrado — el app puede crashear en macOS 26+"
fi
echo ""

# ── 8. Crear DMG para distribución ─────────────────────────────────────────
DMG_NAME="PAEControl_v1.0_mac.dmg"
echo "Creando $DMG_NAME..."

# Crear carpeta temporal para el DMG
DMG_DIR="dist/dmg_tmp"
rm -rf "$DMG_DIR"
mkdir -p "$DMG_DIR"
cp -r "dist/PAE Control.app" "$DMG_DIR/"
ln -s /Applications "$DMG_DIR/Applications"

hdiutil create \
    -volname "PAE Control" \
    -srcfolder "$DMG_DIR" \
    -ov -format UDZO \
    -o "dist/$DMG_NAME" \
    2>/dev/null && echo "OK  DMG creado: dist/$DMG_NAME" \
    || echo "WARN  No se pudo crear DMG (solo se genera en macOS con hdiutil)"

rm -rf "$DMG_DIR"

# ── 9. Resultado ──────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   BUILD COMPLETADO                       ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "  .app  →  dist/PAE Control.app"
[ -f "dist/$DMG_NAME" ] && echo "  .dmg  →  dist/$DMG_NAME"
echo ""
echo "Para distribuir: copia 'PAE Control.app' a la carpeta Aplicaciones"
echo "o comparte el archivo $DMG_NAME."
echo ""

# Abrir carpeta dist
open dist/ 2>/dev/null || true

read -p "Presiona Enter para cerrar..."
