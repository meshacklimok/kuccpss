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
