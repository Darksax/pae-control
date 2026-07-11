"""
make_AppIcon_win.py — Genera assets/AppIcon.ico para Windows
a partir del iconset existente (PNG a múltiples resoluciones).

Requiere Pillow: pip install Pillow
Uso: python make_AppIcon_win.py
"""

import sys
from pathlib import Path

def main():
    try:
        from PIL import Image
    except ImportError:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow", "--quiet"])
        from PIL import Image

    iconset = Path("assets/AppIcon.iconset")
    out_ico  = Path("assets/AppIcon.ico")

    # Tamaños estándar para .ico de Windows
    sizes = [16, 24, 32, 48, 64, 128, 256]

    # Buscar los PNGs disponibles en el iconset
    images = []
    for size in sizes:
        candidates = [
            iconset / f"icon_{size}x{size}.png",
            iconset / f"icon_{size}x{size}@2x.png",  # fallback upscaleado
        ]
        found = None
        for c in candidates:
            if c.exists():
                found = c
                break
        if found:
            img = Image.open(found).convert("RGBA")
            img = img.resize((size, size), Image.LANCZOS)
            images.append(img)

    if not images:
        print("ERROR: No se encontraron imágenes PNG en assets/AppIcon.iconset/")
        sys.exit(1)

    # Guardar como .ico multiresolución
    images[0].save(
        out_ico,
        format="ICO",
        sizes=[(img.width, img.height) for img in images],
        append_images=images[1:],
    )
    print(f"OK  {out_ico}  ({len(images)} tamaños: {[img.width for img in images]})")


if __name__ == "__main__":
    main()
