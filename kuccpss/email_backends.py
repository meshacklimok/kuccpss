import base64
import logging

import requests as http_requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


class ResendEmailBackend(BaseEmailBackend):
    """
    Sends via Resend's REST API (HTTPS/443) instead of SMTP.
    Render's free tier blocks outbound SMTP (port 465/587), which causes
    gunicorn worker timeouts. HTTPS is never blocked.
    """

    def send_messages(self, email_messages):
        api_key = getattr(settings, "RESEND_API_KEY", "")
        if not api_key:
            return 0

        sent = 0
        for message in email_messages:
            try:
                html_body = None
                if hasattr(message, "alternatives"):
                    for content, mimetype in message.alternatives:
                        if mimetype == "text/html":
                            html_body = content
                            break

                payload = {
                    "from": message.from_email,
                    "to": list(message.to),
                    "subject": message.subject,
                    "text": message.body,
                }
                if html_body:
                    payload["html"] = html_body

                attachments = []
                for filename, content, mimetype in getattr(message, "attachments", []) or []:
                    if isinstance(content, str):
                        content = content.encode("utf-8")
                    attachments.append({
                        "filename": filename,
                        "content": base64.b64encode(content).decode("ascii"),
                    })
                if attachments:
                    payload["attachments"] = attachments

                response = http_requests.post(
                    RESEND_API_URL,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=10,
                )
                if response.status_code in (200, 201):
                    sent += 1
                else:
                    logger.error(
                        "Resend API error %s: %s", response.status_code, response.text
                    )
            except Exception as exc:
                logger.error("ResendEmailBackend failed: %s", exc)
                if not self.fail_silently:
                    raise
        return sent
