"""CRM REST API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from datetime import datetime, date
from crm.database import get_db
from crm.models import Contact, Deal, Activity, Tag, ContactSource, LeadStatus, ActivityType

router = APIRouter(prefix="/api/crm", tags=["CRM"])


# --- Schemas ---

class ContactCreate(BaseModel):
    first_name: str
    last_name: str = ""
    email: str | None = None
    phone: str | None = None
    company: str | None = None
    title: str | None = None
    source: ContactSource = ContactSource.MANUAL
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    notes: str | None = None
    interest: str | None = None
    budget_min: int | None = None
    budget_max: int | None = None
    desired_beds: int | None = None
    desired_area: str | None = None
    linkedin_url: str | None = None
    facebook_url: str | None = None
    instagram_handle: str | None = None
    twitter_handle: str | None = None


class ContactUpdate(ContactCreate):
    first_name: str | None = None
    status: LeadStatus | None = None


class DealCreate(BaseModel):
    contact_id: int
    title: str
    value: float | None = None
    status: LeadStatus | None = None
    property_address: str | None = None
    mls_id: str | None = None
    notes: str | None = None
    expected_close_date: date | None = None


class ActivityCreate(BaseModel):
    contact_id: int
    deal_id: int | None = None
    type: ActivityType
    subject: str
    body: str | None = None
    due_date: datetime | None = None


class TagCreate(BaseModel):
    name: str
    color: str = "#3b82f6"


# --- Contact endpoints ---

@router.get("/contacts")
async def list_contacts(
    q: str | None = None,
    status: LeadStatus | None = None,
    source: ContactSource | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Contact).options(selectinload(Contact.tags))
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            or_(
                Contact.first_name.ilike(pattern),
                Contact.last_name.ilike(pattern),
                Contact.email.ilike(pattern),
                Contact.phone.ilike(pattern),
                Contact.company.ilike(pattern),
            )
        )
    if status:
        stmt = stmt.where(Contact.status == status)
    if source:
        stmt = stmt.where(Contact.source == source)
    stmt = stmt.order_by(Contact.updated_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    contacts = result.scalars().all()

    count_stmt = select(func.count(Contact.id))
    total = (await db.execute(count_stmt)).scalar()

    return {
        "contacts": [_contact_to_dict(c) for c in contacts],
        "total": total,
    }


@router.post("/contacts")
async def create_contact(data: ContactCreate, db: AsyncSession = Depends(get_db)):
    contact = Contact(**data.model_dump(exclude_none=True))
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return _contact_to_dict(contact)


@router.get("/contacts/{contact_id}")
async def get_contact(contact_id: int, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Contact)
        .options(selectinload(Contact.tags), selectinload(Contact.activities), selectinload(Contact.deals))
        .where(Contact.id == contact_id)
    )
    result = await db.execute(stmt)
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(404, "Contact not found")
    d = _contact_to_dict(contact)
    d["activities"] = [
        {"id": a.id, "type": a.type.value, "subject": a.subject, "body": a.body,
         "completed": a.completed, "created_at": a.created_at.isoformat()}
        for a in sorted(contact.activities, key=lambda x: x.created_at, reverse=True)[:20]
    ]
    d["deals"] = [
        {"id": dl.id, "title": dl.title, "value": dl.value, "status": dl.status.value,
         "mls_id": dl.mls_id, "created_at": dl.created_at.isoformat()}
        for dl in contact.deals
    ]
    return d


@router.patch("/contacts/{contact_id}")
async def update_contact(contact_id: int, data: ContactUpdate, db: AsyncSession = Depends(get_db)):
    contact = await db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(404, "Contact not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(contact, k, v)
    await db.commit()
    await db.refresh(contact)
    return _contact_to_dict(contact)


@router.delete("/contacts/{contact_id}")
async def delete_contact(contact_id: int, db: AsyncSession = Depends(get_db)):
    contact = await db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(404, "Contact not found")
    await db.delete(contact)
    await db.commit()
    return {"deleted": True}


# --- Deal endpoints ---

@router.get("/deals")
async def list_deals(
    status: LeadStatus | None = None,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Deal).options(selectinload(Deal.contact))
    if status:
        stmt = stmt.where(Deal.status == status)
    stmt = stmt.order_by(Deal.updated_at.desc()).limit(limit)
    result = await db.execute(stmt)
    deals = result.scalars().all()
    return [_deal_to_dict(d) for d in deals]


@router.post("/deals")
async def create_deal(data: DealCreate, db: AsyncSession = Depends(get_db)):
    deal = Deal(**data.model_dump(exclude_none=True))
    db.add(deal)
    await db.commit()
    await db.refresh(deal)
    return _deal_to_dict(deal)


class DealUpdate(BaseModel):
    title: str | None = None
    value: float | None = None
    status: LeadStatus | None = None
    property_address: str | None = None
    mls_id: str | None = None
    notes: str | None = None
    expected_close_date: date | None = None


@router.get("/deals/{deal_id}")
async def get_deal(deal_id: int, db: AsyncSession = Depends(get_db)):
    deal = await db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(404, "Deal not found")
    return _deal_to_dict(deal)


@router.patch("/deals/{deal_id}")
async def update_deal(deal_id: int, data: DealUpdate, db: AsyncSession = Depends(get_db)):
    deal = await db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(404, "Deal not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(deal, k, v)
    await db.commit()
    await db.refresh(deal)
    return _deal_to_dict(deal)


@router.delete("/deals/{deal_id}")
async def delete_deal(deal_id: int, db: AsyncSession = Depends(get_db)):
    deal = await db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(404, "Deal not found")
    await db.delete(deal)
    await db.commit()
    return {"deleted": True}


@router.get("/pipeline")
async def pipeline_view(db: AsyncSession = Depends(get_db)):
    """Get all deals grouped by stage for Kanban view."""
    stmt = (
        select(Deal)
        .options(selectinload(Deal.contact))
        .order_by(Deal.updated_at.desc())
    )
    result = await db.execute(stmt)
    deals = result.scalars().all()

    pipeline = {}
    for s in LeadStatus:
        pipeline[s.value] = []

    for d in deals:
        stage = d.status.value
        if stage in pipeline:
            pipeline[stage].append(_deal_to_dict(d))

    # Stats
    total_value = sum(d.value or 0 for d in deals)
    return {
        "stages": pipeline,
        "total_deals": len(deals),
        "total_value": total_value,
    }


def _deal_to_dict(d: Deal) -> dict:
    contact_name = ""
    contact_email = ""
    if hasattr(d, "contact") and d.contact:
        contact_name = f"{d.contact.first_name or ''} {d.contact.last_name or ''}".strip()
        contact_email = d.contact.email or ""
    return {
        "id": d.id,
        "contact_id": d.contact_id,
        "contact_name": contact_name,
        "contact_email": contact_email,
        "title": d.title,
        "value": d.value,
        "status": d.status.value,
        "property_address": d.property_address,
        "mls_id": d.mls_id,
        "notes": d.notes,
        "expected_close_date": d.expected_close_date.isoformat() if d.expected_close_date else None,
        "created_at": d.created_at.isoformat(),
        "updated_at": d.updated_at.isoformat(),
    }


# --- Activity endpoints ---

@router.post("/activities")
async def create_activity(data: ActivityCreate, db: AsyncSession = Depends(get_db)):
    activity = Activity(**data.model_dump(exclude_none=True))
    db.add(activity)
    await db.commit()
    await db.refresh(activity)
    return {"id": activity.id, "type": activity.type.value, "subject": activity.subject}


# --- Tag endpoints ---

@router.get("/tags")
async def list_tags(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tag).order_by(Tag.name))
    return [{"id": t.id, "name": t.name, "color": t.color} for t in result.scalars().all()]


@router.post("/tags")
async def create_tag(data: TagCreate, db: AsyncSession = Depends(get_db)):
    tag = Tag(**data.model_dump())
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return {"id": tag.id, "name": tag.name, "color": tag.color}


@router.post("/contacts/{contact_id}/tags/{tag_id}")
async def add_tag_to_contact(contact_id: int, tag_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Contact).options(selectinload(Contact.tags)).where(Contact.id == contact_id)
    contact = (await db.execute(stmt)).scalar_one_or_none()
    if not contact:
        raise HTTPException(404, "Contact not found")
    tag = await db.get(Tag, tag_id)
    if not tag:
        raise HTTPException(404, "Tag not found")
    contact.tags.append(tag)
    await db.commit()
    return {"ok": True}


# --- Dashboard stats ---

@router.get("/stats")
async def dashboard_stats(db: AsyncSession = Depends(get_db)):
    total = (await db.execute(select(func.count(Contact.id)))).scalar()
    by_status = {}
    for s in LeadStatus:
        cnt = (await db.execute(
            select(func.count(Contact.id)).where(Contact.status == s)
        )).scalar()
        by_status[s.value] = cnt
    deal_value = (await db.execute(
        select(func.sum(Deal.value)).where(Deal.status != LeadStatus.LOST)
    )).scalar() or 0
    return {
        "total_contacts": total,
        "by_status": by_status,
        "active_pipeline_value": deal_value,
    }


def _contact_to_dict(c: Contact) -> dict:
    return {
        "id": c.id,
        "first_name": c.first_name,
        "last_name": c.last_name,
        "full_name": c.full_name,
        "email": c.email,
        "phone": c.phone,
        "company": c.company,
        "title": c.title,
        "source": c.source.value,
        "status": c.status.value,
        "city": c.city,
        "state": c.state,
        "interest": c.interest,
        "tags": [{"id": t.id, "name": t.name, "color": t.color} for t in c.tags] if c.tags else [],
        "created_at": c.created_at.isoformat(),
        "updated_at": c.updated_at.isoformat(),
        "last_contacted_at": c.last_contacted_at.isoformat() if c.last_contacted_at else None,
    }
