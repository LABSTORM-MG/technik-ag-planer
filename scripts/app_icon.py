"""App-Icon zeichnen (M11): drei schlichte Entwürfe, ohne Schullogo.

    uv run --with pillow scripts/app_icon.py            # Übersicht aller Entwürfe + Standard (B)
    uv run --with pillow scripts/app_icon.py A          # Entwurf A als App-Icon verwenden

Schreibt die Icons nach app/static/icons/ und die Vorschau nach docs/design/app-icon/.
Farben wie die Design-Tokens (Abschnitt 1): Hintergrund, Fläche, Dunkel- und Hellblau.
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ICONS = ROOT / "app" / "static" / "icons"
PREVIEW = ROOT / "docs" / "design" / "app-icon"

BG = (15, 17, 21)  # --color-bg
SURFACE = (31, 35, 44)  # --color-surface-raised
LINE = (42, 47, 58)  # --color-line
PRIMARY = (0, 51, 151)  # --color-primary (Dunkelblau)
ACCENT = (135, 135, 255)  # --color-accent (Hellblau/Flieder)
TEXT = (242, 243, 245)  # --color-text

SCALE = 4  # gezeichnet in 4-facher Größe, dann geglättet verkleinert
BASE = 512


def _canvas():
    size = BASE * SCALE
    return Image.new("RGB", (size, size), BG), size


def _s(value):
    return int(value * SCALE)


def draft_a():
    """Kalenderblatt mit hervorgehobenem Tag."""
    img, _ = _canvas()
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([_s(126), _s(140), _s(386), _s(380)], radius=_s(34), fill=SURFACE)
    d.rounded_rectangle([_s(126), _s(140), _s(386), _s(206)], radius=_s(34), fill=PRIMARY)
    d.rectangle([_s(126), _s(180), _s(386), _s(206)], fill=PRIMARY)
    for x in (186, 326):
        d.rounded_rectangle([_s(x - 9), _s(116), _s(x + 9), _s(164)], radius=_s(9), fill=TEXT)
    for row in range(3):
        for col in range(4):
            cx, cy = 168 + col * 59, 244 + row * 46
            fill = ACCENT if (row, col) == (1, 2) else LINE
            r = 17 if (row, col) == (1, 2) else 11
            d.ellipse([_s(cx - r), _s(cy - r), _s(cx + r), _s(cy + r)], fill=fill)
    return img


def draft_b():
    """Drei Fader eines Mischpults – Technik auf einen Blick."""
    img, _ = _canvas()
    d = ImageDraw.Draw(img)
    for x, knob in ((160, 302), (256, 190), (352, 250)):
        d.rounded_rectangle([_s(x - 7), _s(126), _s(x + 7), _s(386)], radius=_s(7), fill=LINE)
        d.rounded_rectangle(
            [_s(x - 40), _s(knob - 24), _s(x + 40), _s(knob + 24)], radius=_s(13), fill=ACCENT
        )
        d.rectangle([_s(x - 26), _s(knob - 3), _s(x + 26), _s(knob + 3)], fill=PRIMARY)
    return img


def draft_c():
    """Scheinwerfer mit Lichtkegel."""
    img, _ = _canvas()
    d = ImageDraw.Draw(img)
    d.polygon([(_s(214), _s(196)), (_s(298), _s(196)), (_s(392), _s(392)), (_s(120), _s(392))], fill=PRIMARY)
    d.rounded_rectangle([_s(190), _s(118), _s(322), _s(212)], radius=_s(26), fill=SURFACE)
    d.ellipse([_s(222), _s(142), _s(290), _s(210)], fill=ACCENT)
    d.rounded_rectangle([_s(120), _s(384), _s(392), _s(400)], radius=_s(8), fill=ACCENT)
    return img


DRAFTS = {"A": draft_a, "B": draft_b, "C": draft_c}
DEFAULT = "B"


def _resize(img, size):
    return img.resize((size, size), Image.LANCZOS)


def write_icons(key):
    big = DRAFTS[key]()
    ICONS.mkdir(parents=True, exist_ok=True)
    # Motiv liegt innerhalb der inneren 80 % – passt auch als „maskable“ (rund/abgerundet)
    for name, size in [
        ("icon-192.png", 192),
        ("icon-512.png", 512),
        ("icon-maskable-512.png", 512),
        ("apple-touch-icon.png", 180),
        ("favicon-32.png", 32),
    ]:
        _resize(big, size).save(ICONS / name, optimize=True)


def write_preview():
    PREVIEW.mkdir(parents=True, exist_ok=True)
    tiles = []
    for key, draw in DRAFTS.items():
        img = _resize(draw(), 256)
        img.save(PREVIEW / f"entwurf-{key.lower()}.png", optimize=True)
        tiles.append((key, img))
    sheet = Image.new("RGB", (3 * 296 + 40, 340), (23, 26, 33))
    d = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=22)
    for i, (key, img) in enumerate(tiles):
        x = 40 + i * 296
        # abgerundet wie auf dem Home-Bildschirm
        mask = Image.new("L", img.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, 255, 255], radius=56, fill=255)
        sheet.paste(img, (x, 30), mask)
        d.text((x + 100, 298), f"Entwurf {key}", fill=TEXT, font=font)
    sheet.save(PREVIEW / "uebersicht.png", optimize=True)


if __name__ == "__main__":
    choice = (sys.argv[1] if len(sys.argv) > 1 else DEFAULT).upper()
    if choice not in DRAFTS:
        sys.exit(f"Unbekannter Entwurf {choice!r} – A, B oder C")
    write_preview()
    write_icons(choice)
    print(f"App-Icon: Entwurf {choice} → {ICONS.relative_to(ROOT)}")
