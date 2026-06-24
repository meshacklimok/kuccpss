"""
Shared branded email helper.
Every user-facing transactional email should go through send_branded_email()
so they all share the same CareerNext header / footer.
"""
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)

BANNER_COLORS = {
    "green":  "#16a34a",
    "blue":   "#2563eb",
    "amber":  "#d97706",
    "red":    "#dc2626",
    "purple": "#7c3aed",
}


def send_branded_email(
    to,
    subject,
    heading,
    body_lines,
    *,
    banner_label="",
    banner_color="green",
    greeting="",
    table_rows=None,
    cta_url="",
    cta_label="",
    note="",
    user_email="",
    attachments=None,
    fail_silently=True,
):
    """
    Send a branded HTML + plain-text transactional email.

    Args:
        to              — recipient email (str) or list of emails
        subject         — email subject line
        heading         — large heading shown inside the card body
        body_lines      — list of paragraph strings
        banner_label    — short text in the coloured banner strip (e.g. "✓ Confirmed")
        banner_color    — "green" | "blue" | "amber" | "red" | "purple"
        greeting        — e.g. "Hi John,"  (rendered above body_lines)
        table_rows      — list of {"label": str, "value": str, "highlight": bool}
        cta_url         — primary button URL
        cta_label       — primary button label
        note            — small footnote text below the button
        user_email      — shown in footer ("This email was sent to …")
        attachments     — list of (filename, content, mimetype) tuples
        fail_silently   — swallow SMTP errors when True
    """
    if isinstance(to, str):
        to = [to]

    banner_color_hex = BANNER_COLORS.get(banner_color, BANNER_COLORS["green"])

    ctx = {
        "subject": subject,
        "heading": heading,
        "banner_label": banner_label,
        "banner_color_hex": banner_color_hex,
        "greeting": greeting,
        "body_lines": body_lines,
        "table_rows": table_rows or [],
        "cta_url": cta_url,
        "cta_label": cta_label,
        "note": note,
        "user_email": user_email,
        "year": timezone.now().year,
    }

    try:
        html_body = render_to_string("emails/transactional.html", ctx)

        plain_parts = []
        if greeting:
            plain_parts.append(greeting + "\n")
        plain_parts.extend(body_lines)
        if table_rows:
            plain_parts.append("")
            for row in table_rows:
                plain_parts.append(f"{row['label']}: {row['value']}")
        if cta_url:
            plain_parts.append(f"\n{cta_label or 'Open CareerNext'}: {cta_url}")
        if note:
            plain_parts.append(f"\n{note}")
        plain_parts.append("\nCareerNext Team\nsupport@careernext.co.ke\ncareernext.co.ke")
        plain_body = "\n".join(plain_parts)

        email = EmailMultiAlternatives(
            subject=subject,
            body=plain_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=to,
        )
        email.attach_alternative(html_body, "text/html")

        for filename, content, mimetype in (attachments or []):
            email.attach(filename, content, mimetype)

        email.send(fail_silently=fail_silently)

    except Exception as exc:
        logger.error("send_branded_email failed to=%s subject=%r: %s", to, subject, exc)
        if not fail_silently:
            raise
