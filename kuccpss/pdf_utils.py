"""
Shared helpers for ReportLab-generated PDFs.

`enable_site_links(canvas)` makes every CareerNext URL or email drawn on the
canvas clickable, so each PDF view only needs one call after creating its canvas.
"""
import re

SITE_URL = "https://www.careernext.co.ke"

# Emails first so "support@careernext.co.ke" becomes a mailto: link rather than
# a web link on its domain part. Web links may carry a path (e.g. /mentorship/).
_LINK_RE = re.compile(
    r"(?P<email>[\w.+-]+@careernext\.co\.ke)"
    r"|(?P<web>(?<![\w.@/])(?:https?://)?(?:www\.)?careernext\.co\.ke(?:/[^\s|,)]*)?)",
    re.IGNORECASE,
)


def draw_logo_mark(c, x: float, y: float, size: float) -> None:
    """Draw the CareerNext 'Summit' mark with its lower-left corner at (x, y).

    Mirrors static/img/logo-white.svg (lighter tile, made for navy header bands).
    Coordinates below are the SVG's 64x64 grid, flipped to ReportLab's y-up space.
    """
    from reportlab.lib.colors import HexColor

    c.saveState()
    c.translate(x, y + size)
    c.scale(size / 64.0, -size / 64.0)

    clip = c.beginPath()
    clip.roundRect(0, 0, 64, 64, 15)
    c.clipPath(clip, stroke=0, fill=0)

    c.setFillColor(HexColor("#2F5FD0"))
    c.rect(0, 0, 64, 64, fill=1, stroke=0)

    def poly(points, fill):
        path = c.beginPath()
        path.moveTo(*points[0])
        for pt in points[1:]:
            path.lineTo(*pt)
        path.close()
        c.setFillColor(HexColor(fill))
        c.drawPath(path, fill=1, stroke=0)

    poly([(-4, 66), (17, 34), (23, 40), (31, 23), (34.5, 28), (39, 17), (68, 66)], "#FFFFFF")
    poly([(39, 17), (68, 66), (45, 66), (41.5, 38)], "#B9CCF4")
    poly([(31, 23), (34.5, 28), (31.5, 36)], "#B9CCF4")
    poly([(17, 34), (23, 40), (20.5, 44)], "#B9CCF4")

    # Trail
    c.setStrokeColor(HexColor("#16A34A"))
    c.setLineWidth(3.9)
    c.setLineCap(1)
    c.setLineJoin(1)
    trail = c.beginPath()
    trail.moveTo(24, 67)
    for pt in [(38.5, 56.5), (29.5, 49), (38.5, 41.5), (37, 32)]:
        trail.lineTo(*pt)
    c.drawPath(trail, fill=0, stroke=1)
    c.restoreState()

    # Flag sits above the clip so the pole and pennant can reach past the peak.
    c.saveState()
    c.translate(x, y + size)
    c.scale(size / 64.0, -size / 64.0)
    c.setStrokeColor(HexColor("#FFFFFF"))
    c.setLineWidth(2.4)
    c.setLineCap(1)
    c.line(39, 18, 39, 6.5)
    poly([(39.7, 6), (50, 9.4), (39.7, 12.8)], "#4ADE80")
    c.restoreState()


def _href(match: re.Match) -> str:
    if match.group("email"):
        return f"mailto:{match.group('email')}"
    web = match.group("web")
    path = web.split("careernext.co.ke", 1)[1] if "careernext.co.ke" in web.lower() else ""
    return SITE_URL + path


def _add_links(c, text: str, start_x: float, y: float) -> None:
    font, size = c._fontname, c._fontsize
    for m in _LINK_RE.finditer(text):
        x0 = start_x + c.stringWidth(text[: m.start()], font, size)
        x1 = x0 + c.stringWidth(m.group(0), font, size)
        # relative=1 → rect is in current user space (respects translate/rotate).
        c.linkURL(_href(m), (x0, y - size * 0.25, x1, y + size * 0.9),
                  relative=1, thickness=0)


def enable_site_links(c):
    """Wrap the canvas's string-drawing methods so CareerNext links are clickable."""
    draw_left, draw_centre, draw_right = c.drawString, c.drawCentredString, c.drawRightString

    def drawString(x, y, text, *args, **kwargs):
        result = draw_left(x, y, text, *args, **kwargs)
        _add_links(c, str(text), x, y)
        return result

    def drawCentredString(x, y, text, *args, **kwargs):
        result = draw_centre(x, y, text, *args, **kwargs)
        text = str(text)
        _add_links(c, text, x - c.stringWidth(text, c._fontname, c._fontsize) / 2, y)
        return result

    def drawRightString(x, y, text, *args, **kwargs):
        result = draw_right(x, y, text, *args, **kwargs)
        text = str(text)
        _add_links(c, text, x - c.stringWidth(text, c._fontname, c._fontsize), y)
        return result

    c.drawString = drawString
    c.drawCentredString = drawCentredString
    c.drawRightString = drawRightString
    return c
