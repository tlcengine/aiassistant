"""Twilio SMS — send follow-up texts after calls."""

from twilio.rest import Client
from config import get_settings


def send_sms(to: str, body: str) -> str:
    """Send an SMS via Twilio. Returns the message SID."""
    settings = get_settings()
    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    message = client.messages.create(
        to=to,
        from_=settings.twilio_phone_number,
        body=body,
    )
    return message.sid
