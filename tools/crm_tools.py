"""CRM tools — lookup and create contacts in the local PostgreSQL CRM."""

from sqlalchemy import select, or_
from crm.database import async_session
from crm.models import Contact, ContactSource


async def lookup_contact_by_email(email: str) -> dict:
    """Check if an email address exists in the CRM. Returns contact info or not_found."""
    async with async_session() as db:
        stmt = select(Contact).where(Contact.email.ilike(email))
        result = await db.execute(stmt)
        contact = result.scalar_one_or_none()

        if contact:
            return {
                "found": True,
                "id": contact.id,
                "name": f"{contact.first_name or ''} {contact.last_name or ''}".strip(),
                "email": contact.email,
                "phone": contact.phone,
                "company": contact.company,
                "status": contact.status.value if contact.status else None,
            }
        return {"found": False, "email": email}


async def create_crm_contact(
    name: str,
    email: str | None = None,
    phone: str | None = None,
    interest: str = "",
    notes: str = "",
) -> dict:
    """Create a new contact in the local CRM database."""
    # Split name into first/last
    parts = name.strip().split(" ", 1)
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else ""

    async with async_session() as db:
        # Check if email already exists
        if email:
            stmt = select(Contact).where(Contact.email.ilike(email))
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                return {
                    "created": False,
                    "existing": True,
                    "id": existing.id,
                    "name": f"{existing.first_name or ''} {existing.last_name or ''}".strip(),
                    "message": f"Contact already exists: {existing.first_name} {existing.last_name}",
                }

        contact = Contact(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            company="",
            source=ContactSource.AI_ASSISTANT,
            notes=f"Interest: {interest}\n{notes}".strip() if interest or notes else "",
        )
        db.add(contact)
        await db.commit()
        await db.refresh(contact)

        return {
            "created": True,
            "id": contact.id,
            "name": name,
            "email": email,
            "phone": phone,
            "message": f"Added {name} to CRM",
        }
