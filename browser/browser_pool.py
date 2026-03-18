"""Playwright browser lifecycle — singleton browser, isolated contexts per task."""

import logging
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logger = logging.getLogger(__name__)

_playwright = None
_browser: Browser | None = None


async def start_browser():
    """Launch headless Chromium (called once at FastAPI startup)."""
    global _playwright, _browser
    if _browser:
        return
    _playwright = await async_playwright().start()
    _browser = await _playwright.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
    )
    logger.info("Playwright browser started")


async def stop_browser():
    """Close browser (called at FastAPI shutdown)."""
    global _playwright, _browser
    if _browser:
        await _browser.close()
        _browser = None
    if _playwright:
        await _playwright.stop()
        _playwright = None
    logger.info("Playwright browser stopped")


async def create_context() -> BrowserContext:
    """Create an isolated browser context for a task."""
    if not _browser:
        await start_browser()
    ctx = await _browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
    )
    return ctx


async def close_context(ctx: BrowserContext):
    """Close a browser context and all its pages."""
    try:
        await ctx.close()
    except Exception:
        pass
