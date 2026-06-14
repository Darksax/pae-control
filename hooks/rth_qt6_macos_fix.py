"""
Runtime hook: Fix crash en QLibraryInfoPrivate::paths en macOS 26+ (Tahoe / ARM64).

Problema:
  Al importar PyQt6.QtCore, dyld ejecuta el static initializer de
  qdarwinpermissionplugin_location.mm, que llama QLoggingCategory() →
  QLoggingRegistry::instance() → QLibraryInfoPrivate::paths() →
  CFBundleCopyBundleURL(NULL). En macOS 26, CFBundleCopyBundleURL ahora
  llama __CFCheckCFInfoPACSignature antes de verificar NULL → SIGSEGV.

Fix:
  Setear QT_PLUGIN_PATH antes de que Qt inicialice. Con esta var definida,
  QLibraryInfoPrivate::paths() la usa directamente y omite la llamada a
  CFBundleCopyBundleURL, evitando el crash.
"""
import os
import sys

if sys.platform == 'darwin':
    _meipass = getattr(sys, '_MEIPASS', None)
    if _meipass:
        # Rutas candidatas para los plugins de Qt dentro del bundle
        _candidates = [
            os.path.join(_meipass, 'PyQt6', 'Qt6', 'plugins'),
            os.path.join(_meipass, 'PyQt6', 'Qt',  'plugins'),
            os.path.join(_meipass, 'lib', 'qt6', 'plugins'),
            os.path.join(_meipass, 'plugins'),
        ]
        for _p in _candidates:
            if os.path.isdir(_p):
                os.environ.setdefault('QT_PLUGIN_PATH', _p)
                break

        # QT_INSTALL_PREFIX evita que Qt busque su directorio via CFBundle
        os.environ.setdefault('QT_INSTALL_PREFIX', _meipass)
