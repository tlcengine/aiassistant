"""Browser agent — LLM-driven browser automation loop."""

import json
import logging
import anthropic
from config import get_settings
from browser.prompts import BROWSER_AGENT_PROMPT
from browser.browser_tools import BROWSER_TOOLS, execute_browser_tool, take_screenshot
from playwright.async_api import Page

logger = logging.getLogger(__name__)

# Max iterations to prevent runaway loops
MAX_ITERATIONS = 30


async def run_browser_agent(
    page: Page,
    task_description: str,
    conversation_history: list[dict] | None = None,
    user_reply: str | None = None,
) -> tuple[str, str, list[str], list[dict]]:
    """Run the browser agent loop.

    Args:
        page: Playwright page to control
        task_description: What the user wants done
        conversation_history: Previous conversation (for resume after need_info)
        user_reply: User's reply to a need_info question

    Returns:
        (status, result_text, screenshot_urls, conversation_history)
        status is one of: "done", "need_info", "error", "max_iterations"
    """
    settings = get_settings()
    client = anthropic.AsyncAnthropic(
        api_key=settings.anthropic_api_key or "proxy",
        base_url=settings.claude_proxy_url,
    )

    screenshot_urls: list[str] = []

    # Build or resume conversation
    if conversation_history is None:
        conversation_history = []
        conversation_history.append({
            "role": "user",
            "content": f"Task: {task_description}\n\nThe browser is open on a blank page. Start by navigating to the appropriate website or searching Google. Take a screenshot after your first action to see the page.",
        })
    elif user_reply:
        # Resume after need_info — add user reply
        conversation_history.append({
            "role": "user",
            "content": f"User replied: {user_reply}\n\nPlease continue with the task.",
        })

    for iteration in range(MAX_ITERATIONS):
        try:
            response = await client.messages.create(
                model="gemini-3-flash",
                max_tokens=2048,
                system=BROWSER_AGENT_PROMPT,
                tools=BROWSER_TOOLS,
                messages=conversation_history,
            )
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return "error", f"LLM error: {e}", screenshot_urls, conversation_history

        # Collect response blocks
        text_parts = []
        tool_uses = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_uses.append(block)

        # Serialize response content to plain dicts (Anthropic SDK returns objects)
        serialized_content = []
        for block in response.content:
            if block.type == "text":
                serialized_content.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                serialized_content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
        conversation_history.append({"role": "assistant", "content": serialized_content})

        # No tool calls — agent is done or confused
        if not tool_uses:
            return "done", " ".join(text_parts), screenshot_urls, conversation_history

        # Execute each tool call
        tool_result_blocks = []
        final_status = None
        final_text = ""

        for tool_use in tool_uses:
            result = await execute_browser_tool(page, tool_use.name, tool_use.input)

            # Check for terminal states
            if result.get("status") == "done":
                final_status = "done"
                final_text = result.get("result_summary", "Task completed.")
            elif result.get("status") == "need_info":
                final_status = "need_info"
                final_text = result.get("question", "I need more information.")

            # Build tool result
            b64 = result.pop("_screenshot_b64", None)
            if b64:
                screenshot_urls.append(result.get("screenshot_url", ""))
                # Also read page text so agent can "see" what's on screen
                try:
                    page_text = await page.inner_text("body", timeout=5000)
                    if len(page_text) > 4000:
                        page_text = page_text[:4000] + "\n... [truncated]"
                    result["page_text"] = page_text
                except Exception:
                    pass

            tool_result_blocks.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": json.dumps(result),
            })

        conversation_history.append({"role": "user", "content": tool_result_blocks})

        # If we hit a terminal state, return
        if final_status:
            return final_status, final_text, screenshot_urls, conversation_history

        # No auto-screenshot injection — agent should explicitly call screenshot when needed

    return "max_iterations", "Reached maximum steps without completing the task.", screenshot_urls, conversation_history
