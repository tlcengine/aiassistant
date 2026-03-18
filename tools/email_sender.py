"""Email sender — sends HTML emails from claude@certihomes.com via Google Workspace SMTP."""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from config import get_settings

SENDER_EMAIL = "claude@certihomes.com"
REPLY_TO_EMAIL = "krishna@certihomes.com"
SENDER_NAME = "CertiHomes AI Assistant"


def send_email(
    to: str,
    subject: str,
    html_body: str,
    plain_body: str | None = None,
    cc: str | None = None,
) -> dict:
    """Send an HTML email via Google Workspace SMTP.

    Returns dict with success status and message ID.
    """
    settings = get_settings()

    msg = MIMEMultipart("alternative")
    msg["From"] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg["Reply-To"] = REPLY_TO_EMAIL
    if cc:
        msg["Cc"] = cc

    # Plain-text fallback
    if not plain_body:
        plain_body = "Please view this email in an HTML-capable email client."
    msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(SENDER_EMAIL, settings.smtp_app_password)
            recipients = [to]
            if cc:
                recipients.extend([addr.strip() for addr in cc.split(",")])
            server.sendmail(SENDER_EMAIL, recipients, msg.as_string())
        return {"sent": True, "to": to, "subject": subject}
    except Exception as e:
        return {"sent": False, "error": str(e)}
