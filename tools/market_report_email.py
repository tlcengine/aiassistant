"""Generate beautiful HTML market report emails for cities."""

import httpx

MARKETSTATS_API = "http://127.0.0.1:8000/api"


async def fetch_report_data(city: str, state: str = "New Jersey") -> dict:
    """Fetch market report data from MarketStats API."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{MARKETSTATS_API}/report/",
            params={"city": city, "state": state},
        )
        resp.raise_for_status()
        return resp.json()


def _direction_arrow(direction: str) -> str:
    if direction == "up":
        return "▲"
    elif direction == "down":
        return "▼"
    return "—"


def _direction_color(direction: str) -> str:
    if direction == "up":
        return "#22c55e"
    elif direction == "down":
        return "#ef4444"
    return "#6b7280"


def build_market_report_html(data: dict) -> str:
    """Build a beautiful HTML email from market report data."""
    city = data.get("city", "")
    state = data.get("state", "New Jersey")
    headline = data.get("headline", f"Market Report for {city}")
    narrative = data.get("narrative", {})
    kpis = data.get("kpis", [])
    report_date = data.get("report_date", "")
    mls_label = data.get("mls_label", "CJMLS")

    city_slug = city.lower().replace(" ", "-")
    state_slug = state.lower().replace(" ", "-")
    report_url = f"https://marketstats.certihomes.com/report?city={city_slug}&state={state_slug}"
    podcast_url = f"https://marketstats.certihomes.com/podcast?city={city_slug}&state={state_slug}"

    # Build KPI cards
    kpi_cards_html = ""
    for kpi in kpis[:8]:
        label = kpi.get("label", "")
        value = kpi.get("value", "N/A")
        change = kpi.get("change", "")
        direction = kpi.get("direction", "flat")
        arrow = _direction_arrow(direction)
        color = _direction_color(direction)
        change_html = f'<span style="color:{color};font-size:12px;">{arrow} {change}</span>' if change else ""

        kpi_cards_html += f"""
        <td style="padding:8px;text-align:center;background:#f8fafc;border-radius:8px;border:1px solid #e2e8f0;width:25%;">
            <div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;">{label}</div>
            <div style="font-size:22px;font-weight:700;color:#1e293b;margin:4px 0;">{value}</div>
            {change_html}
        </td>
        """

    # Arrange KPIs in 2 rows of 4
    kpi_rows = ""
    kpi_list = kpis[:8]
    for i in range(0, len(kpi_list), 4):
        row_items = kpi_list[i:i+4]
        cells = ""
        for kpi in row_items:
            label = kpi.get("label", "")
            value = kpi.get("value", "N/A")
            change = kpi.get("change", "")
            direction = kpi.get("direction", "flat")
            arrow = _direction_arrow(direction)
            color = _direction_color(direction)
            change_html = f'<span style="color:{color};font-size:12px;">{arrow} {change}</span>' if change else ""
            cells += f"""
            <td style="padding:10px;text-align:center;background:#f8fafc;border-radius:8px;border:1px solid #e2e8f0;width:25%;">
                <div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;">{label}</div>
                <div style="font-size:20px;font-weight:700;color:#1e293b;margin:4px 0;">{value}</div>
                {change_html}
            </td>
            """
        kpi_rows += f'<tr>{cells}</tr><tr><td colspan="4" style="height:8px;"></td></tr>'

    # Narrative sections
    opening = narrative.get("opening", "")
    supply = narrative.get("supply", "")
    demand = narrative.get("demand", "")
    pull_quote = narrative.get("pull_quote", "")
    recommendations = narrative.get("recommendations", "")
    closing = narrative.get("closing", "")

    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f1f5f9;padding:20px 0;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 6px rgba(0,0,0,0.05);">

<!-- Header -->
<tr>
<td style="background:linear-gradient(135deg,#1e40af,#3b82f6);padding:30px 40px;text-align:center;">
    <img src="https://aiassistant.certihomes.com/images/certihomes-logo-email.png" alt="CertiHomes" style="height:200px;display:block;margin:0 auto 16px auto;border-radius:10px;">
    <h1 style="color:#ffffff;font-size:24px;margin:0 0 8px 0;font-weight:700;">📊 Market Report</h1>
    <h2 style="color:#bfdbfe;font-size:18px;margin:0;font-weight:400;">{city}, {state}</h2>
    <p style="color:#93c5fd;font-size:13px;margin:8px 0 0 0;">{report_date} · Source: {mls_label}</p>
</td>
</tr>

<!-- Headline -->
<tr>
<td style="padding:24px 40px 16px;">
    <h3 style="color:#1e293b;font-size:18px;margin:0;line-height:1.4;">{headline}</h3>
</td>
</tr>

<!-- KPIs -->
<tr>
<td style="padding:0 32px 20px;">
    <table width="100%" cellpadding="0" cellspacing="4">
    {kpi_rows}
    </table>
</td>
</tr>

<!-- Opening narrative -->
<tr>
<td style="padding:0 40px 20px;">
    <div style="color:#334155;font-size:14px;line-height:1.7;">{opening}</div>
</td>
</tr>

<!-- Pull Quote -->
{f'''
<tr>
<td style="padding:0 40px 20px;">
    <div style="border-left:4px solid #3b82f6;padding:16px 20px;background:#eff6ff;border-radius:0 8px 8px 0;">
        <p style="color:#1e40af;font-size:15px;font-style:italic;margin:0;line-height:1.6;">"{pull_quote}"</p>
    </div>
</td>
</tr>
''' if pull_quote else ''}

<!-- Supply & Demand -->
<tr>
<td style="padding:0 40px 16px;">
    <h4 style="color:#1e293b;font-size:15px;margin:0 0 8px 0;">📦 Supply</h4>
    <div style="color:#475569;font-size:13px;line-height:1.7;">{supply}</div>
</td>
</tr>
<tr>
<td style="padding:0 40px 16px;">
    <h4 style="color:#1e293b;font-size:15px;margin:0 0 8px 0;">🏷️ Demand</h4>
    <div style="color:#475569;font-size:13px;line-height:1.7;">{demand}</div>
</td>
</tr>

<!-- Recommendations -->
{f'''
<tr>
<td style="padding:0 40px 20px;">
    <h4 style="color:#1e293b;font-size:15px;margin:0 0 8px 0;">💡 Recommendations</h4>
    <div style="color:#475569;font-size:13px;line-height:1.7;">{recommendations}</div>
</td>
</tr>
''' if recommendations else ''}

<!-- CTA Buttons -->
<tr>
<td style="padding:10px 40px 24px;text-align:center;">
    <table cellpadding="0" cellspacing="0" style="margin:0 auto;">
    <tr>
        <td style="padding:0 6px;">
            <a href="{report_url}" style="display:inline-block;background:#3b82f6;color:#ffffff;padding:12px 24px;border-radius:8px;text-decoration:none;font-size:14px;font-weight:600;">📊 Full Interactive Report</a>
        </td>
        <td style="padding:0 6px;">
            <a href="{podcast_url}" style="display:inline-block;background:#8b5cf6;color:#ffffff;padding:12px 24px;border-radius:8px;text-decoration:none;font-size:14px;font-weight:600;">🎙️ Listen to Podcast</a>
        </td>
    </tr>
    </table>
</td>
</tr>

<!-- Closing -->
<tr>
<td style="padding:0 40px 24px;">
    <div style="color:#475569;font-size:14px;line-height:1.6;text-align:center;font-style:italic;">{closing}</div>
</td>
</tr>

<!-- Footer -->
<tr>
<td style="background:#f8fafc;padding:20px 40px;border-top:1px solid #e2e8f0;text-align:center;">
    <p style="color:#94a3b8;font-size:12px;margin:0 0 8px 0;">
        CertiHomes Real Estate · Edison, NJ<br>
        <a href="https://certihomes.com" style="color:#3b82f6;text-decoration:none;">certihomes.com</a> ·
        <a href="https://marketstats.certihomes.com" style="color:#3b82f6;text-decoration:none;">marketstats.certihomes.com</a>
    </p>
    <p style="color:#cbd5e1;font-size:11px;margin:0;">
        Data provided by {mls_label}. Information deemed reliable but not guaranteed.
    </p>
</td>
</tr>

</table>
</td></tr></table>
</body>
</html>
"""
    return html


async def send_market_report_email(
    to_email: str,
    city: str,
    state: str = "New Jersey",
) -> dict:
    """Fetch market data and send a beautiful HTML market report email."""
    from tools.email_sender import send_email

    # Fetch report data
    data = await fetch_report_data(city, state)

    # Build HTML
    html = build_market_report_html(data)

    # Plain text fallback
    headline = data.get("headline", f"Market Report for {city}")
    city_slug = city.lower().replace(" ", "-")
    state_slug = state.lower().replace(" ", "-")
    report_url = f"https://marketstats.certihomes.com/report?city={city_slug}&state={state_slug}"

    plain = f"""Market Report for {city}, {state}

{headline}

View the full interactive report: {report_url}

KPIs:
"""
    for kpi in data.get("kpis", []):
        plain += f"  {kpi.get('label')}: {kpi.get('value')} ({kpi.get('change', 'n/a')})\n"

    plain += f"\n— CertiHomes Real Estate | certihomes.com"

    # Send email
    result = send_email(
        to=to_email,
        subject=f"📊 {city} Market Report — {headline}",
        html_body=html,
        plain_body=plain,
    )

    result["report_url"] = report_url
    result["city"] = city
    return result
