#!/bin/bash
# CLEAN_RESIDUES.command — Elimina residuos de instalaciones previas de PAE Control.
#
# IMPORTANTE: NO toca ~/pae_control/pae.db (tu base de datos) ni el código fuente.
# Doble clic para ejecutar.

BUNDLE_ID="cl.laja.paecontrol"
APP_NAME="PAE Control"

echo "╔══════════════════════════════════════════╗"
echo "║   Limpieza de residuos PAE Control       ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Cerrar la app si está corriendo
pkill -x "PAE Control" 2>/dev/null && echo "App cerrada" && sleep 1

RESIDUES=(
    "$HOME/Library/Saved Application State/${BUNDLE_ID}.savedState"
    "$HOME/Library/Preferences/${BUNDLE_ID}.plist"
    "$HOME/Library/Caches/${BUNDLE_ID}"
    "$HOME/Library/HTTPStorages/${BUNDLE_ID}"
    "$HOME/Library/WebKit/${BUNDLE_ID}"
    "$HOME/Library/Application Support/${APP_NAME}"
    "$HOME/Library/Application Support/${BUNDLE_ID}"
)

echo "Residuos de sistema:"
for p in "${RESIDUES[@]}"; do
    if [ -e "$p" ]; then
        rm -rf "$p" && echo "  BORRADO   $p"
    else
        echo "  no existe $p"
    fi
done

# Preferencias cacheadas por cfprefsd (defaults)
defaults delete "$BUNDLE_ID" 2>/dev/null && echo "  BORRADO   defaults $BUNDLE_ID" \
    || echo "  no existe defaults $BUNDLE_ID"
killall cfprefsd 2>/dev/null

# Crash reports viejos de la app (informativo, los movemos a logs/old_crashes)
mkdir -p "$(dirname "$0")/logs/old_crashes"
N=0
for cr in "$HOME/Library/Logs/DiagnosticReports/"PAE*Control*.ips; do
    [ -e "$cr" ] || continue
    mv "$cr" "$(dirname "$0")/logs/old_crashes/" && N=$((N+1))
done
echo "  $N crash report(s) archivados en logs/old_crashes/"

echo ""

# App instalada (opcional)
if [ -d "/Applications/${APP_NAME}.app" ]; then
    read -p "¿Borrar también /Applications/${APP_NAME}.app? (s/N) " R
    if [[ "$R" == "s" || "$R" == "S" ]]; then
        rm -rf "/Applications/${APP_NAME}.app" && echo "  BORRADO   /Applications/${APP_NAME}.app"
    fi
fi

echo ""
echo "NOTA: ~/pae_control/pae.db (base de datos) NO fue tocada."
echo "Limpieza terminada."
echo ""
read -p "Presiona Enter para cerrar..."
