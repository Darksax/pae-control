#!/usr/bin/env bash
# Corre la app en Python puro y guarda el log — para diagnóstico
cd "$(dirname "$0")"

PYTHON="/Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14"
LOG="debug.log"

echo "── Corriendo PAE Control (Python directo)…"
echo "── Log en: $(pwd)/$LOG"
echo ""

"$PYTHON" main.py > "$LOG" 2>&1
CODE=$?

echo ""
echo "── Proceso terminó (código $CODE). Log guardado en $LOG"
cat "$LOG"
echo ""
read -p "Enter para cerrar…"
