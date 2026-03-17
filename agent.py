"""Claude-powered agent with MLS + CRM tool calls."""

import json
import anthropic
from config import get_settings
from prompts import SYSTEM_PROMPT
from tools import mls, close_crm

# Tool definitions for Claude
TOOLS = [
    {
        "name": "search_listings",
        "description": "Search active MLS listings by location, price, beds, baths, and property type.",
        "input_schema": {
            "type": "object",
            "properties": {
                "zip_code": {"type": "string", "description": "5-digit zip code"},
                "city": {"type": "string"},
                "state": {"type": "string", "description": "2-letter state code"},
                "min_price": {"type": "integer"},
                "max_price": {"type": "integer"},
                "beds": {"type": "integer", "description": "Minimum bedrooms"},
                "baths": {"type": "integer", "description": "Minimum bathrooms"},
                "property_type": {
                    "type": "string",
                    "enum": ["Single Family", "Condo", "Townhouse", "Multi-Family"],
                },
                "limit": {"type": "integer", "default": 5},
            },
        },
    },
    {
        "name": "get_listing_detail",
        "description": "Get full details for a single listing by its MLS ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "listing_id": {"type": "string", "description": "The MLS listing ID"},
            },
            "required": ["listing_id"],
        },
    },
    {
        "name": "get_market_stats",
        "description": "Get market statistics (median price, days on market, inventory) for a geographic area.",
        "input_schema": {
            "type": "object",
            "properties": {
                "zip_code": {"type": "string"},
                "city": {"type": "string"},
                "state": {"type": "string"},
            },
        },
    },
    {
        "name": "create_lead",
        "description": "Create a new lead in Close CRM with the caller's info.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "phone": {"type": "string"},
                "email": {"type": "string"},
                "interest": {"type": "string", "description": "What the caller is looking for"},
                "notes": {"type": "string", "description": "Call summary notes"},
            },
            "required": ["name", "phone"],
        },
    },
    {
        "name": "schedule_callback",
        "description": "Schedule a follow-up callback task in Close CRM.",
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_id": {"type": "string"},
                "due_date": {"type": "string", "description": "ISO date for callback"},
                "text": {"type": "string", "description": "Task description"},
            },
            "required": ["lead_id", "due_date"],
        },
    },
]

# Map tool names to handler functions
TOOL_HANDLERS = {
    "search_listings": mls.search_listings,
    "get_listing_detail": mls.get_listing_detail,
    "get_market_stats": mls.get_market_stats,
    "create_lead": close_crm.create_lead,
    "schedule_callback": close_crm.schedule_callback,
}


async def run_agent(user_message: str, conversation_history: list[dict]) -> tuple[str, list]:
    """Run the Claude agent with tool use. Returns (reply_text, tool_results)."""
    settings = get_settings()
    client = anthropic.AsyncAnthropic(
        api_key=settings.anthropic_api_key or "proxy",
        base_url=settings.claude_proxy_url,
    )

    conversation_history.append({"role": "user", "content": user_message})
    tool_results = []

    while True:
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=conversation_history,
        )

        # Collect text and tool use blocks
        text_parts = []
        tool_uses = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_uses.append(block)

        # Add assistant response to history
        conversation_history.append({"role": "assistant", "content": response.content})

        # If no tool calls, we're done
        if not tool_uses:
            reply = " ".join(text_parts)
            return reply, tool_results

        # Execute tool calls
        tool_result_blocks = []
        for tool_use in tool_uses:
            handler = TOOL_HANDLERS.get(tool_use.name)
            if handler:
                try:
                    result = await handler(**tool_use.input)
                    tool_results.append({"tool": tool_use.name, "result": result})
                    tool_result_blocks.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": json.dumps(result),
                    })
                except Exception as e:
                    tool_result_blocks.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": json.dumps({"error": str(e)}),
                        "is_error": True,
                    })

        conversation_history.append({"role": "user", "content": tool_result_blocks})
