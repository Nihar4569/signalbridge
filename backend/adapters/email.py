"""Email adapter for post-approval notifications.

Default mode is "simulated": we build the email and log it, but do NOT send it.
That keeps the prototype runnable with zero setup and no secrets.

Set EMAIL_MODE=smtp plus the SMTP_* env vars to actually send (e.g. via Gmail
or any SMTP relay). See docs/after_plan_approval.md.
"""
from __future__ import annotations

import smtplib
from email.message import EmailMessage

from ..core import config
from ..core.logging import get_logger

log = get_logger("email")


class EmailSender:
    def send(self, *, to: str, subject: str, body: str) -> dict:
        """Send (or simulate) one email. Always returns a result dict."""
        if config.EMAIL_MODE == "smtp" and config.SMTP_HOST:
            return self._send_smtp(to=to, subject=subject, body=body)

        # Prototype default: do not really send.
        log.info("Simulated email -> %s | %s", to, subject)
        return {"sent": True, "mode": "simulated", "to": to, "subject": subject, "body": body}

    def _send_smtp(self, *, to: str, subject: str, body: str) -> dict:
        try:
            msg = EmailMessage()
            msg["From"] = config.EMAIL_FROM
            msg["To"] = to
            msg["Subject"] = subject
            msg.set_content(body)

            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
                server.starttls()
                if config.SMTP_USER:
                    server.login(config.SMTP_USER, config.SMTP_PASSWORD)
                server.send_message(msg)

            log.info("SMTP email sent -> %s | %s", to, subject)
            return {"sent": True, "mode": "smtp", "to": to, "subject": subject}
        except Exception as exc:  # never let email break the approval flow
            log.warning("SMTP send failed: %s", exc)
            return {"sent": False, "mode": "smtp", "to": to, "subject": subject, "error": type(exc).__name__}
