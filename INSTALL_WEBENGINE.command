#!/bin/bash
# INSTALL_WEBENGINE.command
# Doble clic para instalar PyQt6-WebEngine y activar el visor JUNAEB embebido.

cd "$(dirname "$0")"
echo "==================================================="
echo "  PAE Control — Instalar PyQt6-WebEngine"
echo "==================================================="
echo ""

# Detectar python correcto (mismo que usa la app)
PY=""
for candidate in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" &>/dev/null; then
        PY="$candidate"
        break
    fi
done

if [ -z "$PY" ]; then
    echo "ERROR: No se encontró Python 3. Instala Python desde python.org"
    read -p "Presiona Enter para salir..."
    exit 1
fi

echo "Python detectado: $($PY --version)"
echo ""
echo "Instalando PyQt6-WebEngine (forzando reinstalación)..."

# Intento 1: con --break-system-packages (macOS 12+ / Homebrew)
"$PY" -m pip install --upgrade --force-reinstall PyQt6-WebEngine --break-system-packages 2>/dev/null
RESULT=$?

# Intento 2: sin ese flag si falló
if [ $RESULT -ne 0 ]; then
    echo "(Reintentando sin --break-system-packages...)"
    "$PY" -m pip install --upgrade --force-reinstall PyQt6-WebEngine
    RESULT=$?
fi

# Intento 3: con pip explícito y --user
if [ $RESULT -ne 0 ]; then
    echo "(Reintentando con --user...)"
    "$PY" -m pip install --upgrade --force-reinstall PyQt6-WebEngine --user
    RESULT=$?
fi

if [ $RESULT -eq 0 ]; then
    echo ""
    echo "✓ PyQt6-WebEngine instalado correctamente."
    echo "  Reinicia PAE Control para activar el visor JUNAEB."
else
    echo ""
    echo "✗ Error durante la instalación."
    echo "  Intenta manualmente desde Terminal:"
    echo "  $PY -m pip install --force-reinstall PyQt6-WebEngine --break-system-packages"
fi

echo ""
read -p "Presiona Enter para cerrar..."
