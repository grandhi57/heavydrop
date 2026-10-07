import asyncio
import json
from playwright.async_api import async_playwright

url = "https://www.flipkart.com/crucial-ct1000p3ssd8-1000-gb-desktop-laptop-black-pcie-nvme-internal-solid-state-drive-ssd-p3-3-0-m-2-2280/p/itm2f7d57af46662?pid=IHDGGYEFDFDY32BH"

captured_calls = []

async def intercept():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1366, "height": 900})

        async def handle_route(route, request):
            u = request.url
            if any(k in u for k in ["api", "serviceability", "pincode", "1/action/view", "4/page/fetch", "delivery"]):
                print(f"INTERCEPT: {request.method} {u[:120]}")
                try:
                    post_data = request.post_data
                    headers = dict(request.headers)
                    captured_calls.append({
                        "url": u,
                        "method": request.method,
                        "headers": headers,
                        "post_data": post_data
                    })
                except Exception:
                    pass
            await route.continue_()

        await page.route("**/*", handle_route)

        print("Navigating...")
        await page.goto(url, wait_until="domcontentloaded")
        await asyncio.sleep(2)

        # Click delivery location
        btn = page.locator("text='Select delivery location'").first
        if await btn.is_visible():
            await btn.click()
            await asyncio.sleep(1)

            # Type pincode
            box = await page.locator("input[placeholder='Search by area, street name, pin code']").bounding_box()
            if box:
                await page.mouse.click(box['x'] + 30, box['y'] + 15)
                await page.keyboard.type("560001", delay=100)
                await asyncio.sleep(1.5)

                # Click suggestion
                sug = page.locator("text='560001'").first
                if await sug.is_visible():
                    await sug.click()
                    await asyncio.sleep(3)

        with open("captured_api_calls.json", "w", encoding="utf-8") as out:
            json.dump(captured_calls, out, indent=2)
        print(f"Captured {len(captured_calls)} API calls!")

        # Also let's inspect the final page text after clicking 560001
        text = await page.evaluate("() => document.body.innerText")
        lines = [l.strip() for l in text.split('\n') if any(k in l for k in ['Deliver', 'Seller', 'Stock', '560001', '₹', 'Buy'])]
        print("Page state after 560001:", lines[:15])

        await browser.close()

asyncio.run(intercept())
