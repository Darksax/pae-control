# -*- mode: python ; coding: utf-8 -*-
# PAEControl.spec — PyInstaller · macOS .app bundle
# Uso: pyinstaller PAEControl.spec --clean
#      (o doble clic en BUILD_MAC.command)
#
# NOTA: QtWebEngineWidgets NO se incluye a propósito.
# El módulo junaeb_screen.py detecta su ausencia y abre los links
# en el navegador del sistema (Safari / Chrome) automáticamente.
# Esto reduce el tamaño de ~3 GB a ~400 MB.

from pathlib import Path

block_cipher = None

# ── Datas ──────────────────────────────────────────────────────────────────
datas = [
    ("assets/AppIcon.icns", "assets"),
]
if Path("assets/escudo.png").exists():
    datas.append(("assets/escudo.png", "assets"))

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

# ── Hidden imports ─────────────────────────────────────────────────────────
hidden_imports = [
    # PyQt6 — solo los módulos usados
    "PyQt6.QtCore", "PyQt6.QtGui", "PyQt6.QtWidgets",
    "PyQt6.QtNetwork", "PyQt6.sip",
    # Pantallas
    "ui.theme", "ui.widgets",
    "ui.scan_screen", "ui.students_screen", "ui.reports_screen",
    "ui.bulk_screen", "ui.quotas_screen", "ui.suspensions_screen",
    "ui.junaeb_screen", "ui.config_screen", "ui.import_screen",
    "ui.sync_screen", "ui.main_window",
    # Módulos propios
    "db", "utils", "logic", "sync",
    # Stdlib
    "sqlite3", "csv", "json", "datetime",
    # Supabase + deps (si está instalado)
    "supabase", "gotrue", "postgrest", "storage3",
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
    "tkinter", "unittest", "pydoc", "doctest",
    "email", "html", "http.server", "xmlrpc",
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
    runtime_hooks=["hooks/rth_qt6_macos_fix.py"],
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
    name="PAE Control",
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
    name="PAE Control",
)

app = BUNDLE(
    coll,
    name="PAE Control.app",
    icon="assets/AppIcon.icns",
    bundle_identifier="cl.laja.paecontrol",
    info_plist={
        "CFBundleName":               "PAE Control",
        "CFBundleDisplayName":        "PAE Control",
        "CFBundleShortVersionString": "1.0",
        "CFBundleVersion":            "1.0.0",
        "NSHighResolutionCapable":    True,
        "NSRequiresAquaSystemAppearance": False,
        "CFBundleDocumentTypes":      [],
        "LSMinimumSystemVersion":     "12.0",
        "NSHumanReadableCopyright":   "Liceo Bicentenario Héroes de la Concepción · Laja",
    },
)
