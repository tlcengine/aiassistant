"""CRM data models — contacts, companies, deals, activities, tags."""

import datetime
from sqlalchemy import (
    String, Integer, Text, DateTime, ForeignKey, Table, Column, Enum, Float, Boolean,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from crm.database import Base
import enum


class LeadStatus(str, enum.Enum):
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    WON = "won"
    LOST = "lost"


class ActivityType(str, enum.Enum):
    CALL = "call"
    EMAIL = "email"
    SMS = "sms"
    MEETING = "meeting"
    NOTE = "note"
    TASK = "task"


class ContactSource(str, enum.Enum):
    MANUAL = "manual"
    GMAIL = "gmail"
    PHONE = "phone"
    LINKEDIN = "linkedin"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    TWITTER = "twitter"
    WEBSITE = "website"
    REFERRAL = "referral"
    AI_ASSISTANT = "ai_assistant"


# Many-to-many: contacts <-> tags
contact_tags = Table(
    "contact_tags", Base.metadata,
    Column("contact_id", Integer, ForeignKey("contacts.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100), default="")
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    phone: Mapped[str | None] = mapped_column(String(30), index=True)
    company: Mapped[str | None] = mapped_column(String(200))
    title: Mapped[str | None] = mapped_column(String(200))
    source: Mapped[ContactSource] = mapped_column(
        Enum(ContactSource), default=ContactSource.MANUAL
    )
    status: Mapped[LeadStatus] = mapped_column(
        Enum(LeadStatus), default=LeadStatus.NEW
    )
    address: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(50))
    zip_code: Mapped[str | None] = mapped_column(String(10))
    notes: Mapped[str | None] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    # Social profiles
    linkedin_url: Mapped[str | None] = mapped_column(String(300))
    facebook_url: Mapped[str | None] = mapped_column(String(300))
    instagram_handle: Mapped[str | None] = mapped_column(String(100))
    twitter_handle: Mapped[str | None] = mapped_column(String(100))
    # External IDs for dedup
    gmail_contact_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    # Interest / real estate specific
    interest: Mapped[str | None] = mapped_column(Text)
    budget_min: Mapped[int | None] = mapped_column(Integer)
    budget_max: Mapped[int | None] = mapped_column(Integer)
    desired_beds: Mapped[int | None] = mapped_column(Integer)
    desired_area: Mapped[str | None] = mapped_column(String(200))
    # Timestamps
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_contacted_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    activities: Mapped[list["Activity"]] = relationship(back_populates="contact", cascade="all, delete-orphan")
    deals: Mapped[list["Deal"]] = relationship(back_populates="contact", cascade="all, delete-orphan")
    tags: Mapped[list["Tag"]] = relationship(secondary=contact_tags, back_populates="contacts")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class Deal(Base):
    __tablename__ = "deals"

    id: Mapped[int] = mapped_column(primary_key=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(300))
    value: Mapped[float | None] = mapped_column(Float)
    status: Mapped[LeadStatus] = mapped_column(Enum(LeadStatus), default=LeadStatus.NEW)
    property_address: Mapped[str | None] = mapped_column(Text)
    mls_id: Mapped[str | None] = mapped_column(String(50))
    notes: Mapped[str | None] = mapped_column(Text)
    expected_close_date: Mapped[datetime.date | None] = mapped_column()
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    contact: Mapped["Contact"] = relationship(back_populates="deals")
    activities: Mapped[list["Activity"]] = relationship(back_populates="deal", cascade="all, delete-orphan")


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"))
    deal_id: Mapped[int | None] = mapped_column(ForeignKey("deals.id", ondelete="SET NULL"))
    type: Mapped[ActivityType] = mapped_column(Enum(ActivityType))
    subject: Mapped[str] = mapped_column(String(300))
    body: Mapped[str | None] = mapped_column(Text)
    due_date: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    contact: Mapped["Contact"] = relationship(back_populates="activities")
    deal: Mapped["Deal"] = relationship(back_populates="activities")


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    color: Mapped[str] = mapped_column(String(7), default="#3b82f6")

    contacts: Mapped[list["Contact"]] = relationship(secondary=contact_tags, back_populates="tags")
