#!/usr/bin/env bash
# Corre PAE Control con output visible para ver el error de crash
cd "$(dirname "$0")"

echo "── Corriendo PAE Control (modo debug) …"
echo ""

EXE="dist/PAE Control.app/Contents/MacOS/PAE Control"

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
