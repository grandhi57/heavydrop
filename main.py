"""
Price Deal Tracker — FastAPI Application

Features:
- Individual product price tracking (Amazon / Flipkart)
- Mobile View Category & Search Listing Scraper (Flipkart Laptops)
- Slow Virtual-Scroll harvester for WoW prices & steep discount detection
- Telegram Bot alerts on price drops & steep discounts
- APScheduler for periodic polling
"""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

def proactor_loop_factory():
    return asyncio.ProactorEventLoop()

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import database as db
import notifier
import scraper

# ── Config ───────────────────────────────────────────────────────────────────
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("deal-tracker")

CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL_MINUTES", "3"))
STATIC_DIR = Path(__file__).parent / "static"

# ── Scheduler & Scanning State ───────────────────────────────────────────────
scheduler = AsyncIOScheduler()
is_scanning = False
is_lenovo_scanning = False
LENOVO_CHECK_INTERVAL_SECONDS = int(os.getenv("LENOVO_CHECK_INTERVAL_SECONDS", "60"))

# Real-time scan telemetry state
scan_telemetry = {
    "last_lenovo_scan_time": None,
    "last_lenovo_count": 0,
    "last_lenovo_deals_alerted": 0,
    "last_harvester_scan_time": None,
    "last_harvester_items_count": 0,
    "recent_logs": [],
}

# Active escalations (product_code -> dict with deal info and reminder count)
active_escalations = {}

_last_update_id = 0

def log_scan_event(source: str, message: str, status: str = "ok"):
    from datetime import datetime
    now_str = datetime.now().strftime("%H:%M:%S")
    scan_telemetry["recent_logs"].insert(0, {
        "time": now_str,
        "source": source,
        "message": message,
        "status": status,
    })
    if len(scan_telemetry["recent_logs"]) > 30:
        scan_telemetry["recent_logs"].pop()


async def scheduled_lenovo_poll():
    """Background job: Poll Lenovo Outlet API every 60 seconds with rotating proxies."""
    global is_lenovo_scanning
    if is_lenovo_scanning:
        logger.info("⏳ Lenovo outlet scan already in progress, skipping duplicate run.")
        return
    is_lenovo_scanning = True
    try:
        from datetime import datetime
        logger.info("⚡ Starting scheduled Lenovo Outlet 1-minute scan...")
        laptops = await scraper.fetch_lenovo_outlet_laptops()
        if not laptops:
            logger.warning("No laptops returned from Lenovo outlet API.")
            log_scan_event("Lenovo Outlet", "Poll completed: 0 laptops returned", "warning")
            return

        saved_count, deals_to_alert = await db.upsert_lenovo_products(laptops)
        now_iso = datetime.now().isoformat()
        scan_telemetry["last_lenovo_scan_time"] = now_iso
        scan_telemetry["last_lenovo_count"] = saved_count
        scan_telemetry["last_lenovo_deals_alerted"] = len(deals_to_alert)
        log_scan_event("Lenovo Outlet", f"Harvested {saved_count} laptops ({len(deals_to_alert)} deals queued)")

        logger.info("💾 Lenovo scan saved %d laptops. Deals to alert: %d", saved_count, len(deals_to_alert))

        for deal in deals_to_alert:
            try:
                signal_type = deal.get("signal_type", "banger")
                sent = await notifier.send_deal_alert(
                    deal=deal,
                    signal_type=signal_type,
                    platform="lenovo",
                )
                if sent:
                    if signal_type == "insane_deal":
                        import time
                        active_escalations[deal["product_code"]] = {
                            "start_time": time.time(),
                            "reminders_sent": 0,
                            "deal": deal
                        }
                        logger.info("🚨 INSANE DEAL QUEUED FOR ESCALATION: %s", deal["product_code"])
                        # 📞 Fire CallMeBot voice call for insane deals
                        try:
                            gpu = deal.get("gpu") or ""
                            price = deal.get("current_price", 0)
                            name = deal.get("name", "laptop")
                            call_text = (
                                f"Insane deal alert! {name} with {gpu} at only "
                                f"{price:,.0f} rupees. Open Telegram immediately to buy before it disappears!"
                            )
                            call_result = await notifier.trigger_voice_call(text=call_text)
                            if call_result.get("success"):
                                logger.info("📞 Voice call triggered for insane deal: %s", deal["product_code"])
                            else:
                                logger.warning("📞 Voice call failed: %s", call_result.get("error"))
                        except Exception as call_err:
                            logger.error("📞 Voice call exception: %s", call_err)

                    await db.record_lenovo_alert(
                        deal["product_code"],
                        deal["current_price"],
                        deal["save_percent"],
                    )
            except Exception as alert_err:
                logger.error("Failed to send alert for Lenovo %s: %s", deal.get("product_code"), alert_err)

    except Exception as e:
        logger.error("Error during scheduled Lenovo Outlet scan: %s", e)
        log_scan_event("Lenovo Outlet", f"Scan error: {e}", "error")
    finally:
        is_lenovo_scanning = False


async def scheduled_check_all():
    """Background job: check single products AND active category listings."""
    global is_scanning
    if is_scanning:
        logger.warning("⏳ Scan already in progress, skipping duplicate run.")
        return
    is_scanning = True
    try:
        from datetime import datetime
        logger.info("⏰ Scheduled check starting…")
        log_scan_event("Harvester", "Category & single product check started")
        await _check_all_products()
        await _scan_all_listings()
        now_iso = datetime.now().isoformat()
        scan_telemetry["last_harvester_scan_time"] = now_iso
        log_scan_event("Harvester", "Scheduled scan cycle completed")
        logger.info("✅ Scheduled check complete.")
    except Exception as e:
        logger.error("Error during scheduled check: %s", e)
        log_scan_event("Harvester", f"Check error: {e}", "error")
    finally:
        is_scanning = False
        from datetime import datetime, timedelta
        next_run_time = datetime.now() + timedelta(minutes=CHECK_INTERVAL)
        logger.info(f"💤 Resting for {CHECK_INTERVAL} minutes. Next scan scheduled at {next_run_time.strftime('%H:%M:%S')}")
        scheduler.add_job(
            scheduled_check_all,
            "date",
            run_date=next_run_time,
            id="price_check",
            replace_existing=True,
        )


async def _check_all_products():
    """Scrape all single tracked products."""
    products = await db.get_all_products()
    if not products:
        return

    urls = [p["url"] for p in products]
    results = await scraper.scrape_many(urls)

    for product in products:
        url = product["url"]
        result = results.get(url)

        if result is None or isinstance(result, Exception):
            continue

        await db.update_product_price(
            product_id=product["id"],
            price=result.price,
            title=result.title,
            image_url=result.image_url,
        )
        await db.add_price_history(product["id"], result.price)

        if result.price <= product["target_price"]:
            await notifier.send_price_alert(
                product_id=product["id"],
                title=result.title,
                current_price=result.price,
                target_price=product["target_price"],
                url=url,
                platform=result.platform,
            )


async def _scan_all_listings():
    """Scrape all category listings in mobile view (skips paused listings)."""
    listings = await db.get_all_listings()
    for listing in listings:
        if listing.get("is_paused"):
            logger.info("⏸️ Skipping paused listing %d (%s)", listing["id"], listing.get("title", ""))
            continue
        try:
            await _scan_single_listing(listing["id"])
        except Exception as e:
            logger.error("Periodic scan failed for listing %d: %s", listing["id"], e)


async def scheduled_daily_digest():
    """Background job: Send daily deal digest to Telegram (8 AM & 8 PM IST)."""
    try:
        logger.info("📬 Generating daily deal digest...")
        deals = await db.get_digest_deals(limit=15)
        if deals:
            sent = await notifier.send_daily_digest(deals)
            logger.info("📬 Daily digest %s (%d deals)", "sent ✅" if sent else "skipped", len(deals))
        else:
            logger.info("📬 No active deals for digest — skipping")
    except Exception as e:
        logger.error("Error during daily digest: %s", e)


async def scheduled_retry_failed_alerts():
    """Background job: Retry failed alerts from the queue every 10 minutes."""
    try:
        pending = await db.get_pending_alerts(limit=10)
        if not pending:
            return

        logger.info("🔄 Retrying %d failed alerts...", len(pending))
        for alert in pending:
            try:
                payload = alert["payload"]
                sent = await notifier.send_deal_alert(
                    deal=payload,
                    signal_type=alert["signal_type"],
                    platform=alert["platform"],
                )
                await db.mark_alert_retried(alert["id"], success=sent)
                if sent:
                    logger.info("✅ Retry succeeded for alert %d (%s)", alert["id"], alert["deal_key"])
            except Exception as retry_err:
                logger.error("Retry failed for alert %d: %s", alert["id"], retry_err)
                await db.mark_alert_retried(alert["id"], success=False)
    except Exception as e:
        logger.error("Error during failed alert retry: %s", e)


async def check_escalation_reminders():
    """Background job: Send reminders for unacknowledged Tier 1 deals."""
    import time
    now = time.time()
    
    # Check every active escalation
    for pid, esc in list(active_escalations.items()):
        # Non-stop reminders every 1 second
        elapsed = now - esc["start_time"]
        reminders_sent = esc.get("reminders_sent", 0)
        
        # Calculate how many reminders should have been sent by now (1 reminder per second)
        # Using a slight buffer (1.0) to ensure we don't spam too fast in one tick
        target_reminders = int(elapsed / 1.0)
        
        if reminders_sent < target_reminders:
            r_num = reminders_sent + 1
            logger.info("⏰ Sending 1-second interval reminder %d for unacknowledged deal %s", r_num, pid)
            try:
                deal = esc["deal"]
                msg = (
                    f"⏰ <b>URGENT REMINDER {r_num}: DON'T MISS THIS!</b> ⏰\n\n"
                    f"🔥 <b>{deal.get('name')}</b> is still unacknowledged at <b>₹{deal.get('current_price',0):,.0f}</b>.\n\n"
                    f"🔗 <a href=\"{deal.get('url','')}\">Buy Now</a>\n"
                )
                # Use a unique cooldown key for each reminder
                cooldown_key = f"rem_{r_num}_{pid}_{deal.get('current_price',0)}"
                import notifier
                # We pass the reminder message directly using the internal dispatcher
                bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
                chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
                
                if bot_token and chat_id:
                    payload = {
                        "chat_id": chat_id,
                        "text": msg,
                        "parse_mode": "HTML",
                        "reply_markup": {
                            "inline_keyboard": [[
                                {"text": "✅ Acknowledge (Stop Pinging)", "callback_data": f"ack_{pid}"}
                            ]]
                        }
                    }
                    import httpx
                    async with httpx.AsyncClient() as client:
                        await client.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json=payload)
                        
                active_escalations[pid]["reminders_sent"] = r_num
            except Exception as e:
                logger.error("Failed to send reminder for %s: %s", pid, e)
                
        # Auto expire after 24 hours to prevent memory leaks if completely ignored
        if elapsed > 24 * 60 * 60:
            logger.info("Escalation for %s auto-expired after 24 hours", pid)
            active_escalations.pop(pid, None)


async def poll_telegram_updates():
    """Background job: poll Telegram for /ack callbacks."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not bot_token or bot_token == "your_bot_token_here":
        return
        
    global _last_update_id
    try:
        if '_last_update_id' not in globals():
            _last_update_id = 0
            
        import httpx
        url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
        params = {"offset": _last_update_id, "timeout": 5, "allowed_updates": ["callback_query"]}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    for update in data.get("result", []):
                        _last_update_id = update["update_id"] + 1
                        
                        if "callback_query" in update:
                            cb = update["callback_query"]
                            cb_data = cb.get("data", "")
                            
                            if cb_data.startswith("ack_"):
                                pid = cb_data[4:]
                                if pid in active_escalations:
                                    active_escalations.pop(pid)
                                    logger.info("✅ Telegram User acknowledged deal %s. Escalation stopped.", pid)
                                    
                                    # Answer callback to remove loading state
                                    cb_id = cb.get("id")
                                    await client.post(
                                        f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery",
                                        json={"callback_query_id": cb_id, "text": "Deal Acknowledged! Escalation stopped."}
                                    )
    except Exception as e:
        pass # Ignore minor polling errors

# ── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_db()
    logger.info("📦 Database initialized.")

    from datetime import datetime, timedelta
    scheduler.add_job(
        scheduled_check_all,
        "date",
        run_date=datetime.now() + timedelta(seconds=15),
        id="price_check",
        replace_existing=True,
    )
    scheduler.add_job(
        scheduled_lenovo_poll,
        "interval",
        seconds=LENOVO_CHECK_INTERVAL_SECONDS,
        id="lenovo_outlet_poll",
        replace_existing=True,
    )
    # Daily deal digest at 8:00 AM IST (02:30 UTC) and 8:00 PM IST (14:30 UTC)
    scheduler.add_job(
        scheduled_daily_digest,
        "cron",
        hour="2,14",
        minute=30,
        id="daily_digest",
        replace_existing=True,
    )
    # Retry failed alerts every 10 minutes
    scheduler.add_job(
        scheduled_retry_failed_alerts,
        "interval",
        minutes=10,
        id="retry_failed_alerts",
        replace_existing=True,
    )
    # Check for escalation reminders every 1 second
    scheduler.add_job(
        check_escalation_reminders,
        "interval",
        seconds=1,
        id="check_escalation_reminders",
        replace_existing=True,
    )
    # Poll Telegram for callbacks every 5 seconds
    scheduler.add_job(
        poll_telegram_updates,
        "interval",
        seconds=5,
        id="poll_telegram_updates",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("⏲️  Scheduler started: Flipkart/Amazon every %dm, Lenovo Outlet every %ds, Digest 8AM+8PM IST, Alert retry 10m.", CHECK_INTERVAL, LENOVO_CHECK_INTERVAL_SECONDS)

    # Initial instant Lenovo scan in background
    asyncio.create_task(scheduled_lenovo_poll())

    # Auto-seed requested IKEA Modular Sofas listing
    try:
        ikea_target_url = "https://www.ikea.com/in/en/search/?q=modula%20sofa&filters=f-seats%3A38768%7C38769"
        existing_listings = await db.get_all_listings()
        ikea_entry = next((l for l in existing_listings if l["url"] == ikea_target_url), None)
        if not ikea_entry:
            new_ikea = await db.add_listing(
                url=ikea_target_url,
                title="IKEA Modular Sofas",
                category="sofas",
                discount_threshold_pct=10.0,
            )
            logger.info("🛋️ Auto-seeded IKEA Modular Sofas listing ID %d", new_ikea["id"])
            asyncio.create_task(_scan_single_listing(new_ikea["id"]))
        else:
            # Refresh IKEA scan in background on startup
            asyncio.create_task(_scan_single_listing(ikea_entry["id"]))
    except Exception as e:
        logger.warning("Auto-seed IKEA error: %s", e)

    yield

    scheduler.shutdown(wait=False)
    logger.info("🛑 Scheduler stopped.")


# ── FastAPI App ──────────────────────────────────────────────────────────────
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Price Deal Tracker",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# ── Pydantic Models ─────────────────────────────────────────────────────────
class ProductCreate(BaseModel):
    url: str
    target_price: float


class ListingCreate(BaseModel):
    url: str
    title: str = ""
    category: str = "laptops"
    discount_threshold_pct: float = 10.0


# ── Static UI ────────────────────────────────────────────────────────────────
@app.get("/")
async def serve_index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ═══════════════════════════════════════════════════════════════════════════
# Category / Listing Tracker Routes (Flipkart Laptops Mobile Scraper)
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/api/listings")
async def list_listings():
    """Get all monitored listing/category URLs."""
    listings = await db.get_all_listings()
    return listings


@app.post("/api/listings", status_code=201)
async def create_listing(data: ListingCreate):
    """Add a category or search listing URL (e.g. Flipkart Laptops) to track."""
    url = data.url.strip()
    if not url:
        raise HTTPException(400, "Listing URL is required")
    url_lower = url.lower()
    if "flipkart" not in url_lower and "amazon" not in url_lower and "ikea" not in url_lower:
        raise HTTPException(400, "Currently Flipkart, Amazon, and IKEA listings are supported")

    try:
        listing = await db.add_listing(
            url=url,
            title=data.title,
            category=data.category,
            discount_threshold_pct=data.discount_threshold_pct,
        )
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            raise HTTPException(409, "This listing URL is already being tracked")
        raise HTTPException(500, str(e))

    # Trigger an initial background harvest
    asyncio.create_task(_scan_single_listing(listing["id"]))

    return listing


@app.delete("/api/listings/{listing_id}")
async def remove_listing(listing_id: int):
    """Stop tracking a listing and delete harvested items."""
    deleted = await db.delete_listing(listing_id)
    if not deleted:
        raise HTTPException(404, "Listing not found")
    return {"status": "deleted", "id": listing_id}


@app.post("/api/listings/{listing_id}/scan")
async def force_scan_listing(listing_id: int, scrolls: int = Query(default=25, ge=5, le=60)):
    """
    Trigger an immediate mobile virtual-scroll scan on this listing.
    Slowly scrolls and harvests WoW prices & steep discounts.
    """
    listing = await db.get_listing(listing_id)
    if not listing:
        raise HTTPException(404, "Listing not found")

    result = await _scan_single_listing(listing_id, max_scrolls=scrolls)
    return result


@app.get("/api/all-deals")
async def get_all_deals_route(
    sort_by: str = Query(default="steepest"),
    filter_type: str = Query(default="all"),
    platform: str = Query(default="all"),
    category: str = Query(default="all"),
    ram: str = Query(default="all"),
    gpu: str = Query(default="all"),
    q: str = Query(default=""),
    in_stock_only: bool = Query(default=False),
    limit: int = Query(default=200, le=500),
):
    """Retrieve normalized live deal stream across all platforms & categories."""
    return await db.get_all_deals(
        sort_by=sort_by,
        filter_type=filter_type,
        platform=platform,
        category=category,
        ram=ram,
        gpu=gpu,
        q=q,
        in_stock_only=in_stock_only,
        limit=limit,
    )


@app.get("/api/deal-history/{pid:path}")
async def get_deal_history(pid: str):
    """Lazy-load price history for a single product (for trend modal)."""
    conn = await db.get_db()
    try:
        # Try listing_price_history first (Flipkart/IKEA)
        rows = await conn.execute_fetchall(
            """SELECT effective_price, regular_price, wow_price, recorded_at
               FROM listing_price_history WHERE pid = ? ORDER BY recorded_at ASC""",
            (pid,),
        )
        if rows:
            return [dict(r) for r in rows]

        # Try lenovo_price_history
        rows = await conn.execute_fetchall(
            """SELECT price as effective_price, save_percent, recorded_at
               FROM lenovo_price_history WHERE product_code = ? ORDER BY recorded_at ASC""",
            (pid,),
        )
        if rows:
            return [dict(r) for r in rows]

        # Try single product tracker
        rows = await conn.execute_fetchall(
            """SELECT price as effective_price, checked_at as recorded_at
               FROM price_history WHERE product_id = ? ORDER BY checked_at ASC""",
            (pid,),
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()


@app.get("/api/listings/{listing_id}/products")
async def get_listing_products_route(
    listing_id: int,
    sort_by: str = Query(default="steepest", pattern="^(steepest|lowest_price|wow_only|newest|latest_drop|discount|savings|price_asc|price_desc)$"),
):
    """Retrieve all harvested laptops/products for a listing."""
    listing = await db.get_listing(listing_id)
    if not listing:
        raise HTTPException(404, "Listing not found")

    products = await db.get_listing_products(listing_id, sort_by=sort_by)
    return {
        "listing": listing,
        "total": len(products),
        "products": products,
    }


async def _scan_single_listing(listing_id: int, max_scrolls: int = 60) -> dict:
    """Core logic to run mobile virtual-scroll harvest on a listing."""
    listing = await db.get_listing(listing_id)
    if not listing:
        return {"error": "Listing not found"}

    url = listing["url"]
    threshold_pct = float(listing.get("discount_threshold_pct") or 10.0)
    category = (listing.get("category") or "").lower()
    title = (listing.get("title") or "").lower()
    url_lower = url.lower()

    # Rule: ONLY for laptops apply dead laptop exchange. For any other product (RAM, SSD, etc.), do NOT add exchange!
    is_laptop = "laptop" in category or "laptop" in url_lower or "laptop" in title
    apply_exchange = is_laptop

    # For small categories with few items, optimize scrolls so background scans finish fast
    if max_scrolls == 25 and ("ram" in category or "dish" in category):
        max_scrolls = 8

    if "ikea" in url_lower:
        logger.info("🛋️ Starting IKEA SIK harvest for listing %d (%s)...", listing_id, url)
        try:
            items = await scraper.scrape_ikea_search(url)
        except Exception as e:
            logger.error("IKEA scrape failed for %d: %s", listing_id, e)
            fail_count = await db.update_listing_scrape_status(listing_id, "error", str(e)[:200])
            if fail_count >= 3:
                await notifier.send_deal_alert(
                    {"name": f"IKEA Scraper (listing {listing_id})", "url": url, "effective_price": 0},
                    signal_type="price_drop", platform="system",
                )
                logger.warning("⚠️ IKEA scraper failed %d consecutive times for listing %d", fail_count, listing_id)
            return {"error": str(e), "listing_id": listing_id}
    else:
        logger.info(
            "🚀 Starting mobile virtual-scroll for listing %d (%s) [exchange=%s, category=%s, scrolls=%d]...",
            listing_id, url, apply_exchange, category, max_scrolls
        )
        try:
            # 1. Harvest items using mobile emulation + slow virtual scrolling
            items = await scraper.scrape_listing_mobile(
                url,
                max_scrolls=max_scrolls,
                scroll_delay=0.8,
                apply_exchange=apply_exchange,
                category=category,
            )
        except Exception as e:
            logger.error("Mobile listing scrape failed for %d: %s", listing_id, e)
            fail_count = await db.update_listing_scrape_status(listing_id, "error", str(e)[:200])
            if fail_count >= 3:
                logger.warning("⚠️ Flipkart scraper failed %d consecutive times for listing %d", fail_count, listing_id)
            return {"error": str(e), "listing_id": listing_id}

    if not items:
        logger.warning("No items harvested for listing %d", listing_id)
        return {"status": "completed", "items_found": 0, "discounts_alerted": 0}

    # 1b. Pre-verify candidates showing large drops (> 35%) using localized delivery pincode PDP check
    # This prevents phantom/ghost sellers (like OmniTechRetail) in search index from poisoning the database!
    for item in items:
        pid = item.get("pid")
        if not pid:
            continue
        old_eff = await db.get_listing_product_effective_price(pid)
        if old_eff and item.get("effective_price") and item["effective_price"] < old_eff:
            cand_drop = ((old_eff - item["effective_price"]) / old_eff) * 100
            if cand_drop > 35.0:
                logger.info(
                    "🔍 Candidate drop of %.1f%% detected for %s (₹%s -> ₹%s). Verifying on PDP with pincode...",
                    cand_drop, pid, old_eff, item["effective_price"]
                )
                v = await scraper.verify_flipkart_pdp_price(item["url"])
                if v.get("success"):
                    verified_eff = v["verified_effective_price"]
                    logger.info(
                        "📍 PDP verified price for %s: ₹%s (Search card was ₹%s)",
                        pid, verified_eff, item["effective_price"]
                    )
                    item["effective_price"] = verified_eff
                    if v.get("verified_regular_price"):
                        item["regular_price"] = v["verified_regular_price"]
                    if v.get("verified_wow_price"):
                        item["wow_price"] = v["verified_wow_price"]

    # 2. Save items to DB and detect steep discounts compared to previous records
    steep_deals = await db.save_listing_products(listing_id, items, threshold_pct=threshold_pct)

    logger.info(
        "💾 Saved %d items for listing %d. Steep discounts detected: %d",
        len(items), listing_id, len(steep_deals)
    )

    # Reset scrape failure counter on success
    await db.update_listing_scrape_status(listing_id, "ok")

    # 3. Send Telegram alerts for steep discounts
    alert_count = 0
    for deal in steep_deals:
        drop_pct = deal["discount_pct"]
        effective_price = deal["effective_price"]
        prev_price = deal.get("previous_price")

        # Selective Double-Check Rule:
        # Double-check on product page with localized delivery pincode when drop is large (> 35%)
        # to catch ghost sellers (e.g. OmniTechRetail) and monthly EMI artifacts!
        if drop_pct > 35.0:
            logger.info(
                "🔍 Large drop detected (%.1f%% > 35%%) for %s (%s). Double-checking product page with pincode...",
                drop_pct, deal["pid"], deal.get("name", "")
            )
            v = await scraper.verify_flipkart_pdp_price(deal["url"])
            if v.get("success"):
                verified_eff = v["verified_effective_price"]
                verified_drop = 0.0
                if prev_price and prev_price > verified_eff:
                    verified_drop = round(((prev_price - verified_eff) / prev_price) * 100, 1)

                if verified_drop < threshold_pct:
                    logger.warning(
                        "⚠️ False flag suppressed for %s: Listing candidate was ₹%s (%.1f%% drop), but product page verified price is ₹%s (real drop: %.1f%%). Updating DB.",
                        deal["pid"], effective_price, drop_pct, verified_eff, verified_drop
                    )
                    await db.update_listing_product_price(
                        pid=deal["pid"],
                        effective_price=verified_eff,
                        regular_price=v.get("verified_regular_price"),
                        wow_price=v.get("verified_wow_price"),
                        discount_pct=verified_drop,
                    )
                    continue  # Suppress false alert!
                else:
                    logger.info("✅ Genuine >50%% drop confirmed on product page for %s: ₹%s (%.1f%% drop)", deal["pid"], verified_eff, verified_drop)
                    deal["effective_price"] = verified_eff
                    deal["discount_pct"] = verified_drop
                    if v.get("verified_wow_price"):
                        deal["wow_price"] = v["verified_wow_price"]
                    if v.get("verified_regular_price"):
                        deal["regular_price"] = v["verified_regular_price"]

        # Determine platform from URL
        deal_url_lower = deal.get("url", "").lower()
        platform = "flipkart"
        if "ikea" in deal_url_lower:
            platform = "ikea"
        elif "amazon" in deal_url_lower:
            platform = "amazon"

        signal_type = deal.get("signal_type", "price_drop")
        sent = await notifier.send_deal_alert(
            deal=deal,
            signal_type=signal_type,
            platform=platform,
        )
        if sent:
            alert_count += 1
            await db.record_listing_alert(deal["pid"], deal["effective_price"])

    return {
        "status": "completed",
        "items_found": len(items),
        "discounts_alerted": alert_count,
        "steep_deals": steep_deals,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Single Product Routes
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/api/products")
async def list_products():
    return await db.get_all_products()


@app.post("/api/products", status_code=201)
async def create_product(data: ProductCreate):
    url = data.url.strip()
    if not url:
        raise HTTPException(400, "URL is required")
    if data.target_price <= 0:
        raise HTTPException(400, "Target price must be positive")

    url_lower = url.lower()
    if "amazon" not in url_lower and "flipkart" not in url_lower:
        raise HTTPException(400, "Only Amazon and Flipkart URLs are supported")

    try:
        product = await db.add_product(url, data.target_price)
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            raise HTTPException(409, "This URL is already being tracked")
        raise HTTPException(500, str(e))

    asyncio.create_task(_check_single_product(product["id"]))
    return product


@app.delete("/api/products/{product_id}")
async def remove_product(product_id: int):
    deleted = await db.delete_product(product_id)
    if not deleted:
        raise HTTPException(404, "Product not found")
    return {"status": "deleted", "id": product_id}


@app.post("/api/products/{product_id}/check")
async def force_check_one(product_id: int):
    return await _check_single_product(product_id)


@app.post("/api/check-all")
async def force_check_all():
    global is_scanning
    if is_scanning:
        return {"status": "in_progress", "message": "Scan already running in background"}
    asyncio.create_task(scheduled_check_all())
    return {"status": "started", "message": "Price checks & listing scans initiated"}


@app.get("/api/products/{product_id}/history")
async def product_history(product_id: int):
    product = await db.get_product(product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    history = await db.get_price_history(product_id)
    return {"product": product, "history": history}


@app.get("/api/status")
async def api_status():
    job = scheduler.get_job("price_check")
    next_run = str(job.next_run_time) if job else None
    l_job = scheduler.get_job("lenovo_outlet_poll")
    lenovo_next = str(l_job.next_run_time) if l_job else None
    products = await db.get_all_products()
    listings = await db.get_all_listings()
    l_stats = await db.get_lenovo_stats()
    return {
        "status": "running",
        "scheduler_active": scheduler.running,
        "is_scanning": is_scanning,
        "next_check": next_run,
        "tracked_products": len(products),
        "tracked_listings": len(listings),
        "check_interval_minutes": CHECK_INTERVAL,
        "delivery_pincode": os.getenv("DELIVERY_PINCODE", "560016"),
        "is_lenovo_scanning": is_lenovo_scanning,
        "lenovo_next_check": lenovo_next,
        "lenovo_products_count": l_stats.get("total_count", 0),
        "lenovo_banger_deals_count": l_stats.get("banger_count", 0),
        "telemetry": scan_telemetry,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Notification Intelligence & Listing Management Routes
# ═══════════════════════════════════════════════════════════════════════════

@app.patch("/api/listings/{listing_id}")
async def update_listing_route(listing_id: int, action: str = Query(default=""), threshold: float | None = Query(default=None)):
    """Pause/resume a listing or update its alert threshold."""
    listing = await db.get_listing(listing_id)
    if not listing:
        raise HTTPException(404, "Listing not found")

    if action == "pause":
        await db.pause_listing(listing_id)
        return {"status": "paused", "listing_id": listing_id}
    elif action == "resume":
        await db.resume_listing(listing_id)
        return {"status": "resumed", "listing_id": listing_id}
    elif threshold is not None:
        if threshold < 1.0 or threshold > 90.0:
            raise HTTPException(400, "Threshold must be between 1% and 90%")
        await db.update_listing_threshold(listing_id, threshold)
        return {"status": "updated", "listing_id": listing_id, "new_threshold": threshold}
    else:
        raise HTTPException(400, "Specify action=pause|resume or threshold=<value>")


class BulkListingCreate(BaseModel):
    urls: list[str]
    discount_threshold_pct: float = 10.0


@app.post("/api/listings/bulk", status_code=201)
async def create_bulk_listings(data: BulkListingCreate):
    """Add multiple listing URLs at once. Auto-categorizes each URL."""
    results = []
    for url in data.urls:
        url = url.strip()
        if not url:
            continue
        url_lower = url.lower()
        if "flipkart" not in url_lower and "amazon" not in url_lower and "ikea" not in url_lower:
            results.append({"url": url, "status": "skipped", "reason": "Unsupported platform"})
            continue
        try:
            listing = await db.add_listing(
                url=url,
                title="",
                category="",
                discount_threshold_pct=data.discount_threshold_pct,
            )
            asyncio.create_task(_scan_single_listing(listing["id"]))
            results.append({"url": url, "status": "created", "listing_id": listing["id"], "title": listing.get("title", "")})
        except Exception as e:
            if "UNIQUE constraint" in str(e):
                results.append({"url": url, "status": "skipped", "reason": "Already tracked"})
            else:
                results.append({"url": url, "status": "error", "reason": str(e)[:100]})
    return {"created": sum(1 for r in results if r["status"] == "created"), "results": results}


@app.get("/api/notifications/log")
async def get_notification_log_route(limit: int = Query(default=50, le=200)):
    """Retrieve recent notification history."""
    return await db.get_notification_log(limit=limit)


@app.get("/api/health")
async def health_check():
    """Scraper health dashboard — shows status of all tracked listings and scrapers."""
    listings = await db.get_all_listings()
    l_stats = await db.get_lenovo_stats()

    listing_health = []
    for listing in listings:
        listing_health.append({
            "id": listing["id"],
            "title": listing.get("title", ""),
            "category": listing.get("category", ""),
            "status": listing.get("scrape_status", "ok"),
            "is_paused": bool(listing.get("is_paused", 0)),
            "consecutive_failures": listing.get("consecutive_failures", 0),
            "last_error": listing.get("last_error"),
            "last_scraped": listing.get("last_scraped"),
            "total_items": listing.get("total_items", 0),
        })

    # Check pending alert queue
    pending_alerts = await db.get_pending_alerts(limit=50)

    return {
        "overall_status": "healthy" if all(l["status"] == "ok" for l in listing_health) else "degraded",
        "listings": listing_health,
        "lenovo_outlet": {
            "status": "ok",
            "total_products": l_stats.get("total_count", 0),
            "banger_deals": l_stats.get("banger_count", 0),
            "is_scanning": is_lenovo_scanning,
        },
        "pending_alert_retries": len(pending_alerts),
        "scheduler_active": scheduler.running,
    }


@app.post("/api/digest/trigger")
async def trigger_digest():
    """Manually trigger a deal digest notification."""
    asyncio.create_task(scheduled_daily_digest())
    return {"status": "started", "message": "Deal digest generation initiated"}


# ═══════════════════════════════════════════════════════════════════════════
# Lenovo India Outlet Routes
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/api/lenovo/products")
@app.get("/api/lenovo-outlet")
async def get_lenovo_products_route(
    sort_by: str = Query("discount"),
    series: str | None = Query(None),
    min_discount: float | None = Query(None),
    in_stock_only: bool = Query(False),
    search: str | None = Query(None),
    gpu_filter: str | None = Query(None),
):
    """Get tracked Lenovo Outlet laptops with optional filtering and sorting."""
    return await db.get_lenovo_products(
        sort_by=sort_by,
        series=series,
        min_discount=min_discount,
        in_stock_only=in_stock_only,
        search=search,
        gpu_filter=gpu_filter,
    )


@app.post("/api/lenovo/scan")
@app.post("/api/lenovo-outlet/scan")
async def force_lenovo_scan():
    """Immediately trigger a live scan of the Lenovo India Refurbished Outlet."""
    global is_lenovo_scanning
    if is_lenovo_scanning:
        return {"status": "in_progress", "message": "Lenovo Outlet scan is already running"}
    asyncio.create_task(scheduled_lenovo_poll())
    return {"status": "started", "message": "Lenovo Outlet scan initiated"}


@app.get("/api/lenovo/stats")
async def get_lenovo_stats_route():
    """Get metrics and quick stats for the Lenovo Outlet tab."""
    stats = await db.get_lenovo_stats()
    job = scheduler.get_job("lenovo_outlet_poll")
    stats["next_run"] = str(job.next_run_time) if job else None
    stats["is_scanning"] = is_lenovo_scanning
    stats["interval_seconds"] = LENOVO_CHECK_INTERVAL_SECONDS
    return stats


@app.post("/api/test-voice-call")
async def test_voice_call():
    """Trigger a test Telegram voice call via CallMeBot and test the escalation ping loop."""
    # 1. Fire Voice Call
    result = await notifier.trigger_voice_call(
        text="This is a test call from your deal tracker. Voice call alerts are working correctly. You will receive calls like this when an insane deal is detected!"
    )
    
    # 2. Inject a fake deal into active_escalations to test the reminder loop
    import time
    test_deal = {
        "product_code": "TEST_DEAL",
        "name": "TEST LAPTOP DEAL",
        "current_price": 65000,
        "url": "https://www.lenovo.com/in/outletin/en/p/test"
    }
    
    active_escalations["TEST_DEAL"] = {
        "start_time": time.time(),
        "reminders_sent": 0,
        "deal": test_deal
    }
    
    # Also send the initial message with the ack button right now!
    import httpx, os
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    msg = (
        "🚨🚨🚨 <b>TEST INSANE DEAL ALERT</b> 🚨🚨🚨\n\n"
        "🔥 <b>RTX 4060 Laptop @ ₹65,000</b>\n"
        "💻 <b>Lenovo ThinkPad P16v Gen 2</b>\n"
        "⚠️ <i>This is a TEST notification. If you do not click Acknowledge below, I will ping you every 15 seconds!</i>"
    )
    payload = {
        "chat_id": chat_id,
        "text": msg,
        "parse_mode": "HTML",
        "reply_markup": {
            "inline_keyboard": [[
                {"text": "✅ Acknowledge (Stop Pinging)", "callback_data": "ack_TEST_DEAL"}
            ]]
        }
    }
    async with httpx.AsyncClient() as client:
        await client.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json=payload)

    return result


@app.get("/api/ack/{product_code}")
async def ack_deal(product_code: str):
    """Acknowledge a deal to stop escalation reminders."""
    if product_code in active_escalations:
        active_escalations.pop(product_code)
        logger.info("✅ User acknowledged deal %s. Escalation stopped.", product_code)
        return {"status": "success", "message": f"Deal {product_code} acknowledged"}
    return {"status": "not_found", "message": "Deal not active or already acknowledged"}


async def _check_single_product(product_id: int) -> dict:
    product = await db.get_product(product_id)
    if not product:
        return {"error": "Product not found"}

    try:
        result = await scraper.scrape_product(product["url"])
    except Exception as e:
        logger.error("Scrape failed for product %d: %s", product_id, e)
        return {"error": str(e), "product_id": product_id}

    await db.update_product_price(
        product_id=product_id,
        price=result.price,
        title=result.title,
        image_url=result.image_url,
    )
    await db.add_price_history(product_id, result.price)

    alerted = False
    if result.price <= product["target_price"]:
        alerted = await notifier.send_price_alert(
            product_id=product_id,
            title=result.title,
            current_price=result.price,
            target_price=product["target_price"],
            url=product["url"],
            platform=result.platform,
        )

    return {
        "product_id": product_id,
        "title": result.title,
        "price": result.price,
        "alerted": alerted,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Telegram Bot Configuration & Test Routes
# ═══════════════════════════════════════════════════════════════════════════

class TelegramChatIdUpdate(BaseModel):
    chat_id: str


@app.post("/api/telegram/test")
@app.post("/api/test-alert")
async def telegram_test_route():
    """Send a realistic test alert to the configured Telegram chat."""
    success, message = await notifier.send_test_alert()
    return {"success": success, "message": message, "chat_id": os.getenv("TELEGRAM_CHAT_ID", "")}


@app.post("/api/telegram/detect")
async def telegram_detect_route():
    """Poll for recent /start messages to auto-configure chat ID."""
    return await notifier.auto_detect_chat_id()


@app.post("/api/telegram/chat-id")
async def set_telegram_chat_id_route(data: TelegramChatIdUpdate):
    """Manually update Telegram Chat ID in .env."""
    cid = data.chat_id.strip()
    if not cid:
        raise HTTPException(400, "chat_id cannot be empty")
    os.environ["TELEGRAM_CHAT_ID"] = cid
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            content = f.read()
        import re
        content = re.sub(r"^TELEGRAM_CHAT_ID=.*$", f"TELEGRAM_CHAT_ID={cid}", content, flags=re.MULTILINE)
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(content)
    return {"success": True, "chat_id": cid, "message": f"Updated TELEGRAM_CHAT_ID to {cid}"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "7860"))
    uvicorn.run("main:app", host="0.0.0.0", port=port)

