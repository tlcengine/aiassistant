"""Outbound voice calls via Twilio — call a contact and deliver a TTS message."""

import logging
from twilio.rest import Client
from config import get_settings
from sqlalchemy import select, or_
from crm.database import async_session
from crm.models import Contact

logger = logging.getLogger(__name__)

# In-memory store: CallSid -> {message, contact_name}
# Populated when a call is initiated, read by the TwiML webhook
pending_calls: dict[str, dict] = {}

# Krishna's forwarding number
KRISHNA_PHONE = "+19084305187"


async def lookup_contact_by_name(name: str) -> dict | None:
    """Look up a contact by name in the CRM. Returns phone + name or None."""
    async with async_session() as db:
        parts = name.strip().split(" ", 1)
        first = parts[0]
        last = parts[1] if len(parts) > 1 else ""

        if last:
            stmt = select(Contact).where(
                Contact.first_name.ilike(f"%{first}%"),
                Contact.last_name.ilike(f"%{last}%"),
            )
        else:
            stmt = select(Contact).where(
                or_(
                    Contact.first_name.ilike(f"%{first}%"),
                    Contact.last_name.ilike(f"%{first}%"),
                )
            )
        result = await db.execute(stmt)
        contact = result.scalar_one_or_none()

        if contact and contact.phone:
            return {
                "name": f"{contact.first_name or ''} {contact.last_name or ''}".strip(),
                "phone": contact.phone,
                "email": contact.email,
            }
    return None


async def make_outbound_call(
    phone: str = "",
    message: str = "",
    contact_name: str = "",
) -> dict:
    """Initiate an outbound call via Twilio.

    If phone is empty but contact_name is provided, looks up the CRM first.
    The message is stored in memory and retrieved by the /outbound-twiml webhook.
    """
    settings = get_settings()

    # If no phone provided, try CRM lookup
    if not phone and contact_name:
        contact = await lookup_contact_by_name(contact_name)
        if contact:
            phone = contact["phone"]
            if not contact_name:
                contact_name = contact["name"]
        else:
            return {
                "success": False,
                "error": f"Could not find a phone number for '{contact_name}' in the CRM.",
            }

    if not phone:
        return {
            "success": False,
            "error": "No phone number provided and no contact name to look up.",
        }

    # Normalize phone number
    phone = phone.strip()
    if not phone.startswith("+"):
        phone = "+1" + phone.replace("-", "").replace("(", "").replace(")", "").replace(" ", "")

    # Webhook URL for Twilio to fetch TwiML when the call is answered
    webhook_url = "https://aiassistant.certihomes.com/outbound-twiml"

    try:
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        call = client.calls.create(
            to=phone,
            from_=settings.twilio_phone_number,
            url=webhook_url,
            method="POST",
            status_callback="https://aiassistant.certihomes.com/call-status",
            status_callback_method="POST",
        )

        # Store the message so the TwiML webhook can retrieve it
        pending_calls[call.sid] = {
            "message": message,
            "contact_name": contact_name,
        }

        logger.info(f"Outbound call initiated: {call.sid} to {phone}")
        return {
            "success": True,
            "call_sid": call.sid,
            "to": phone,
            "contact_name": contact_name,
            "message": message,
        }

    except Exception as e:
        logger.exception("Failed to initiate outbound call")
        return {"success": False, "error": str(e)}
