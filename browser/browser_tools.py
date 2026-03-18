"""Browser tool definitions and handlers for the LLM agent."""

import base64
import logging
import os
import uuid
from pathlib import Path
from playwright.async_api import Page

logger = logging.getLogger(__name__)

SCREENSHOT_DIR = Path("/home/krish/aiassistant/static/screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

# Tool schemas for Claude/Gemini
BROWSER_TOOLS = [
    {
        "name": "navigate",
        "description": "Navigate to a URL in the browser.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The full URL to navigate to"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "click",
        "description": "Click an element on the page. Use CSS selector, text content, or role selector.",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector, text='Button Text', or role=button[name='Submit']",
                },
            },
            "required": ["selector"],
        },
    },
    {
        "name": "fill",
        "description": "Fill a form field with text. Clears existing value first.",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector for the input field"},
                "value": {"type": "string", "description": "Text to type into the field"},
            },
            "required": ["selector", "value"],
        },
    },
    {
        "name": "select_option",
        "description": "Select an option from a dropdown/select element.",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector for the select element"},
                "value": {"type": "string", "description": "Option value or label to select"},
            },
            "required": ["selector", "value"],
        },
    },
    {
        "name": "press_key",
        "description": "Press a keyboard key (Enter, Tab, Escape, ArrowDown, etc.).",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Key name: Enter, Tab, Escape, ArrowDown, etc."},
            },
            "required": ["key"],
        },
    },
    {
        "name": "scroll",
        "description": "Scroll the page up or down.",
        "input_schema": {
            "type": "object",
            "properties": {
                "direction": {"type": "string", "enum": ["up", "down"], "default": "down"},
                "amount": {"type": "integer", "description": "Pixels to scroll", "default": 500},
            },
        },
    },
    {
        "name": "screenshot",
        "description": "Take a screenshot of the current page. Returns the image so you can see what's on screen.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "read_page_text",
        "description": "Extract all visible text from the current page. Use when you need to read content without a screenshot.",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "Optional CSS selector to read text from a specific element. Omit for full page.",
                },
            },
        },
    },
    {
        "name": "search_google",
        "description": "Search Google for a query. Shortcut that navigates to Google and performs the search.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "wait",
        "description": "Wait for a specified number of seconds (for dynamic content to load).",
        "input_schema": {
            "type": "object",
            "properties": {
                "seconds": {"type": "number", "description": "Seconds to wait", "default": 2},
            },
        },
    },
    {
        "name": "done",
        "description": "Signal that the task is complete. Provide a summary of what was accomplished.",
        "input_schema": {
            "type": "object",
            "properties": {
                "result_summary": {"type": "string", "description": "Summary of what was accomplished"},
            },
            "required": ["result_summary"],
        },
    },
    {
        "name": "need_info",
        "description": "Signal that you need more information from the user to continue. The task will pause and the user will be emailed with your question.",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The specific question to ask the user"},
            },
            "required": ["question"],
        },
    },
]


async def take_screenshot(page: Page) -> tuple[str, str]:
    """Take a screenshot, save to disk, return (base64_data, public_url)."""
    filename = f"{uuid.uuid4().hex[:12]}.png"
    filepath = SCREENSHOT_DIR / filename
    screenshot_bytes = await page.screenshot(type="png")
    filepath.write_bytes(screenshot_bytes)
    b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
    public_url = f"https://aiassistant.certihomes.com/screenshots/{filename}"
    return b64, public_url


async def execute_browser_tool(page: Page, tool_name: str, tool_input: dict) -> dict:
    """Execute a browser tool and return the result."""
    try:
        if tool_name == "navigate":
            await page.goto(tool_input["url"], wait_until="domcontentloaded", timeout=30000)
            return {"status": "ok", "url": page.url, "title": await page.title()}

        elif tool_name == "click":
            selector = tool_input["selector"]
            # Try text selector first if it looks like plain text
            if not any(c in selector for c in [".", "#", "[", ">", ":"]):
                try:
                    await page.get_by_text(selector, exact=False).first.click(timeout=5000)
                    return {"status": "clicked", "selector": selector}
                except Exception:
                    pass
            await page.click(selector, timeout=10000)
            return {"status": "clicked", "selector": selector}

        elif tool_name == "fill":
            await page.fill(tool_input["selector"], tool_input["value"], timeout=10000)
            return {"status": "filled", "selector": tool_input["selector"]}

        elif tool_name == "select_option":
            await page.select_option(
                tool_input["selector"], label=tool_input["value"], timeout=10000
            )
            return {"status": "selected", "value": tool_input["value"]}

        elif tool_name == "press_key":
            await page.keyboard.press(tool_input["key"])
            return {"status": "pressed", "key": tool_input["key"]}

        elif tool_name == "scroll":
            direction = tool_input.get("direction", "down")
            amount = tool_input.get("amount", 500)
            delta = amount if direction == "down" else -amount
            await page.mouse.wheel(0, delta)
            return {"status": "scrolled", "direction": direction, "amount": amount}

        elif tool_name == "screenshot":
            b64, url = await take_screenshot(page)
            return {"status": "ok", "screenshot_url": url, "_screenshot_b64": b64}

        elif tool_name == "read_page_text":
            selector = tool_input.get("selector")
            if selector:
                el = page.locator(selector).first
                text = await el.inner_text(timeout=5000)
            else:
                text = await page.inner_text("body", timeout=10000)
            # Truncate to avoid blowing up context
            if len(text) > 8000:
                text = text[:8000] + "\n... [truncated]"
            return {"status": "ok", "text": text}

        elif tool_name == "search_google":
            await page.goto(
                f"https://www.google.com/search?q={tool_input['query']}",
                wait_until="domcontentloaded",
                timeout=15000,
            )
            return {"status": "ok", "query": tool_input["query"], "url": page.url}

        elif tool_name == "wait":
            seconds = tool_input.get("seconds", 2)
            await page.wait_for_timeout(min(seconds, 10) * 1000)
            return {"status": "ok", "waited": seconds}

        elif tool_name == "done":
            return {"status": "done", "result_summary": tool_input["result_summary"]}

        elif tool_name == "need_info":
            return {"status": "need_info", "question": tool_input["question"]}

        else:
            return {"error": f"Unknown tool: {tool_name}"}

    except Exception as e:
        logger.warning(f"Browser tool {tool_name} error: {e}")
        return {"error": str(e)}
