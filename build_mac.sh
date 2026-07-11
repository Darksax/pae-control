#!/bin/bash
# build_mac.sh — Genera PAE Control.app para macOS
# Requiere: pip install pyinstaller PyQt6 openpyxl

set -e

echo "=== PAE Control — Build macOS ==="

# Instalar dependencias
pip install PyQt6 openpyxl pyinstaller --upgrade

# Limpiar builds anteriores
rm -rf build dist __pycache__

# Generar .app
pyinstaller \
  --name "PAE Control" \
  --windowed \
  --onedir \
  --add-data "ui:ui" \
  --hidden-import PyQt6.QtCore \
  --hidden-import PyQt6.QtGui \
  --hidden-import PyQt6.QtWidgets \
  --hidden-import openpyxl \
  --hidden-import sqlite3 \
  main.py

echo ""
echo "=== Build completado ==="
echo "App generada en: dist/PAE Control.app"
echo ""
echo "Para distribuir: comprime dist/PAE Control.app en un .zip"
