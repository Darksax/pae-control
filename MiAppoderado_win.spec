# -*- mode: python ; coding: utf-8 -*-
# MiAppoderado_win.spec — PyInstaller · Windows .exe
# Uso: pyinstaller MiAppoderado_win.spec --clean
#      (o doble clic en BUILD_WIN.bat)

import os
from pathlib import Path

block_cipher = None

# ── Datas ──────────────────────────────────────────────────────────────────
datas = []
if Path("assets/AppIcon.ico").exists():
    datas.append(("assets/AppIcon.ico", "assets"))
if Path("assets/escudo.png").exists():
    datas.append(("assets/escudo.png", "assets"))
if Path("assets/fonts/Inter.ttf").exists():
    datas.append(("assets/fonts/Inter.ttf", "assets/fonts"))
for _icon_svg in Path("assets/icons").glob("*.svg"):
    datas.append((str(_icon_svg), "assets/icons"))

_supabase_bins    = []
_supabase_hidden  = []
try:
    from PyInstaller.utils.hooks import collect_all
    _sd, _sb, _sh = collect_all("supabase")
    datas            += _sd
    _supabase_bins   += _sb
    _supabase_hidden += _sh
except Exception:
    pass

# certifi se importa dentro de un try/except a nivel de función en
# bootstrap_client.py/updater.py (_verified_ssl_ctx) — PyInstaller detecta
# imports normales por análisis estático, pero uno function-local dentro de
# un try/except es más fácil que se le escape. Se agrega explícito acá en
# vez de confiar en que el hook de certifi se dispare solo.
try:
    from PyInstaller.utils.hooks import collect_all
    _cd, _cb, _ch = collect_all("certifi")
    datas   += _cd
    _supabase_bins   += _cb
    _supabase_hidden += _ch
except Exception:
    pass

# ── Hidden imports ─────────────────────────────────────────────────────────
hidden_imports = [
    "PyQt6.QtCore", "PyQt6.QtGui", "PyQt6.QtWidgets",
    "PyQt6.QtWebEngineWidgets", "PyQt6.QtWebEngineCore",
    "PyQt6.QtNetwork", "PyQt6.QtSvg", "PyQt6.sip",
    "ui.theme", "ui.widgets", "ui.icons",
    "ui.scan_screen", "ui.students_screen", "ui.reports_screen",
    "ui.quotas_screen", "ui.config_screen", "ui.import_screen",
    "ui.sync_screen", "ui.main_window", "ui.inspectoria_screen",
    "ui.assistant_widget",
    "db", "utils", "logic", "sync", "assistant", "bootstrap_client", "updater",
    "sqlite3", "csv", "json", "datetime", "certifi",
    "supabase", "supabase_auth", "supabase_functions",
    "postgrest", "storage3", "realtime",
    "httpx", "anyio", "httpcore", "sniffio",
] + _supabase_hidden

excludes = ["tkinter", "matplotlib", "numpy", "scipy", "pandas", "test"]

# ── Analysis ───────────────────────────────────────────────────────────────
a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[] + _supabase_bins,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# En Windows: un solo .exe sin consola
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="MiAppoderado",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,               # comprime el ejecutable
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,           # sin ventana de terminal
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/AppIcon.ico" if Path("assets/AppIcon.ico").exists() else None,
    version_file=None,
)
