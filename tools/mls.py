"""MLS API integration — connects to MarketStats FastAPI on geo.tlcengine.com.

Data sources (MongoDB on 172.26.1.151:27017, db: housing-prices):
  - bridge-cjmls (CJMLS Central Jersey MLS) — ~298K listings, NJ
  - bridge-fmls (FMLS Georgia MLS) — ~1.2M listings, GA
  - trestle (NY, stale) — ~410K listings
  - tax-assessment-data — ~12.7M records (NJ)

MarketStats API runs on geo.tlcengine.com:8000 (internal: 172.26.1.45)
"""

import httpx

# MarketStats API on geo.tlcengine.com (internal network)
MARKETSTATS_API = "http://127.0.0.1:8000/api"


async def search_listings(
    zip_code: str | None = None,
    city: str | None = None,
    state: str = "New Jersey",
    min_price: int | None = None,
    max_price: int | None = None,
    beds: int | None = None,
    baths: int | None = None,
    property_type: str | None = None,
    status: str = "Closed",
    limit: int = 10,
) -> dict:
    """Search MLS listings from CJMLS/FMLS via MarketStats API."""
    # geo_type and geo_values are required
    geo_type = "City"
    geo_values = ""
    if city:
        geo_type = "City"
        geo_values = city
    elif zip_code:
        geo_type = "PostalCode"
        geo_values = zip_code

    params: dict = {
        "state": state,
        "geo_type": geo_type,
        "geo_values": geo_values,
        "page_size": limit,
        "page": 1,
        "sort_by": "CloseDate",
        "sort_order": "desc",
    }
    if status:
        params["status"] = status
    if min_price:
        params["min_price"] = min_price
    if max_price:
        params["max_price"] = max_price
    if beds:
        params["bedrooms"] = beds
    if property_type:
        params["property_type"] = property_type

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{MARKETSTATS_API}/listings/", params=params)
        resp.raise_for_status()
        data = resp.json()
        # Simplify for the agent — handle both MarketStats API (lowercase)
        # and raw Bridge/RETS field names (CamelCase)
        listings = data.get("listings", data.get("items", []))
        simplified = []
        for l in listings[:limit]:
            # Address: try MarketStats flat format first, then Bridge format
            address = l.get("address") or f"{l.get('StreetNumber', '')} {l.get('StreetName', '')} {l.get('StreetSuffix', '')}".strip()
            city = l.get("city") or l.get("City", "")
            zip_code = l.get("zip_code") or l.get("PostalCode", "")
            listing_id = l.get("id") or l.get("ListingId", "")

            # Build property page URL
            addr_slug = address.replace(" ", "-")
            city_slug = city.replace(" ", "-")
            state_abbr = "NJ"
            portal_url = f"https://krishnam.tlcengine.com/propertydetail/{listing_id}/{addr_slug}_{city_slug}_{state_abbr}_{zip_code}" if listing_id else ""

            simplified.append({
                "id": listing_id,
                "address": address,
                "city": city,
                "zip": zip_code,
                "price": l.get("close_price") or l.get("ClosePrice") or l.get("list_price") or l.get("ListPrice"),
                "list_price": l.get("list_price") or l.get("ListPrice"),
                "close_price": l.get("close_price") or l.get("ClosePrice"),
                "beds": l.get("bedrooms") or l.get("BedroomsTotal"),
                "baths": l.get("bathrooms") or l.get("BathroomsTotalDecimal"),
                "sqft": l.get("sqft") or l.get("BuildingAreaTotal"),
                "dom": l.get("days_on_market") or l.get("DaysOnMarket"),
                "status": l.get("status") or l.get("StandardStatus"),
                "property_type": l.get("property_type") or l.get("PropertyType"),
                "close_date": l.get("close_date") or l.get("CloseDate"),
                "portal_url": portal_url,
            })
        return {"total": data.get("total", len(simplified)), "listings": simplified}


async def get_listing_detail(listing_id: str, state: str = "New Jersey") -> dict:
    """Get full details for a single listing by MongoDB ID."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{MARKETSTATS_API}/listings/{listing_id}",
            params={"state": state},
        )
        resp.raise_for_status()
        return resp.json()


async def get_market_stats(
    zip_code: str | None = None,
    city: str | None = None,
    state: str = "New Jersey",
    metric: str = "MedianSalesPrice",
    years: int = 5,
) -> dict:
    """Get time-series market stats for an area.

    Available metrics: MedianSalesPrice, AverageSalesPrice, NewListings,
    ClosedSales, Inventory, PendingSales, DaysOnMarket, PricePerSqFt,
    PctOfListPrice, ListToSaleRatio, DollarVolume, MonthsSupply, AbsorptionRate
    """
    geo_type = "City"
    geo_values = ""
    if city:
        geo_type = "City"
        geo_values = city
    elif zip_code:
        geo_type = "PostalCode"
        geo_values = zip_code

    params = {
        "state": state,
        "metric": metric,
        "geo_type": geo_type,
        "geo_values": geo_values,
        "years": years,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{MARKETSTATS_API}/metrics/", params=params)
        resp.raise_for_status()
        return resp.json()


async def get_market_report(
    city: str,
    state: str = "New Jersey",
) -> dict:
    """Get a full market report with KPIs, narrative, and recent sales for a city."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{MARKETSTATS_API}/report/",
            params={"city": city, "state": state},
        )
        resp.raise_for_status()
        data = resp.json()
        # Extract the most useful parts for the agent
        return {
            "city": city,
            "headline": data.get("headline", ""),
            "narrative": data.get("narrative", ""),
            "kpis": data.get("kpis", []),
            "recent_sales": data.get("recent_sales", [])[:5],
            "report_url": f"https://marketstats.certihomes.com/report?city={city.lower().replace(' ', '-')}&state={state.lower().replace(' ', '-')}",
        }


async def get_fast_stats(
    city: str | None = None,
    zip_code: str | None = None,
    state: str = "New Jersey",
) -> dict:
    """Get all 13 metrics snapshot for an area in a single call."""
    geo_type = "City"
    geo_values = ""
    if city:
        geo_type = "City"
        geo_values = city
    elif zip_code:
        geo_type = "PostalCode"
        geo_values = zip_code

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{MARKETSTATS_API}/faststats/",
            params={"state": state, "geo_type": geo_type, "geo_values": geo_values},
        )
        resp.raise_for_status()
        return resp.json()


async def get_forecast(
    city: str | None = None,
    zip_code: str | None = None,
    state: str = "New Jersey",
    forecast_months: int = 12,
) -> dict:
    """Get price forecast with confidence bands for an area."""
    geo_type = "City"
    geo_values = ""
    if city:
        geo_type = "City"
        geo_values = city
    elif zip_code:
        geo_type = "PostalCode"
        geo_values = zip_code

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{MARKETSTATS_API}/forecast/",
            params={
                "state": state,
                "geo_type": geo_type,
                "geo_values": geo_values,
                "forecast_months": forecast_months,
            },
        )
        resp.raise_for_status()
        return resp.json()


async def get_tax_data(
    address: str | None = None,
    zip_code: str | None = None,
    county: str | None = None,
    municipality: str | None = None,
) -> dict:
    """Look up property tax data — search by address or get summary by area."""
    async with httpx.AsyncClient(timeout=30) as client:
        if address:
            params: dict = {"query": address, "limit": 5}
            if county:
                params["county"] = county
            resp = await client.get(f"{MARKETSTATS_API}/tax/search", params=params)
            resp.raise_for_status()
            return resp.json()
        elif county and municipality:
            resp = await client.get(
                f"{MARKETSTATS_API}/tax/summary",
                params={"county": county, "municipality": municipality},
            )
            resp.raise_for_status()
            return resp.json()
        elif county:
            resp = await client.get(
                f"{MARKETSTATS_API}/tax/summary",
                params={"county": county},
            )
            resp.raise_for_status()
            return resp.json()
        else:
            return {"error": "Provide an address, or county+municipality for tax lookup"}


async def predict_tax(
    county: str,
    municipality: str,
    property_class: str = "2",
    current_value: int = 0,
    bedrooms: int = 3,
    sqft: int = 1500,
    year_built: int = 1990,
    lot_size: int = 5000,
) -> dict:
    """Predict property tax based on comparables."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{MARKETSTATS_API}/tax/predict",
            json={
                "county": county,
                "municipality": municipality,
                "property_class": property_class,
                "current_value": current_value,
                "bedrooms": bedrooms,
                "sqft": sqft,
                "year_built": year_built,
                "lot_size": lot_size,
            },
        )
        resp.raise_for_status()
        return resp.json()
