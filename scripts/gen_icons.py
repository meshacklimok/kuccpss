"""
Generate CareerNext PNG / ICO brand assets from the SVG logo design.

Renders the logo mark (solid navy tile + rising path + forward arrowhead)
directly with Pillow.

Outputs (into static/images/):
  icon-192.png, icon-512.png   -> PWA maskable icons (full-bleed tile)
  icon-180.png                 -> apple-touch-icon
  favicon.ico                  -> multi-size favicon (16/32/48)
  logo-og.png                  -> 1200x630 social share card (light bg + lockup)
"""
import os
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(__file__), "..", "static", "images")
os.makedirs(OUT, exist_ok=True)

# Brand tile colour (solid navy — the site uses no colour gradients)
BRAND = (0x1e, 0x3a, 0x8a)


def quad_points(p0, c, p1, n=40):
    pts = []
    for i in range(n + 1):
        t = i / n
        mt = 1 - t
        x = mt * mt * p0[0] + 2 * mt * t * c[0] + t * t * p1[0]
        y = mt * mt * p0[1] + 2 * mt * t * c[1] + t * t * p1[1]
        pts.append((x, y))
    return pts


def draw_mark_glyph(draw, f, ox=0.0, oy=0.0, color=(255, 255, 255)):
    """Draw the rising-path glyph in a 64-unit space scaled by f, offset (ox,oy)."""
    def S(p):
        return (ox + p[0] * f, oy + p[1] * f)

    w = int(6 * f)  # stroke width
    r = w / 2

    # Rising path: two quadratics (matches the SVG M16 48 Q30 48 34 34 T 48 16)
    curve = quad_points((16, 48), (30, 48), (34, 34)) + quad_points((34, 34), (38, 20), (48, 16))
    # Arrowhead polyline 48,26 -> 48,16 -> 38,16
    arrow = [(48, 26), (48, 16), (38, 16)]

    for seq in (curve, arrow):
        pts = [S(p) for p in seq]
        draw.line(pts, fill=color, width=w, joint="curve")
        # round caps / joins
        for (x, y) in pts:
            draw.ellipse([x - r, y - r, x + r, y + r], fill=color)

    # starting node dot (filled circle r5 at 16,48)
    cx, cy = S((16, 48))
    dr = 5 * f
    draw.ellipse([cx - dr, cy - dr, cx + dr, cy + dr], fill=color)


def render_mark(size, full_bleed=True, ss=4):
    """Render the square mark at `size`px. full_bleed = no rounded corners (maskable)."""
    big = size * ss
    tile = Image.new("RGB", (big, big), BRAND)
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))

    if full_bleed:
        img.paste(tile, (0, 0))
    else:
        mask = Image.new("L", (big, big), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, big - 1, big - 1], radius=int(big * 0.14), fill=255)
        img.paste(tile, (0, 0), mask)

    f = big / 64.0
    draw_mark_glyph(ImageDraw.Draw(img), f)
    return img.resize((size, size), Image.LANCZOS)


def _font(sz):
    for name in ("seguisb.ttf", "segoeuib.ttf", "arialbd.ttf", "Arialbd.ttf"):
        try:
            return ImageFont.truetype(name, sz)
        except OSError:
            continue
    return ImageFont.load_default()


def render_og():
    """1200x630 social share card: light bg, mark + wordmark + tagline."""
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), (240, 244, 255))
    d = ImageDraw.Draw(img)

    mark = render_mark(240, full_bleed=False)
    img.paste(mark, (180, 150), mark)

    big = _font(96)
    sub = _font(34)
    # wordmark "Career" (dark) + "Next" (green)
    tx = 450
    ty = 250
    d.text((tx, ty), "Career", font=big, fill=(30, 41, 59))
    cw = d.textlength("Career", font=big)
    d.text((tx + cw, ty), "Next", font=big, fill=(0x16, 0xa3, 0x4a))
    d.text((tx + 4, ty + 130), "Kenya's KCSE career guidance & cluster points", font=sub, fill=(0x64, 0x74, 0x8b))
    return img


def main():
    for size in (192, 512):
        render_mark(size, full_bleed=True).save(os.path.join(OUT, f"icon-{size}.png"))
    render_mark(180, full_bleed=True).save(os.path.join(OUT, "icon-180.png"))

    ico = render_mark(64, full_bleed=False)
    ico.save(os.path.join(OUT, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48)])

    render_og().save(os.path.join(OUT, "logo-og.png"))

    print("Generated:", ", ".join(sorted(os.listdir(OUT))))


if __name__ == "__main__":
    main()
