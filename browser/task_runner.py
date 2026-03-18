"""Background task runner — picks up pending browser tasks and runs them."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from sqlalchemy import select, update
from crm.database import async_session
from browser.models import BrowserTask, TaskStatus
from browser.browser_pool import create_context, close_context
from browser.browser_agent import run_browser_agent
from tools.email_sender import send_email

logger = logging.getLogger(__name__)

POLL_INTERVAL = 5  # seconds


def _build_result_email(task: BrowserTask, screenshot_urls: list[str]) -> str:
    """Build HTML email with task results and screenshots."""
    screenshots_html = ""
    for i, url in enumerate(screenshot_urls[-3:]):  # Last 3 screenshots
        screenshots_html += f'<img src="{url}" style="max-width:100%;border:1px solid #ddd;border-radius:8px;margin:8px 0;" /><br/>'

    return f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
        <div style="background:#0f172a;padding:20px;border-radius:12px 12px 0 0;text-align:center;">
            <img src="https://aiassistant.certihomes.com/images/certihomes-logo-email.png" style="height:60px;" />
        </div>
        <div style="background:#1e293b;padding:24px;border-radius:0 0 12px 12px;color:#e2e8f0;">
            <h2 style="color:#38bdf8;margin-top:0;">Task Completed</h2>
            <p style="color:#94a3b8;font-size:14px;"><strong>Task:</strong> {task.description}</p>
            <div style="background:#0f172a;border-radius:8px;padding:16px;margin:16px 0;">
                <p style="color:#e2e8f0;font-size:15px;line-height:1.6;">{task.result_summary or 'Task completed.'}</p>
            </div>
            {f'<h3 style="color:#94a3b8;">Screenshots</h3>{screenshots_html}' if screenshots_html else ''}
            <hr style="border-color:#334155;margin:20px 0;" />
            <p style="color:#64748b;font-size:12px;">
                Task ID: {task.short_id} |
                Reply to this email if you have follow-up questions.
            </p>
        </div>
    </div>
    """


def _build_question_email(task: BrowserTask, screenshot_urls: list[str]) -> str:
    """Build HTML email asking user for more info."""
    last_screenshot = ""
    if screenshot_urls:
        last_screenshot = f'<img src="{screenshot_urls[-1]}" style="max-width:100%;border:1px solid #ddd;border-radius:8px;margin:8px 0;" />'

    return f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
        <div style="background:#0f172a;padding:20px;border-radius:12px 12px 0 0;text-align:center;">
            <img src="https://aiassistant.certihomes.com/images/certihomes-logo-email.png" style="height:60px;" />
        </div>
        <div style="background:#1e293b;padding:24px;border-radius:0 0 12px 12px;color:#e2e8f0;">
            <h2 style="color:#fbbf24;margin-top:0;">I Need Your Help</h2>
            <p style="color:#94a3b8;font-size:14px;"><strong>Task:</strong> {task.description}</p>
            <div style="background:#0f172a;border-radius:8px;padding:16px;margin:16px 0;">
                <p style="color:#e2e8f0;font-size:16px;line-height:1.6;"><strong>{task.question}</strong></p>
            </div>
            {f'<p style="color:#94a3b8;">Here is what I see right now:</p>{last_screenshot}' if last_screenshot else ''}
            <div style="background:#1a3330;border:1px solid #22c55e;border-radius:8px;padding:16px;margin:16px 0;">
                <p style="color:#22c55e;font-size:14px;margin:0;">
                    <strong>Just reply to this email with your answer</strong> and I'll continue working on the task.
                </p>
            </div>
            <hr style="border-color:#334155;margin:20px 0;" />
            <p style="color:#64748b;font-size:12px;">Task ID: {task.short_id}</p>
        </div>
    </div>
    """


async def _run_single_task(task: BrowserTask):
    """Execute one browser task."""
    logger.info(f"Running browser task {task.short_id}: {task.description[:80]}")

    # Update status to running
    async with async_session() as db:
        await db.execute(
            update(BrowserTask)
            .where(BrowserTask.id == task.id)
            .values(status=TaskStatus.RUNNING)
        )
        await db.commit()

    ctx = None
    try:
        ctx = await create_context()
        page = await ctx.new_page()
        await page.goto("about:blank")

        # Resume or start fresh
        conversation = task.conversation if task.conversation else None
        user_reply = None
        if task.status == TaskStatus.WAITING_FOR_INPUT and task.conversation:
            # This is a resumed task — look for the user's reply in description
            # (check_replies.py appends the reply to conversation)
            conversation = task.conversation
            # The reply is injected by check_replies as extra context
            user_reply = task.question  # Will be overridden by check_replies

        status, result_text, screenshot_urls, conversation_history = await run_browser_agent(
            page=page,
            task_description=task.description,
            conversation_history=conversation,
            user_reply=user_reply if task.conversation else None,
        )

        # Serialize conversation (strip base64 images to save space)
        clean_history = _strip_images_from_history(conversation_history)

        # Update task in DB
        async with async_session() as db:
            values = {
                "conversation": clean_history,
                "screenshots": screenshot_urls,
                "updated_at": datetime.now(timezone.utc),
            }

            if status == "done":
                values["status"] = TaskStatus.COMPLETED
                values["result_summary"] = result_text
                values["completed_at"] = datetime.now(timezone.utc)
                # Send result email
                if task.user_email:
                    html = _build_result_email(task, screenshot_urls)
                    task.result_summary = result_text  # for the template
                    send_email(
                        to=task.user_email,
                        subject=f"{task.email_subject_tag} Completed: {task.description[:50]}",
                        html_body=_build_result_email(
                            type("T", (), {"description": task.description, "result_summary": result_text, "short_id": task.short_id})(),
                            screenshot_urls,
                        ),
                    )
                logger.info(f"Task {task.short_id} completed: {result_text[:100]}")

            elif status == "need_info":
                values["status"] = TaskStatus.WAITING_FOR_INPUT
                values["question"] = result_text
                # Send question email
                if task.user_email:
                    send_email(
                        to=task.user_email,
                        subject=f"{task.email_subject_tag} Question about: {task.description[:50]}",
                        html_body=_build_question_email(
                            type("T", (), {"description": task.description, "question": result_text, "short_id": task.short_id})(),
                            screenshot_urls,
                        ),
                    )
                logger.info(f"Task {task.short_id} needs info: {result_text[:100]}")

            else:  # error or max_iterations
                values["status"] = TaskStatus.FAILED
                values["error_message"] = result_text
                if task.user_email:
                    send_email(
                        to=task.user_email,
                        subject=f"{task.email_subject_tag} Could not complete: {task.description[:50]}",
                        html_body=f"<p>Sorry, I wasn't able to complete your task: <strong>{task.description}</strong></p><p>Error: {result_text}</p>",
                    )
                logger.warning(f"Task {task.short_id} failed: {result_text[:100]}")

            await db.execute(
                update(BrowserTask)
                .where(BrowserTask.id == task.id)
                .values(**values)
            )
            await db.commit()

    except Exception as e:
        logger.exception(f"Task {task.short_id} crashed: {e}")
        async with async_session() as db:
            await db.execute(
                update(BrowserTask)
                .where(BrowserTask.id == task.id)
                .values(status=TaskStatus.FAILED, error_message=str(e))
            )
            await db.commit()
    finally:
        if ctx:
            await close_context(ctx)


def _strip_images_from_history(history: list) -> list:
    """Remove base64 image data from conversation to save DB space."""
    clean = []
    for msg in history:
        if isinstance(msg.get("content"), list):
            clean_content = []
            for block in msg["content"]:
                if isinstance(block, dict) and block.get("type") == "image":
                    clean_content.append({"type": "text", "text": "[screenshot taken]"})
                elif isinstance(block, dict) and block.get("source", {}).get("type") == "base64":
                    clean_content.append({"type": "text", "text": "[screenshot taken]"})
                else:
                    # Strip nested images in tool results
                    if isinstance(block, dict) and isinstance(block.get("content"), list):
                        stripped = [
                            b for b in block["content"]
                            if not (isinstance(b, dict) and b.get("type") == "image")
                        ]
                        block = {**block, "content": stripped}
                    clean_content.append(block)
            clean.append({**msg, "content": clean_content})
        else:
            clean.append(msg)
    return clean


async def run_forever():
    """Background loop that polls for pending tasks."""
    logger.info("Browser task runner started")
    while True:
        try:
            async with async_session() as db:
                stmt = (
                    select(BrowserTask)
                    .where(BrowserTask.status == TaskStatus.PENDING)
                    .order_by(BrowserTask.created_at.asc())
                    .limit(1)
                )
                result = await db.execute(stmt)
                task = result.scalar_one_or_none()

            if task:
                await _run_single_task(task)
            else:
                await asyncio.sleep(POLL_INTERVAL)

        except Exception as e:
            logger.exception(f"Task runner error: {e}")
            await asyncio.sleep(POLL_INTERVAL)
