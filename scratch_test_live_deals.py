import asyncio
import os
from playwright.async_api import async_playwright

ARTIFACT_DIR = r"C:\Users\kotta\.gemini\antigravity\brain\556f6c6c-ae3b-4a3b-a272-3f237167aa4b"

async def main():
    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        print("Navigating to http://127.0.0.1:8000...")
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")

        # Wait for live deals cards to appear
        await page.wait_for_selector("#live-deals-grid > div", timeout=10000)
        await asyncio.sleep(1.0)

        # 1. Main Live Deals Hub Screenshot
        path_hub = os.path.join(ARTIFACT_DIR, "live_deals_unified_hub.png")
        await page.screenshot(path=path_hub)
        print(f"Captured {path_hub}")

        # 2. Click on '⚡ Slashed Today (< 24h)'
        btn_fresh = page.locator("#btn-live-filter-fresh_drops")
        if await btn_fresh.count() > 0:
            await btn_fresh.click()
            await asyncio.sleep(1.0)
            path_fresh = os.path.join(ARTIFACT_DIR, "live_deals_fresh_drops.png")
            await page.screenshot(path=path_fresh)
            print(f"Captured {path_fresh}")

        # 3. Switch to Dense Table View
        btn_table = page.locator("#live-view-table")
        if await btn_table.count() > 0:
            await btn_table.click()
            await asyncio.sleep(0.8)
            path_table = os.path.join(ARTIFACT_DIR, "live_deals_table_view.png")
            await page.screenshot(path=path_table)
            print(f"Captured {path_table}")

        # 4. Switch back to Cards and test Trend Modal
        btn_cards = page.locator("#live-view-cards")
        await btn_cards.click()
        await asyncio.sleep(0.5)

        # Click the first sparkline button to open trend modal
        spark = page.locator("#live-deals-grid button[onclick*='openPriceTrendModal']").first
        if await spark.count() > 0:
            await spark.click()
            await page.wait_for_selector("#price-trend-modal:not(.hidden)", timeout=5000)
            await asyncio.sleep(0.8)
            path_modal = os.path.join(ARTIFACT_DIR, "live_deals_trend_modal.png")
            await page.screenshot(path=path_modal)
            print(f"Captured {path_modal}")

        await browser.close()
        print("All verification screenshots completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())
