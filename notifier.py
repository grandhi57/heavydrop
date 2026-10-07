"""
Telegram notification module.

Sends price-drop alerts and steep discount notifications via the Telegram Bot API using httpx.
Includes cooldown mechanisms to avoid spamming the same alert.
"""

import logging
import os
import time

from dotenv import load_dotenv
import httpx

load_dotenv()

logger = logging.getLogger(__name__)

# Cooldown: don't re-alert for the same product within 6 hours
_COOLDOWN_SECONDS = 6 * 60 * 60
_COOLDOWN_FILE = "cooldowns.json"
_last_alert_times: dict[str, float] = {}  # key -> timestamp

def _load_cooldowns():
    global _last_alert_times
    import json, os
    if os.path.exists(_COOLDOWN_FILE):
        try:
            with open(_COOLDOWN_FILE, "r") as f:
                _last_alert_times = json.load(f)
        except Exception:
            _last_alert_times = {}

def _save_cooldowns():
    import json
    try:
        with open(_COOLDOWN_FILE, "w") as f:
            json.dump(_last_alert_times, f)
    except Exception:
        pass

# Initialize on load
_load_cooldowns()

def _is_on_cooldown(key: str) -> bool:
    """Check if an alert key is still on cooldown."""
    last_time = _last_alert_times.get(key)
    if last_time is None:
        return False
    return (time.time() - last_time) < _COOLDOWN_SECONDS


def _set_cooldown(key: str) -> None:
    """Mark an alert key as recently alerted."""
    _last_alert_times[key] = time.time()
    _save_cooldowns()


async def send_price_alert(
    product_id: int,
    title: str,
    current_price: float,
    target_price: float,
    url: str,
    platform: str,
) -> bool:
    """
    [LEGACY WRAPPER] Send a Telegram alert if a single tracked product price dropped to/below target.
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not bot_token or not chat_id or bot_token == "your_bot_token_here":
        logger.warning("Telegram not configured — skipping alert for product %d", product_id)
        return False

    cooldown_key = f"prod_{product_id}"
    if _is_on_cooldown(cooldown_key):
        logger.info("Product %d is on cooldown — skipping alert", product_id)
        return False

    drop_pct = ((target_price - current_price) / target_price) * 100 if target_price > 0 else 0
    platform_name = platform.capitalize()

    message = (
        f"🔥 <b>-{drop_pct:.1f}% DROP</b> | <b>₹{current_price:,.0f}</b> (Target: ₹{target_price:,.0f})\n\n"
        f"📦 <b>{title}</b>\n\n"
        f"🔗 <a href=\"{url}\">Open on {platform_name}</a>"
    )

    return await _dispatch_telegram(bot_token, chat_id, message, cooldown_key)


async def send_steep_discount_alert(
    title: str,
    effective_price: float,
    previous_price: float | None,
    mrp: float | None,
    wow_price: float | None,
    regular_price: float | None,
    url: str,
    drop_pct: float,
    pid: str,
    name: str = "",
    cpu: str = "",
    ram: str = "",
    ssd: str = "",
    gpu: str = "",
    exchange_discount: float | None = None,
) -> bool:
    """
    [LEGACY WRAPPER] Send an ultra-minimal Telegram alert for a steep price discount.
    Includes PPD percentage drop, current price, product name, 1-line basic specs, exchange bonus, and direct link.
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not bot_token or not chat_id or bot_token == "your_bot_token_here":
        logger.warning("Telegram not configured — skipping steep discount alert for %s", pid)
        return False

    cooldown_key = f"pid_{pid}"
    if _is_on_cooldown(cooldown_key):
        logger.info("PID %s is on cooldown — skipping steep discount alert", pid)
        return False

    display_name = name or title[:60]

    # Dynamic Category Icons
    icon = "📦"
    combined_text = f"{display_name} {title}".lower()
    if "laptop" in combined_text or "notebook" in combined_text or "macbook" in combined_text:
        icon = "💻"
    elif any(k in combined_text for k in ["ram", "ddr5", "ddr4", "ddr3", "memory", "sdram"]):
        icon = "💾"
    elif "dish" in combined_text or "dishwasher" in combined_text:
        icon = "🍽️"
    elif "washing machine" in combined_text or "washer" in combined_text:
        icon = "🧺"
    elif any(k in combined_text for k in ["tv", "television", "oled", "qled"]):
        icon = "📺"
    elif any(k in combined_text for k in ["refrigerator", "fridge", "freezer"]):
        icon = "❄️"
    elif any(k in combined_text for k in ["phone", "smartphone", "mobile", "iphone", "galaxy"]):
        icon = "📱"
    elif any(k in combined_text for k in ["ssd", "nvme", "hard drive", "storage"]):
        icon = "💽"
    elif any(k in combined_text for k in ["headphone", "earphone", "airpods", "audio", "earbuds"]):
        icon = "🎧"
    elif any(k in combined_text for k in ["watch", "smartwatch"]):
        icon = "⌚"

    # Compact 1-line basic specs
    spec_parts = []
    ignored_placeholders = {
        "standard processor", "processor in title",
        "ram in specs", "storage in specs",
        "integrated graphics", "dishwasher"
    }
    for s in [cpu, ram, ssd, gpu]:
        if not s:
            continue
        s_clean = s.strip()
        if s_clean.lower() in ignored_placeholders:
            continue
        spec_parts.append(s_clean)

    specs_line = f"⚙️ {' • '.join(spec_parts)}\n" if spec_parts else ""

    price_str = f"₹{effective_price:,.0f}"
    was_str = f" (was ₹{previous_price:,.0f})" if previous_price and previous_price > effective_price else ""

    message = (
        f"🔥 <b>-{drop_pct:.1f}% DROP</b> | <b>{price_str}</b>{was_str}\n\n"
        f"{icon} <b>{display_name}</b>\n"
        f"{specs_line}\n"
        f"🔗 <a href=\"{url}\">Open on Flipkart</a>"
    )

    return await _dispatch_telegram(bot_token, chat_id, message, cooldown_key)


async def send_lenovo_deal_alert(
    product_code: str,
    name: str,
    series: str,
    cpu: str,
    ram: str,
    ssd: str,
    gpu: str,
    current_price: float,
    mrp: float | None,
    save_percent: float,
    save_amount: float,
    condition: str,
    url: str,
    vram: str = "",
    is_dedicated_gpu: int = 0,
    alert_reason: str = "",
) -> bool:
    """
    [LEGACY WRAPPER] Send an immediate alert for a Lenovo Outlet deal.
    Formatted for banger deals (>50% off) or significant price drops,
    with top priority visual emphasis on GPU & VRAM.
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not bot_token or not chat_id or bot_token == "your_bot_token_here":
        logger.warning("Telegram not configured — skipping Lenovo deal alert for %s", product_code)
        return False

    header_title = alert_reason or f"🔥 <b>-{save_percent:.0f}% OFF</b> | <b>₹{current_price:,.0f}</b>"

    # Prominent Dedicated GPU Header
    gpu_badge = ""
    if gpu:
        vram_str = f" ({vram})" if vram else ""
        if is_dedicated_gpu:
            gpu_badge = f"🎮 <b>GPU: {gpu}{vram_str} [DEDICATED]</b>"
        else:
            gpu_badge = f"🖥️ GPU: {gpu}{vram_str}"

    # General specs
    spec_items = [s for s in [cpu, ram, ssd] if s]
    specs_str = " • ".join(spec_items) if spec_items else ""

    lines = [
        f"⚡ <b>LENOVO OUTLET BANGER DEAL!</b>",
        f"{header_title}",
        "",
        f"💻 <b>{name}</b>",
    ]
    if gpu_badge:
        lines.append(gpu_badge)
    if specs_str:
        lines.append(f"⚙️ {specs_str}")
    if condition:
        lines.append(f"🏷️ <b>{condition}</b>")

    lines.append("")
    lines.append(f"💰 Deal Price: <b>₹{current_price:,.0f}</b>")
    if mrp and mrp > current_price:
        save_val = save_amount if save_amount > 0 else (mrp - current_price)
        lines.append(f"❌ MRP: <s>₹{mrp:,.0f}</s> (Save ₹{save_val:,.0f})")

    lines.append("")
    lines.append(f"🔗 <a href=\"{url}\">Open on Lenovo Outlet</a>")

    message = "\n".join(lines)
    cooldown_key = f"lenovo_{product_code}_{save_percent:.0f}_{current_price:.0f}"
    return await _dispatch_telegram(bot_token, chat_id, message, cooldown_key)


async def trigger_voice_call(text: str = None) -> dict:
    """
    Trigger a Telegram voice call via CallMeBot.
    The user must have started @CallMeBot_txtbot before this will work.
    
    CallMeBot API: http://api.callmebot.com/start.php?user=@username&text=MESSAGE&lang=en-IN-Standard-D&rpt=2
    
    Returns a dict with 'success' bool and 'error' or 'message'.
    """
    username = os.getenv("CALLMEBOT_TELEGRAM_USER", "").strip()
    if not username:
        return {"success": False, "error": "CALLMEBOT_TELEGRAM_USER not configured in .env"}

    if not text:
        text = (
            "ALERT! Insane laptop deal detected by your deal tracker! "
            "Open Telegram immediately to check the deal before it disappears!"
        )

    import urllib.parse
    encoded_text = urllib.parse.quote(text)
    api_url = (
        f"http://api.callmebot.com/start.php"
        f"?user=@{username}"
        f"&text={encoded_text}"
        f"&lang=en-IN-Standard-D"
        f"&rpt=2"
    )

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(api_url)
            if resp.status_code == 200:
                logger.info("📞 CallMeBot voice call triggered for @%s", username)
                return {"success": True, "message": f"Voice call triggered for @{username}"}
            else:
                logger.warning("📞 CallMeBot returned HTTP %d: %s", resp.status_code, resp.text[:200])
                return {"success": False, "error": f"CallMeBot HTTP {resp.status_code}: {resp.text[:100]}"}
    except Exception as e:
        logger.error("📞 CallMeBot voice call failed: %s", e)
        return {"success": False, "error": str(e)}


async def _dispatch_telegram(
    bot_token: str, chat_id: str, message: str, cooldown_key: str,
    max_retries: int = 3,
    reply_markup: dict = None,
) -> bool:
    """Internal helper to dispatch message to Telegram with exponential backoff retry."""
    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    import asyncio
    delays = [5, 15, 30]  # exponential backoff delays in seconds

    for attempt in range(max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(api_url, json=payload)

                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", delays[min(attempt, len(delays) - 1)]))
                    if attempt < max_retries:
                        logger.warning(
                            "Telegram rate limited (429). Retry-After: %ds. Attempt %d/%d",
                            retry_after, attempt + 1, max_retries
                        )
                        await asyncio.sleep(retry_after)
                        continue
                    else:
                        logger.error("Telegram rate limited after %d retries — giving up", max_retries)
                        return False

                response.raise_for_status()

            _set_cooldown(cooldown_key)
            logger.info("✅ Telegram alert sent (%s)", cooldown_key)
            return True

        except httpx.HTTPStatusError as e:
            if attempt < max_retries and e.response.status_code >= 500:
                delay = delays[min(attempt, len(delays) - 1)]
                logger.warning(
                    "Telegram server error %s. Retrying in %ds (attempt %d/%d)",
                    e.response.status_code, delay, attempt + 1, max_retries
                )
                await asyncio.sleep(delay)
                continue
            logger.error("Telegram API error: %s — %s", e.response.status_code, e.response.text)
            return False
        except Exception as e:
            if attempt < max_retries:
                delay = delays[min(attempt, len(delays) - 1)]
                logger.warning(
                    "Telegram dispatch failed: %s. Retrying in %ds (attempt %d/%d)",
                    e, delay, attempt + 1, max_retries
                )
                await asyncio.sleep(delay)
                continue
            logger.error("Failed to send Telegram alert after %d retries: %s", max_retries, e)
            return False

    return False


# ═══════════════════════════════════════════════════════════════════════════
# Unified Deal Alert — Single entry point for all platforms & signal types
# ═══════════════════════════════════════════════════════════════════════════

def _build_unified_message(deal: dict, signal_type: str) -> str:
    """
    Build a consistent Telegram message from a normalized deal dict.
    
    Signal types: 'price_drop', 'banger', 'discovery', 'all_time_low', 'target_hit'
    """
    platform = deal.get("platform", "Unknown")
    
    # === Header: Signal Badge + Price ===
    effective_price = deal.get("effective_price") or deal.get("current_price", 0)
    discount_pct = deal.get("discount_pct", 0) or deal.get("save_percent", 0)
    previous_price = deal.get("previous_price")
    mrp = deal.get("mrp")
    
    price_str = f"₹{effective_price:,.0f}"
    was_str = ""
    ref = previous_price or mrp
    if ref and ref > effective_price:
        was_str = f" (was ₹{ref:,.0f})"
    
    import math
    disc_floored = math.floor(float(discount_pct or 0.0) * 10.0) / 10.0
    disc_str = f"{disc_floored:.1f}"

    signal_badges = {
        "price_drop": f"🔻 <b>-{disc_str}% DROP</b> | <b>{price_str}</b>{was_str}",
        "banger": f"🔥 <b>-{disc_str}% BANGER</b> | <b>{price_str}</b>{was_str}",
        "gpu_deal": f"🎮 <b>-{disc_str}% GPU DEAL</b> | <b>{price_str}</b>{was_str}",
        "lenovo_deal": f"⚡ <b>-{disc_str}% LENOVO DEAL</b> | <b>{price_str}</b>{was_str}",
        "discovery": f"🆕 <b>NEW DEAL: -{disc_str}%</b> | <b>{price_str}</b>{was_str}",
        "all_time_low": f"📉 <b>ALL-TIME LOW</b> | <b>{price_str}</b>{was_str}",
        "target_hit": f"🎯 <b>TARGET HIT!</b> | <b>{price_str}</b>{was_str}",
        "insane_deal": f"🚨 <b>INSANE DEAL</b> | <b>{price_str}</b>{was_str}",
        "great_deal": f"⚡ <b>GREAT VALUE</b> | <b>{price_str}</b>{was_str}",
    }
    header = signal_badges.get(signal_type, f"🔔 <b>Deal Alert</b> | <b>{price_str}</b>")
    
    # === Product Name ===
    display_name = deal.get("name") or deal.get("title", "Unknown Product")
    if len(display_name) > 70:
        display_name = display_name[:67] + "..."
    
    # === Dynamic Category Icon ===
    icon = "📦"
    combined_text = f"{display_name}".lower()
    if "laptop" in combined_text or "notebook" in combined_text or "macbook" in combined_text:
        icon = "💻"
    elif any(k in combined_text for k in ["ram", "ddr5", "ddr4", "ddr3", "memory", "sdram"]):
        icon = "💾"
    elif "dish" in combined_text or "dishwasher" in combined_text:
        icon = "🍽️"
    elif any(k in combined_text for k in ["ssd", "nvme", "hard drive", "storage"]):
        icon = "💽"
    elif any(k in combined_text for k in ["tv", "television", "oled", "qled"]):
        icon = "📺"
    elif any(k in combined_text for k in ["phone", "smartphone", "mobile", "iphone"]):
        icon = "📱"
    elif any(k in combined_text for k in ["sofa", "furniture", "ikea", "modular"]):
        icon = "🛋️"
    elif any(k in combined_text for k in ["headphone", "earphone", "earbuds", "airpods"]):
        icon = "🎧"
    elif any(k in combined_text for k in ["watch", "smartwatch"]):
        icon = "⌚"
    elif any(k in combined_text for k in ["refrigerator", "fridge"]):
        icon = "❄️"
    elif any(k in combined_text for k in ["washing machine", "washer"]):
        icon = "🧺"
    
    # === Specs Line ===
    spec_parts = []
    ignored_placeholders = {
        "standard processor", "processor in title",
        "ram in specs", "storage in specs",
        "integrated graphics", "dishwasher"
    }
    for key in ["cpu", "ram", "ssd", "gpu"]:
        s = deal.get(key, "")
        if not s:
            continue
        s_clean = s.strip()
        if s_clean.lower() in ignored_placeholders:
            continue
        spec_parts.append(s_clean)
    
    # GPU/VRAM emphasis for Lenovo
    vram = deal.get("vram", "")
    is_dedicated = deal.get("is_dedicated_gpu", 0)
    gpu_val = deal.get("gpu", "")
    gpu_line = ""
    if gpu_val and platform.lower() in ["lenovo", "lenovo outlet"]:
        vram_str = f" ({vram})" if vram else ""
        if is_dedicated:
            gpu_line = f"🎮 <b>GPU: {gpu_val}{vram_str} [DEDICATED]</b>\n"
        elif "radeon" in gpu_val.lower():
            gpu_line = f"⚡ <b>GPU: {gpu_val}{vram_str} [AMD RADEON]</b>\n"
        else:
            gpu_line = f"🖥️ <b>GPU: {gpu_val}{vram_str}</b>\n"
    
    specs_line = f"⚙️ {' • '.join(spec_parts)}\n" if spec_parts else ""
    
    # === Condition badge (Lenovo refurbished) ===
    condition = deal.get("condition", "")
    condition_line = f"🏷️ <b>{condition}</b>\n" if condition and "REFURBISHED" in condition.upper() else ""
    
    # === Savings line ===
    savings_line = ""
    if mrp and mrp > effective_price:
        save_amount = mrp - effective_price
        savings_line = f"💰 Save ₹{save_amount:,.0f} off MRP ₹{mrp:,.0f}\n"
    
    # === Platform & recency ===
    # Normalize platform name
    platform_display = {
        "flipkart": "Flipkart",
        "lenovo": "Lenovo Outlet",
        "lenovo outlet": "Lenovo Outlet",
        "ikea": "IKEA",
        "amazon": "Amazon",
    }.get(platform.lower(), platform)
    
    # === Direct link ===
    url = deal.get("url", "")
    link_line = f"🔗 <a href=\"{url}\">Open on {platform_display}</a>" if url else ""
    
    # === Assemble ===
    lines = [
        header,
        "",
        f"{icon} <b>{display_name}</b>",
    ]
    if gpu_line:
        lines.append(gpu_line.rstrip())
    if specs_line:
        lines.append(specs_line.rstrip())
    if condition_line:
        lines.append(condition_line.rstrip())
    if savings_line:
        lines.append(savings_line.rstrip())
    
    lines.append(f"📍 {platform_display}")
    lines.append("")
    if link_line:
        lines.append(link_line)
    
    return "\n".join(lines)


async def send_deal_alert(
    deal: dict,
    signal_type: str = "price_drop",
    platform: str = "flipkart",
) -> bool:
    """
    Unified deal alert — single entry point for all platforms and signal types.
    
    Args:
        deal: Normalized deal dict with keys like effective_price/current_price, name, title,
              cpu, ram, ssd, gpu, url, mrp, discount_pct/save_percent, etc.
        signal_type: One of 'price_drop', 'banger', 'discovery', 'all_time_low', 'target_hit'
        platform: Platform name for display (flipkart, lenovo, ikea, amazon)
    
    Returns:
        True if alert was sent successfully.
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    
    if not bot_token or not chat_id or bot_token == "your_bot_token_here":
        logger.warning("Telegram not configured — skipping %s alert", signal_type)
        return False
    
    # Build cooldown key from deal identifiers
    pid = deal.get("pid") or deal.get("product_code") or deal.get("id", "unknown")
    price = deal.get("effective_price") or deal.get("current_price", 0)
    cooldown_key = f"{platform}_{signal_type}_{pid}"
    
    if _is_on_cooldown(cooldown_key):
        logger.info("Deal %s (%s) is on cooldown — skipping", pid, signal_type)
        return False
    
    # Enrich deal with platform for message builder
    deal_enriched = dict(deal)
    deal_enriched["platform"] = platform
    
    message = _build_unified_message(deal_enriched, signal_type)
    
    reply_markup = None
    if signal_type == "insane_deal":
        reply_markup = {
            "inline_keyboard": [[
                {"text": "✅ Acknowledge (Stop Pinging)", "callback_data": f"ack_{pid}"}
            ]]
        }
    
    sent = await _dispatch_telegram(
        bot_token, chat_id, message, cooldown_key, reply_markup=reply_markup
    )
    
    # Log notification (async, best-effort)
    try:
        from database import log_notification
        preview = f"{signal_type}: {deal.get('name', '')[:50]} @ ₹{price:,.0f}"
        await log_notification(
            deal_key=str(pid),
            platform=platform,
            signal_type=signal_type,
            message_preview=preview,
            status="sent" if sent else "failed",
        )
    except Exception as log_err:
        logger.debug("Notification logging failed (non-critical): %s", log_err)
    
    # Queue for retry if failed
    if not sent:
        try:
            from database import queue_failed_alert
            await queue_failed_alert(
                deal_key=str(pid),
                platform=platform,
                signal_type=signal_type,
                payload=deal_enriched,
            )
            logger.info("Queued failed alert for retry: %s %s", signal_type, pid)
        except Exception as q_err:
            logger.debug("Alert queue failed (non-critical): %s", q_err)
    
    return sent


async def send_daily_digest(deals: list[dict]) -> bool:
    """
    Send a compact daily digest of top active deals to Telegram.
    
    Args:
        deals: List of deal dicts from get_digest_deals(), expected to be sorted by hot_score.
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    
    if not bot_token or not chat_id or bot_token == "your_bot_token_here":
        logger.warning("Telegram not configured — skipping daily digest")
        return False
    
    if not deals:
        logger.info("No deals for digest — skipping")
        return False
    
    # Count signal types
    fresh_count = sum(1 for d in deals if d.get("is_fresh"))
    banger_count = sum(1 for d in deals if d.get("is_banger"))
    
    lines = [
        f"🗞️ <b>Deal Digest — Top {len(deals)} Active Deals</b>",
        f"🔥 {banger_count} bangers • ⚡ {fresh_count} fresh drops",
        "",
    ]
    
    for i, deal in enumerate(deals[:15], 1):
        name = deal.get("name") or deal.get("title", "?")[:40]
        price = deal.get("effective_price") or deal.get("current_price", 0)
        disc = deal.get("discount_pct", 0) or deal.get("save_percent", 0)
        platform = deal.get("platform", "")
        url = deal.get("url", "")
        
        is_fresh = "⚡" if deal.get("is_fresh") else ""
        is_banger = "🔥" if deal.get("is_banger") else ""
        badges = f"{is_fresh}{is_banger}" or "•"
        
        if url:
            lines.append(f"{badges} <b>-{disc:.0f}%</b> ₹{price:,.0f} — <a href=\"{url}\">{name[:35]}</a>")
        else:
            lines.append(f"{badges} <b>-{disc:.0f}%</b> ₹{price:,.0f} — {name[:35]}")
    
    if len(deals) > 15:
        lines.append(f"\n... and {len(deals) - 15} more deals on the dashboard")
    
    lines.append("\n🌐 <a href=\"http://127.0.0.1:8000\">Open Dashboard</a>")
    
    message = "\n".join(lines)
    return await _dispatch_telegram(bot_token, chat_id, message, f"digest_{time.strftime('%Y%m%d_%H')}")


async def auto_detect_chat_id() -> dict:
    """
    Polls getUpdates from the Telegram Bot API to automatically detect the
    chat ID of the user who recently messaged or started the bot.
    If found, updates the in-memory environment and writes to .env.
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not bot_token or bot_token == "your_bot_token_here":
        return {"success": False, "error": "TELEGRAM_BOT_TOKEN is not configured in .env"}

    api_url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(api_url)
            resp.raise_for_status()
            data = resp.json()

        updates = data.get("result", [])
        if not updates:
            return {
                "success": False,
                "error": "No incoming messages found yet. Please open Telegram, search for @Heaviest_drop_ever_bot, and press 'Start' or send a message, then try again."
            }

        # Look for the newest message with chat information
        latest_update = updates[-1]
        msg = latest_update.get("message") or latest_update.get("channel_post") or latest_update.get("my_chat_member")
        if not msg or "chat" not in msg:
            return {"success": False, "error": "No valid chat found in recent updates."}

        detected_id = str(msg["chat"]["id"])
        user_name = msg["chat"].get("first_name") or msg["chat"].get("title") or msg["chat"].get("username") or "User"

        # Update environment and save to .env
        os.environ["TELEGRAM_CHAT_ID"] = detected_id
        env_path = os.path.join(os.path.dirname(__file__), ".env")
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                content = f.read()
            import re
            content = re.sub(r"^TELEGRAM_CHAT_ID=.*$", f"TELEGRAM_CHAT_ID={detected_id}", content, flags=re.MULTILINE)
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(content)

        return {
            "success": True,
            "chat_id": detected_id,
            "user_name": user_name,
            "message": f"Successfully detected Chat ID {detected_id} ({user_name}) and saved to .env!"
        }

    except Exception as e:
        return {"success": False, "error": f"Failed to poll Telegram updates: {e}"}


async def send_test_alert(custom_chat_id: str | None = None) -> tuple[bool, str]:
    """Send a realistic test alert to Telegram to verify the connection and format."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = (custom_chat_id or os.getenv("TELEGRAM_CHAT_ID", "")).strip()

    if not bot_token or bot_token == "your_bot_token_here":
        return False, "TELEGRAM_BOT_TOKEN is not configured in .env"

    # If chat_id is currently set to the bot username (@..._bot), attempt auto-detection first
    if not chat_id or chat_id.lower().endswith("_bot") or chat_id == "@Heaviest_drop_ever_bot":
        detection = await auto_detect_chat_id()
        if detection.get("success"):
            chat_id = detection["chat_id"]
        else:
            return False, (
                "Notice: TELEGRAM_CHAT_ID in .env is currently set to '@Heaviest_drop_ever_bot' (which is the bot itself). "
                "Telegram bots cannot message themselves! "
                "Please open Telegram, open https://t.me/Heaviest_drop_ever_bot, and tap 'Start' (or send 'hi'). "
                "Then click 'Test Telegram' again — it will automatically detect your personal chat ID!"
            )

    sample_message = (
        "🔥 <b>-18.5% DROP</b> | <b>₹1,35,800</b> (was ₹1,66,490)\n\n"
        "💻 <b>DELL Alienware 15 Gaming Laptop</b>\n"
        "⚙️ AMD Ryzen 7 • 16GB • 512GB SSD • RTX 4050\n\n"
        "🔗 <a href=\"https://www.flipkart.com\">Open on Flipkart</a>\n\n"
        "<i>(Test notification — bot connected & minimal template active!)</i>"
    )

    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": sample_message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(api_url, json=payload)
            if resp.status_code == 403 and "bot can't send messages to the bot" in resp.text:
                return False, (
                    "Forbidden: The bot cannot message itself. "
                    "Please message @Heaviest_drop_ever_bot on Telegram first so it can message you!"
                )
            resp.raise_for_status()
        return True, f"✅ Test notification sent successfully to Telegram chat {chat_id}!"
    except Exception as e:
        return False, f"Telegram API error: {e}"


async def send_test_message(text: str = "🏓 Deal Tracker is connected!") -> bool:
    """Send a simple test message to verify Telegram config."""
    ok, _ = await send_test_alert()
    return ok
