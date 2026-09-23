"""
Async Playwright scraper engine for Flipkart Laptops (Mobile View) and Amazon/Flipkart single products.

Optimizations:
- Image & media blocking (zero image downloads, maximum speed & minimum bandwidth)
- Mobile Viewport Emulation (Flipkart React Native Web layout with WoW bank prices)
- Virtual Scroll Harvester using multi-channel scrolling (Mouse wheel, PageDown, inner ScrollView)
- Automatic Laptop Spec Parser (Name, CPU, RAM, SSD, GPU)
- Concurrency limiter (max 3 simultaneous scrapes)
"""

import asyncio
import json
import logging
import os
import random
import re
from dataclasses import dataclass

from dotenv import load_dotenv
from playwright.async_api import async_playwright, Page

load_dotenv()

logger = logging.getLogger(__name__)

# ── Concurrency limiter ─────────────────────────────────────────────────────
_semaphore = asyncio.Semaphore(3)

# ── Mobile User-Agents ──────────────────────────────────────────────────────
MOBILE_USER_AGENTS = [
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36",
]

DESKTOP_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]


@dataclass
class ScrapedProduct:
    title: str
    price: float
    image_url: str
    platform: str


def _parse_price(raw: str) -> float | None:
    if not raw:
        return None
    # Match only the first valid currency token to prevent concatenated values
    match = re.search(r"₹?\s*([\d,]+(?:\.\d+)?)", raw)
    if not match:
        return None
    cleaned = match.group(1).replace(",", "")
    try:
        val = float(cleaned)
        # Valid products on Flipkart are between ₹200 and ₹8,00,000
        if val < 200 or val > 800000:
            return None
        return val
    except (ValueError, TypeError):
        return None


def _get_proxy_config() -> dict | None:
    """
    Parses and selects a proxy from RESIDENTIAL_PROXY_URL.
    Supports:
    1. Single rotating proxy: 'http://user:pass@p.webshare.io:80'
    2. Comma/newline separated proxy list (Webshare format): rotates randomly on each scan
    3. Webshare format: 'ip:port:user:pass' or 'user:pass@ip:port'
    """
    raw = os.getenv("RESIDENTIAL_PROXY_URL", "").strip()
    if not raw:
        return None

    proxies = [p.strip() for p in re.split(r"[,;\r\n]+", raw) if p.strip()]
    if not proxies:
        return None

    chosen = random.choice(proxies)
    from urllib.parse import urlparse

    parts = chosen.split(":")
    if len(parts) == 4 and "@" not in chosen:
        ip, port, user, pwd = parts
        return {
            "server": f"http://{ip}:{port}",
            "username": user,
            "password": pwd,
        }

    if not chosen.startswith("http://") and not chosen.startswith("https://") and not chosen.startswith("socks5://"):
        chosen = f"http://{chosen}"

    parsed = urlparse(chosen)
    port_str = f":{parsed.port}" if parsed.port else ""
    cfg = {"server": f"{parsed.scheme}://{parsed.hostname}{port_str}"}
    if parsed.username:
        cfg["username"] = parsed.username
    if parsed.password:
        cfg["password"] = parsed.password

    return cfg


# ═══════════════════════════════════════════════════════════════════════════
# Product Spec Parser (Laptops, RAM / Memory, Computer Hardware)
# ═══════════════════════════════════════════════════════════════════════════

def parse_product_specs(title: str, badges: list[str] = None, category: str = "general") -> dict:
    """Universal product specification and clean name extractor across all categories."""
    badges = badges or []
    cat_lower = category.lower()
    title_lower = title.lower()

    # ── Category Resolution ───────────────────────────────────────────
    if "laptop" in cat_lower:
        is_laptop, is_ssd, is_ram, is_dishwasher = True, False, False, False
    elif "ssd" in cat_lower or "nvme" in cat_lower:
        is_laptop, is_ssd, is_ram, is_dishwasher = False, True, False, False
    elif "ram" in cat_lower or "memory" in cat_lower:
        is_laptop, is_ssd, is_ram, is_dishwasher = False, False, True, False
    elif "dish" in cat_lower:
        is_laptop, is_ssd, is_ram, is_dishwasher = False, False, False, True
    else:
        is_dishwasher = bool(re.search(r"\b(?:dishwasher|place settings)\b", title, re.I))
        is_laptop = bool(re.search(r"\b(?:Gaming Laptop|Laptop|Notebook|MacBook|ThinkPad|IdeaPad|Zenbook|Vivobook|Inspiron|Pavilion|Yoga|Victus|LOQ|Legion|Predator|TUF|ROG|Katana|Vostro|Latitude|Windows 11|Win 11|Intel Core|Core Ultra|Ryzen|Athlon|Celeron)\b", title, re.I)) and not is_dishwasher
        is_ram = not is_laptop and not is_dishwasher and bool(re.search(r"\b(?:DDR[345]|SO-?DIMM|UDIMM|PC SDRAM)\b", title, re.I))
        is_ssd = not is_laptop and not is_ram and not is_dishwasher and bool(re.search(r"\b(?:NVMe|Solid State Drive|Internal SSD|PCIe NVMe|M\.2 NVMe)\b", title, re.I))

    # ── 1. Dishwashers ────────────────────────────────────────────────
    if is_dishwasher and not is_laptop:
        cap_match = re.search(r"\b(\d+\s*Place\s*Settings?)\b", title, re.I)
        cap = cap_match.group(1).title() if cap_match else ""

        install_match = re.search(r"\b(Free\s*Standing|Table\s*Top|Counter\s*Top|Built-?in)\b", title, re.I)
        install = install_match.group(1).title() if install_match else ""

        feat_parts = []
        prog_match = re.search(r"\b(\d+\s*Wash\s*Programs?)\b", title, re.I)
        if prog_match:
            feat_parts.append(prog_match.group(1).title())
        if re.search(r"\b(?:Inbuilt\s*Heater|Hot\s*Water)\b", title, re.I):
            feat_parts.append("Inbuilt Heater")
        if re.search(r"\b(?:Intensive\s*Kadhai(?:\s*Cleaning)?|Kadhai)\b", title, re.I):
            feat_parts.append("Kadhai Cleaning")

        feature_line = " • ".join(feat_parts) if feat_parts else ""

        # Clean Name (Brand + Model)
        brand_match = re.search(r"^(?:(?:by\s+)?A\s+TATA\s+Product\s+)?(Voltas\s+Beko|Faber|Midea|Bosch|LG|IFB|Godrej|Haier|Siemens)", title, re.I)
        brand = brand_match.group(1) if brand_match else ""
        if not brand:
            brand = title.split()[0]

        model_part = ""
        for token in ["DT8S", "DT8B", "MDWTT0802D", "FFSD", "DFS", "SMS"]:
            if token.lower() in title_lower:
                model_part = token
                break

        clean_name = f"{brand} {model_part} Dishwasher".replace("  ", " ").strip()
        if not clean_name or len(clean_name) < 8:
            clean_name = re.sub(r"\s*(?:Free Standing|Place Settings|Dishwasher|by A TATA Product).*$", "", title, flags=re.I).strip() + " Dishwasher"

        return {
            "name": clean_name[:45].strip(),
            "cpu": cap,
            "ram": install,
            "ssd": feature_line or "Table Top",
            "gpu": "Dishwasher",
        }

    # ── 2. RAM / Memory Modules ───────────────────────────────────────
    if is_ram and not is_laptop:
        cap_match = re.search(r"\b(\d+\s*x\s*\d+\s*GB|\d+\s*GB)\b", title, re.I)
        ram_cap = cap_match.group(1).upper().replace(" ", "") if cap_match else ""

        gen_match = re.search(r"\b(DDR5|DDR4|DDR3)\b", title, re.I)
        ram_gen = gen_match.group(1).upper() if gen_match else ""

        speed_match = re.search(r"\b(\d{4}(?:\s*MHz|\s*MT/s)?)\b", title, re.I)
        ram_speed = ""
        if speed_match:
            spd = speed_match.group(1).upper().replace(" ", "")
            if not spd.endswith("MHZ") and not spd.endswith("MT/S"):
                spd += "MHz"
            ram_speed = spd

        form_factor = ""
        if re.search(r"\b(?:SO-?DIMM|Laptop)\b", title, re.I):
            form_factor = "Laptop (SO-DIMM)"
        elif re.search(r"\b(?:Desktop|PC|UDIMM)\b", title, re.I):
            form_factor = "Desktop (UDIMM)"

        chan_match = re.search(r"\b(Dual Channel|Single Channel)\b", title, re.I)
        channel = chan_match.group(1) if chan_match else ""

        brand_match = re.search(
            r"^(?:SAI DEPENDO HUB\s+)?(Crucial|Corsair|Kingston|G\.Skill|Samsung|Adata|Teamgroup|Patriot|Transcend|Hynix|SK hynix)",
            title,
            re.I,
        )
        brand = brand_match.group(1) if brand_match else ""
        clean_name = f"{brand} {ram_gen} {ram_cap} RAM".strip() if brand else f"{ram_gen} {ram_cap} RAM".strip()
        if not clean_name or len(clean_name) < 4:
            clean_name = title.split("(")[0].strip()[:45]

        gen_speed = f"{ram_gen} {ram_speed}".strip() or ram_gen or ram_speed
        return {
            "name": clean_name[:45].strip(),
            "cpu": gen_speed,
            "ram": ram_cap,
            "ssd": form_factor,
            "gpu": channel,
        }

    # ── 3. Solid State Drives (SSDs) ──────────────────────────────────
    if is_ssd and not is_laptop:
        cap_match = re.search(r"\b(\d+\s*(?:TB|GB))\b", title, re.I)
        capacity = cap_match.group(1).upper().replace(" ", "") if cap_match else ""

        # Interface & Generation
        gen = ""
        if re.search(r"\b(?:Gen\s*5|PCIe\s*5|5\.0)\b", title, re.I):
            gen = "Gen 5"
        elif re.search(r"\b(?:Gen\s*4|PCIe\s*4|4\.0)\b", title, re.I):
            gen = "Gen 4"
        elif re.search(r"\b(?:Gen\s*3|PCIe\s*3|3\.0)\b", title, re.I):
            gen = "Gen 3"

        nvme_type = "M.2 NVMe" if re.search(r"\b(?:NVMe|PCIe)\b", title, re.I) else ("M.2 SATA" if "m.2" in title_lower else "SATA SSD")
        interface_str = f"{nvme_type} {gen}".strip() if gen else nvme_type

        # Speed (e.g. 7450 MB/s or 5000 MB/s)
        speed_match = re.search(r"\b(Up to\s*\d{3,5}\s*MB/s|\d{3,5}\s*MB/s)\b", title, re.I)
        speed = speed_match.group(1).title() if speed_match else ""

        # Form factor or heatsink
        heatsink = "With Heatsink" if re.search(r"\bheatsink\b", title, re.I) else ""

        # Brand extraction
        brand_match = re.search(
            r"\b(Samsung|Crucial|Western Digital|WD Black|WD|Kingston|ADATA|Corsair|Seagate|Lexar|SanDisk|Teamgroup|Gigabyte|MSI|Consistent|Ant Esports|EVM|Matrix|Intelaxy|M[il]cron|Biwin|Zebronics|Hikvision|Presolve|Starkway|PNY|Miphi)\b",
            title,
            re.I
        )
        brand = brand_match.group(1) if brand_match else ""
        if brand.lower() == "wd":
            brand = "WD"
        elif brand.lower() == "adata":
            brand = "ADATA"
        elif brand.lower() == "evm":
            brand = "EVM"
        elif brand.lower() == "pny":
            brand = "PNY"
        elif brand:
            brand = brand.title()

        # Model extraction
        model_match = re.search(
            r"\b(990\s*Pro|990\s*EVO\s*Plus|990\s*EVO|990|980\s*Pro|980|970\s*Evo\s*Plus|970\s*Evo|970\s*Pro|9100\s*Pro|T700|T500|P3\s*Plus|P3|P5\s*Plus|P5|SN850X|SN850|SN770|SN7100|SN580|SN570|SN5100|KC3000|NV2|NV3|Firecuda\s*530|E3000|MN26|NV7400|Gammix\s*S70\s*Blade|Gammix|S70\s*Blade|AN1500)\b",
            title,
            re.I
        )
        model = model_match.group(1).strip() if model_match else ""

        clean_name = f"{brand} {model} {capacity} NVMe SSD".replace("  ", " ").strip() if (brand and model) else (
            f"{brand} {capacity} {nvme_type}".strip() if brand else f"{capacity} {nvme_type}".strip()
        )
        if not clean_name or len(clean_name) < 4:
            clean_name = title.split("(")[0].strip()[:50]

        tag_spec = heatsink or speed or "Solid State"
        return {
            "name": clean_name[:50].strip(),
            "cpu": capacity or "SSD",
            "ram": interface_str,
            "ssd": tag_spec,
            "gpu": "Storage",
        }

    # ── 4. Laptops ────────────────────────────────────────────────────
    if is_laptop:
        ram = ""
        ram_match = re.search(r"\b(\d+\s*GB)\b(?!\s*(?:Graphics|GFX|VRAM|SSD|Storage|EMMC))", title, re.I)
        if ram_match:
            ram = ram_match.group(1).upper().replace(" ", "")
        else:
            for b in badges:
                b_match = re.search(r"\b(\d+\s*GB)\s*(?:DDR\d+|RAM)?\b", b, re.I)
                if b_match and "graphics" not in b.lower():
                    ram = b_match.group(1).upper().replace(" ", "")
                    break

        ssd = ""
        ssd_match = re.search(r"\b(\d+\s*(?:GB|TB)\s*(?:SSD|EMMC|HDD|Storage))\b", title, re.I)
        if ssd_match:
            ssd = ssd_match.group(1).upper()
        else:
            for b in badges:
                b_match = re.search(r"\b(\d+\s*(?:GB|TB)\s*(?:SSD|EMMC|HDD))\b", b, re.I)
                if b_match:
                    ssd = b_match.group(1).upper()
                    break

        gpu = ""
        for b in badges:
            b_lower = b.lower()
            if any(k in b_lower for k in ["rtx", "geforce", "radeon", "gfx", "graphics", "iris", "arc"]):
                gpu = b.strip()
                break
        if not gpu:
            gpu_match = re.search(
                r"\b(?:NVIDIA\s+GeForce\s+)?(RTX\s*\d{4}(?:\s*Ti)?(?:\s*\d+\s*GB)?|GTX\s*\d{4}(?:\s*Ti)?|Radeon\s*[A-Za-z0-9]+|Intel\s+Iris\s+X[e]|Intel\s+Arc\s+[A-Za-z0-9]+)\b",
                title,
                re.I,
            )
            if gpu_match:
                gpu = gpu_match.group(0).strip()
        if not gpu:
            gpu = "Integrated Graphics"

        cpu = ""
        cpu_patterns = [
            r"AMD\s+Ryzen\s+(?:AI\s+Max\+?|[3579]\s+(?:Octa|Hexa|Quad)\s+Core|[3579]\s+\d+[A-Za-z0-9\+\-]*|[3579](?:\s+1[0-4]th\s+Gen)?|[3579])",
            r"Intel\s+(?:Core\s+)?(?:Ultra\s+)?[iI]?[3579](?:\s+1[0-4]th\s+Gen|\s+\d+[A-Za-z0-9]*|-\d+[A-Za-z0-9]*)?",
            r"Intel\s+Celeron(?:\s+Dual\s+Core)?(?:\s+[A-Za-z0-9]+)?",
            r"(?:Apple\s+)?M[1-4](?:\s+(?:Pro|Max))?",
            r"MediaTek\s+[A-Za-z0-9\s]+",
            r"Qualcomm\s+Snapdragon\s+[A-Za-z0-9\s\+]+",
        ]
        for pattern in cpu_patterns:
            m = re.search(r"\b(" + pattern + r")\b", title, re.I)
            if m:
                cpu = m.group(0).strip()
                break
        if not cpu:
            for b in badges:
                if any(k in b.lower() for k in ["core", "ryzen", "celeron", "snapdragon", "kompanio"]):
                    cpu = b.strip()
                    break
        if not cpu:
            cpu = "Standard Processor"

        name = title.split(" - (")[0]
        name = re.sub(r"\s*(?:for Creator|with Touch Screen|MSO \d+|M365|\+ M365|AI PC).*$", "", name, flags=re.I)
        name = re.sub(r"\s*(?:AMD Ryzen|Intel Core|Intel Celeron|Apple M|Thin and Light|Gaming Laptop).*$", "", name, flags=re.I).strip()
        if not name or len(name) < 3:
            name = title[:45] if title else "Laptop"

        return {
            "name": name.strip()[:45],
            "cpu": cpu or "Processor in title",
            "ram": ram or "RAM in specs",
            "ssd": ssd or "Storage in specs",
            "gpu": gpu or "Integrated Graphics",
        }

    # ── 4. Universal Generic Product Fallback ─────────────────────────
    spec_tokens = []
    if badges:
        spec_tokens = [b.strip() for b in badges[:4] if b.strip()]
    else:
        patterns = [
            r"\b\d+(?:\.\d+)?\s*(?:kg|Litres?|L|Ton|inch|Place\s*Settings?|mAh|RPM|W)\b",
            r"\b[1-5]\s*Star\b",
            r"\b(?:4K\s*Ultra\s*HD|Full\s*HD|QLED|OLED|LED)\b",
            r"\b(?:Front\s*Load|Top\s*Load|Fully\s*Automatic|Semi\s*Automatic)\b",
            r"\b(?:Frost\s*Free|Direct\s*Cool|Inverter)\b",
            r"\b(?:Wireless|Bluetooth|ANC|Noise\s*Cancellation)\b",
        ]
        for pat in patterns:
            found = re.findall(pat, title, re.I)
            for f in found:
                f_clean = f.strip()
                if f_clean and f_clean.lower() not in [x.lower() for x in spec_tokens]:
                    spec_tokens.append(f_clean)
                if len(spec_tokens) >= 4:
                    break
            if len(spec_tokens) >= 4:
                break

    clean_name = re.sub(r"\s*(?:with\s+Bank\s+offer|Free\s+Delivery|Exchange\s+offer|\([^\)]+\)).*$", "", title, flags=re.I).strip()
    if not clean_name:
        clean_name = title[:45]

    return {
        "name": clean_name[:45].strip(),
        "cpu": spec_tokens[0] if len(spec_tokens) > 0 else "",
        "ram": spec_tokens[1] if len(spec_tokens) > 1 else "",
        "ssd": spec_tokens[2] if len(spec_tokens) > 2 else "",
        "gpu": spec_tokens[3] if len(spec_tokens) > 3 else "",
    }


parse_laptop_specs = parse_product_specs


# ═══════════════════════════════════════════════════════════════════════════
# Mobile Listing Virtual-Scroll Extractor JS
# ═══════════════════════════════════════════════════════════════════════════

JS_MOBILE_PRODUCT_EXTRACTOR = """
() => {
    const cleanPrice = (str) => {
        if (!str) return null;
        // Match only a single currency token like ₹59,990 or 59,990
        const match = str.match(/₹\s*([0-9,]+(?:\.[0-9]+)?)/);
        let cleaned = '';
        if (match) {
            cleaned = match[1].replace(/,/g, '');
        } else {
            cleaned = str.replace(/[^0-9.]/g, '');
        }
        const n = parseFloat(cleaned);
        // Valid products on Flipkart are between ₹200 and ₹8,00,000
        if (isNaN(n) || n < 200 || n > 800000) return null;
        return n;
    };

    const found = [];
    const seenPids = new Set();
    const links = document.querySelectorAll('a[href*="/p/"]');

    links.forEach(a => {
        const href = a.getAttribute('href') || '';
        if (!href.includes('/p/')) return;

        // Extract PID
        let pid = '';
        const pidMatch = href.match(/[?&]pid=([A-Z0-9]+)/i);
        if (pidMatch) {
            pid = pidMatch[1];
        } else {
            const itmMatch = href.match(/\\/p\\/(itm[a-z0-9]+)/i);
            if (itmMatch) pid = itmMatch[1];
        }
        if (!pid || seenPids.has(pid)) return;

        // Title
        let title = '';
        const clampEl = a.querySelector('[style*="-webkit-line-clamp"]');
        if (clampEl) {
            title = clampEl.innerText.trim();
        } else {
            title = a.innerText.trim();
        }
        if (!title || title.length < 5) return;

        // Card Container search
        let card = a.parentElement;
        let depth = 0;
        while (card && depth < 8) {
            if (card.style.transform || (card.className && card.className.includes('css-g5y9jx'))) {
                break;
            }
            card = card.parentElement;
            depth++;
        }
        if (!card) card = a.parentElement || a;

        // Extract Spec Badges (e.g. "NVIDIA GeForce RTX 4050 6 GB GFX", "16 GB DDR5 RAM")
        const badges = [];
        const badgeContainers = card.querySelectorAll('[style*="border-width: 1px"], [style*="border-width:1px"]');
        badgeContainers.forEach(bc => {
            const text = bc.innerText ? bc.innerText.trim() : '';
            if (text && text.length > 2 && text.length < 60) {
                badges.push(text);
            }
        });

        // Prices
        let mrp = null;
        let regularPrice = null;
        let wowPrice = null;

        // 1. WoW / Bank offer price
        const allDivs = Array.from(card.querySelectorAll('div, span'));
        for (const el of allDivs) {
            const text = (el.innerText || '').trim();
            const style = el.getAttribute('style') || '';
            const isBlue = style.includes('22, 66, 185') || style.includes('22,66,185');

            // Detect if this element represents an EMI installment breakdown (e.g. ₹7,332 x 6m or ₹7,332/month)
            const parentText = (el.parentElement ? el.parentElement.innerText : '').toLowerCase();
            const nextText = (el.nextElementSibling ? el.nextElementSibling.innerText : '').toLowerCase();
            const selfText = text.toLowerCase();
            const fullContext = selfText + ' ' + parentText + ' ' + nextText;

            const isEmi = fullContext.includes('/month') || fullContext.includes('per month') ||
                          fullContext.includes('/m ') || fullContext.includes('/m\\n') ||
                          fullContext.includes('no cost emi') || fullContext.includes('standard emi') ||
                          /\bx\s*\d+\s*m\b/i.test(fullContext);

            // Monthly EMI is NOT a discounted WoW deal (it's paying the regular price over time).
            // Skip any EMI monthly installment from being captured as the lump-sum WoW deal.
            if (isEmi) {
                continue;
            }

            if (isBlue && text.includes('₹')) {
                let parsed = cleanPrice(text);
                if (parsed) {
                    wowPrice = parsed;
                }
            } else if (text.toLowerCase().includes('bank offer') || text.toLowerCase().includes('lowest price')) {
                const parent = el.parentElement;
                if (parent) {
                    const priceNodes = parent.querySelectorAll('div, span');
                    for (const pn of priceNodes) {
                        const pnText = (pn.innerText || '').toLowerCase();
                        if (pnText.includes('/month') || pnText.includes('per month') || pnText.includes('emi') || /\bx\s*\d+\s*m\b/i.test(pnText)) continue;
                        if (pn !== el && pn.innerText && pn.innerText.includes('₹')) {
                            let p = cleanPrice(pn.innerText);
                            if (p && (!wowPrice || p < wowPrice)) {
                                wowPrice = p;
                            }
                        }
                    }
                }
            }
        }

        // 2. MRP (strikethrough)
        const strikeEls = card.querySelectorAll('[style*="line-through"]');
        for (const s of strikeEls) {
            if (s.innerText && s.innerText.includes('₹')) {
                const parsed = cleanPrice(s.innerText);
                if (parsed) {
                    mrp = parsed;
                    break;
                }
            }
        }

        // 3. Regular Selling Price
        for (const el of allDivs) {
            const style = el.getAttribute('style') || '';
            if (style.includes('line-through')) continue;
            if (style.includes('22, 66, 185') || style.includes('22,66,185')) continue;

            // Only inspect leaf nodes to prevent concatenating sibling/child prices
            if (el.children && el.children.length > 0) continue;

            const text = (el.innerText || '').trim();
            const parentText = (el.parentElement ? el.parentElement.innerText : '').toLowerCase();
            const selfText = text.toLowerCase();
            const fullContext = selfText + ' ' + parentText;

            // Skip exchange offers & EMI installment notes
            if (fullContext.includes('exchange')) continue;
            if (fullContext.includes('/month') || fullContext.includes('per month') || fullContext.includes('emi') || /\bx\s*\d+\s*m\b/i.test(fullContext)) continue;

            if (text.startsWith('₹') && text.length <= 15) {
                const parsed = cleanPrice(text);
                if (parsed && parsed !== mrp && parsed !== wowPrice) {
                    regularPrice = parsed;
                    break;
                }
            }
        }

        if (!regularPrice && !wowPrice && mrp) {
            regularPrice = mrp;
        }

        // Sanity check: WoW price must be a realistic lump-sum discount off regular selling price
        // Genuine bank WoW discounts range between 3% and 40% off (wowPrice >= 0.55 * regularPrice).
        // If wowPrice < 0.55 * regularPrice, it is an EMI fragment (e.g. ₹7,332 on ₹43,990) and MUST be rejected!
        if (regularPrice && wowPrice) {
            if (wowPrice >= regularPrice || wowPrice < (regularPrice * 0.55) || wowPrice < 200) {
                wowPrice = null;
            }
        }

        const effectivePrice = wowPrice || regularPrice;
        if (!effectivePrice) return;

        let fullUrl = href;
        if (fullUrl.startsWith('/')) {
            fullUrl = 'https://www.flipkart.com' + fullUrl;
        }

        seenPids.add(pid);
        found.push({
            pid,
            title,
            badges,
            url: fullUrl,
            image_url: '',  // Images explicitly disabled
            mrp,
            regular_price: regularPrice || effectivePrice,
            wow_price: wowPrice,
            effective_price: effectivePrice
        });
    });

    return found;
}
"""


# ── Aggressive Bandwidth / Data-Saver Blocking ──────────────────────────────
BLOCKED_RESOURCE_TYPES = {"image", "media", "font"}
BLOCKED_DOMAINS_AND_PATTERNS = [
    # Analytics & Trackers
    "google-analytics.com",
    "googletagmanager.com",
    "doubleclick.net",
    "connect.facebook.net",
    "facebook.com/tr",
    "branch.io",
    "crashlytics",
    "clarity.ms",
    "hotjar.com",
    "criteo.com",
    "criteo.net",
    "bat.bing.com",
    "scorecardresearch.com",
    "omniture.com",
    "tiqcdn.com",
    "tealium",
    # Telemetry / Beacons
    "/telemetry",
    "/beacon",
    "/collect",
    "/events",
    "/logger",
    "/pageview",
    # Ads & Heavy Junk
    "adservice.google",
    "securepubads",
    "pubmatic.com",
    "rubiconproject.com",
    "adnxs.com",
]


async def _setup_data_saver_routes(context) -> None:
    """
    Aggressively blocks unnecessary media, fonts, analytics, ads, and telemetry
    to reduce proxy bandwidth consumption by 70-80% on every scrape.
    """
    async def _interceptor(route):
        req = route.request
        res_type = req.resource_type
        url_lower = req.url.lower()

        # 1. Block heavy resource types
        if res_type in BLOCKED_RESOURCE_TYPES:
            await route.abort()
            return

        # 2. Block media/font file extensions
        if re.search(r"\.(?:png|jpe?g|webp|gif|svg|ico|woff2?|ttf|eot|otf|mp4|webm|mp3)(?:\?.*)?$", url_lower):
            await route.abort()
            return

        # 3. Block tracking, telemetry, and advertising requests
        if any(pattern in url_lower for pattern in BLOCKED_DOMAINS_AND_PATTERNS):
            await route.abort()
            return

        await route.continue_()

    await context.route("**/*", _interceptor)


# ── Flipkart Dead Laptop Exchange Auto-Setup ─────────────────────────────────
EXCHANGE_SEED_URL = (
    "https://www.flipkart.com/hp-omen-ai-amd-ryzen-7-octa-core-350-24-gb-1-tb-ssd-windows-11-home-8-gb-graphics-nvidia-geforce-rtx-5050-16-ap0165ax-gaming-laptop/p/itm5661c90728083?pid=COMHEHHXKFQSABXZ"
)


async def setup_dead_laptop_exchange(page: Page, pincode: str = "560001") -> bool:
    """
    Initializes a dead / non-working laptop exchange on Flipkart.
    Navigates to a seed laptop with exchange enabled, sets delivery pincode,
    selects 'Laptop' -> 'Any - Laptop Not Working' -> confirms exchange.
    This binds the exchange bonus session to the browser context so all subsequent
    listing cards and product navigations benefit from active exchange discounts and bonuses.
    """
    logger.info("🔄 Pre-loading dead laptop exchange into session (Pincode: %s)...", pincode)
    try:
        await page.goto(EXCHANGE_SEED_URL, wait_until="domcontentloaded", timeout=45000)
        await asyncio.sleep(2.5)

        # 1. Pincode entry
        pin_trigger = page.locator("text='Change pincode to exchange item'").first
        if await pin_trigger.count() > 0:
            await pin_trigger.click()
            await asyncio.sleep(1.2)
            pin_input = page.locator("input[placeholder*='pincode' i], input#pincodeInputId").first
            if await pin_input.count() > 0:
                await pin_input.fill(pincode)
                await page.keyboard.press("Enter")
                await asyncio.sleep(2.5)
                logger.info("📍 Delivery pincode set to %s", pincode)

        # 2. Click 'Select a product to exchange'
        try:
            sel_btn = page.locator("text='Select a product to exchange'").first
            await sel_btn.wait_for(state="visible", timeout=12000)
            await sel_btn.scroll_into_view_if_needed()
            await sel_btn.click()
            await asyncio.sleep(2.0)
        except Exception:
            clicked = await page.evaluate("""() => {
                const el = Array.from(document.querySelectorAll('*')).find(e => (e.innerText || '').trim() === 'Select a product to exchange');
                if (el) { el.click(); return true; }
                return false;
            }""")
            if not clicked:
                logger.info("Exchange product selection button not found or already configured.")
                return False
            await asyncio.sleep(2.0)

        # 3. Select Category: 'Laptop'
        laptop_clicked = await page.evaluate("""() => {
            const el = Array.from(document.querySelectorAll('*')).find(e => (e.innerText || '').trim() === 'Laptop' && e.style.cursor === 'pointer');
            if (el) { el.click(); return true; }
            const fallback = Array.from(document.querySelectorAll('*')).find(e => (e.innerText || '').trim() === 'Laptop');
            if (fallback) { fallback.click(); return true; }
            return false;
        }""")
        if not laptop_clicked:
            logger.warning("Could not select Laptop category in exchange modal.")
            return False

        await asyncio.sleep(1.2)

        # Click Next
        await page.evaluate("""() => {
            const btn = Array.from(document.querySelectorAll('div, button, span')).find(e => (e.innerText || '').trim() === 'Next');
            if (btn) btn.click();
        }""")
        await asyncio.sleep(1.8)

        # 4. Select Brand: 'Any - Laptop Not Working'
        dead_opt = page.locator("text='Any - Laptop Not Working'").first
        if await dead_opt.count() > 0:
            await dead_opt.click()
            await asyncio.sleep(1.0)
            # Click Next
            await page.evaluate("""() => {
                const btn = Array.from(document.querySelectorAll('div, button, span')).find(e => (e.innerText || '').trim() === 'Next');
                if (btn) btn.click();
            }""")
            await asyncio.sleep(1.8)
        else:
            logger.warning("Could not find 'Any - Laptop Not Working' in exchange brand list.")
            return False

        # 5. Agree to Terms & Confirm Exchange
        await page.evaluate("""() => {
            const cb = document.querySelector('input[type=\"checkbox\"]');
            if (cb && !cb.checked) cb.click();
            const terms = Array.from(document.querySelectorAll('*')).find(e => (e.innerText || '').includes('agree to the terms'));
            if (terms) terms.click();
        }""")
        await asyncio.sleep(0.8)

        confirmed = await page.evaluate("""() => {
            const btn = Array.from(document.querySelectorAll('button, div, span')).find(e => (e.innerText || '').trim() === 'Confirm Exchange');
            if (btn) { btn.click(); return true; }
            return false;
        }""")

        if confirmed:
            await asyncio.sleep(2.5)
            logger.info("✅ Dead laptop exchange successfully confirmed and attached to session!")
            return True
        else:
            logger.warning("Could not click 'Confirm Exchange' button.")
            return False

    except Exception as e:
        logger.warning("⚠️ Exchange setup skipped: %s. Continuing with direct listing harvest.", e)
        return False


async def scrape_listing_mobile(
    url: str,
    max_scrolls: int = 15,
    scroll_delay: float = 0.9,
    apply_exchange: bool = False,
    category: str = "general",
) -> list[dict]:
    """
    Scrapes a Flipkart listing in Mobile View.
    Blocks all image/media requests to ensure maximum speed and minimum overhead.
    Optionally pre-loads a dead/non-working laptop exchange into the session (for laptops only).
    Uses multi-channel virtual scrolling to harvest products, specs, and WoW prices.
    """
    async with _semaphore:
        proxy_config = _get_proxy_config()
        if proxy_config:
            logger.info("🛡️ Using proxy server: %s", proxy_config.get("server"))
        user_agent = random.choice(MOBILE_USER_AGENTS)

        playwright = await async_playwright().start()
        browser = None
        harvested_products: dict[str, dict] = {}

        try:
            browser = await playwright.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )

            exchange_cookies = []
            # Pre-load dead laptop exchange ONLY when apply_exchange is True (laptops only)
            if apply_exchange:
                pincode = os.getenv("DEFAULT_PINCODE", "560001").strip()
                desktop_ctx = await browser.new_context(
                    user_agent=random.choice(DESKTOP_USER_AGENTS),
                    viewport={"width": 1280, "height": 800},
                    locale="en-IN",
                    timezone_id="Asia/Kolkata",
                )
                await _setup_data_saver_routes(desktop_ctx)
                desktop_page = await desktop_ctx.new_page()
                try:
                    ex_ok = await setup_dead_laptop_exchange(desktop_page, pincode=pincode)
                    if ex_ok:
                        exchange_cookies = await desktop_ctx.cookies()
                        logger.info("🍪 Captured %d session cookies with active exchange bonus", len(exchange_cookies))
                except Exception as e:
                    logger.warning("Exchange setup encountered issue: %s", e)
                finally:
                    await desktop_ctx.close()

            # Mobile emulation context for virtual scroll listing
            context = await browser.new_context(
                user_agent=user_agent,
                proxy=proxy_config,
                viewport={"width": 390, "height": 844},
                device_scale_factor=2,
                is_mobile=True,
                has_touch=True,
                locale="en-IN",
                timezone_id="Asia/Kolkata",
            )

            # 🛑 CRITICAL OPTIMIZATION: Aggressively block images, fonts, analytics & telemetry
            await _setup_data_saver_routes(context)

            if exchange_cookies:
                await context.add_cookies(exchange_cookies)

            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-IN', 'en-US', 'en'] });
            """)

            page = await context.new_page()

            resp = None
            for nav_attempt in range(2):
                try:
                    logger.info("📱 Navigating to mobile listing (data saver active, attempt %d): %s", nav_attempt + 1, url)
                    resp = await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    break
                except Exception as nav_err:
                    if nav_attempt == 0:
                        logger.warning("Proxy connection failed (%s), rotating to another proxy...", nav_err)
                        proxy_config = _get_proxy_config()
                        await context.close()
                        context = await browser.new_context(
                            user_agent=user_agent,
                            proxy=proxy_config,
                            viewport={"width": 390, "height": 844},
                            device_scale_factor=2,
                            is_mobile=True,
                            has_touch=True,
                            locale="en-IN",
                            timezone_id="Asia/Kolkata",
                        )
                        await _setup_data_saver_routes(context)
                        if exchange_cookies:
                            await context.add_cookies(exchange_cookies)
                        page = await context.new_page()
                    else:
                        raise nav_err

            page_title = (await page.title()).lower()
            if "recaptcha" in page_title or (resp and resp.status == 403):
                if proxy_config:
                    logger.warning("⚠️ Proxy %s was challenged with Flipkart reCAPTCHA. Retrying with clean connection…", proxy_config.get("server"))
                    await browser.close()
                    browser = await playwright.chromium.launch(
                        headless=True,
                        args=["--disable-blink-features=AutomationControlled"],
                    )
                    context = await browser.new_context(
                        user_agent=user_agent,
                        viewport={"width": 390, "height": 844},
                        device_scale_factor=2,
                        is_mobile=True,
                        has_touch=True,
                        locale="en-IN",
                        timezone_id="Asia/Kolkata",
                    )
                    await _setup_data_saver_routes(context)
                    page = await context.new_page()
                    await page.goto(url, wait_until="domcontentloaded", timeout=45000)

            # Wait initial render
            await asyncio.sleep(2.0)

            logger.info("📜 Starting virtual scroll for %d iterations…", max_scrolls)
            for scroll_idx in range(max_scrolls):
                # 1. Harvest currently visible cards in the DOM
                current_batch = await page.evaluate(JS_MOBILE_PRODUCT_EXTRACTOR)
                for item in current_batch:
                    pid = item["pid"]
                    # Skip junk accessories sellers spam into SSD category (VR headsets, expansion cards, risers, etc.)
                    if category == "ssd" and re.search(r"\b(?:VR\s*Headset|Virtual\s*Reality|VR\s*Box|Glasses|Expansion\s*Card|Riser\s*Card|PCI-?E\s*(?:Adapter|Riser|Slots)|USB\s*(?:Card|Hub)|Docking\s*Station|Heatsink\s*Solution|M\.2\s*NVME\s*to\s*PCIe)\b", item.get("title", ""), re.I):
                        continue
                    if pid not in harvested_products or (not harvested_products[pid].get("wow_price") and item.get("wow_price")):
                        # Parse product specs (supporting RAM, laptops, and hardware)
                        specs = parse_product_specs(item["title"], item.get("badges", []), category=category)
                        item.update(specs)
                        harvested_products[pid] = item

                # 2. Multi-channel scroll: Dispatch wheel + keyboard PageDown + inner container scrollTop
                await page.mouse.move(200, 400)
                await page.mouse.wheel(0, 800)
                await page.keyboard.press("PageDown")

                await page.evaluate("""() => {
                    const scrollables = document.querySelectorAll('.r-150rngu, [style*="overflow-y"], [style*="overflow:"]');
                    scrollables.forEach(el => { el.scrollTop += 800; });
                    window.scrollBy(0, 800);
                    if (document.scrollingElement) {
                        document.scrollingElement.scrollTop += 800;
                    }
                }""")

                # 3. Brief pause allowing virtual list to mount next set of items
                await asyncio.sleep(scroll_delay)

            logger.info(
                "✅ Finished mobile listing scrape. Harvested %d unique items.",
                len(harvested_products),
            )
            return list(harvested_products.values())

        finally:
            if browser:
                await browser.close()
            await playwright.stop()


async def apply_flipkart_pincode(page: Page, pincode: str = None) -> bool:
    """
    Ensures Flipkart has confirmed the user's delivery pincode so prices,
    sellers, and bank discounts reflect 100% genuine local fulfillment instead
    of unassigned placeholder/ghost sellers (like OmniTechRetail).
    """
    pincode = (pincode or os.getenv("DELIVERY_PINCODE") or os.getenv("DEFAULT_PINCODE") or "560016").strip()
    try:
        has_pin = await page.evaluate(f"() => document.body.innerText.includes('{pincode}')")
        if has_pin:
            return True

        loc = page.locator("text='Select delivery location'").first
        if await loc.count() > 0:
            await loc.click()
            await asyncio.sleep(1.0)
            inp = page.locator("input[placeholder*='pin code' i]").first
            if await inp.count() > 0:
                await inp.fill(pincode)
                await asyncio.sleep(1.5)
                # Click first suggestion matching the pincode
                items = await page.query_selector_all("div, li, span")
                for el in items:
                    txt = (await el.inner_text() or "").strip()
                    if pincode in txt and len(txt) < 80:
                        await el.click()
                        break
                await asyncio.sleep(2.0)
                try:
                    await page.click('text="Confirm"', timeout=4000)
                    await asyncio.sleep(3.0)
                except Exception:
                    pass
                logger.info("📍 Applied and confirmed delivery pincode: %s", pincode)
                return True
    except Exception as e:
        logger.debug("Pincode setup skipped/failed: %s", e)
    return False


async def verify_flipkart_pdp_price(url: str) -> dict:
    """
    Visits a Flipkart product detail page (PDP) on desktop viewport with delivery pincode applied
    to double-check deals where drop > 35%.
    Distinguishes genuine deep clearance drops from monthly EMI artifacts or ghost sellers.
    Uses data saver mode (images/media blocked) to verify in ~2.5s with minimal bandwidth.
    """
    playwright = await async_playwright().start()
    browser = None
    try:
        browser = await playwright.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            user_agent=random.choice(DESKTOP_USER_AGENTS),
            viewport={"width": 1280, "height": 800},
            locale="en-IN",
            timezone_id="Asia/Kolkata",
        )
        await _setup_data_saver_routes(context)
        page = await context.new_page()

        resp = await page.goto(url, wait_until="domcontentloaded", timeout=25000)
        page_title = (await page.title()).lower()
        if "recaptcha" in page_title or (resp and resp.status == 403):
            logger.warning("⚠️ Captcha encountered during PDP verification for: %s", url)
            return {"success": False, "reason": "captcha"}

        await asyncio.sleep(1.5)
        # Apply delivery pincode before reading PDP price
        await apply_flipkart_pincode(page)

        data = await page.evaluate('''() => {
            const clean = (str) => {
                if (!str) return null;
                const match = str.match(/₹\\s*([0-9,]+(?:\\.[0-9]+)?)/);
                if (!match) return null;
                const n = parseFloat(match[1].replace(/,/g, ''));
                return (isNaN(n) || n < 200 || n > 800000) ? null : n;
            };

            let regularPrice = null;
            let wowPrice = null;
            let maxFont = 0;

            const allLeaves = [];
            document.querySelectorAll('*').forEach(el => {
                if (el.children.length === 0) {
                    const t = (el.innerText || '').trim();
                    if (t.includes('₹')) {
                        const style = window.getComputedStyle(el);
                        const fs = parseFloat(style.fontSize) || 0;
                        const strike = style.textDecorationLine.includes('line-through') || style.textDecoration.includes('line-through');
                        allLeaves.push({ text: t, fs, strike });
                    }
                }
            });

            // 1. Regular selling price is the prominent un-struck price (largest font >= 18px)
            for (const item of allLeaves) {
                if (!item.strike && !item.text.toLowerCase().includes('/m') && !/\\bx\\s*\\d+\\s*m\\b/i.test(item.text)) {
                    if (item.fs > maxFont) {
                        const p = clean(item.text);
                        if (p) {
                            maxFont = item.fs;
                            regularPrice = p;
                        }
                    }
                }
            }

            // 2. Check for "Buy at ₹...", "Lowest price for you", or "Lowest price"
            for (const item of allLeaves) {
                const tLower = item.text.toLowerCase();
                if (tLower.includes('buy at') || tLower.includes('lowest price')) {
                    const p = clean(item.text);
                    if (p && (!regularPrice || p < regularPrice)) {
                        wowPrice = p;
                    }
                }
            }

            const titleEl = document.querySelector('h1, [style*="-webkit-line-clamp"]');
            const title = titleEl ? titleEl.innerText.trim() : '';

            return { title, regularPrice, wowPrice };
        }''')

        reg = data.get("regularPrice")
        wow = data.get("wowPrice")
        effective = wow if wow and reg and wow < reg else reg

        if not effective:
            return {"success": False, "reason": "no_price"}

        return {
            "title": data.get("title", ""),
            "verified_regular_price": reg,
            "verified_wow_price": wow,
            "verified_effective_price": effective,
            "success": True,
        }

    except Exception as e:
        logger.warning("Error verifying PDP price for %s: %s", url, e)
        return {"success": False, "reason": str(e)}
    finally:
        if browser:
            await browser.close()
        await playwright.stop()


# ═══════════════════════════════════════════════════════════════════════════
# Single Product Scraper
# ═══════════════════════════════════════════════════════════════════════════

async def _extract_amazon(page: Page) -> ScrapedProduct:
    await page.wait_for_selector("#productTitle", timeout=15000)
    title = ""
    for sel in ["#productTitle"]:
        el = await page.query_selector(sel)
        if el:
            title = (await el.inner_text()).strip()
            break

    price = None
    price_selectors = [
        "span.a-price-whole",
        "#priceblock_ourprice",
        "#priceblock_dealprice",
        "span.a-offscreen",
        "#corePrice_feature_div span.a-offscreen",
    ]
    for sel in price_selectors:
        el = await page.query_selector(sel)
        if el:
            raw = (await el.inner_text()).strip()
            price = _parse_price(raw)
            if price is not None:
                break

    if price is None:
        raise ValueError("Could not extract price from Amazon page")

    return ScrapedProduct(
        title=title or "Unknown Product",
        price=price,
        image_url="",
        platform="amazon",
    )


async def _extract_flipkart(page: Page) -> ScrapedProduct:
    # Resilient DOM evaluation using TreeWalker & computed CSS font sizes
    # Matches both legacy Flipkart PDPs and modern React/Next.js dynamic layouts
    data = await page.evaluate("""() => {
        const clean = (str) => {
            if (!str) return null;
            const match = str.match(/(?:₹|Rs\\.?)\\s*([0-9,]+(?:\\.[0-9]+)?)/i);
            if (!match) return null;
            const n = parseFloat(match[1].replace(/,/g, ''));
            return (isNaN(n) || n < 100 || n > 1000000) ? null : n;
        };

        let regularPrice = null;
        let wowPrice = null;
        let maxFont = 0;

        const allLeaves = [];
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
        let node;
        while ((node = walker.nextNode())) {
            const t = node.nodeValue.trim();
            if ((t.includes('₹') || t.toLowerCase().includes('rs.')) && t.length < 50) {
                const el = node.parentElement;
                if (!el) continue;
                const style = window.getComputedStyle(el);
                const fs = parseFloat(style.fontSize) || 0;
                const strike = style.textDecorationLine.includes('line-through') || style.textDecoration.includes('line-through');
                allLeaves.push({ text: t, fs, strike, elText: el.innerText || '' });
            }
        }

        // 1. Regular selling price is the prominent un-struck price (largest font >= 16px)
        for (const item of allLeaves) {
            const tLower = item.text.toLowerCase();
            if (!item.strike && !tLower.includes('/m') && !/\\bx\\s*\\d+\\s*m\\b/i.test(tLower) && !tLower.includes('off') && !tLower.includes('fee')) {
                if (item.fs > maxFont) {
                    const p = clean(item.text);
                    if (p) {
                        maxFont = item.fs;
                        regularPrice = p;
                    }
                }
            }
        }

        // 2. Check for "Buy at ₹...", "Lowest price for you", or "Lowest price"
        for (const item of allLeaves) {
            const tLower = (item.text + ' ' + item.elText).toLowerCase();
            if (tLower.includes('buy at') || tLower.includes('lowest price')) {
                const p = clean(item.text) || clean(item.elText);
                if (p && (!regularPrice || p < regularPrice)) {
                    wowPrice = p;
                }
            }
        }

        // Clean document title vs h1
        const docTitle = document.title.split(/Price in India|\\||- Buy/i)[0].trim();
        const titleEl = document.querySelector('h1, span.VU-ZEz, span.B_NuCI');
        let h1Title = titleEl ? titleEl.innerText.replace(/\\s*\\.{3}\\s*more$/i, '').trim() : '';

        const resolvedTitle = (docTitle && docTitle.length >= h1Title.length) ? docTitle : (h1Title || docTitle);

        const metaOg = document.querySelector('meta[property="og:image"], meta[name="og:image"]');
        const imgEl = document.querySelector('img[src*="rukminim"], img[src*="image/"], img._396cs4, img.DByuf4');
        const imageUrl = (metaOg ? metaOg.content : '') || (imgEl ? imgEl.src : '');

        return {
            title: resolvedTitle,
            regularPrice,
            wowPrice,
            effectivePrice: wowPrice || regularPrice,
            imageUrl
        };
    }""")

    effective_price = data.get("effectivePrice")
    resolved_title = data.get("title") or "Unknown Product"
    image_url = data.get("imageUrl") or ""

    if effective_price is None:
        raise ValueError("Could not extract price from Flipkart page")

    return ScrapedProduct(
        title=resolved_title,
        price=effective_price,
        image_url=image_url,
        platform="flipkart",
    )


async def scrape_product(url: str) -> ScrapedProduct:
    async with _semaphore:
        proxy_config = _get_proxy_config()
        if proxy_config:
            logger.info("🛡️ Using proxy server: %s", proxy_config.get("server"))
        user_agent = random.choice(DESKTOP_USER_AGENTS)

        playwright = await async_playwright().start()
        browser = None
        try:
            browser = await playwright.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )

            context = await browser.new_context(
                user_agent=user_agent,
                proxy=proxy_config,
                viewport={"width": 1920, "height": 1080},
                locale="en-IN",
                timezone_id="Asia/Kolkata",
            )
            # Aggressively block images, fonts, analytics, ads & telemetry
            await _setup_data_saver_routes(context)

            page = await context.new_page()

            for nav_attempt in range(2):
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    break
                except Exception as nav_err:
                    if nav_attempt == 0:
                        logger.warning("Proxy connection failed (%s), rotating to fresh proxy...", nav_err)
                        proxy_config = _get_proxy_config()
                        await context.close()
                        context = await browser.new_context(
                            user_agent=user_agent,
                            proxy=proxy_config,
                            viewport={"width": 1920, "height": 1080},
                            locale="en-IN",
                            timezone_id="Asia/Kolkata",
                        )
                        await _setup_data_saver_routes(context)
                        page = await context.new_page()
                    else:
                        raise nav_err

            await asyncio.sleep(1.5)

            url_lower = url.lower()
            if "amazon" in url_lower:
                result = await _extract_amazon(page)
            elif "flipkart" in url_lower:
                await apply_flipkart_pincode(page)
                result = await _extract_flipkart(page)
            else:
                raise ValueError(f"Unsupported platform: {url}")

            return result

        finally:
            if browser:
                await browser.close()
            await playwright.stop()


async def scrape_many(urls: list[str]) -> dict[str, ScrapedProduct | Exception]:
    async def _safe_scrape(u: str) -> tuple[str, ScrapedProduct | Exception]:
        try:
            result = await scrape_product(u)
            return (u, result)
        except Exception as e:
            logger.error("Failed to scrape %s: %s", u, e)
            return (u, e)

    tasks = [_safe_scrape(u) for u in urls]
    results = await asyncio.gather(*tasks)
    return dict(results)


# ═══════════════════════════════════════════════════════════════════════════
# Lenovo India Outlet Fast API Scraper
# ═══════════════════════════════════════════════════════════════════════════

def _get_httpx_proxy_url() -> str | None:
    cfg = _get_proxy_config()
    if not cfg:
        return None
    server = cfg.get("server", "").rstrip("/")
    user = cfg.get("username")
    pwd = cfg.get("password")
    if user and pwd:
        scheme, _, host_port = server.partition("://")
        if not host_port:
            host_port = scheme
            scheme = "http"
        return f"{scheme}://{user}:{pwd}@{host_port}"
    return server


def parse_lenovo_specs(raw_title: str, summary: str = "", classification: list[dict] = None) -> dict:
    """Extract clean laptop name, series, CPU, RAM, SSD, GPU, VRAM, and dedicated flag from Lenovo data."""
    text = f"{raw_title} {summary}"

    # Series
    series = "Lenovo"
    if "ThinkPad" in text:
        series = "ThinkPad"
    elif "Legion" in text:
        series = "Legion"
    elif "Yoga" in text:
        series = "Yoga"
    elif "LOQ" in text:
        series = "LOQ"
    elif "IdeaPad" in text:
        series = "IdeaPad"
    elif "ThinkBook" in text:
        series = "ThinkBook"

    # CPU
    cpu = ""
    if classification:
        for c in classification:
            if c.get("a") == "Processor":
                cpu = c.get("b", "").strip()
                cpu = re.sub(r"\s*Processor\s*\(.*$", "", cpu, flags=re.IGNORECASE).strip()
                cpu = re.sub(r"[\x00-\x1f\x7f-\x9f\ufffd]", "", cpu).strip()
                break

    if not cpu:
        cpu_match = re.search(r"\b(Core\s*Ultra\s*\d|Ultra\s*\d|Core\s*\d|Intel\s+i[3579](?:-\w+)?|i[3579](?:-\w+)?|Ryzen\s*\d(?:\s*\w+)?)\b", text, re.IGNORECASE)
        if cpu_match:
            cpu = cpu_match.group(1).strip()

    # RAM
    ram = ""
    ram_match = re.search(r"\b(\d+\s*(?:GB|TB))\s*(?:RAM|Memory)?\b", text, re.IGNORECASE)
    if ram_match:
        ram = ram_match.group(1).strip()
        if "gb" not in ram.lower() and "tb" not in ram.lower():
            ram = f"{ram} GB"

    # SSD / Storage
    ssd = ""
    ssd_match = re.search(r"\b(\d+\s*(?:GB|TB)?)\s*(?:SSD|Storage|NVMe|PCIe)\b", text, re.IGNORECASE)
    if ssd_match:
        val = ssd_match.group(1).strip()
        if "gb" not in val.lower() and "tb" not in val.lower():
            val = f"{val} GB"
        ssd = f"{val} SSD"
    else:
        stor_tokens = re.findall(r"\b(\d+\s*(?:GB|TB))\b", text, re.IGNORECASE)
        if len(stor_tokens) >= 2:
            s2 = stor_tokens[1].strip()
            if s2 != ram:
                ssd = f"{s2} SSD"

    # GPU & VRAM extraction
    gpu = ""
    vram = ""
    is_dedicated = False

    raw_gpu_text = ""
    if classification:
        for c in classification:
            if c.get("a") == "Graphic Card":
                raw_gpu_text = c.get("b", "").strip()
                break

    raw_gpu_text = re.sub(r"[\x00-\x1f\x7f-\x9f\ufffd\xae\u2122\u00ae®™]", " ", raw_gpu_text)
    raw_gpu_text = re.sub(r"\s+", " ", raw_gpu_text).strip()

    combined_gpu_src = f"{raw_gpu_text} {text}"
    combined_gpu_src = re.sub(r"[\x00-\x1f\x7f-\x9f\ufffd\xae\u2122\u00ae®™]", " ", combined_gpu_src)
    combined_gpu_src = re.sub(r"\s+", " ", combined_gpu_src).strip()

    # VRAM regex
    vram_match = re.search(r"\b(\d+\s*GB(?:\s*GDDR\d[A-Z]*)?)\b", combined_gpu_src, re.IGNORECASE)
    if vram_match:
        v = vram_match.group(1).upper()
        # Normalise formatting e.g. "8GB GDDR6" or "8GB"
        v = re.sub(r"\s+", " ", v).strip()
        vram = v.replace("GB GDDR", "GB GDDR")

    # Dedicated GPU detection: RTX, GTX, MX, Radeon RX, Quadro, Ada
    rtx_match = re.search(r"\b(RTX\s*\d{3,4}(?:\s*Ti)?(?:\s*Ada(?:\s*Generation)?)?|GTX\s*\d{4}(?:\s*Ti)?|MX\d{3}|RTX\s*A\d{3,4}(?:\s*Ada(?:\s*Generation)?)?|Quadro\s*\w+|T\d{3,4})\b", combined_gpu_src, re.IGNORECASE)
    if rtx_match:
        matched_chip = rtx_match.group(1).strip()
        matched_chip = re.sub(r"RTX(\d)", r"RTX \1", matched_chip, flags=re.IGNORECASE)
        matched_chip = re.sub(r"(\d+)Ada", r"\1 Ada", matched_chip, flags=re.IGNORECASE)
        gpu = f"NVIDIA GeForce {matched_chip}" if ("RTX" in matched_chip.upper() or "GTX" in matched_chip.upper()) else f"NVIDIA {matched_chip}"
        is_dedicated = True
    elif re.search(r"\bRadeon\s*RX\s*\w+\b", combined_gpu_src, re.IGNORECASE):
        rx_match = re.search(r"\b(Radeon\s*RX\s*\w+)\b", combined_gpu_src, re.IGNORECASE)
        gpu = f"AMD {rx_match.group(1).strip()}"
        is_dedicated = True
    elif "Arc A" in combined_gpu_src or "Arc M" in combined_gpu_src:
        arc_match = re.search(r"\b(Arc\s*[AM]\d{3}[A-Z]*)\b", combined_gpu_src, re.IGNORECASE)
        gpu = f"Intel {arc_match.group(1).strip()}" if arc_match else "Intel Arc Discrete"
        is_dedicated = True
    elif "Arc" in combined_gpu_src:
        arc_match = re.search(r"\b(Arc(?:\s*\d{3}[A-Z]*)?)\b", combined_gpu_src, re.IGNORECASE)
        gpu = f"Intel {arc_match.group(1).strip()}" if arc_match else "Intel Arc"
        is_dedicated = False
    elif "Radeon 780M" in combined_gpu_src or "Radeon 680M" in combined_gpu_src or "Radeon 660M" in combined_gpu_src:
        rad_match = re.search(r"\b(Radeon\s*\d{3}M)\b", combined_gpu_src, re.IGNORECASE)
        gpu = f"AMD {rad_match.group(1).strip()}"
        is_dedicated = False
    elif "Radeon" in combined_gpu_src:
        gpu = "AMD Radeon Graphics"
        is_dedicated = False
    elif "Iris" in combined_gpu_src:
        gpu = "Intel Iris Xe"
        is_dedicated = False
    elif "Adreno" in combined_gpu_src:
        gpu = "Qualcomm Adreno"
        is_dedicated = False
    elif "Intel" in combined_gpu_src or "UHD" in combined_gpu_src:
        gpu = "Intel UHD Graphics"
        is_dedicated = False
    else:
        if raw_gpu_text:
            gpu = re.sub(r"\s*Laptop GPU.*$", "", raw_gpu_text, flags=re.IGNORECASE).strip()
        else:
            gpu = "Integrated Graphics"
        is_dedicated = False

    if not vram:
        vram = "Dedicated" if is_dedicated else "Shared VRAM"

    return {
        "series": series,
        "cpu": cpu,
        "ram": ram,
        "ssd": ssd,
        "gpu": gpu,
        "vram": vram,
        "is_dedicated_gpu": 1 if is_dedicated else 0,
    }


async def fetch_lenovo_outlet_laptops() -> list[dict]:
    """
    Direct high-speed OpenAPI fetch for all Lenovo Refurbished & Outlet Laptops.
    Uses proxy rotation from the residential pool.
    Paginates through all pages (~156 products in 4 pages).
    Returns list of normalized laptop dictionaries.
    """
    import httpx

    base_url = "https://openapi.lenovo.com/in/outletin/en/ofp/search/dlp/product/query/get/_tsc"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Referer": "https://www.lenovo.com/in/outletin/en/laptops/?sortBy=savingPercent",
        "Origin": "https://www.lenovo.com",
        "Accept": "application/json, text/plain, */*",
    }

    all_laptops = []
    seen_codes = set()

    for page_num in range(1, 10):
        proxy_url = _get_httpx_proxy_url()
        mounts = {"all://": httpx.AsyncHTTPTransport(proxy=proxy_url)} if proxy_url else {}

        params = {
            "pageFilterId": "afdcd3f7-d8e6-4e9e-a76a-d6060dc75ae9",
            "subSeriesCode": "",
            "loyalty": "false",
            "params": json.dumps({
                "classificationGroupIds": "400001",
                "pageFilterId": "afdcd3f7-d8e6-4e9e-a76a-d6060dc75ae9",
                "facets": [],
                "page": str(page_num),
                "pageSize": 40,
                "groupCode": "",
                "init": False,
                "sorts": ["savingPercent"],
                "version": "v2",
                "enablePreselect": True,
                "clickedSort": True,
                "subseriesCode": "",
            })
        }

        try:
            async with httpx.AsyncClient(mounts=mounts, timeout=15, verify=False) as client:
                resp = await client.get(base_url, params=params, headers=headers)
                if resp.status_code != 200 and mounts:
                    logger.info("Proxy returned HTTP %d, falling back to direct connection for Lenovo page %d...", resp.status_code, page_num)
                    async with httpx.AsyncClient(timeout=15, verify=False) as direct_client:
                        resp = await direct_client.get(base_url, params=params, headers=headers)

                if resp.status_code != 200:
                    logger.warning("Lenovo API page %d returned HTTP %d", page_num, resp.status_code)
                    break

                data = resp.json()
                page_data = data.get("data", {}).get("data", [{}])
                if not page_data:
                    break

                products_raw = page_data[0].get("products", [])
                if not products_raw:
                    break

                for item in products_raw:
                    pcode = item.get("productCode") or item.get("code")
                    if not pcode or pcode in seen_codes:
                        continue
                    seen_codes.add(pcode)

                    name = item.get("productName") or item.get("name") or pcode
                    summary = item.get("summary") or item.get("cardSummary") or ""
                    classifications = item.get("classification", [])
                    specs = parse_lenovo_specs(name, summary, classifications)

                    final_price = float(item.get("finalPrice") or 0.0)
                    web_price = float(item.get("webPrice") or 0.0)
                    save_pct = float(item.get("savePercent") or 0.0)
                    save_amount = float(item.get("saveAmount") or 0.0)
                    condition = item.get("productCondition") or "CERTIFIED REFURBISHED"

                    raw_url = item.get("url") or ""
                    if raw_url and not raw_url.startswith("http"):
                        # Ensure we use the correct India Outlet path prefix
                        if raw_url.startswith("/p/"):
                            url = f"https://www.lenovo.com/in/outletin/en{raw_url}"
                        else:
                            url = f"https://www.lenovo.com{raw_url}"
                    else:
                        url = raw_url or f"https://www.lenovo.com/in/outletin/en/p/{pcode}"

                    # Stock check: purchaseFlag is True if buyable, marketingStatus == 'Available'
                    in_stock = 1 if item.get("purchaseFlag", True) and item.get("marketingStatus") != "Out of stock" else 0

                    laptop_dict = {
                        "product_code": pcode,
                        "name": name,
                        "series": specs["series"],
                        "cpu": specs["cpu"],
                        "ram": specs["ram"],
                        "ssd": specs["ssd"],
                        "gpu": specs["gpu"],
                        "vram": specs["vram"],
                        "is_dedicated_gpu": specs["is_dedicated_gpu"],
                        "current_price": final_price,
                        "mrp": web_price if web_price > 0 else None,
                        "save_percent": save_pct,
                        "save_amount": save_amount,
                        "condition": condition,
                        "url": url,
                        "in_stock": in_stock,
                    }
                    all_laptops.append(laptop_dict)

        except Exception as e:
            logger.error("Error fetching Lenovo Outlet page %d: %s", page_num, e)
            break

    logger.info("⚡ Lenovo Outlet Scraper completed: %d total laptops fetched", len(all_laptops))
    return all_laptops


async def scrape_ikea_search(url: str) -> list[dict]:
    """
    Directly query IKEA India's official SIK Search API (sik.search.blue.cdtapps.com)
    for modular sofas and furniture search pages.
    Parses exact product specifications, pricing, IKEA Family discounts, and high-res images.
    """
    import urllib.parse
    import httpx

    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)

    query = params.get("q", ["sofa"])[0]
    raw_filters = params.get("filters", [""])[0]

    filter_config = {
        "subcategories-style": "tree-navigation",
        "max-num-filters": 4,
        "presetFilters": False,
    }

    if raw_filters:
        for f_part in raw_filters.split(";"):
            if ":" in f_part:
                k, v = f_part.split(":", 1)
                filter_config[k] = v.split("|")

    api_url = "https://sik.search.blue.cdtapps.com/in/en/search?c=sr&v=20250507"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Content-Type": "text/plain;charset=UTF-8",
        "Accept": "application/json",
        "Referer": "https://www.ikea.com/",
        "Origin": "https://www.ikea.com",
    }

    payload = {
        "searchParameters": {"input": query, "type": "QUERY"},
        "allowAutocorrect": True,
        "isUserLoggedIn": False,
        "isB2B": False,
        "listingABTest": True,
        "components": [
            {
                "component": "PRIMARY_AREA",
                "columns": 4,
                "types": {"main": "PRODUCT", "breakouts": ["PLANNER", "CATEGORY", "CONTENT"]},
                "filterConfig": filter_config,
                "window": {"size": 48, "offset": 0},
                "allVariants": False,
                "forceFilterCalculation": True,
            }
        ],
    }

    logger.info("🛋️ Scraping IKEA SIK API for query='%s', filters=%s", query, filter_config)

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(api_url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    products = []
    for r in data.get("results", []):
        if r.get("component") == "PRIMARY_AREA":
            for item in r.get("items", []):
                p = item.get("product")
                if not p:
                    continue
                sp = p.get("salesPrice") or {}
                price = float(sp.get("numeral") or 0.0)
                if price <= 0:
                    continue

                prev_price = None
                prev_data = sp.get("previousPrice") or sp.get("previous")
                if isinstance(prev_data, dict) and "wholeNumber" in prev_data:
                    try:
                        prev_price = float(prev_data["wholeNumber"].replace(",", ""))
                    except Exception:
                        pass

                discount_pct = 0.0
                if prev_price and prev_price > price:
                    discount_pct = round(((prev_price - price) / prev_price) * 100, 1)

                name = p.get("name", "IKEA Modular Sofa")
                type_name = p.get("typeName", "Modular Sofa")
                design = p.get("validDesignText", "")

                full_title = f"{name} ({type_name})"
                if design:
                    full_title += f" - {design}"

                is_family_deal = "FAMILY_PRICE" in sp.get("tags", []) or sp.get("tag") == "FAMILY_PRICE"
                tags_desc = "IKEA Family Offer" if is_family_deal else "Modular Section"

                pid = f"IKEA_{p.get('id', p.get('itemNo', ''))}"

                products.append({
                    "pid": pid,
                    "title": full_title,
                    "name": f"{name} {type_name}".strip(),
                    "cpu": type_name,              # e.g. 4-seat sofa
                    "ram": design or "Modular",     # e.g. Viarp beige/brown
                    "ssd": tags_desc,               # e.g. IKEA Family Offer
                    "gpu": "IKEA Furniture",
                    "effective_price": price,
                    "regular_price": prev_price or price,
                    "mrp": prev_price or price,
                    "wow_price": price if is_family_deal else None,
                    "discount_pct": discount_pct,
                    "url": p.get("pipUrl", url),
                    "image_url": "",
                    "is_dedicated_gpu": 0,
                })

    logger.info("🛋️ IKEA SIK Scraper harvested %d products for %s", len(products), url)
    return products
