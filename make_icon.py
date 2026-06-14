"""
make_icon.py — Genera assets/AppIcon.icns para PAE Control
Requiere: pillow  (pip install pillow)
Uso:       python3 make_icon.py
"""

import os
import sys
import subprocess

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Instalando pillow…")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pillow"])
    from PIL import Image, ImageDraw, ImageFont


BG_COLOR = (0, 122, 255)   # #007AFF
FG_COLOR = (255, 255, 255)
LABEL    = "PAE"

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

FONT_PATHS = [
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/SFNSDisplay.ttf",
    "/System/Library/Fonts/SFNSText.ttf",
    "/System/Library/Fonts/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
]


def _load_font(size: int):
    for path in FONT_PATHS:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return None


def draw_icon(size: int) -> Image.Image:
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    radius = max(4, int(size * 0.225))
    draw.rounded_rectangle([0, 0, size - 1, size - 1],
                           radius=radius, fill=BG_COLOR)

    if size < 32:
        return img

    font_size = max(8, int(size * 0.30))
    font = _load_font(font_size)

    if font is None:
        # Sin TrueType: posición manual aproximada
        draw.text((int(size * 0.20), int(size * 0.35)), LABEL, fill=FG_COLOR)
        return img

    try:
        bbox = draw.textbbox((0, 0), LABEL, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        x  = (size - tw) / 2 - bbox[0]
        y  = (size - th) / 2 - bbox[1]
        draw.text((x, y), LABEL, font=font, fill=FG_COLOR)
    except Exception:
        draw.text((int(size * 0.20), int(size * 0.35)), LABEL,
                  font=font, fill=FG_COLOR)

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
