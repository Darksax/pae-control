#!/usr/bin/env bash
# Corre MiAppoderado con output visible para ver el error de crash
cd "$(dirname "$0")"

echo "── Corriendo MiAppoderado (modo debug) …"
echo ""

EXE="dist/MiAppoderado.app/Contents/MacOS/MiAppoderado"

if [ ! -f "$EXE" ]; then
    echo "✗  No se encontró el ejecutable: $EXE"
    echo "   Compila primero con COMPILAR.command"
    read -p "Enter para cerrar…"; exit 1
fi

# Correr con output completo
"$EXE" 2>&1

echo ""
echo "── Proceso terminó con código: $?"
read -p "Enter para cerrar…"
