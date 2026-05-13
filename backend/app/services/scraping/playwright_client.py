"""Context manager de Playwright para el scraper del portal.

Proporciona un context manager asíncrono que abre un browser Chromium
con configuración anti-detección y lo cierra al salir.

Uso:
    async with playwright_page() as page:
        await page.goto(url)
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from playwright.async_api import Page, async_playwright

from app.config import settings


@asynccontextmanager
async def playwright_page() -> AsyncIterator[Page]:
    """Abre un browser Chromium, crea una página y la cierra al salir."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=settings.playwright_headless)
        context = await browser.new_context(
            user_agent=settings.scraping_user_agent,
            locale="es-CL",
            # Viewport realista para no activar layouts mobile-only
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()
        page.set_default_timeout(settings.playwright_timeout_ms)
        try:
            yield page
        finally:
            await context.close()
            await browser.close()
