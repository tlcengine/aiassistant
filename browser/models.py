"""BrowserTask model — async task queue for browser agent jobs."""

import datetime
import enum
import uuid
from sqlalchemy import String, Text, DateTime, Enum, func, JSON
from sqlalchemy.orm import Mapped, mapped_column
from crm.database import Base


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_FOR_INPUT = "waiting_for_input"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


def _new_uuid() -> str:
    return str(uuid.uuid4())


class BrowserTask(Base):
    __tablename__ = "browser_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[str] = mapped_column(String(36), unique=True, default=_new_uuid)
    user_email: Mapped[str | None] = mapped_column(String(255))
    caller_phone: Mapped[str | None] = mapped_column(String(30))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.PENDING
    )
    result_summary: Mapped[str | None] = mapped_column(Text)
    result_html: Mapped[str | None] = mapped_column(Text)
    screenshots: Mapped[dict | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    conversation: Mapped[dict | None] = mapped_column(JSON)
    question: Mapped[str | None] = mapped_column(Text)
    email_thread_id: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def short_id(self) -> str:
        return self.task_id[:8]

    @property
    def email_subject_tag(self) -> str:
        return f"[TASK-{self.short_id}]"
