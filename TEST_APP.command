#!/bin/bash
# TEST_APP.command — Prueba el .app recién compilado SIN instalarlo.
# Ejecuta el binario directo desde dist/, en modo debug, con todo el
# output (Python + Qt + crash) capturado en logs/.
# Doble clic para ejecutar.

cd "$(dirname "$0")"

APP_BIN="dist/PAE Control.app/Contents/MacOS/PAE Control"

if [ ! -f "$APP_BIN" ]; then
    echo "ERROR: No existe dist/PAE Control.app — compila primero con BUILD_MAC.command"
    read -p "Presiona Enter para salir..."
    exit 1
fi

mkdir -p logs
TS=$(date +%Y%m%d_%H%M%S)
LOG="logs/test_${TS}.log"

echo "╔══════════════════════════════════════════╗"
echo "║   TEST PAE Control (sin instalar)        ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "Log de esta sesión: $LOG"
echo "Cierra la app normalmente cuando termines de probar."
echo ""

# Modo debug de la app + diagnóstico Qt
export PAE_DEBUG=1
export PYTHONFAULTHANDLER=1
export QT_DEBUG_PLUGINS=1

"$APP_BIN" --debug 2>&1 | tee "$LOG"
EC=${PIPESTATUS[0]}

echo "" | tee -a "$LOG"
echo "── Exit code: $EC ──" | tee -a "$LOG"

if [ "$EC" -ne 0 ]; then
    echo "La app NO terminó limpia." | tee -a "$LOG"
    # Esperar a que macOS escriba el crash report y copiarlo a logs/
    sleep 3
    CR=$(ls -t "$HOME/Library/Logs/DiagnosticReports/"PAE*Control*.ips 2>/dev/null | head -1)
    if [ -n "$CR" ]; then
        # Solo copiar si es de los últimos 2 minutos (no uno viejo)
        if [ -n "$(find "$CR" -mmin -2 2>/dev/null)" ]; then
            cp "$CR" "logs/crash_${TS}.ips"
            echo "Crash report copiado: logs/crash_${TS}.ips" | tee -a "$LOG"
        fi
    fi
    echo ""
    echo "Revisa también:"
    echo "  logs/fault.log   (crashes nativos capturados por Python)"
    echo "  logs/errors.log  (excepciones Python)"
else
    echo "OK  La app cerró limpia (exit 0)."
fi

echo ""
read -p "Presiona Enter para cerrar..."
