
import asyncio
from playwright.async_api import async_playwright

async def debug_flipkart_exchange():
    url = "https://www.flipkart.com/hp-omen-ai-amd-ryzen-7-octa-core-350-24-gb-1-tb-ssd-windows-11-home-8-gb-graphics-nvidia-geforce-rtx-5050-16-ap0165ax-gaming-laptop/p/itm5661c90728083?pid=COMHEHHXKFQSABXZ"
    print("Starting browser...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
        )
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await asyncio.sleep(3)
        
        await page.evaluate("""() => {
            const el = Array.from(document.querySelectorAll(\"*\")).find(e => (e.innerText || \"\").trim() === \"Select a product to exchange\");
            if (el) el.click();
        }""")
        await asyncio.sleep(2)
        
        await page.evaluate("""() => {
            const el = Array.from(document.querySelectorAll(\"*\")).find(e => (e.innerText || \"\").trim() === \"Laptop\");
            if (el) el.click();
        }""")
        await asyncio.sleep(1)
        await page.evaluate("""() => {
            const btn = Array.from(document.querySelectorAll(\"div, button, span\")).find(e => (e.innerText || \"\").trim() === \"Next\");
            if (btn) btn.click();
        }""")
        await asyncio.sleep(3)
        
        # Click Dell
        await page.evaluate("""() => {
            const el = Array.from(document.querySelectorAll(\"*\")).find(e => (e.innerText || \"\").trim() === \"Dell\");
            if (el) el.click();
        }""")
        await asyncio.sleep(1)
        await page.evaluate("""() => {
            const btn = Array.from(document.querySelectorAll(\"div, button, span\")).find(e => (e.innerText || \"\").trim() === \"Next\");
            if (btn) btn.click();
        }""")
        await asyncio.sleep(3)
        
        # Dump Processor screen
        texts = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll(\"div\")).map(e => e.innerText).filter(t => t && t.length < 30);
        }""")
        for t in set(texts):
            print(t.encode("ascii", "ignore").decode("ascii"))

        # Click Core i5
        print("Clicking Core i5...")
        await page.evaluate("""() => {
            const el = Array.from(document.querySelectorAll(\"*\")).find(e => (e.innerText || \"\").includes(\"Core i5\"));
            if (el) el.click();
        }""")
        await asyncio.sleep(1)
        await page.evaluate("""() => {
            const btn = Array.from(document.querySelectorAll(\"div, button, span\")).find(e => (e.innerText || \"\").trim() === \"Next\");
            if (btn) btn.click();
        }""")
        await asyncio.sleep(3)

        # Dump Gen screen
        texts2 = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll(\"div\")).map(e => e.innerText).filter(t => t && t.length < 30);
        }""")
        print("--- GEN SCREEN ---")
        for t in set(texts2):
            print(t.encode("ascii", "ignore").decode("ascii"))
            
        # Click 5th Gen
        print("Clicking 5th Gen...")
        await page.evaluate("""() => {
            const el = Array.from(document.querySelectorAll(\"*\")).find(e => (e.innerText || \"\").includes(\"5th Gen\"));
            if (el) el.click();
        }""")
        await asyncio.sleep(1)
        await page.evaluate("""() => {
            const btn = Array.from(document.querySelectorAll(\"div, button, span\")).find(e => (e.innerText || \"\").trim() === \"Next\");
            if (btn) btn.click();
        }""")
        await asyncio.sleep(3)
        
        # Dump Condition screen
        texts3 = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll(\"div\")).map(e => e.innerText).filter(t => t && t.length < 30);
        }""")
        print("--- CONDITION SCREEN ---")
        for t in set(texts3):
            print(t.encode("ascii", "ignore").decode("ascii"))

        await browser.close()

asyncio.run(debug_flipkart_exchange())

