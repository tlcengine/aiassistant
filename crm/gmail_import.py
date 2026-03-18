"""Gmail/Google Contacts import via People API."""

import json
import logging
import os
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request

# Allow scope changes (Google often adds openid/profile)
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
from googleapiclient.discovery import build
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from crm.models import Contact, ContactSource
from config import get_settings

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/contacts.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]

TOKEN_PATH = Path.home() / ".config" / "aiassistant" / "google_token.json"


def get_oauth_flow(redirect_uri: str) -> Flow:
    settings = get_settings()
    client_config = {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri],
        }
    }
    return Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=redirect_uri)


def get_credentials() -> Credentials | None:
    if not TOKEN_PATH.exists():
        return None
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json())
    return creds if creds and creds.valid else None


def save_credentials(creds: Credentials):
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(creds.to_json())


async def import_google_contacts(db: AsyncSession) -> dict:
    """Fetch contacts from Google People API and upsert into CRM."""
    creds = get_credentials()
    if not creds:
        return {"error": "Not authenticated. Visit /api/crm/gmail/auth to connect."}

    service = build("people", "v1", credentials=creds)
    imported = 0
    skipped = 0
    page_token = None

    while True:
        results = service.people().connections().list(
            resourceName="people/me",
            pageSize=200,
            personFields="names,emailAddresses,phoneNumbers,organizations,photos,addresses",
            pageToken=page_token,
        ).execute()

        connections = results.get("connections", [])
        for person in connections:
            resource_name = person.get("resourceName", "")
            names = person.get("names", [{}])
            name = names[0] if names else {}
            first = name.get("givenName", "")
            last = name.get("familyName", "")
            if not first and not last:
                skipped += 1
                continue

            emails = person.get("emailAddresses", [])
            email = emails[0].get("value") if emails else None
            phones = person.get("phoneNumbers", [])
            phone = phones[0].get("canonicalForm") or (phones[0].get("value") if phones else None)
            orgs = person.get("organizations", [])
            company = orgs[0].get("name") if orgs else None
            title = orgs[0].get("title") if orgs else None
            photos = person.get("photos", [])
            avatar = photos[0].get("url") if photos else None
            addresses = person.get("addresses", [])
            addr = addresses[0] if addresses else {}

            # Upsert by gmail_contact_id
            existing = (await db.execute(
                select(Contact).where(Contact.gmail_contact_id == resource_name)
            )).scalar_one_or_none()

            if existing:
                existing.first_name = first or existing.first_name
                existing.last_name = last or existing.last_name
                existing.email = email or existing.email
                existing.phone = phone or existing.phone
                existing.company = company or existing.company
                existing.title = title or existing.title
                existing.avatar_url = avatar or existing.avatar_url
                skipped += 1
            else:
                contact = Contact(
                    first_name=first,
                    last_name=last,
                    email=email,
                    phone=phone,
                    company=company,
                    title=title,
                    avatar_url=avatar,
                    city=addr.get("city"),
                    state=addr.get("region"),
                    zip_code=addr.get("postalCode"),
                    source=ContactSource.GMAIL,
                    gmail_contact_id=resource_name,
                )
                db.add(contact)
                imported += 1

        page_token = results.get("nextPageToken")
        if not page_token:
            break

    await db.commit()
    return {"imported": imported, "updated": skipped}
