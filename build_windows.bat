@echo off
REM build_windows.bat — Genera PAE Control.exe para Windows
REM Requiere: pip install pyinstaller PyQt6 openpyxl

echo === PAE Control - Build Windows ===

pip install PyQt6 openpyxl pyinstaller --upgrade

rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

pyinstaller ^
  --name "PAE Control" ^
  --windowed ^
  --onedir ^
  --add-data "ui;ui" ^
  --hidden-import PyQt6.QtCore ^
  --hidden-import PyQt6.QtGui ^
  --hidden-import PyQt6.QtWidgets ^
  --hidden-import openpyxl ^
  --hidden-import sqlite3 ^
  main.py

echo.
echo === Build completado ===
echo Ejecutable en: dist\PAE Control\PAE Control.exe
pause
