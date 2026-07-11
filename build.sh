#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  build.sh — Compilador PAE Control.app
#  Uso: cd pae_control && bash build.sh
#  Requisito: Python 3.14 de python.org instalado en /Library/Frameworks/...
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

PYTHON="/Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14"
PIP="$PYTHON -m pip"
PYINSTALLER="$PYTHON -m PyInstaller"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║        PAE Control — Build Script        ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── 1. Verificar Python ──────────────────────────────────────────────────────
if [ ! -f "$PYTHON" ]; then
    echo "✗  Python 3.14 no encontrado en $PYTHON"
    echo "   Descárgalo desde https://www.python.org/downloads/"
    exit 1
fi
echo "✓  Python: $($PYTHON --version)"

# ── 2. Instalar dependencias si faltan ───────────────────────────────────────
echo ""
echo "── Verificando dependencias …"
$PIP install --quiet pyinstaller pillow PyQt6 2>/dev/null || \
$PIP install pyinstaller pillow PyQt6

echo "✓  Dependencias OK"

# ── 3. Generar ícono ─────────────────────────────────────────────────────────
echo ""
echo "── Generando AppIcon.icns …"
$PYTHON make_icon.py

# ── 4. Limpiar builds anteriores ────────────────────────────────────────────
echo ""
echo "── Limpiando builds anteriores …"
rm -rf build dist __pycache__
find . -name "*.pyc" -delete 2>/dev/null || true
echo "✓  Limpio"

# ── 5. Compilar ──────────────────────────────────────────────────────────────
echo ""
echo "── Compilando .app con PyInstaller …"
echo "   (puede tardar 1–3 minutos)"
echo ""
$PYINSTALLER PAEControl.spec --noconfirm

# ── 6. Verificar resultado ───────────────────────────────────────────────────
APP="dist/PAE Control.app"
if [ -d "$APP" ]; then
    SIZE=$(du -sh "$APP" | cut -f1)
    echo ""
    echo "╔══════════════════════════════════════════╗"
    echo "║  ✅  Build exitoso: dist/PAE Control.app  ║"
    printf  "║      Tamaño: %-28s ║\n" "$SIZE"
    echo "╚══════════════════════════════════════════╝"
    echo ""
    echo "Para abrir:"
    echo "  open \"dist/PAE Control.app\""
    echo ""
    echo "Para mover a /Applications:"
    echo "  cp -r \"dist/PAE Control.app\" /Applications/"
    echo ""
else
    echo "✗  Build falló — revisa los mensajes de error arriba."
    exit 1
fi
