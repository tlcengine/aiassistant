"""Claude-powered agent with MLS + CRM + Email + Property Portal tool calls."""

import json
import asyncio
import anthropic
from config import get_settings
from prompts import SYSTEM_PROMPT
from tools import mls, close_crm, sms
from tools.email_sender import send_email
from tools.market_report_email import send_market_report_email
from tools.crm_tools import lookup_contact_by_email, create_crm_contact

# Tool definitions for Claude
TOOLS = [
    {
        "name": "search_listings",
        "description": "Search MLS listings from CJMLS (Central Jersey) and FMLS by location, price, beds, baths, and property type. Returns recent closed sales by default.",
        "input_schema": {
            "type": "object",
            "properties": {
                "zip_code": {"type": "string", "description": "5-digit zip code"},
                "city": {"type": "string", "description": "City name (e.g., Edison, Princeton, Monroe)"},
                "state": {"type": "string", "description": "Full state name (e.g., New Jersey, Georgia)", "default": "New Jersey"},
                "min_price": {"type": "integer"},
                "max_price": {"type": "integer"},
                "beds": {"type": "integer", "description": "Minimum bedrooms"},
                "baths": {"type": "integer", "description": "Minimum bathrooms"},
                "property_type": {
                    "type": "string",
                    "enum": ["Residential", "Condo", "Townhouse", "Multi-Family"],
                },
                "status": {"type": "string", "default": "Closed", "description": "Listing status: Closed, Active, Pending"},
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
        "description": "Get market statistics for a city or zip code. Available metrics: MedianSalesPrice, AverageSalesPrice, NewListings, Inventory, PendingSales, ClosedSales, DaysOnMarket, MonthsSupplyOfInventory, PercentOfListPriceReceived, PricePerSquareFoot, TotalDollarVolume, AbsorptionRate, ListToSaleRatio.",
        "input_schema": {
            "type": "object",
            "properties": {
                "zip_code": {"type": "string"},
                "city": {"type": "string", "description": "City name (e.g., Edison, Princeton, Monroe)"},
                "state": {"type": "string", "default": "New Jersey"},
                "metric": {"type": "string", "default": "MedianSalesPrice", "description": "Which metric to retrieve"},
            },
        },
    },
    {
        "name": "get_market_report",
        "description": "Get a comprehensive market report with all KPIs for a city — includes median price, inventory, DOM, absorption rate, narrative, and trends.",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"},
                "state": {"type": "string", "default": "New Jersey"},
            },
            "required": ["city"],
        },
    },
    {
        "name": "get_fast_stats",
        "description": "Quick all-13-metrics snapshot for an area — faster than full market report.",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string"},
                "zip_code": {"type": "string"},
                "state": {"type": "string", "default": "New Jersey"},
            },
        },
    },
    {
        "name": "get_tax_data",
        "description": "Look up property tax assessment data by address, or get a summary for a county/municipality. Covers 12.7M NJ property records.",
        "input_schema": {
            "type": "object",
            "properties": {
                "address": {"type": "string", "description": "Street address to search"},
                "county": {"type": "string", "description": "NJ county name (e.g., Middlesex, Essex)"},
                "municipality": {"type": "string", "description": "Municipality name (e.g., Edison, Newark)"},
            },
        },
    },
    {
        "name": "get_forecast",
        "description": "Get a price forecast with confidence bands for a city or zip code.",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string"},
                "zip_code": {"type": "string"},
                "state": {"type": "string", "default": "New Jersey"},
                "forecast_months": {"type": "integer", "default": 12, "description": "Months to forecast (3-24)"},
            },
        },
    },
    {
        "name": "predict_tax",
        "description": "Predict property tax for a property based on comparable properties in the area.",
        "input_schema": {
            "type": "object",
            "properties": {
                "county": {"type": "string", "description": "NJ county"},
                "municipality": {"type": "string", "description": "Municipality name"},
                "current_value": {"type": "integer", "description": "Current property value estimate"},
                "bedrooms": {"type": "integer", "default": 3},
                "sqft": {"type": "integer", "default": 1500},
                "year_built": {"type": "integer", "default": 1990},
                "lot_size": {"type": "integer", "default": 5000, "description": "Lot size in sqft"},
            },
            "required": ["county", "municipality"],
        },
    },
    {
        "name": "send_email",
        "description": "Send an email to a recipient. Use this to send property links, market reports, or follow-up messages. Emails come from claude@certihomes.com with reply-to krishna@certihomes.com.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string", "description": "Email subject line"},
                "html_body": {"type": "string", "description": "HTML email body content"},
                "plain_body": {"type": "string", "description": "Plain text fallback (optional)"},
                "cc": {"type": "string", "description": "CC recipients (comma-separated, optional)"},
            },
            "required": ["to", "subject", "html_body"],
        },
    },
    {
        "name": "send_market_report_email",
        "description": "Send a beautiful HTML market report email for a city. Fetches live data from CJMLS and generates a professional report with KPIs, narrative analysis, and links to the interactive report and podcast. Use this when someone asks to email or send a market report.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to_email": {"type": "string", "description": "Recipient email address"},
                "city": {"type": "string", "description": "City name (e.g., Edison, Princeton, Monroe)"},
                "state": {"type": "string", "default": "New Jersey"},
            },
            "required": ["to_email", "city"],
        },
    },
    {
        "name": "send_sms",
        "description": "Send an SMS text message to a phone number via Twilio.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Phone number in +1XXXXXXXXXX format"},
                "body": {"type": "string", "description": "The SMS message text"},
            },
            "required": ["to", "body"],
        },
    },
    {
        "name": "send_market_report_link",
        "description": "Send a market report URL for a city via SMS or email. For rich HTML reports, prefer send_market_report_email instead.",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"},
                "to_phone": {"type": "string", "description": "Phone number to send SMS to (optional)"},
                "to_email": {"type": "string", "description": "Email address to send report to (optional)"},
            },
            "required": ["city"],
        },
    },
    {
        "name": "search_portal_listings",
        "description": "Search the CJMLS property portal (nextjs.tlcengine.com / krishnam.tlcengine.com) for active listings with autocomplete. Use when a user asks about a specific address or wants to check if a property is still available.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search text — address, city, zip, MLS number"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "lookup_contact_by_email",
        "description": "Check if an email address already exists in the CRM. Use this AFTER sending an email to determine if you need to collect the person's name and phone to add them as a new contact.",
        "input_schema": {
            "type": "object",
            "properties": {
                "email": {"type": "string", "description": "Email address to look up"},
            },
            "required": ["email"],
        },
    },
    {
        "name": "create_crm_contact",
        "description": "Add a new contact to the CRM. Use this when lookup_contact_by_email returns not found, after asking the caller for their name and optionally their cell number.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Full name (e.g., John Smith)"},
                "email": {"type": "string", "description": "Email address"},
                "phone": {"type": "string", "description": "Cell phone number (optional)"},
                "interest": {"type": "string", "description": "What they're looking for"},
                "notes": {"type": "string", "description": "Call summary notes"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "create_lead",
        "description": "Create a new lead in Close CRM (external) with the caller's info.",
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


async def _send_market_report_link(city: str, to_phone: str | None = None, to_email: str | None = None) -> dict:
    """Generate a market report URL and optionally send via SMS or email."""
    city_slug = city.lower().replace(" ", "-")
    report_url = f"https://marketstats.certihomes.com/report?city={city_slug}&state=new-jersey"
    result = {"city": city, "report_url": report_url}

    if to_email:
        # Send rich HTML email
        email_result = await send_market_report_email(to_email, city)
        result.update(email_result)

    if to_phone:
        msg = f"Here's the latest market report for {city}, NJ: {report_url}"
        sid = sms.send_sms(to=to_phone, body=msg)
        result["sms_sent"] = True
        result["sms_sid"] = sid

    return result


def _send_sms_tool(to: str, body: str) -> dict:
    """Wrapper for SMS tool."""
    sid = sms.send_sms(to=to, body=body)
    return {"sent": True, "sid": sid}


def _send_email_tool(to: str, subject: str, html_body: str, plain_body: str | None = None, cc: str | None = None) -> dict:
    """Wrapper for email tool."""
    return send_email(to=to, subject=subject, html_body=html_body, plain_body=plain_body, cc=cc)


async def _search_portal_listings(query: str) -> dict:
    """Search the TLCengine CJMLS portal for listings by address/city/zip."""
    import httpx
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Use the suggest/autocomplete endpoint
            resp = await client.get(
                f"{settings.tlcengine_api_url}/suggest/get",
                params={
                    "text": query,
                    "mlsnumber": 1,
                    "streetaddress": 1,
                    "city": 1,
                    "zipcode": 1,
                    "county": 1,
                },
            )
            resp.raise_for_status()
            suggestions = resp.json()

            # Build property URLs for any matching listings
            results = []
            for item in suggestions[:5] if isinstance(suggestions, list) else []:
                listing_id = item.get("ListingId") or item.get("id", "")
                address = item.get("StreetAddress") or item.get("address", "")
                city = item.get("City") or item.get("city", "")
                state = item.get("State") or "NJ"
                zip_code = item.get("ZipCode") or item.get("zip", "")

                # Build portal URL
                addr_slug = address.replace(" ", "-")
                city_slug = city.replace(" ", "-")
                portal_url = f"https://krishnam.tlcengine.com/propertydetail/{listing_id}/{addr_slug}_{city_slug}_{state}_{zip_code}" if listing_id else ""

                results.append({
                    "listing_id": listing_id,
                    "address": address,
                    "city": city,
                    "state": state,
                    "zip": zip_code,
                    "portal_url": portal_url,
                    "raw": item,
                })

            return {"query": query, "results": results, "total": len(results)}
    except Exception as e:
        # Fall back to MarketStats search
        return {"query": query, "results": [], "error": str(e), "fallback": "Use search_listings tool instead"}


# Map tool names to handler functions
TOOL_HANDLERS = {
    "search_listings": mls.search_listings,
    "get_listing_detail": mls.get_listing_detail,
    "get_market_stats": mls.get_market_stats,
    "get_market_report": mls.get_market_report,
    "get_fast_stats": mls.get_fast_stats,
    "get_tax_data": mls.get_tax_data,
    "get_forecast": mls.get_forecast,
    "predict_tax": mls.predict_tax,
    "send_sms": _send_sms_tool,
    "send_email": _send_email_tool,
    "send_market_report_email": send_market_report_email,
    "send_market_report_link": _send_market_report_link,
    "search_portal_listings": _search_portal_listings,
    "lookup_contact_by_email": lookup_contact_by_email,
    "create_crm_contact": create_crm_contact,
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
            model="gemini-3-flash",
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
                    result = await handler(**tool_use.input) if asyncio.iscoroutinefunction(handler) else handler(**tool_use.input)
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
