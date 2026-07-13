#!/bin/bash
# INSTALL_SUPABASE.command
# Doble clic para instalar supabase-py y activar la sincronización con Supabase.

cd "$(dirname "$0")"
echo "==================================================="
echo "  MiAppoderado — Instalar supabase-py"
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
echo "Instalando supabase-py..."
"$PY" -m pip install --upgrade supabase

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ supabase-py instalado correctamente."
    echo "  Reinicia MiAppoderado y usa la pantalla Sync Supabase."
else
    echo ""
    echo "✗ Error durante la instalación."
    echo "  Intenta manualmente:"
    echo "  $PY -m pip install supabase"
fi

echo ""
read -p "Presiona Enter para cerrar..."
