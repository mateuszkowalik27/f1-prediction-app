"""Rysuje ikony aplikacji: wykres w tle i duża flaga w szachownicę na środku.

Uruchom:  .venv/bin/python scripts/make_icons.py   (wymaga Pillow: .venv/bin/pip install pillow)
Z jednej geometrii powstają: public/icons/*.png oraz public/favicon.svg.
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
BG, RED, RED_LIGHT = (15, 17, 22), (225, 6, 0), (255, 59, 48)
WHITE, DARK = (245, 245, 247), (15, 17, 22)
S = 512

CHART = [(30, 392), (110, 336), (180, 366), (262, 290), (340, 318), (420, 204), (486, 150)]
GRID_Y = [110, 190, 270, 350, 430]
POLE_X, POLE_TOP, POLE_BOTTOM = 142, 158, 412
FLAG_X, FLAG_Y, COLS, ROWS, CW, CH, WAVE = POLE_X, 178, 6, 4, 38, 38, 9


FLAG_ANGLE = 45  # stopnie, przeciwnie do ruchu wskazówek zegara (flaga zadarta w górę w prawo)


def rot(points):
    """Obraca całą flagę (z drzewcem) wokół środka ikony."""
    t = math.radians(FLAG_ANGLE)
    c, s = math.cos(t), math.sin(t)
    return [(S / 2 + (x - S / 2) * c + (y - S / 2) * s, S / 2 - (x - S / 2) * s + (y - S / 2) * c) for x, y in points]


def wave(col):
    return WAVE * math.sin(col * 0.9 + 0.3)


def flag_cells():
    """Komórki szachownicy: (4 wierzchołki, kolor). Kolumny falują w pionie."""
    cells = []
    for r in range(ROWS):
        for c in range(COLS):
            x0, x1 = FLAG_X + c * CW, FLAG_X + (c + 1) * CW
            y0, y1 = FLAG_Y + r * CH, FLAG_Y + (r + 1) * CH
            pts = [(x0, y0 + wave(c)), (x1, y0 + wave(c + 1)), (x1, y1 + wave(c + 1)), (x0, y1 + wave(c))]
            cells.append((pts, WHITE if (r + c) % 2 == 0 else DARK))
    return cells


def flag_outline():
    top = [(FLAG_X + c * CW, FLAG_Y + wave(c)) for c in range(COLS + 1)]
    bottom = [(FLAG_X + c * CW, FLAG_Y + ROWS * CH + wave(c)) for c in range(COLS, -1, -1)]
    return top + bottom


def transform(points, k):
    """Skaluje względem środka ikony (dla wersji maskable zostawiamy margines bezpieczeństwa)."""
    return [(S / 2 + (x - S / 2) * k, S / 2 + (y - S / 2) * k) for x, y in points]


def render_png(size, rounded=True, k=1.0, ss=4):
    W = size * ss
    f = W / S
    base = Image.new("RGBA", (W, W), BG + (255,))

    def P(points):
        return [(x * f, y * f) for x, y in transform(points, k)]

    def layer(draw_fn):
        im = Image.new("RGBA", (W, W), (0, 0, 0, 0))
        draw_fn(ImageDraw.Draw(im))
        return im

    def grid(d):
        for y in GRID_Y:
            a, b = P([(36, y), (476, y)])
            d.line([a, b], fill=(255, 255, 255, 22), width=max(1, int(2 * f * k)))
    base = Image.alpha_composite(base, layer(grid))

    def area(d):
        d.polygon(P(CHART + [(CHART[-1][0], 452), (CHART[0][0], 452)]), fill=RED + (95,))
    base = Image.alpha_composite(base, layer(area))

    def line(d):
        pts = P(CHART)
        w = 15 * f * k
        d.line(pts, fill=RED_LIGHT + (255,), width=int(w), joint="curve")
        for x, y in pts:
            d.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=RED_LIGHT + (255,))
    base = Image.alpha_composite(base, layer(line))

    def shadow(d):
        d.polygon([(x + 5 * f * k, y + 7 * f * k) for x, y in P(rot(flag_outline()))], fill=(0, 0, 0, 120))
    base = Image.alpha_composite(base, layer(shadow))

    def flag(d):
        pw = 11 * f * k
        (x0, y0), (x1, y1) = P(rot([(POLE_X, POLE_TOP), (POLE_X, POLE_BOTTOM)]))
        d.line([(x0, y0), (x1, y1)], fill=WHITE + (255,), width=int(pw))
        d.ellipse([x0 - pw * 0.75, y0 - pw * 0.75, x0 + pw * 0.75, y0 + pw * 0.75], fill=WHITE + (255,))
        for pts, color in flag_cells():
            d.polygon(P(rot(pts)), fill=color + (255,))
        outline = P(rot(flag_outline()))
        d.line(outline + [outline[0]], fill=WHITE + (255,), width=int(5 * f * k), joint="curve")
    base = Image.alpha_composite(base, layer(flag))

    if rounded:
        mask = Image.new("L", (W, W), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, W - 1, W - 1], radius=int(W * 0.2), fill=255)
        out = Image.new("RGBA", (W, W), (0, 0, 0, 0))
        out.paste(base, mask=mask)
        base = out
    return base.resize((size, size), Image.LANCZOS)


def svg():
    def pts(points):
        return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {S} {S}">',
             f'<rect width="{S}" height="{S}" rx="{S * 0.2:.0f}" fill="rgb{BG}"/>']
    for y in GRID_Y:
        parts.append(f'<line x1="36" y1="{y}" x2="476" y2="{y}" stroke="#fff" stroke-opacity=".09" stroke-width="2"/>')
    area = CHART + [(CHART[-1][0], 452), (CHART[0][0], 452)]
    parts.append(f'<polygon points="{pts(area)}" fill="rgb{RED}" fill-opacity=".37"/>')
    parts.append(f'<polyline points="{pts(CHART)}" fill="none" stroke="rgb{RED_LIGHT}" stroke-width="15" stroke-linecap="round" stroke-linejoin="round"/>')
    shifted = [(x + 5, y + 7) for x, y in rot(flag_outline())]
    parts.append(f'<polygon points="{pts(shifted)}" fill="#000" fill-opacity=".47"/>')
    (px0, py0), (px1, py1) = rot([(POLE_X, POLE_TOP), (POLE_X, POLE_BOTTOM)])
    parts.append(f'<line x1="{px0:.1f}" y1="{py0:.1f}" x2="{px1:.1f}" y2="{py1:.1f}" stroke="rgb{WHITE}" stroke-width="11" stroke-linecap="round"/>')
    for cell, color in flag_cells():
        parts.append(f'<polygon points="{pts(rot(cell))}" fill="rgb{color}"/>')
    parts.append(f'<polygon points="{pts(rot(flag_outline()))}" fill="none" stroke="rgb{WHITE}" stroke-width="5" stroke-linejoin="round"/>')
    parts.append("</svg>")
    return "\n".join(parts)


if __name__ == "__main__":
    out = ROOT / "public" / "icons"
    out.mkdir(parents=True, exist_ok=True)
    render_png(512).save(out / "icon-512.png")
    render_png(192).save(out / "icon-192.png")
    render_png(180, rounded=False).save(out / "apple-touch-icon.png")             # iOS sam zaokrągla rogi
    render_png(512, rounded=False, k=0.78).save(out / "icon-512-maskable.png")    # treść w "bezpiecznym" środku
    (ROOT / "public" / "favicon.svg").write_text(svg(), encoding="utf-8")
    print("ikony zapisane w", out)
