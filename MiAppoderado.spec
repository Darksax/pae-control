# -*- mode: python ; coding: utf-8 -*-
# MiAppoderado.spec — PyInstaller · macOS .app bundle
# Uso: pyinstaller MiAppoderado.spec --clean
#      (o doble clic en BUILD_MAC.command)
#
# NOTA: QtWebEngineWidgets NO se incluye a propósito — reduce el tamaño de
# ~3 GB a ~400 MB. Ningún módulo actual lo necesita.

from pathlib import Path
import sys

sys.path.insert(0, ".")
from patchnotes import VERSION as _APP_VERSION   # una sola fuente de verdad para la versión

block_cipher = None

# ── Datas ──────────────────────────────────────────────────────────────────
datas = [
    ("assets/AppIcon.icns", "assets"),
]
if Path("assets/escudo.png").exists():
    datas.append(("assets/escudo.png", "assets"))
if Path("assets/fonts/Inter.ttf").exists():
    datas.append(("assets/fonts/Inter.ttf", "assets/fonts"))
for _icon_svg in Path("assets/icons").glob("*.svg"):
    datas.append((str(_icon_svg), "assets/icons"))

_supabase_bins   = []
_supabase_hidden = []
try:
    from PyInstaller.utils.hooks import collect_all
    _sd, _sb, _sh = collect_all("supabase")
    datas            += _sd
    _supabase_bins   += _sb
    _supabase_hidden += _sh
except Exception:
    pass

# certifi se importa dentro de un try/except a nivel de función en
# bootstrap_client.py/updater.py (_verified_ssl_ctx) — más fácil que se le
# escape al análisis estático de PyInstaller que un import normal. Se
# agrega explícito en vez de confiar en que su hook se dispare solo.
try:
    from PyInstaller.utils.hooks import collect_all
    _cd, _cb, _ch = collect_all("certifi")
    datas            += _cd
    _supabase_bins   += _cb
    _supabase_hidden += _ch
except Exception:
    pass

# ── Hidden imports ─────────────────────────────────────────────────────────
hidden_imports = [
    # PyQt6 — solo los módulos usados
    "PyQt6.QtCore", "PyQt6.QtGui", "PyQt6.QtWidgets",
    "PyQt6.QtNetwork", "PyQt6.QtSvg", "PyQt6.sip",
    # Pantallas
    "ui.theme", "ui.widgets", "ui.icons",
    "ui.scan_screen", "ui.students_screen", "ui.reports_screen",
    "ui.quotas_screen", "ui.config_screen", "ui.import_screen",
    "ui.sync_screen", "ui.main_window", "ui.inspectoria_screen",
    "ui.assistant_widget",
    # Módulos propios
    "db", "utils", "logic", "sync", "assistant", "bootstrap_client", "updater",
    # Stdlib
    "sqlite3", "csv", "json", "datetime", "certifi",
    # Supabase + deps (si está instalado) — gotrue fue renombrado a supabase_auth
    "supabase", "supabase_auth", "supabase_functions",
    "postgrest", "storage3", "realtime",
    "httpx", "anyio", "httpcore", "sniffio",
] + _supabase_hidden

# ── Exclusiones — reducen tamaño significativamente ───────────────────────
excludes = [
    # Chromium / WebEngine — el mayor culpable (~1 GB)
    "PyQt6.QtWebEngineWidgets",
    "PyQt6.QtWebEngineCore",
    "PyQt6.QtWebEngineQuick",
    "PyQt6.QtWebChannel",
    # Qt módulos no usados por la app
    "PyQt6.QtMultimedia",
    "PyQt6.QtMultimediaWidgets",
    "PyQt6.QtQml",
    "PyQt6.QtQuick",
    "PyQt6.QtQuickWidgets",
    "PyQt6.QtBluetooth",
    "PyQt6.QtNfc",
    "PyQt6.QtSensors",
    "PyQt6.QtSerialPort",
    "PyQt6.QtLocation",
    "PyQt6.QtPositioning",
    "PyQt6.QtRemoteObjects",
    "PyQt6.QtTextToSpeech",
    "PyQt6.QtSql",
    "PyQt6.QtTest",
    "PyQt6.QtDesigner",
    "PyQt6.QtHelp",
    "PyQt6.QtOpenGL",
    "PyQt6.QtOpenGLWidgets",
    # Python stdlib no usados
    # NO excluir "html" (lo usa ui/import_screen.py) ni "email"
    # (lo requiere http.client/urllib, usado por updater.py)
    "tkinter", "unittest", "pydoc", "doctest",
    "http.server", "xmlrpc",
    # Científicas
    "matplotlib", "numpy", "scipy", "pandas",
    "PIL", "cv2", "sklearn",
]

# ── Analysis ───────────────────────────────────────────────────────────────
a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[] + _supabase_bins,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    # runtime hook eliminado: el hack NSApplication atacaba el main bundle,
    # pero el crash era por el bundle de QtCore (install names planos + Qt 6.11).
    # Fix real: pin PyQt6==6.9.1 en BUILD_MAC.command.
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MiAppoderado",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,              # NO hacer strip en Apple Silicon (rompe PAC signatures)
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/AppIcon.icns",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,              # NO strip en Apple Silicon (rompe PAC signatures)
    upx=False,
    upx_exclude=[],
    name="MiAppoderado",
)

app = BUNDLE(
    coll,
    name="MiAppoderado.app",
    icon="assets/AppIcon.icns",
    bundle_identifier="cl.laja.miappoderado",
    info_plist={
        "CFBundleName":               "MiAppoderado",
        "CFBundleDisplayName":        "MiAppoderado",
        "CFBundleShortVersionString": _APP_VERSION,
        "CFBundleVersion":            _APP_VERSION,
        "NSHighResolutionCapable":    True,
        "NSRequiresAquaSystemAppearance": False,
        "CFBundleDocumentTypes":      [],
        "LSMinimumSystemVersion":     "12.0",
        "NSHumanReadableCopyright":   "Liceo Bicentenario Héroes de la Concepción · Laja",
    },
)
