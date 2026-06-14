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
echo "Instalando PyQt6-WebEngine..."
"$PY" -m pip install --upgrade PyQt6-WebEngine

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ PyQt6-WebEngine instalado correctamente."
    echo "  Reinicia PAE Control para activar el visor JUNAEB."
else
    echo ""
    echo "✗ Error durante la instalación."
    echo "  Intenta manualmente:"
    echo "  $PY -m pip install PyQt6-WebEngine"
fi

echo ""
read -p "Presiona Enter para cerrar..."
