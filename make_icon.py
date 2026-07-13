"""
make_icon.py — Genera assets/AppIcon.icns para MiAppoderado
Requiere: pillow  (pip install pillow)
Uso:       python3 make_icon.py
"""

import os
import sys
import subprocess

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("Instalando pillow…")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pillow"])
    from PIL import Image, ImageDraw


# Paleta institucional de la app (ver ui/theme.py) — azul de marca de fondo,
# glifo en blanco para máximo contraste y legibilidad a 16×16.
BG_COLOR = (79, 142, 247)     # C.BLUE "#4F8EF7"
FG_COLOR = (255, 255, 255)

ICONSET_MAP = {
    "icon_16x16.png":      16,
    "icon_16x16@2x.png":   32,
    "icon_32x32.png":      32,
    "icon_32x32@2x.png":   64,
    "icon_128x128.png":    128,
    "icon_128x128@2x.png": 256,
    "icon_256x256.png":    256,
    "icon_256x256@2x.png": 512,
    "icon_512x512.png":    512,
    "icon_512x512@2x.png": 1024,
}


def draw_icon(size: int) -> Image.Image:
    """
    Glifo minimalista de 'apoderado/guardián': cabeza + hombros en blanco
    sobre fondo azul institucional, mismo lenguaje visual que los íconos
    Lucide usados en el resto de la app (trazo simple, sin texto, legible
    incluso a 16×16 donde el texto ya no se lee).
    """
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    radius = max(4, int(size * 0.225))
    draw.rounded_rectangle([0, 0, size - 1, size - 1],
                           radius=radius, fill=BG_COLOR)

    cx = size / 2

    # Cabeza
    head_r  = size * 0.145
    head_cy = size * 0.375
    draw.ellipse(
        [cx - head_r, head_cy - head_r, cx + head_r, head_cy + head_r],
        fill=FG_COLOR
    )

    # Hombros — rectángulo con esquinas superiores redondeadas, esquinas
    # inferiores rectas (se recortan contra el borde del ícono)
    body_w      = size * 0.50
    body_top    = size * 0.565
    body_bottom = size * 0.85
    try:
        draw.rounded_rectangle(
            [cx - body_w / 2, body_top, cx + body_w / 2, body_bottom],
            radius=body_w / 2, fill=FG_COLOR,
            corners=(True, True, False, False),
        )
    except TypeError:
        # Pillow < 9.2 no soporta 'corners' — fallback: pieslice + rect
        draw.pieslice(
            [cx - body_w / 2, body_top, cx + body_w / 2, body_top + body_w],
            180, 360, fill=FG_COLOR
        )
        draw.rectangle(
            [cx - body_w / 2, body_top + body_w / 2, cx + body_w / 2, body_bottom],
            fill=FG_COLOR
        )

    return img


def build_icns():
    os.makedirs("assets/AppIcon.iconset", exist_ok=True)

    for fname, px in ICONSET_MAP.items():
        path = f"assets/AppIcon.iconset/{fname}"
        draw_icon(px).save(path, "PNG")
        print(f"  ✓  {path}  ({px}×{px})")

    result = subprocess.run(
        ["iconutil", "-c", "icns",
         "assets/AppIcon.iconset",
         "-o", "assets/AppIcon.icns"],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        print(f"✗  iconutil error: {result.stderr}")
        sys.exit(1)

    print("✅  assets/AppIcon.icns generado.")


if __name__ == "__main__":
    build_icns()
