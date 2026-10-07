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

        # ── Performance Indexes ──────────────────────────────────────────────
        await db.execute("CREATE INDEX IF NOT EXISTS idx_lph_pid_recorded ON listing_price_history(pid, recorded_at DESC)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_lenovo_ph_pid_recorded ON lenovo_price_history(product_code, recorded_at DESC)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_lp_discount ON listing_products(discount_pct DESC)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_lenovo_discount ON lenovo_products(save_percent DESC)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_lenovo_instock ON lenovo_products(in_stock)")

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
                ) WHERE rn <= 60
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
                ) WHERE rn <= 60
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


import math

def floor1(val: float | None) -> float:
    """Floor a float to 1 decimal place."""
    if val is None:
        return 0.0
    try:
        f = float(val)
        return math.floor(f * 10.0) / 10.0
    except Exception:
        return 0.0

GPU_DEAL_THRESHOLDS = {
    "insane": {
        "RTX 5090": 300000,
        "RTX 5080": 200000,
        "RTX 5070": 150000,
        "RTX 5060": 85000,
        "RTX 5050": 75000,
        "RTX 4060": 70000,
        "RTX 4050": 55000,
        "RTX 5000 Ada": 350000,
        "RTX 2000 Ada": 400000,
    },
    "great": {
        "RTX 5080": 250000,
        "RTX 5070": 180000,
        "RTX 5060": 100000,
        "RTX 5050": 90000,
        "RTX 4060": 85000,
        "RTX 4050": 65000,
        "RTX 3060": 65000,
        "RTX 3050": 55000,
        "RTX 500 Ada": 80000,
    }
}

def _classify_gpu_tier(gpu_str: str) -> str:
    g = gpu_str.upper()
    if "5090" in g: return "RTX 5090"
    if "5080" in g: return "RTX 5080"
    if "5070" in g: return "RTX 5070"
    if "5060" in g: return "RTX 5060"
    if "5050" in g: return "RTX 5050"
    if "4090" in g: return "RTX 4090"
    if "4080" in g: return "RTX 4080"
    if "4070" in g: return "RTX 4070"
    if "4060" in g: return "RTX 4060"
    if "4050" in g: return "RTX 4050"
    if "3060" in g: return "RTX 3060"
    if "3050" in g: return "RTX 3050"
    if "5000 ADA" in g: return "RTX 5000 Ada"
    if "2000 ADA" in g: return "RTX 2000 Ada"
    if "500 ADA" in g: return "RTX 500 Ada"
    return ""

def _evaluate_lenovo_deal(item: dict) -> tuple[bool, str, str]:
    """
    Evaluate if a Lenovo laptop qualifies as a deal for Telegram alert.
    Lenovo outlet items at normal discounts (25-45%) on dedicated GPUs,
    AMD Radeon, or ThinkPads are high-value deals.
    Returns (is_deal, alert_reason, signal_type).
    """
    save_pct = float(item.get("save_percent", 0.0) or 0.0)
    is_dedicated = int(item.get("is_dedicated_gpu", 0))
    gpu_str = str(item.get("gpu", "")).upper()
    series_str = str(item.get("series", "")).upper()
    name_str = str(item.get("name", "")).upper()
    ram_str = str(item.get("ram", "")).upper()
    
    save_floored = floor1(save_pct)
    gpu_tier = _classify_gpu_tier(gpu_str)
    current_price = float(item.get("current_price", 0.0) or 0.0)
    gpu_short = item.get("gpu", "Dedicated GPU")
    
    if (gpu_tier and current_price < GPU_DEAL_THRESHOLDS["insane"].get(gpu_tier, -1)) or \
       (is_dedicated and "32" in ram_str and current_price < 90000):
        return True, f"🚨 INSANE DEAL: {gpu_short} @ ₹{current_price:,.0f}", "insane_deal"
        
    if (gpu_tier and current_price < GPU_DEAL_THRESHOLDS["great"].get(gpu_tier, -1)) or \
       ("32" in ram_str and current_price < 65000):
        return True, f"⚡ GREAT DEAL: {gpu_short} @ ₹{current_price:,.0f}", "great_deal"
    
    # 1. Super Banger (>= 45%)
    if save_pct >= 45.0:
        return True, f"🔥 Banger Deal: -{save_floored:.1f}% OFF", "banger"
    
    # 2. Dedicated GPU (RTX 30/40/50, Ada, Quadro, GTX) with >= 25% discount
    if (is_dedicated or "RTX" in gpu_str or "ADA" in gpu_str or "QUADRO" in gpu_str or "GTX" in gpu_str) and save_pct >= 25.0:
        return True, f"🎮 Dedicated GPU Deal ({gpu_short}): -{save_floored:.1f}% OFF", "gpu_deal"
        
    # 3. AMD Radeon laptops with >= 30% discount
    if ("RADEON" in gpu_str or "RX " in gpu_str) and save_pct >= 30.0:
        return True, f"⚡ AMD Radeon Deal: -{save_floored:.1f}% OFF", "lenovo_deal"
        
    # 4. Premium ThinkPads (X1, T-series, P-series, L-series) with >= 30% discount
    if ("THINKPAD" in series_str or "THINKPAD" in name_str) and save_pct >= 30.0:
        return True, f"💼 ThinkPad Deal: -{save_floored:.1f}% OFF", "lenovo_deal"
        
    # 5. General Lenovo Outlet laptops with solid discount >= 35%
    if save_pct >= 35.0:
        return True, f"🏷️ Lenovo Outlet Deal: -{save_floored:.1f}% OFF", "lenovo_deal"
        
    return False, "", ""

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

            is_deal, deal_reason, deal_signal = _evaluate_lenovo_deal(item)

            if not row:
                if is_deal and in_stock:
                    deal_obj = dict(item)
                    deal_obj["alert_reason"] = deal_reason
                    deal_obj["signal_type"] = deal_signal
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

                if is_deal and in_stock:
                    if last_alerted_pct is None:
                        should_alert = True
                        alert_reason = deal_reason
                        signal_type = deal_signal
                    elif save_pct > (last_alerted_pct + 0.9):
                        should_alert = True
                        alert_reason = f"🚀 Discount Increased: {floor1(last_alerted_pct):.1f}% ➔ {floor1(save_pct):.1f}% OFF"
                        signal_type = deal_signal
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

        # ── Mark products no longer returned by the scraper as out of stock ──
        scanned_pcodes = [item["product_code"] for item in items]
        if scanned_pcodes:
            placeholders = ",".join(["?"] * len(scanned_pcodes))
            await db.execute(
                f"""UPDATE lenovo_products 
                   SET in_stock = 0 
                   WHERE product_code NOT IN ({placeholders}) AND in_stock = 1""",
                scanned_pcodes
            )
        else:
            # If the scraper returned absolutely nothing, it might be an error, but if it truly returned []
            # we should technically mark all as out of stock. Be careful here.
            await db.execute("UPDATE lenovo_products SET in_stock = 0 WHERE in_stock = 1")

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
                ) WHERE rn <= 60
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
                # Evaluate deals for UI badges
                is_deal, deal_reason, signal_type = _evaluate_lenovo_deal(p)
                if signal_type == "insane_deal":
                    p["tier"] = "insane"
                elif signal_type == "great_deal":
                    p["tier"] = "great"
                elif is_deal:
                    p["tier"] = "good"
                else:
                    p["tier"] = "none"

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
    sort_by: str = "steepest",
    filter_type: str = "all",
    platform: str = "all",
    category: str = "all",
    ram: str = "all",
    gpu: str = "all",
    q: str = "",
    in_stock_only: bool = False,
    limit: int = 200,
) -> dict:
    """
    Fetch and aggregate all active deals into a single normalized stream.
    Two metrics per product:
      - discount_pct: MRP → current price discount
      - steep_drop_pct: price drop vs 5-day stable price (mode)
    Price history is NOT attached — fetched on demand via /api/deal-history.
    """
    from datetime import datetime, timezone
    from collections import Counter

    now = datetime.now(timezone.utc)
    db = await get_db()
    deals = []

    try:
        # ── Pre-compute 5-day price modes for steep drop calculation ──
        recent_modes = {}

        if platform in ("all", "flipkart", "ikea"):
            hist_fk = await db.execute_fetchall("""
                SELECT pid, effective_price
                FROM listing_price_history
                WHERE recorded_at >= datetime('now', '-5 days')
            """)
            temp_fk = {}
            for h in hist_fk:
                temp_fk.setdefault(h["pid"], []).append(h["effective_price"])
            for pid_key, prices in temp_fk.items():
                if prices:
                    recent_modes[pid_key] = Counter(prices).most_common(1)[0][0]

        if platform in ("all", "lenovo"):
            hist_ln = await db.execute_fetchall("""
                SELECT product_code as pid, price as effective_price
                FROM lenovo_price_history
                WHERE recorded_at >= datetime('now', '-5 days')
            """)
            temp_ln = {}
            for h in hist_ln:
                temp_ln.setdefault(h["pid"], []).append(h["effective_price"])
            for pid_key, prices in temp_ln.items():
                if prices:
                    recent_modes[pid_key] = Counter(prices).most_common(1)[0][0]

        # ── 1. Lenovo Outlet Products ──
        if platform in ("all", "lenovo"):
            lenovo_query = """
                SELECT product_code, name, series, cpu, ram, ssd, gpu, vram, condition,
                       current_price, mrp, save_percent, save_amount, url, in_stock,
                       first_seen_at, last_scanned_at, last_alerted_at, is_dedicated_gpu
                FROM lenovo_products
                WHERE save_percent > 0
            """
            if in_stock_only:
                lenovo_query += " AND in_stock = 1"

            lenovo_rows = await db.execute_fetchall(lenovo_query)
            for r in lenovo_rows:
                curr = r["current_price"] or 0.0
                orig = r["mrp"] or curr
                disc = floor1(r["save_percent"])
                savings = round(r["save_amount"] or (orig - curr if orig > curr else 0.0))

                mode_price = recent_modes.get(r["product_code"])
                steep_drop_pct = 0.0
                if mode_price and mode_price > curr:
                    steep_drop_pct = floor1(((mode_price - curr) / mode_price) * 100.0)

                deals.append({
                    "id": f"lenovo_{r['product_code']}",
                    "pid": r["product_code"],
                    "platform": "lenovo",
                    "platform_label": "Lenovo Outlet",
                    "category": "laptops",
                    "category_label": "Laptop",
                    "name": r["name"],
                    "current_price": curr,
                    "original_price": orig,
                    "discount_pct": disc,
                    "savings_amount": savings,
                    "steep_drop_pct": steep_drop_pct,
                    "steep_mode_price": mode_price or 0,
                    "url": r["url"],
                    "image_url": "",
                    "cpu": r["cpu"],
                    "ram": r["ram"],
                    "ssd": r["ssd"],
                    "gpu": r["gpu"],
                    "last_updated": r["last_scanned_at"],
                })

        # ── 2. Harvester Listing Products (Flipkart & IKEA) ──
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
            disc = floor1(r["discount_pct"] if r["discount_pct"] is not None else (floor1(((orig - curr) / orig) * 100.0) if orig > curr else 0.0))
            savings = round(orig - curr if orig > curr else 0.0)

            cat = r["category"] or "general"
            cat_label = {
                "laptops": "Laptop",
                "ssd": "M.2 SSD",
                "ram": "DDR RAM",
                "dish_washer": "Dishwasher",
                "sofas": "Sofa / Furniture",
            }.get(cat, cat.title())

            mode_price = recent_modes.get(r["pid"])
            steep_drop_pct = 0.0
            if mode_price and mode_price > curr:
                steep_drop_pct = floor1(((mode_price - curr) / mode_price) * 100.0)

            deals.append({
                "id": f"listing_{r['pid']}",
                "pid": r["pid"],
                "platform": prod_platform,
                "platform_label": "IKEA" if is_ikea else "Flipkart",
                "category": cat,
                "category_label": cat_label,
                "name": r["name"] or r["title"],
                "current_price": curr,
                "original_price": orig,
                "discount_pct": disc,
                "savings_amount": savings,
                "steep_drop_pct": steep_drop_pct,
                "steep_mode_price": mode_price or 0,
                "url": r["url"],
                "image_url": r["image_url"] or "",
                "cpu": r["cpu"],
                "ram": r["ram"],
                "ssd": r["ssd"],
                "gpu": r["gpu"],
                "last_updated": r["last_updated"],
            })

        # ── 3. Filtering ──
        filtered = []
        q_lower = q.strip().lower()
        for d in deals:
            if category != "all" and d["category"] != category:
                continue

            # Specs Filters
            d_ram = (d.get("ram") or "").lower()
            if ram != "all":
                if ram == "32gb" and not any(k in d_ram for k in ["32gb", "32 gb", "64gb", "64 gb"]):
                    continue
                elif ram != "32gb" and ram.replace("gb", " gb") not in d_ram and ram not in d_ram:
                    continue

            d_gpu = (d.get("gpu") or "").lower()
            if gpu != "all":
                if gpu == "rtx_30" and not any(k in d_gpu for k in ["rtx 30", "rtx30", "3050", "3060", "3070", "3080"]):
                    continue
                elif gpu == "rtx_40" and not any(k in d_gpu for k in ["rtx 40", "rtx40", "4050", "4060", "4070", "4080", "4090"]):
                    continue
                elif gpu == "rtx_50" and not any(k in d_gpu for k in ["rtx 50", "rtx50", "5060", "5070", "5080", "5090"]):
                    continue
                elif gpu == "amd" and not any(k in d_gpu for k in ["radeon", "rx ", "rx6", "rx7"]):
                    continue

            if q_lower:
                haystack = f"{d['name']} {d['category_label']} {d['platform_label']} {d.get('cpu', '')} {d.get('ram', '')} {d.get('ssd', '')} {d.get('gpu', '')}".lower()
                if q_lower not in haystack:
                    continue
            filtered.append(d)

        # ── 4. Sorting ──
        if sort_by == "steepest":
            filtered.sort(key=lambda x: (x["steep_drop_pct"], x["discount_pct"], x["savings_amount"]), reverse=True)
        elif sort_by == "discount":
            filtered.sort(key=lambda x: x["discount_pct"], reverse=True)
        elif sort_by == "price_asc":
            filtered.sort(key=lambda x: x["current_price"])
        elif sort_by == "price_desc":
            filtered.sort(key=lambda x: x["current_price"], reverse=True)
        elif sort_by == "savings":
            filtered.sort(key=lambda x: x["savings_amount"], reverse=True)
        else:
            filtered.sort(key=lambda x: (x["steep_drop_pct"], x["discount_pct"]), reverse=True)

        return {
            "total": len(filtered),
            "deals": filtered[:limit],
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
