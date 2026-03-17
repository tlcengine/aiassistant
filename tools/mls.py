"""MLS API integration — search listings and market stats from tlcengine APIs."""

import httpx
from config import get_settings


async def search_listings(
    zip_code: str | None = None,
    city: str | None = None,
    state: str | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    beds: int | None = None,
    baths: int | None = None,
    property_type: str | None = None,
    limit: int = 5,
) -> dict:
    """Search active MLS listings with filters."""
    settings = get_settings()
    params = {"status": "Active", "limit": limit}
    if zip_code:
        params["postalCode"] = zip_code
    if city:
        params["city"] = city
    if state:
        params["state"] = state
    if min_price:
        params["listPrice_gte"] = min_price
    if max_price:
        params["listPrice_lte"] = max_price
    if beds:
        params["bedsTotal_gte"] = beds
    if baths:
        params["bathsTotal_gte"] = baths
    if property_type:
        params["propertyType"] = property_type

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{settings.mls_api_base_url}/listings",
            params=params,
            headers={"Authorization": f"Bearer {settings.mls_api_token}"},
        )
        resp.raise_for_status()
        return resp.json()


async def get_listing_detail(listing_id: str) -> dict:
    """Get full details for a single listing by MLS ID."""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{settings.mls_api_base_url}/listings/{listing_id}",
            headers={"Authorization": f"Bearer {settings.mls_api_token}"},
        )
        resp.raise_for_status()
        return resp.json()


async def get_market_stats(
    zip_code: str | None = None,
    city: str | None = None,
    state: str | None = None,
) -> dict:
    """Get market statistics (median price, DOM, inventory) for an area."""
    settings = get_settings()
    params = {}
    if zip_code:
        params["postalCode"] = zip_code
    if city:
        params["city"] = city
    if state:
        params["state"] = state

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{settings.mls_api_base_url}/market-stats",
            params=params,
            headers={"Authorization": f"Bearer {settings.mls_api_token}"},
        )
        resp.raise_for_status()
        return resp.json()
