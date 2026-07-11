"""
Runtime hook: Fix crash en QLibraryInfoPrivate::paths en macOS 26+ (Tahoe / ARM64).

═══════════════════════════════════════════════════════════════════════════════
CAUSA RAÍZ CONFIRMADA (5 crashes idénticos analizados)
═══════════════════════════════════════════════════════════════════════════════

Stack invariante en todos los crashes:
  _GLOBAL__sub_I_qdarwinpermissionplugin_location.mm   ← static init de QtCore
  → QLoggingCategory::QLoggingCategory()
  → QLoggingRegistry::instance()
  → QLibraryInfoPrivate::paths(DataPath)
  → QCoreApplication::applicationDirPath()  [pre-QApp path, usa CFBundle]
  → CFBundleGetMainBundle()                 ← retorna NULL
  → CFBundleCopyBundleURL(NULL)             ← pasa NULL al siguiente
  → __CFCheckCFInfoPACSignature(NULL)       ← nuevo en macOS 26
  → lee NULL+8 = 0x8                        ← SIGSEGV / EXC_BAD_ACCESS

x0=0, far=0x8, x8=0x8 en TODOS los crashes → bundle pointer es NULL.

═══════════════════════════════════════════════════════════════════════════════
POR QUÉ FALLARON LOS INTENTOS ANTERIORES
═══════════════════════════════════════════════════════════════════════════════

• QT_PLUGIN_PATH       — solo cubre PluginsPath, no DataPath
• QT_INSTALL_PREFIX    — NO es una env var válida de Qt (no hace nada)
• NSApplicationLoad()  — carga AppKit pero NO crea [NSApp]
                         → CFBundleGetMainBundle() sigue retornando NULL
• qt.conf              — Qt usa CFBundle para ENCONTRAR qt.conf (mismo crash)

═══════════════════════════════════════════════════════════════════════════════
FIX REAL
═══════════════════════════════════════════════════════════════════════════════

[NSApplication sharedApplication] crea el singleton de NSApplication.
Esto registra el main bundle en CoreFoundation.
Después de esta llamada, CFBundleGetMainBundle() retorna un CFBundleRef válido.

NSApplication es un singleton: llamarlo antes de QApplication es seguro.
PyQt6 / QApplication también lo llama internamente — la segunda llamada
simplemente retorna la instancia existente.
"""
import os
import sys

if sys.platform == 'darwin':

    # ── Fix principal: crear NSApplication singleton ───────────────────────────
    # Esto registra el main bundle → CFBundleGetMainBundle() retorna válido
    # → Qt no crashea en QLibraryInfoPrivate::paths durante static init.
    try:
        import ctypes

        _libobjc = ctypes.CDLL('/usr/lib/libobjc.A.dylib')
        _libobjc.objc_getClass.restype  = ctypes.c_void_p
        _libobjc.objc_getClass.argtypes = [ctypes.c_char_p]
        _libobjc.sel_registerName.restype  = ctypes.c_void_p
        _libobjc.sel_registerName.argtypes = [ctypes.c_char_p]
        _libobjc.objc_msgSend.restype  = ctypes.c_void_p
        _libobjc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

        # Cargar AppKit si no está cargado
        ctypes.CDLL('/System/Library/Frameworks/AppKit.framework/AppKit')

        # [NSApplication sharedApplication]
        _NSApp  = _libobjc.objc_getClass(b'NSApplication')
        _sel_sa = _libobjc.sel_registerName(b'sharedApplication')
        _libobjc.objc_msgSend(_NSApp, _sel_sa)

    except Exception:
        pass

    # ── Env vars de Qt (respaldo) ──────────────────────────────────────────────
    _meipass = getattr(sys, '_MEIPASS', None)
    if _meipass:
        _plugin_candidates = [
            os.path.join(_meipass, 'PyQt6', 'Qt6', 'plugins'),
            os.path.join(_meipass, 'PyQt6', 'Qt',  'plugins'),
            os.path.join(_meipass, 'lib', 'qt6', 'plugins'),
            os.path.join(_meipass, 'plugins'),
        ]
        for _p in _plugin_candidates:
            if os.path.isdir(_p):
                os.environ.setdefault('QT_PLUGIN_PATH', _p)
                break

        # QT_LOGGING_CONF=/dev/null: si Qt chequea esto antes del DataPath lookup,
        # evita la búsqueda de config de logging completamente.
        os.environ.setdefault('QT_LOGGING_CONF', '/dev/null')
