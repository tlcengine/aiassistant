"""Close CRM integration — create leads, log activities, schedule tasks."""

import httpx
from config import get_settings


async def create_lead(
    name: str,
    phone: str,
    email: str | None = None,
    interest: str = "",
    notes: str = "",
) -> dict:
    """Create a new lead in Close CRM from a caller."""
    settings = get_settings()
    contacts = [{"name": name, "phones": [{"phone": phone, "type": "mobile"}]}]
    if email:
        contacts[0]["emails"] = [{"email": email, "type": "office"}]

    payload = {
        "name": name,
        "contacts": contacts,
        "custom": {
            "interest": interest,
            "source": "AI Receptionist",
        },
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.close.com/api/v1/lead/",
            json=payload,
            auth=(settings.close_api_key, ""),
        )
        resp.raise_for_status()
        lead = resp.json()

    # Add call notes
    if notes:
        async with httpx.AsyncClient(timeout=30) as client:
            await client.post(
                "https://api.close.com/api/v1/activity/note/",
                json={"lead_id": lead["id"], "note": notes},
                auth=(settings.close_api_key, ""),
            )

    return lead


async def schedule_callback(lead_id: str, due_date: str, text: str = "AI Receptionist callback") -> dict:
    """Create a follow-up task in Close CRM."""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.close.com/api/v1/task/",
            json={
                "lead_id": lead_id,
                "type": "call",
                "due_date": due_date,
                "text": text,
            },
            auth=(settings.close_api_key, ""),
        )
        resp.raise_for_status()
        return resp.json()
