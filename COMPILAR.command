#!/usr/bin/env bash
# Doble clic en Finder → abre Terminal y compila PAE Control.app

cd "$(dirname "$0")"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║        PAE Control — Compilando…         ║"
echo "╚══════════════════════════════════════════╝"
echo ""

PYTHON="/Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14"

if [ ! -f "$PYTHON" ]; then
    echo "✗  Python 3.14 no encontrado."
    echo "   Descárgalo desde https://www.python.org/downloads/"
    echo ""
    read -p "Presiona Enter para cerrar…"
    exit 1
fi

echo "✓  Python: $($PYTHON --version)"
echo ""

# Instalar dependencias
echo "── Instalando dependencias…"
$PYTHON -m pip install --quiet pyinstaller pillow PyQt6 2>&1 | grep -E "(error|ERROR|Successfully|already)" || true
echo "✓  Dependencias OK"
echo ""

# Generar ícono
echo "── Generando ícono…"
$PYTHON make_icon.py
echo ""

# Limpiar
echo "── Limpiando build anterior…"
rm -rf build dist __pycache__
echo "✓  Limpio"
echo ""

# Compilar
echo "── Compilando (1–3 min)…"
$PYTHON -m PyInstaller PAEControl.spec --noconfirm

APP="dist/PAE Control.app"
if [ -d "$APP" ]; then
    SIZE=$(du -sh "$APP" | cut -f1)
    echo ""
    echo "╔══════════════════════════════════════════╗"
    echo "║  ✅  PAE Control.app listo en dist/       ║"
    printf  "║      Tamaño: %-28s ║\n" "$SIZE"
    echo "╚══════════════════════════════════════════╝"
    echo ""
    # Abrir carpeta dist en Finder
    open dist/
else
    echo "✗  Falló el build. Revisa los errores arriba."
fi

echo ""
read -p "Presiona Enter para cerrar…"
