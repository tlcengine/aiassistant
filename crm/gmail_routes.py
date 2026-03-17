"""Gmail OAuth + import routes."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from crm.database import get_db
from crm.gmail_import import get_oauth_flow, save_credentials, get_credentials, import_google_contacts

router = APIRouter(prefix="/api/crm/gmail", tags=["Gmail Import"])


@router.get("/auth")
async def gmail_auth(request: Request):
    """Start Google OAuth flow to connect Gmail contacts."""
    redirect_uri = str(request.url_for("gmail_callback"))
    flow = get_oauth_flow(redirect_uri)
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return RedirectResponse(auth_url)


@router.get("/callback")
async def gmail_callback(request: Request, code: str):
    """OAuth callback — exchange code for tokens and save."""
    redirect_uri = str(request.url_for("gmail_callback"))
    flow = get_oauth_flow(redirect_uri)
    flow.fetch_token(code=code)
    save_credentials(flow.credentials)
    return RedirectResponse("/crm?toast=Gmail+connected+successfully")


@router.get("/status")
async def gmail_status():
    """Check if Gmail is connected."""
    creds = get_credentials()
    return {"connected": creds is not None}


@router.post("/import")
async def gmail_import(db: AsyncSession = Depends(get_db)):
    """Import contacts from connected Gmail account."""
    result = await import_google_contacts(db)
    return result
