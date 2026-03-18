"""Browser task API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel
from crm.database import get_db
from browser.models import BrowserTask, TaskStatus

router = APIRouter(prefix="/api/browser", tags=["Browser Agent"])


class TaskCreate(BaseModel):
    description: str
    user_email: str | None = None
    caller_phone: str | None = None


class TaskReply(BaseModel):
    reply: str


@router.post("/tasks")
async def create_task(data: TaskCreate, db: AsyncSession = Depends(get_db)):
    """Create a new browser automation task."""
    task = BrowserTask(
        description=data.description,
        user_email=data.user_email,
        caller_phone=data.caller_phone,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return {
        "task_id": task.task_id,
        "short_id": task.short_id,
        "status": task.status.value,
        "description": task.description,
        "message": f"Task queued. Results will be emailed to {task.user_email}." if task.user_email else "Task queued.",
    }


@router.get("/tasks")
async def list_tasks(
    status: TaskStatus | None = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """List browser tasks."""
    stmt = select(BrowserTask).order_by(BrowserTask.created_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(BrowserTask.status == status)
    result = await db.execute(stmt)
    tasks = result.scalars().all()
    return [_task_to_dict(t) for t in tasks]


@router.get("/tasks/{task_id}")
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)):
    """Get a task by its UUID or short ID."""
    stmt = select(BrowserTask).where(
        (BrowserTask.task_id == task_id) | (BrowserTask.task_id.startswith(task_id))
    )
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Task not found")
    return _task_to_dict(task)


@router.post("/tasks/{task_id}/reply")
async def reply_to_task(task_id: str, data: TaskReply, db: AsyncSession = Depends(get_db)):
    """Manually reply to a task that's waiting for input (alternative to email)."""
    stmt = select(BrowserTask).where(
        (BrowserTask.task_id == task_id) | (BrowserTask.task_id.startswith(task_id))
    )
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Task not found")
    if task.status != TaskStatus.WAITING_FOR_INPUT:
        raise HTTPException(400, f"Task is not waiting for input (status: {task.status.value})")

    # Inject the reply into the conversation and set back to pending
    conversation = task.conversation or []
    conversation.append({
        "role": "user",
        "content": f"User replied: {data.reply}\n\nPlease continue with the task.",
    })
    await db.execute(
        update(BrowserTask)
        .where(BrowserTask.id == task.id)
        .values(
            status=TaskStatus.PENDING,
            conversation=conversation,
            question=None,
        )
    )
    await db.commit()
    return {"status": "resumed", "task_id": task.task_id}


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str, db: AsyncSession = Depends(get_db)):
    """Cancel a pending or running task."""
    stmt = select(BrowserTask).where(
        (BrowserTask.task_id == task_id) | (BrowserTask.task_id.startswith(task_id))
    )
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Task not found")
    await db.execute(
        update(BrowserTask)
        .where(BrowserTask.id == task.id)
        .values(status=TaskStatus.CANCELLED)
    )
    await db.commit()
    return {"status": "cancelled", "task_id": task.task_id}


def _task_to_dict(t: BrowserTask) -> dict:
    return {
        "task_id": t.task_id,
        "short_id": t.short_id,
        "status": t.status.value,
        "description": t.description,
        "user_email": t.user_email,
        "result_summary": t.result_summary,
        "question": t.question,
        "error_message": t.error_message,
        "screenshots": t.screenshots,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
    }
