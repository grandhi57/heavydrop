"""
SQLite database layer using aiosqlite for async access.
Manages:
1. Individual tracked products and price history.
2. Tracked category/search listings (Flipkart Laptops) with parsed specs (CPU, RAM, SSD, GPU) and WoW prices.
"""

import aiosqlite
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "deal_tracker.db"


async def get_db() -> aiosqlite.Connection:
    """Get an async database connection with row factory enabled."""
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db():
    """Create tables if they don't exist and run column migrations."""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")

        # ── Single Product Tracker Tables ─────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                url         TEXT    UNIQUE NOT NULL,
                title       TEXT    DEFAULT '',
                image_url   TEXT    DEFAULT '',
                current_price REAL  DEFAULT NULL,
                target_price  REAL  NOT NULL,
                platform    TEXT    NOT NULL DEFAULT 'unknown',
                last_checked TEXT   DEFAULT NULL,
                created_at  TEXT    NOT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id  INTEGER NOT NULL,
                price       REAL    NOT NULL,
                checked_at  TEXT    NOT NULL,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            )
        """)

        # ── Listing / Category Tracker Tables ─────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS listings (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                url                     TEXT    UNIQUE NOT NULL,
                title                   TEXT    DEFAULT '',
                category                TEXT    DEFAULT 'laptops',
                discount_threshold_pct  REAL    DEFAULT 10.0,
                last_scraped            TEXT    DEFAULT NULL,
                total_items             INTEGER DEFAULT 0,
                created_at              TEXT    NOT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS listing_products (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id      INTEGER NOT NULL,
                pid             TEXT    UNIQUE NOT NULL,
                name            TEXT    DEFAULT '',
                title           TEXT    NOT NULL,
                cpu             TEXT    DEFAULT '',
                ram             TEXT    DEFAULT '',
                ssd             TEXT    DEFAULT '',
                gpu             TEXT    DEFAULT '',
                url             TEXT    NOT NULL,
                image_url       TEXT    DEFAULT '',
                mrp             REAL    DEFAULT NULL,
                regular_price   REAL    DEFAULT NULL,
                wow_price       REAL    DEFAULT NULL,
                effective_price REAL    NOT NULL,
                previous_price  REAL    DEFAULT NULL,
                discount_pct    REAL    DEFAULT 0.0,
                last_alerted_price REAL DEFAULT NULL,
                last_alerted_at TEXT    DEFAULT NULL,
                last_updated    TEXT    NOT NULL,
                FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE
            )
        """)

        # Auto-migrate columns if table already existed
        cols_needed = [
            ("name", "TEXT DEFAULT ''"),
            ("cpu", "TEXT DEFAULT ''"),
            ("ram", "TEXT DEFAULT ''"),
            ("ssd", "TEXT DEFAULT ''"),
            ("gpu", "TEXT DEFAULT ''"),
            ("last_alerted_price", "REAL DEFAULT NULL"),
            ("last_alerted_at", "TEXT DEFAULT NULL"),
            ("exchange_discount", "REAL DEFAULT NULL"),
            ("vram", "TEXT DEFAULT ''"),
            ("is_dedicated_gpu", "INTEGER DEFAULT 0"),
        ]
        for col, col_def in cols_needed:
            try:
                await db.execute(f"ALTER TABLE listing_products ADD COLUMN {col} {col_def}")
            except Exception:
                pass  # Column already exists

        # Multi-signal notification schema additions
        new_listing_cols = [
            ("historical_low", "REAL DEFAULT NULL"),
            ("reference_discount_pct", "REAL DEFAULT 0.0"),
            ("first_seen_at", "TEXT DEFAULT NULL"),
        ]
        for col, col_def in new_listing_cols:
            try:
                await db.execute(f"ALTER TABLE listing_products ADD COLUMN {col} {col_def}")
            except Exception:
                pass

        await db.execute("""
            CREATE TABLE IF NOT EXISTS listing_price_history (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                pid             TEXT    NOT NULL,
                regular_price   REAL    DEFAULT NULL,
                wow_price       REAL    DEFAULT NULL,
                effective_price REAL    NOT NULL,
                recorded_at     TEXT    NOT NULL
            )
        """)

        # ── Lenovo Outlet Tracker Tables ──────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS lenovo_products (
                id                          INTEGER PRIMARY KEY AUTOINCREMENT,
                product_code                TEXT    UNIQUE NOT NULL,
                name                        TEXT    NOT NULL,
                series                      TEXT    DEFAULT '',
                cpu                         TEXT    DEFAULT '',
                ram                         TEXT    DEFAULT '',
                ssd                         TEXT    DEFAULT '',
                gpu                         TEXT    DEFAULT '',
                vram                        TEXT    DEFAULT '',
                is_dedicated_gpu            INTEGER DEFAULT 0,
                current_price               REAL    NOT NULL,
                mrp                         REAL    DEFAULT NULL,
                save_percent                REAL    DEFAULT 0.0,
                save_amount                 REAL    DEFAULT 0.0,
                condition                   TEXT    DEFAULT 'CERTIFIED REFURBISHED',
                url                         TEXT    NOT NULL,
                in_stock                    INTEGER DEFAULT 1,
                first_seen_at               TEXT    NOT NULL,
                last_scanned_at             TEXT    NOT NULL,
                last_alerted_price          REAL    DEFAULT NULL,
                last_alerted_discount_pct   REAL    DEFAULT NULL,
                last_alerted_at             TEXT    DEFAULT NULL
            )
        """)

        for col, col_def in [("vram", "TEXT DEFAULT ''"), ("is_dedicated_gpu", "INTEGER DEFAULT 0")]:
            try:
                await db.execute(f"ALTER TABLE lenovo_products ADD COLUMN {col} {col_def}")
            except Exception:
                pass

        # Historical low tracking for Lenovo
        for col, col_def in [("historical_low", "REAL DEFAULT NULL")]:
            try:
                await db.execute(f"ALTER TABLE lenovo_products ADD COLUMN {col} {col_def}")
            except Exception:
                pass

        # Listing health & pause support
        new_listings_cols = [
            ("is_paused", "INTEGER DEFAULT 0"),
            ("scrape_status", "TEXT DEFAULT 'ok'"),
            ("consecutive_failures", "INTEGER DEFAULT 0"),
            ("last_error", "TEXT DEFAULT NULL"),
        ]
        for col, col_def in new_listings_cols:
            try:
                await db.execute(f"ALTER TABLE listings ADD COLUMN {col} {col_def}")
            except Exception:
                pass

        await db.execute("""
            CREATE TABLE IF NOT EXISTS lenovo_price_history (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                product_code    TEXT    NOT NULL,
                price           REAL    NOT NULL,
                save_percent    REAL    NOT NULL,
                recorded_at     TEXT    NOT NULL
            )
        """)

        # ── Notification System Tables ────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS alert_queue (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                deal_key        TEXT    NOT NULL,
                platform        TEXT    NOT NULL,
                signal_type     TEXT    NOT NULL,
                payload_json    TEXT    NOT NULL,
                created_at      TEXT    NOT NULL,
                status          TEXT    DEFAULT 'pending',
                retry_count     INTEGER DEFAULT 0,
                last_retry_at   TEXT    DEFAULT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS notification_log (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                deal_key        TEXT    NOT NULL,
                platform        TEXT    NOT NULL,
                signal_type     TEXT    NOT NULL,
                message_preview TEXT    DEFAULT '',
                sent_at         TEXT    NOT NULL,
                status          TEXT    NOT NULL DEFAULT 'sent'
            )
        """)

        await db.commit()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _detect_platform(url: str) -> str:
    url_lower = url.lower()
    if "amazon" in url_lower:
        return "amazon"
    elif "flipkart" in url_lower:
        return "flipkart"
    return "unknown"


# ═══════════════════════════════════════════════════════════════════════════
# Single Product Operations
# ═══════════════════════════════════════════════════════════════════════════

async def add_product(url: str, target_price: float) -> dict:
    platform = _detect_platform(url)
    now = _now_iso()
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO products (url, target_price, platform, created_at)
               VALUES (?, ?, ?, ?)""",
            (url.strip(), target_price, platform, now),
        )
        await db.commit()
        product_id = cursor.lastrowid
        row = await db.execute_fetchall(
            "SELECT * FROM products WHERE id = ?", (product_id,)
        )
        return dict(row[0]) if row else {}
    finally:
        await db.close()


async def get_all_products() -> list[dict]:
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT * FROM products ORDER BY created_at DESC"
        )
        products = [dict(r) for r in rows]
        if products:
            pids = [p["id"] for p in products]
            placeholders = ",".join("?" for _ in pids)
            history_rows = await db.execute_fetchall(
                f"""
                SELECT product_id, price, checked_at
                FROM (
                    SELECT product_id, price, checked_at,
                           ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY id DESC) as rn
                    FROM price_history
                    WHERE product_id IN ({placeholders})
                ) WHERE rn <= 10
                ORDER BY product_id, checked_at ASC
                """,
                pids,
            )
            h_map = {}
            for hr in history_rows:
                h = dict(hr)
                h["effective_price"] = h["price"]
                h["recorded_at"] = h["checked_at"]
                pid = h["product_id"]
                if pid not in h_map:
                    h_map[pid] = []
                h_map[pid].append(h)
            for p in products:
                p["price_history"] = h_map.get(p["id"], [])
        return products
    finally:
        await db.close()


async def get_product(product_id: int) -> dict | None:
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT * FROM products WHERE id = ?", (product_id,)
        )
        return dict(rows[0]) if rows else None
    finally:
        await db.close()


async def update_product_price(
    product_id: int,
    price: float,
    title: str = "",
    image_url: str = "",
) -> None:
    now = _now_iso()
    db = await get_db()
    try:
        await db.execute(
            """UPDATE products
               SET current_price = ?, title = ?, image_url = ?, last_checked = ?
               WHERE id = ?""",
            (price, title, image_url, now, product_id),
        )
        await db.commit()
    finally:
        await db.close()


async def add_price_history(product_id: int, price: float) -> None:
    now = _now_iso()
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO price_history (product_id, price, checked_at) VALUES (?, ?, ?)",
            (product_id, price, now),
        )
        await db.commit()
    finally:
        await db.close()


async def get_price_history(product_id: int, limit: int = 50) -> list[dict]:
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            """SELECT * FROM price_history
               WHERE product_id = ?
               ORDER BY checked_at DESC
               LIMIT ?""",
            (product_id, limit),
        )
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def delete_product(product_id: int) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute(
            "DELETE FROM products WHERE id = ?", (product_id,)
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


def infer_listing_meta(url: str) -> tuple[str, str]:
    """
    Automatically deduce a clean title and normalized category from any Flipkart or e-commerce URL.
    Examples:
      - search?q=dish+washer&...8+Place+Settings -> ("Flipkart 8 Place Settings Dish Washer", "dish_washer")
      - search?q=ram&...DDR5 -> ("Flipkart DDR5 RAM", "ram")
      - search?q=laptop -> ("Flipkart Laptops", "laptops")
    """
    import re
    from urllib.parse import urlparse, parse_qs, unquote
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)

    # 1. Extract main query
    q = (qs.get("q", [""])[0]).replace("+", " ").strip()

    # 2. Extract facet/filter info if present
    facets = qs.get("p[]", [])
    facet_desc = []
    for f in facets:
        f_clean = unquote(f)
        if "=" in f_clean:
            val = f_clean.split("=")[-1].replace("+", " ").strip()
            if val and val.lower() not in [x.lower() for x in facet_desc]:
                facet_desc.append(val)

    extra = " ".join(facet_desc).strip()

    if not q:
        # Check path (e.g. /laptops/pr, /televisions/pr, /dishwashers/pr)
        path_parts = [p for p in parsed.path.split("/") if p and p != "pr" and p != "search"]
        if path_parts:
            q = path_parts[0].replace("-", " ")

    q_lower = q.lower()
    if "laptop" in q_lower or "notebook" in q_lower:
        cat = "laptops"
    elif "ssd" in q_lower or "nvme" in q_lower or "solid state" in q_lower:
        cat = "ssd"
    elif "ram" in q_lower or "ddr" in q_lower or "memory" in q_lower:
        cat = "ram"
    elif "dish" in q_lower or "washer" in q_lower:
        cat = "dish_washer"
    elif "tv" in q_lower or "television" in q_lower:
        cat = "tv"
    elif "washing machine" in q_lower:
        cat = "washing_machine"
    elif "phone" in q_lower or "mobile" in q_lower:
        cat = "smartphone"
    elif "refrigerator" in q_lower or "fridge" in q_lower:
        cat = "refrigerator"
    else:
        cat = re.sub(r"[^a-z0-9_]+", "_", q_lower).strip("_") or "general"

    title_parts = ["Flipkart"]
    if extra:
        title_parts.append(extra)
    if q:
        title_parts.append(q.upper() if len(q) <= 4 else q.title())
    else:
        title_parts.append("Products")

    title = " ".join(title_parts).strip()
    # Normalize common hardware acronyms in title
    acronyms = {"Ssd": "SSD", "Nvme": "NVMe", "Pcie": "PCIe", "Ram": "RAM", "Ddr5": "DDR5", "Ddr4": "DDR4"}
    for wrong, right in acronyms.items():
        title = re.sub(rf"\b{wrong}\b", right, title)
    return title, cat


async def add_listing(url: str, title: str = "", category: str = "", discount_threshold_pct: float = 10.0) -> dict:
    now = _now_iso()
    inferred_title, inferred_cat = infer_listing_meta(url)
    if not title:
        title = inferred_title
    if not category or category == "laptops":
        category = inferred_cat

    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO listings (url, title, category, discount_threshold_pct, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (url.strip(), title.strip(), category.strip(), discount_threshold_pct, now),
        )
        await db.commit()
        listing_id = cursor.lastrowid
        rows = await db.execute_fetchall("SELECT * FROM listings WHERE id = ?", (listing_id,))
        return dict(rows[0]) if rows else {}
    finally:
        await db.close()


async def get_all_listings() -> list[dict]:
    db = await get_db()
    try:
        rows = await db.execute_fetchall("SELECT * FROM listings ORDER BY created_at DESC")
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_listing(listing_id: int) -> dict | None:
    db = await get_db()
    try:
        rows = await db.execute_fetchall("SELECT * FROM listings WHERE id = ?", (listing_id,))
        return dict(rows[0]) if rows else None
    finally:
        await db.close()


async def delete_listing(listing_id: int) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute("DELETE FROM listings WHERE id = ?", (listing_id,))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def save_listing_products(
    listing_id: int,
    items: list[dict],
    threshold_pct: float = 10.0,
) -> list[dict]:
    """
    Save or update harvested laptops for a listing including specs.
    Compares against the immediately preceding scan price in the DB.
    Prevents duplicate triggering by checking last_alerted_price and last_alerted_at.
    Returns items that experienced a steep discount (drop >= threshold_pct).
    """
    now = _now_iso()
    steep_discount_items = []
    db = await get_db()

    try:
        pids = [item["pid"] for item in items]
        if not pids:
            return []

        # Bulk fetch existing
        placeholders = ",".join(["?"] * len(pids))
        existing_rows = await db.execute_fetchall(
            f"SELECT * FROM listing_products WHERE pid IN ({placeholders})", pids
        )
        existing_map = {row["pid"]: dict(row) for row in existing_rows}

        inserts = []
        updates = []
        history_inserts = []

        for item in items:
            pid = item["pid"]
            name = item.get("name") or item["title"][:50]
            title = item["title"]
            cpu = item.get("cpu", "")
            ram = item.get("ram", "")
            ssd = item.get("ssd", "")
            gpu = item.get("gpu", "")
            url = item["url"]
            image_url = item.get("image_url", "")
            mrp = item.get("mrp")
            regular_price = item.get("regular_price")
            wow_price = item.get("wow_price")
            effective_price = item["effective_price"]
            exchange_discount = item.get("exchange_discount")

            if not effective_price or effective_price < 200 or effective_price > 800000:
                continue

            drop_pct = 0.0
            row = existing_map.get(pid)

            if row:
                old_effective = row["effective_price"]
                last_alerted_price = row["last_alerted_price"]
                last_alerted_at = row["last_alerted_at"]
                prev_discount_pct = row["discount_pct"] or 0.0
                prev_recorded_prev = row["previous_price"]

                ref_price = max(p for p in [mrp, regular_price] if p and p > effective_price) if any(p and p > effective_price for p in [mrp, regular_price]) else None
                ref_disc = round(((ref_price - effective_price) / ref_price) * 100, 1) if ref_price and ref_price > effective_price else 0.0

                scan_drop_pct = 0.0
                if old_effective and effective_price < old_effective:
                    scan_drop_pct = round(((old_effective - effective_price) / old_effective) * 100, 1)

                cum_drop_pct = 0.0
                if last_alerted_price and effective_price < last_alerted_price:
                    cum_drop_pct = round(((last_alerted_price - effective_price) / last_alerted_price) * 100, 1)

                existing_hist_low = row.get("historical_low") if row.get("historical_low") else effective_price
                new_hist_low = min(existing_hist_low, effective_price)
                is_all_time_low = effective_price < existing_hist_low if existing_hist_low else False
                
                should_alert = False
                signal_type = "price_drop"
                alert_reason = ""
                
                if ref_disc >= 50.0 and (last_alerted_price is None or effective_price < last_alerted_price):
                    should_alert = True
                    signal_type = "banger"
                    alert_reason = f"🔥 BANGER: {ref_disc:.0f}% off reference price"
                elif is_all_time_low and (last_alerted_price is None or effective_price < last_alerted_price):
                    should_alert = True
                    signal_type = "all_time_low"
                    alert_reason = f"📉 ALL-TIME LOW: ₹{effective_price:,.0f}"
                elif scan_drop_pct >= threshold_pct or cum_drop_pct >= threshold_pct:
                    should_alert = True
                    signal_type = "price_drop"
                    drop_val = max(scan_drop_pct, cum_drop_pct)
                    alert_reason = f"🔻 Price Drop: -{drop_val:.0f}%"
                    
                if should_alert:
                    alert_item = dict(item)
                    alert_item["previous_price"] = old_effective
                    alert_item["discount_pct"] = ref_disc if signal_type == "banger" else max(scan_drop_pct, cum_drop_pct)
                    alert_item["signal_type"] = signal_type
                    alert_item["alert_reason"] = alert_reason
                    steep_discount_items.append(alert_item)

                if old_effective and effective_price <= old_effective:
                    drop_pct = scan_drop_pct or prev_discount_pct
                    prev_price = prev_recorded_prev or old_effective
                else:
                    drop_pct = 0.0
                    prev_price = old_effective

                updates.append((
                    name, title, cpu, ram, ssd, gpu,
                    effective_price, prev_price, mrp, wow_price, regular_price, drop_pct, exchange_discount,
                    url, image_url, now, new_hist_low, ref_disc, pid, listing_id
                ))

                if old_effective != effective_price or row.get("regular_price") != regular_price or row.get("wow_price") != wow_price:
                    history_inserts.append((pid, regular_price, wow_price, effective_price, now))

            else:
                ref_price = max(p for p in [mrp, regular_price] if p and p > effective_price) if any(p and p > effective_price for p in [mrp, regular_price]) else None
                ref_disc = round(((ref_price - effective_price) / ref_price) * 100, 1) if ref_price and ref_price > effective_price else 0.0

                if ref_disc >= 50.0:
                    banger_item = dict(item)
                    banger_item["previous_price"] = None
                    banger_item["discount_pct"] = ref_disc
                    banger_item["signal_type"] = "banger"
                    banger_item["alert_reason"] = f"🔥 BANGER: {ref_disc:.0f}% off reference price"
                    steep_discount_items.append(banger_item)
                elif ref_disc >= 25.0:
                    discovery_item = dict(item)
                    discovery_item["previous_price"] = None
                    discovery_item["discount_pct"] = ref_disc
                    discovery_item["signal_type"] = "discovery"
                    discovery_item["alert_reason"] = f"🆕 NEW DEAL: {ref_disc:.0f}% off reference price"
                    steep_discount_items.append(discovery_item)

                inserts.append((
                    listing_id, pid, name, title, cpu, ram, ssd, gpu, url, image_url, mrp,
                    regular_price, wow_price, effective_price, None, 0.0,
                    exchange_discount, effective_price, ref_disc, now, now
                ))
                history_inserts.append((pid, regular_price, wow_price, effective_price, now))

        if inserts:
            await db.executemany(
                """INSERT INTO listing_products
                   (listing_id, pid, name, title, cpu, ram, ssd, gpu, url, image_url, mrp,
                    regular_price, wow_price, effective_price, previous_price, discount_pct,
                    exchange_discount, historical_low, reference_discount_pct, first_seen_at, last_updated)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                inserts
            )
            
        if updates:
            await db.executemany(
                """UPDATE listing_products
                   SET name = ?, title = ?, cpu = ?, ram = ?, ssd = ?, gpu = ?,
                       effective_price = ?, previous_price = ?, mrp = ?, wow_price = ?, regular_price = ?, discount_pct = ?, exchange_discount = ?,
                       url = ?, image_url = ?, last_updated = ?, historical_low = ?, reference_discount_pct = ?
                   WHERE pid = ? AND listing_id = ?""",
                updates
            )

        if history_inserts:
            await db.executemany(
                """INSERT INTO listing_price_history (pid, regular_price, wow_price, effective_price, recorded_at)
                   VALUES (?, ?, ?, ?, ?)""",
                history_inserts
            )

        await db.execute(
            "UPDATE listings SET last_scraped = ?, total_items = (SELECT COUNT(*) FROM listing_products WHERE listing_id = ?) WHERE id = ?",
            (now, listing_id, listing_id)
        )

        await db.commit()
        return steep_discount_items

    finally:
        await db.close()


async def record_listing_alert(pid: str, price: float):
    """Mark a listing product as having had an alert sent at this price."""
    now = _now_iso()
    db = await get_db()
    try:
        await db.execute(
            """UPDATE listing_products
               SET last_alerted_price = ?, last_alerted_at = ?
               WHERE pid = ?""",
            (price, now, pid),
        )
        await db.commit()
    finally:
        await db.close()


async def update_listing_product_price(
    pid: str,
    effective_price: float,
    regular_price: float = None,
    wow_price: float = None,
    discount_pct: float = 0.0,
):
    """Correct a listing product's price and reset discount_pct in DB after PDP verification."""
    now = _now_iso()
    db = await get_db()
    try:
        await db.execute(
            """UPDATE listing_products
               SET effective_price = ?, regular_price = COALESCE(?, regular_price),
                   wow_price = ?, discount_pct = ?, last_updated = ?
               WHERE pid = ?""",
            (effective_price, regular_price, wow_price, discount_pct, now, pid),
        )
        await db.commit()
    finally:
        await db.close()


async def get_listing_product_effective_price(pid: str) -> float | None:
    """Get the current recorded effective price for a listing product."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT effective_price FROM listing_products WHERE pid = ?",
            (pid,),
        )
        if rows and rows[0]["effective_price"]:
            return float(rows[0]["effective_price"])
        return None
    finally:
        await db.close()


async def get_listing_products(listing_id: int, sort_by: str = "steepest") -> list[dict]:
    """Retrieve harvested products for a listing with sorting and recent price history."""
    db = await get_db()
    try:
        order_clause = "ORDER BY discount_pct DESC, effective_price ASC"
        if sort_by == "lowest_price":
            order_clause = "ORDER BY effective_price ASC"
        elif sort_by == "wow_only":
            order_clause = "WHERE wow_price IS NOT NULL ORDER BY wow_price ASC"
        elif sort_by in ("newest", "latest_drop"):
            order_clause = "ORDER BY (CASE WHEN last_alerted_at IS NOT NULL THEN 0 ELSE 1 END), COALESCE(last_alerted_at, last_updated) DESC, discount_pct DESC"

        query = f"SELECT * FROM listing_products WHERE listing_id = ? {order_clause}"
        rows = await db.execute_fetchall(query, (listing_id,))
        products = [dict(r) for r in rows]

        if products:
            pids = [p["pid"] for p in products]
            placeholders = ",".join("?" for _ in pids)
            history_rows = await db.execute_fetchall(
                f"""
                SELECT pid, effective_price, regular_price, wow_price, recorded_at
                FROM (
                    SELECT pid, effective_price, regular_price, wow_price, recorded_at,
                           ROW_NUMBER() OVER (PARTITION BY pid ORDER BY id DESC) as rn
                    FROM listing_price_history
                    WHERE pid IN ({placeholders})
                ) WHERE rn <= 6
                ORDER BY pid, recorded_at ASC
                """,
                pids,
            )
            history_map = {}
            for hr in history_rows:
                h = dict(hr)
                pid = h["pid"]
                if pid not in history_map:
                    history_map[pid] = []
                history_map[pid].append(h)

            for p in products:
                p["price_history"] = history_map.get(p["pid"], [])

        return products
    finally:
        await db.close()


# ═══════════════════════════════════════════════════════════════════════════
# Lenovo Outlet Tracker Operations
# ═══════════════════════════════════════════════════════════════════════════

async def upsert_lenovo_products(items: list[dict]) -> tuple[int, list[dict]]:
    """
    Upsert laptops from Lenovo outlet API scan.
    Returns (total_saved, deals_to_alert).
    
    Alert Deduplication Rules:
    1. Banger Deal (>= 50% discount):
       - If product has never been alerted: ALERT!
       - If previously alerted:
         - Alert ONLY if discount percentage further increased (e.g. 52% -> 60%)
         - OR if price dropped below last_alerted_price!
         - Otherwise (same or lower discount & same or higher price): DO NOT ALERT!
    2. Price Drop on existing laptop (< 50%):
       - If price dropped below previous price AND below last_alerted_price: ALERT!
    """
    db = await get_db()
    try:
        now_iso = _now_iso()
        deals_to_alert = []
        
        pcodes = [str(item.get("product_code", "")).strip() for item in items if item.get("product_code")]
        if not pcodes:
            return 0, []

        placeholders = ",".join(["?"] * len(pcodes))
        existing_rows = await db.execute_fetchall(
            f"SELECT * FROM lenovo_products WHERE product_code IN ({placeholders})", pcodes
        )
        existing_map = {row["product_code"]: dict(row) for row in existing_rows}

        inserts = []
        updates = []
        history_inserts = []

        for item in items:
            pcode = str(item.get("product_code", "")).strip()
            if not pcode:
                continue

            price = float(item.get("current_price", 0.0) or 0.0)
            mrp = float(item.get("mrp", 0.0) or 0.0) if item.get("mrp") else None
            save_pct = float(item.get("save_percent", 0.0) or 0.0)
            save_amount = float(item.get("save_amount", 0.0) or 0.0)
            name = str(item.get("name", "")).strip()
            series = str(item.get("series", "")).strip()
            cpu = str(item.get("cpu", "")).strip()
            ram = str(item.get("ram", "")).strip()
            ssd = str(item.get("ssd", "")).strip()
            gpu = str(item.get("gpu", "")).strip()
            vram = str(item.get("vram", "")).strip()
            is_dedicated_gpu = int(item.get("is_dedicated_gpu", 0))
            condition = str(item.get("condition", "CERTIFIED REFURBISHED")).strip()
            url = str(item.get("url", "")).strip()
            in_stock = int(item.get("in_stock", 1))

            row = existing_map.get(pcode)

            if not row:
                if save_pct >= 50.0 and in_stock:
                    deal_obj = dict(item)
                    deal_obj["alert_reason"] = f"🔥 Banger Deal: {save_pct:.0f}% OFF"
                    deal_obj["signal_type"] = "banger"
                    deals_to_alert.append(deal_obj)

                inserts.append((
                    pcode, name, series, cpu, ram, ssd, gpu, vram, is_dedicated_gpu,
                    price, mrp, save_pct, save_amount,
                    condition, url, in_stock, now_iso, now_iso, price
                ))
                history_inserts.append((pcode, price, save_pct, now_iso))

            else:
                prev_price = float(row["current_price"])
                prev_save_pct = float(row["save_percent"] or 0.0)
                last_alerted_pct = float(row["last_alerted_discount_pct"]) if row["last_alerted_discount_pct"] is not None else None
                last_alerted_price = float(row["last_alerted_price"]) if row["last_alerted_price"] is not None else None

                existing_hist_low = float(row.get("historical_low") or row["current_price"])
                new_hist_low = min(existing_hist_low, price)
                is_all_time_low = price < existing_hist_low

                if abs(price - prev_price) > 0.01 or abs(save_pct - prev_save_pct) > 0.01:
                    history_inserts.append((pcode, price, save_pct, now_iso))

                should_alert = False
                alert_reason = ""
                signal_type = ""

                if save_pct >= 50.0 and in_stock:
                    if last_alerted_pct is None:
                        should_alert = True
                        alert_reason = f"🔥 Banger Deal: {save_pct:.0f}% OFF"
                        signal_type = "banger"
                    elif save_pct > last_alerted_pct:
                        should_alert = True
                        alert_reason = f"🚀 Discount Increased: {last_alerted_pct:.0f}% ➔ {save_pct:.0f}% OFF"
                        signal_type = "banger"
                    elif last_alerted_price is not None and price < last_alerted_price:
                        diff = last_alerted_price - price
                        should_alert = True
                        alert_reason = f"📉 Price Dropped: -₹{diff:,.0f} (Now ₹{price:,.0f})"
                        signal_type = "price_drop"
                elif price < prev_price and in_stock:
                    if last_alerted_price is None or price < last_alerted_price:
                        diff = prev_price - price
                        should_alert = True
                        alert_reason = f"📉 Price Dropped: -₹{diff:,.0f} (Now ₹{price:,.0f})"
                        signal_type = "price_drop"

                if should_alert:
                    deal_obj = dict(item)
                    deal_obj["alert_reason"] = alert_reason
                    deal_obj["previous_price"] = prev_price
                    deal_obj["signal_type"] = signal_type
                    deals_to_alert.append(deal_obj)

                if is_all_time_low and in_stock and not should_alert:
                    deal_obj = dict(item)
                    deal_obj["alert_reason"] = f"📉 ALL-TIME LOW: ₹{price:,.0f}"
                    deal_obj["signal_type"] = "all_time_low"
                    deal_obj["previous_price"] = prev_price
                    deals_to_alert.append(deal_obj)

                updates.append((
                    name, series, cpu, ram, ssd, gpu, vram, is_dedicated_gpu,
                    price, mrp, save_pct, save_amount,
                    condition, url, in_stock, now_iso, new_hist_low, pcode
                ))

        if inserts:
            await db.executemany(
                """INSERT INTO lenovo_products (
                       product_code, name, series, cpu, ram, ssd, gpu, vram, is_dedicated_gpu,
                       current_price, mrp, save_percent, save_amount,
                       condition, url, in_stock, first_seen_at, last_scanned_at, historical_low
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                inserts
            )
            
        if updates:
            await db.executemany(
                """UPDATE lenovo_products
                   SET name = ?, series = ?, cpu = ?, ram = ?, ssd = ?, gpu = ?, vram = ?, is_dedicated_gpu = ?,
                       current_price = ?, mrp = ?, save_percent = ?, save_amount = ?,
                       condition = ?, url = ?, in_stock = ?, last_scanned_at = ?, historical_low = ?
                   WHERE product_code = ?""",
                updates
            )

        if history_inserts:
            await db.executemany(
                """INSERT INTO lenovo_price_history (product_code, price, save_percent, recorded_at)
                   VALUES (?, ?, ?, ?)""",
                history_inserts
            )

        await db.commit()
        return len(inserts) + len(updates), deals_to_alert
        
    finally:
        await db.close()


async def record_lenovo_alert(product_code: str, price: float, discount_pct: float):
    """Mark a Lenovo product as alerted at the given price & discount."""
    db = await get_db()
    try:
        now_iso = _now_iso()
        await db.execute(
            """
            UPDATE lenovo_products
            SET last_alerted_price = ?,
                last_alerted_discount_pct = ?,
                last_alerted_at = ?
            WHERE product_code = ?
            """,
            (price, discount_pct, now_iso, product_code),
        )
        await db.commit()
    finally:
        await db.close()


async def get_lenovo_products(
    sort_by: str = "discount",
    series: str | None = None,
    min_discount: float | None = None,
    in_stock_only: bool = False,
    search: str | None = None,
    gpu_filter: str | None = None,
) -> list[dict]:
    """Retrieve Lenovo outlet laptops with filtering, sorting, and price history."""
    db = await get_db()
    try:
        query = "SELECT * FROM lenovo_products WHERE 1=1"
        params: list = []

        if series:
            query += " AND series = ?"
            params.append(series)

        if min_discount is not None:
            query += " AND save_percent >= ?"
            params.append(min_discount)

        if in_stock_only:
            query += " AND in_stock = 1"

        if gpu_filter == "dedicated":
            query += " AND is_dedicated_gpu = 1"
        elif gpu_filter == "rtx50":
            query += " AND is_dedicated_gpu = 1 AND (gpu LIKE '%5060%' OR gpu LIKE '%5070%' OR gpu LIKE '%5080%' OR gpu LIKE '%5090%' OR gpu LIKE '%RTX 50%' OR gpu LIKE '%RTX50%')"
        elif gpu_filter == "rtx40":
            query += " AND is_dedicated_gpu = 1 AND (gpu LIKE '%4050%' OR gpu LIKE '%4060%' OR gpu LIKE '%4070%' OR gpu LIKE '%4080%' OR gpu LIKE '%4090%' OR gpu LIKE '%RTX 40%' OR gpu LIKE '%RTX40%')"
        elif gpu_filter == "rtx30":
            query += " AND is_dedicated_gpu = 1 AND (gpu LIKE '%3050%' OR gpu LIKE '%3060%' OR gpu LIKE '%3070%' OR gpu LIKE '%3080%' OR gpu LIKE '%RTX 30%' OR gpu LIKE '%RTX30%')"
        elif gpu_filter == "ada":
            query += " AND is_dedicated_gpu = 1 AND (gpu LIKE '%Ada%' OR gpu LIKE '%RTX A%' OR gpu LIKE '%Quadro%')"
        elif gpu_filter == "gtx_mx":
            query += " AND is_dedicated_gpu = 1 AND (gpu LIKE '%GTX%' OR gpu LIKE '%MX%' OR gpu LIKE '%Arc A%')"
        elif gpu_filter == "vram8":
            query += " AND is_dedicated_gpu = 1 AND (vram LIKE '%8GB%' OR vram LIKE '%12GB%' OR vram LIKE '%16GB%')"
        elif gpu_filter == "vram6":
            query += " AND is_dedicated_gpu = 1 AND (vram LIKE '%6GB%' OR vram LIKE '%8GB%' OR vram LIKE '%12GB%' OR vram LIKE '%16GB%')"


        if search:
            query += " AND (name LIKE ? OR cpu LIKE ? OR ram LIKE ? OR ssd LIKE ? OR gpu LIKE ? OR vram LIKE ? OR product_code LIKE ?)"
            term = f"%{search}%"
            params.extend([term, term, term, term, term, term, term])

        if sort_by == "price_asc":
            query += " ORDER BY current_price ASC"
        elif sort_by == "price_desc":
            query += " ORDER BY current_price DESC"
        elif sort_by == "newest":
            query += " ORDER BY first_seen_at DESC, last_scanned_at DESC"
        elif sort_by == "gpu":
            query += " ORDER BY is_dedicated_gpu DESC, save_percent DESC, current_price ASC"
        else:  # default: discount
            query += " ORDER BY save_percent DESC, current_price ASC"

        rows = await db.execute_fetchall(query, params)
        products = [dict(r) for r in rows]

        if products:
            pcodes = [p["product_code"] for p in products]
            placeholders = ",".join("?" for _ in pcodes)
            history_rows = await db.execute_fetchall(
                f"""
                SELECT product_code, price, save_percent, recorded_at
                FROM (
                    SELECT product_code, price, save_percent, recorded_at,
                           ROW_NUMBER() OVER (PARTITION BY product_code ORDER BY id DESC) as rn
                    FROM lenovo_price_history
                    WHERE product_code IN ({placeholders})
                ) WHERE rn <= 6
                ORDER BY product_code, recorded_at ASC
                """,
                pcodes,
            )
            h_map = {}
            for hr in history_rows:
                h = dict(hr)
                h["effective_price"] = h.get("price")
                code = h["product_code"]
                if code not in h_map:
                    h_map[code] = []
                h_map[code].append(h)

            for p in products:
                p["price_history"] = h_map.get(p["product_code"], [])

        return products
    finally:
        await db.close()


async def get_lenovo_stats() -> dict:
    """Get aggregated statistics for the Lenovo outlet tab."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall("""
            SELECT
                COUNT(*) as total_count,
                SUM(CASE WHEN save_percent >= 50.0 THEN 1 ELSE 0 END) as banger_count,
                SUM(CASE WHEN is_dedicated_gpu = 1 THEN 1 ELSE 0 END) as dedicated_gpu_count,
                SUM(CASE WHEN gpu LIKE '%RTX 50%' OR gpu LIKE '%RTX50%' OR gpu LIKE '%5060%' OR gpu LIKE '%5070%' OR gpu LIKE '%5080%' THEN 1 ELSE 0 END) as rtx50_count,
                SUM(CASE WHEN gpu LIKE '%RTX 40%' OR gpu LIKE '%RTX40%' OR gpu LIKE '%4050%' OR gpu LIKE '%4060%' OR gpu LIKE '%4070%' OR gpu LIKE '%4080%' THEN 1 ELSE 0 END) as rtx40_count,
                SUM(CASE WHEN gpu LIKE '%RTX 30%' OR gpu LIKE '%RTX30%' OR gpu LIKE '%3050%' OR gpu LIKE '%3060%' OR gpu LIKE '%3070%' OR gpu LIKE '%3080%' THEN 1 ELSE 0 END) as rtx30_count,
                SUM(CASE WHEN gpu LIKE '%Ada%' OR gpu LIKE '%RTX A%' OR gpu LIKE '%Quadro%' THEN 1 ELSE 0 END) as ada_count,
                SUM(CASE WHEN gpu LIKE '%RTX%' THEN 1 ELSE 0 END) as rtx_count,
                MAX(save_percent) as max_discount,
                MIN(current_price) as min_price,
                MAX(last_scanned_at) as last_scanned
            FROM lenovo_products
        """)
        if rows and rows[0]["total_count"]:
            r = rows[0]
            return {
                "total_count": r["total_count"] or 0,
                "banger_count": r["banger_count"] or 0,
                "dedicated_gpu_count": r["dedicated_gpu_count"] or 0,
                "rtx50_count": r["rtx50_count"] or 0,
                "rtx40_count": r["rtx40_count"] or 0,
                "rtx30_count": r["rtx30_count"] or 0,
                "ada_count": r["ada_count"] or 0,
                "rtx_count": r["rtx_count"] or 0,
                "max_discount": r["max_discount"] or 0.0,
                "min_price": r["min_price"] or 0.0,
                "last_scanned": r["last_scanned"],
            }
        return {
            "total_count": 0,
            "banger_count": 0,
            "dedicated_gpu_count": 0,
            "rtx50_count": 0,
            "rtx40_count": 0,
            "rtx30_count": 0,
            "ada_count": 0,
            "rtx_count": 0,
            "max_discount": 0.0,
            "min_price": 0.0,
            "last_scanned": None,
        }

    finally:
        await db.close()


async def get_all_deals(
    sort_by: str = "latest_drop",
    filter_type: str = "all",
    platform: str = "all",
    category: str = "all",
    q: str = "",
    limit: int = 120,
) -> dict:
    """
    Fetch and aggregate all active deals across Lenovo Outlet, Flipkart categories,
    IKEA furniture, and tracked products into a single normalized live stream.
    Supports recency-aware sorting ('latest_drop', 'hot_score', 'steepest', etc.).
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    db = await get_db()
    deals = []

    try:
        # 1. Lenovo Outlet Products
        if platform in ("all", "lenovo"):
            lenovo_rows = await db.execute_fetchall("""
                SELECT product_code, name, series, cpu, ram, ssd, gpu, vram, condition,
                       current_price, mrp, save_percent, save_amount, url, in_stock,
                       first_seen_at, last_scanned_at, last_alerted_at, is_dedicated_gpu
                FROM lenovo_products
                WHERE save_percent > 0 AND in_stock = 1
            """)
            for r in lenovo_rows:
                curr = r["current_price"] or 0.0
                orig = r["mrp"] or curr
                disc = round(r["save_percent"] or 0.0, 1)
                savings = round(r["save_amount"] or (orig - curr if orig > curr else 0.0))
                ts_str = r["last_alerted_at"] or r["first_seen_at"] or r["last_scanned_at"]

                age_hours = 999.0
                if ts_str:
                    try:
                        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        age_hours = max(0.0, (now - dt).total_seconds() / 3600.0)
                    except Exception:
                        pass

                is_fresh = age_hours <= 48.0 or bool(r["last_alerted_at"])
                fresh_bonus = max(0.0, 40.0 - (age_hours * 1.5)) if is_fresh else 0.0
                hot_score = round(disc * 1.2 + min(30.0, savings / 3000.0) + fresh_bonus, 1)

                deals.append({
                    "id": f"lenovo_{r['product_code']}",
                    "pid": r["product_code"],
                    "platform": "lenovo",
                    "platform_label": "Lenovo Outlet",
                    "category": "laptops",
                    "category_label": "Laptop",
                    "name": r["name"],
                    "title": r["name"],
                    "current_price": curr,
                    "original_price": orig,
                    "discount_pct": disc,
                    "savings_amount": savings,
                    "drop_timestamp": ts_str,
                    "age_hours": round(age_hours, 1),
                    "is_fresh": is_fresh,
                    "hot_score": hot_score,
                    "url": r["url"],
                    "image_url": "",
                    "in_stock": True,
                    "cpu": r["cpu"],
                    "ram": r["ram"],
                    "ssd": r["ssd"],
                    "gpu": r["gpu"],
                    "vram": r["vram"] or "",
                    "is_banger": disc >= 50.0,
                })

        # 2. Harvester Listing Products (Flipkart & IKEA)
        listing_rows = await db.execute_fetchall("""
            SELECT lp.id, lp.listing_id, lp.pid, lp.name, lp.title, lp.url, lp.image_url,
                   lp.mrp, lp.regular_price, lp.wow_price, lp.effective_price, lp.previous_price,
                   lp.discount_pct, lp.last_updated, lp.last_alerted_at,
                   lp.cpu, lp.ram, lp.ssd, lp.gpu, lp.exchange_discount,
                   l.category
            FROM listing_products lp
            JOIN listings l ON lp.listing_id = l.id
            WHERE lp.discount_pct > 0 OR (lp.mrp IS NOT NULL AND lp.mrp > lp.effective_price)
        """)
        for r in listing_rows:
            url_lower = (r["url"] or "").lower()
            is_ikea = "ikea.com" in url_lower or (r["pid"] or "").startswith("IKEA_")
            prod_platform = "ikea" if is_ikea else "flipkart"
            if platform != "all" and platform != prod_platform:
                continue

            curr = r["effective_price"] or 0.0
            candidates = [p for p in (r["mrp"], r["regular_price"], r["previous_price"]) if p and p > curr]
            orig = max(candidates) if candidates else (r["mrp"] or r["regular_price"] or curr)
            disc = round(r["discount_pct"] or (round(((orig - curr) / orig) * 100, 1) if orig > curr else 0.0), 1)
            savings = round(orig - curr if orig > curr else 0.0)
            ts_str = r["last_alerted_at"] or r["last_updated"]

            age_hours = 999.0
            if ts_str:
                try:
                    dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    age_hours = max(0.0, (now - dt).total_seconds() / 3600.0)
                except Exception:
                    pass

            is_fresh = (age_hours <= 48.0 and disc > 0) or bool(r["last_alerted_at"])
            fresh_bonus = max(0.0, 40.0 - (age_hours * 1.5)) if is_fresh else 0.0
            hot_score = round(disc * 1.2 + min(30.0, savings / 3000.0) + fresh_bonus, 1)

            cat = r["category"] or "general"
            cat_label = {
                "laptops": "Laptop",
                "ssd": "M.2 SSD",
                "ram": "DDR RAM",
                "dish_washer": "Dishwasher",
                "sofas": "Sofa / Furniture",
            }.get(cat, cat.title())

            deals.append({
                "id": f"listing_{r['pid']}",
                "pid": r["pid"],
                "platform": prod_platform,
                "platform_label": "IKEA" if is_ikea else "Flipkart",
                "category": cat,
                "category_label": cat_label,
                "name": r["name"] or r["title"],
                "title": r["title"],
                "current_price": curr,
                "original_price": orig,
                "discount_pct": disc,
                "savings_amount": savings,
                "drop_timestamp": ts_str,
                "age_hours": round(age_hours, 1),
                "is_fresh": is_fresh,
                "hot_score": hot_score,
                "url": r["url"],
                "image_url": r["image_url"] or "",
                "in_stock": True,
                "cpu": r["cpu"],
                "ram": r["ram"],
                "ssd": r["ssd"],
                "gpu": r["gpu"],
                "vram": "",
                "is_banger": disc >= 50.0,
            })

        # 3. Filtering
        total_before_filter = len(deals)
        fresh_count = sum(1 for d in deals if d["is_fresh"])
        bangers_count = sum(1 for d in deals if d["is_banger"])

        filtered = []
        q_lower = q.strip().lower()
        for d in deals:
            if category != "all" and d["category"] != category:
                continue
            if filter_type == "fresh_drops" and not d["is_fresh"]:
                continue
            if filter_type == "bangers" and not d["is_banger"]:
                continue
            if filter_type == "in_stock" and not d["in_stock"]:
                continue
            if q_lower:
                haystack = f"{d['name']} {d['title']} {d['category_label']} {d['platform_label']} {d.get('cpu', '')} {d.get('ram', '')} {d.get('ssd', '')} {d.get('gpu', '')}".lower()
                if q_lower not in haystack:
                    continue
            filtered.append(d)

        # 4. Sorting
        if sort_by == "latest_drop":
            # Sort by is_fresh first, then lowest age_hours (most recent), then highest discount
            filtered.sort(key=lambda x: (x["is_fresh"], -x["age_hours"], x["discount_pct"]), reverse=True)
        elif sort_by == "hot_score":
            filtered.sort(key=lambda x: x["hot_score"], reverse=True)
        elif sort_by == "steepest":
            filtered.sort(key=lambda x: (x["discount_pct"], x["savings_amount"]), reverse=True)
        elif sort_by == "price_asc":
            filtered.sort(key=lambda x: x["current_price"])
        elif sort_by == "price_desc":
            filtered.sort(key=lambda x: x["current_price"], reverse=True)
        elif sort_by == "savings":
            filtered.sort(key=lambda x: x["savings_amount"], reverse=True)
        else:
            filtered.sort(key=lambda x: (x["is_fresh"], -x["age_hours"], x["discount_pct"]), reverse=True)

        sliced = filtered[:limit]

        # 5. Batch-attach Price History to the sliced items for sparklines and trend modal
        lenovo_codes = [d["pid"] for d in sliced if d["platform"] == "lenovo"]
        listing_pids = [d["pid"] for d in sliced if d["platform"] in ("flipkart", "ikea")]

        h_map = {}
        if lenovo_codes:
            placeholders = ",".join(["?"] * len(lenovo_codes))
            h_rows = await db.execute_fetchall(f"""
                SELECT product_code, price as current_price, recorded_at
                FROM lenovo_price_history
                WHERE product_code IN ({placeholders})
                ORDER BY recorded_at ASC
            """, lenovo_codes)
            for hr in h_rows:
                code = hr["product_code"]
                h_map.setdefault(code, []).append({
                    "effective_price": hr["current_price"],
                    "recorded_at": hr["recorded_at"],
                })

        if listing_pids:
            placeholders = ",".join(["?"] * len(listing_pids))
            h_rows = await db.execute_fetchall(f"""
                SELECT pid, regular_price, wow_price, effective_price, recorded_at
                FROM listing_price_history
                WHERE pid IN ({placeholders})
                ORDER BY recorded_at ASC
            """, listing_pids)
            for hr in h_rows:
                pid = hr["pid"]
                h_map.setdefault(pid, []).append({
                    "regular_price": hr["regular_price"],
                    "wow_price": hr["wow_price"],
                    "effective_price": hr["effective_price"],
                    "recorded_at": hr["recorded_at"],
                })

        for d in sliced:
            d["price_history"] = h_map.get(d["pid"], [])

        return {
            "total": len(filtered),
            "total_all": total_before_filter,
            "fresh_count": fresh_count,
            "bangers_count": bangers_count,
            "deals": sliced,
        }

    finally:
        await db.close()


async def queue_failed_alert(deal_key: str, platform: str, signal_type: str, payload: dict) -> None:
    """Queue a failed alert for later retry."""
    import json
    now = _now_iso()
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO alert_queue (deal_key, platform, signal_type, payload_json, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (deal_key, platform, signal_type, json.dumps(payload), now),
        )
        await db.commit()
    finally:
        await db.close()


async def get_pending_alerts(limit: int = 20) -> list[dict]:
    """Fetch pending alerts from the queue for retry."""
    import json
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            """SELECT * FROM alert_queue
               WHERE status = 'pending' AND retry_count < 5
               ORDER BY created_at ASC LIMIT ?""",
            (limit,),
        )
        results = []
        for r in rows:
            d = dict(r)
            d["payload"] = json.loads(d["payload_json"])
            results.append(d)
        return results
    finally:
        await db.close()


async def mark_alert_retried(alert_id: int, success: bool) -> None:
    """Update alert queue entry after a retry attempt."""
    now = _now_iso()
    db = await get_db()
    try:
        if success:
            await db.execute(
                "UPDATE alert_queue SET status = 'sent', last_retry_at = ? WHERE id = ?",
                (now, alert_id),
            )
        else:
            await db.execute(
                "UPDATE alert_queue SET retry_count = retry_count + 1, last_retry_at = ? WHERE id = ?",
                (now, alert_id),
            )
        await db.commit()
    finally:
        await db.close()


async def log_notification(deal_key: str, platform: str, signal_type: str, message_preview: str, status: str = "sent") -> None:
    """Record a notification in the audit log."""
    now = _now_iso()
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO notification_log (deal_key, platform, signal_type, message_preview, sent_at, status)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (deal_key, platform, signal_type, message_preview[:200], now, status),
        )
        await db.commit()
    finally:
        await db.close()


async def get_notification_log(limit: int = 50) -> list[dict]:
    """Retrieve recent notification log entries."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT * FROM notification_log ORDER BY sent_at DESC LIMIT ?",
            (limit,),
        )
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def update_listing_scrape_status(
    listing_id: int, status: str = "ok", error: str | None = None, reset_failures: bool = False
) -> int:
    """Update scrape health status for a listing. Returns consecutive_failures count."""
    db = await get_db()
    try:
        if reset_failures or status == "ok":
            await db.execute(
                """UPDATE listings
                   SET scrape_status = 'ok', consecutive_failures = 0, last_error = NULL
                   WHERE id = ?""",
                (listing_id,),
            )
            await db.commit()
            return 0
        else:
            await db.execute(
                """UPDATE listings
                   SET scrape_status = ?, consecutive_failures = consecutive_failures + 1,
                       last_error = ?
                   WHERE id = ?""",
                (status, error, listing_id),
            )
            await db.commit()
            rows = await db.execute_fetchall(
                "SELECT consecutive_failures FROM listings WHERE id = ?",
                (listing_id,),
            )
            return int(rows[0]["consecutive_failures"]) if rows else 0
    finally:
        await db.close()


async def get_digest_deals(limit: int = 10) -> list[dict]:
    """Get top deals for daily digest, sorted by hot_score, fresh items preferred."""
    result = await get_all_deals(
        sort_by="hot_score",
        filter_type="all",
        platform="all",
        category="all",
        q="",
        limit=limit,
    )
    return result.get("deals", []) if isinstance(result, dict) else []


async def pause_listing(listing_id: int) -> bool:
    """Pause a listing (skip during scheduled scans)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "UPDATE listings SET is_paused = 1 WHERE id = ?",
            (listing_id,),
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def resume_listing(listing_id: int) -> bool:
    """Resume a paused listing."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "UPDATE listings SET is_paused = 0, scrape_status = 'ok', consecutive_failures = 0, last_error = NULL WHERE id = ?",
            (listing_id,),
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def update_listing_threshold(listing_id: int, threshold_pct: float) -> bool:
    """Update the alert discount threshold for a listing."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "UPDATE listings SET discount_threshold_pct = ? WHERE id = ?",
            (threshold_pct, listing_id),
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()
