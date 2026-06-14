# -*- mode: python ; coding: utf-8 -*-
# PAEControl_win.spec — PyInstaller · Windows .exe
# Uso: pyinstaller PAEControl_win.spec --clean
#      (o doble clic en BUILD_WIN.bat)

import os
from pathlib import Path

block_cipher = None

# ── Datas ──────────────────────────────────────────────────────────────────
datas = [
    ("assets/AppIcon.ico", "assets"),
]
if Path("assets/escudo.png").exists():
    datas.append(("assets/escudo.png", "assets"))

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

# ── Hidden imports ─────────────────────────────────────────────────────────
hidden_imports = [
    "PyQt6.QtCore", "PyQt6.QtGui", "PyQt6.QtWidgets",
    "PyQt6.QtWebEngineWidgets", "PyQt6.QtWebEngineCore",
    "PyQt6.QtNetwork", "PyQt6.sip",
    "ui.theme", "ui.widgets",
    "ui.scan_screen", "ui.students_screen", "ui.reports_screen",
    "ui.bulk_screen", "ui.quotas_screen", "ui.suspensions_screen",
    "ui.junaeb_screen", "ui.config_screen", "ui.import_screen",
    "ui.sync_screen", "ui.main_window",
    "db", "utils", "logic", "sync",
    "sqlite3", "csv", "json", "datetime",
    "supabase", "gotrue", "postgrest", "storage3",
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
    name="PAE Control",
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
    icon="assets/AppIcon.ico",
    version_file=None,
)
