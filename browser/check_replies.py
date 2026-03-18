#!/usr/bin/env python3
"""Cron script — checks claude@certihomes.com inbox for replies to browser task emails.

Runs every 2 minutes via crontab:
  */2 * * * * /home/krish/anaconda3/bin/python /home/krish/aiassistant/browser/check_replies.py

Matches emails by subject line pattern [TASK-xxxxxxxx].
"""

import asyncio
import base64
import email
import logging
import os
import re
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select, update
from crm.database import async_session
from browser.models import BrowserTask, TaskStatus

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Pattern to match [TASK-xxxxxxxx] in subject
TASK_PATTERN = re.compile(r"\[TASK-([a-f0-9]{8})\]", re.IGNORECASE)


def get_gmail_service():
    """Get Gmail API service using stored credentials."""
    from crm.gmail_import import get_credentials
    from googleapiclient.discovery import build

    creds = get_credentials()
    if not creds:
        logger.warning("No Gmail credentials — skipping reply check")
        return None
    return build("gmail", "v1", credentials=creds)


def extract_reply_text(payload: dict) -> str:
    """Extract the reply text from a Gmail message payload."""
    parts = payload.get("parts", [])
    body_data = payload.get("body", {}).get("data", "")

    # Try to get plain text part
    for part in parts:
        if part.get("mimeType") == "text/plain":
            data = part.get("body", {}).get("data", "")
            if data:
                text = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                # Strip quoted reply (everything after "On ... wrote:" or "> " lines)
                lines = text.split("\n")
                reply_lines = []
                for line in lines:
                    if re.match(r"^On .+ wrote:$", line.strip()):
                        break
                    if line.strip().startswith(">"):
                        break
                    reply_lines.append(line)
                return "\n".join(reply_lines).strip()

    # Fallback to body data
    if body_data:
        return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace").strip()

    return ""


async def process_replies():
    """Check Gmail for replies to task emails and resume tasks."""
    service = get_gmail_service()
    if not service:
        return

    try:
        # Search for unread emails with TASK- in subject
        results = service.users().messages().list(
            userId="me",
            q='subject:"[TASK-" is:unread to:claude@certihomes.com',
            maxResults=10,
        ).execute()

        messages = results.get("messages", [])
        if not messages:
            logger.info("No task reply emails found")
            return

        logger.info(f"Found {len(messages)} potential task replies")

        for msg_info in messages:
            msg = service.users().messages().get(
                userId="me", id=msg_info["id"], format="full"
            ).execute()

            # Extract subject
            headers = msg.get("payload", {}).get("headers", [])
            subject = ""
            from_addr = ""
            for h in headers:
                if h["name"].lower() == "subject":
                    subject = h["value"]
                if h["name"].lower() == "from":
                    from_addr = h["value"]

            # Match task ID from subject
            match = TASK_PATTERN.search(subject)
            if not match:
                logger.warning(f"No task ID in subject: {subject}")
                continue

            short_id = match.group(1)
            logger.info(f"Processing reply for task {short_id} from {from_addr}")

            # Extract reply text
            reply_text = extract_reply_text(msg.get("payload", {}))
            if not reply_text:
                logger.warning(f"Empty reply for task {short_id}")
                continue

            logger.info(f"Reply text: {reply_text[:200]}")

            # Find the task in DB
            async with async_session() as db:
                stmt = select(BrowserTask).where(
                    BrowserTask.task_id.startswith(short_id)
                )
                result = await db.execute(stmt)
                task = result.scalar_one_or_none()

                if not task:
                    logger.warning(f"Task {short_id} not found in DB")
                    continue

                if task.status != TaskStatus.WAITING_FOR_INPUT:
                    logger.info(f"Task {short_id} is {task.status.value}, not waiting — skipping")
                    continue

                # Inject reply into conversation and set to pending
                conversation = task.conversation or []
                conversation.append({
                    "role": "user",
                    "content": f"User replied: {reply_text}\n\nPlease continue with the task.",
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
                logger.info(f"Task {short_id} resumed with user reply")

            # Mark email as read
            service.users().messages().modify(
                userId="me",
                id=msg_info["id"],
                body={"removeLabelIds": ["UNREAD"]},
            ).execute()
            logger.info(f"Marked email {msg_info['id']} as read")

    except Exception as e:
        logger.exception(f"Error checking replies: {e}")


if __name__ == "__main__":
    asyncio.run(process_replies())
