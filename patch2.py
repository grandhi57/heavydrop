import re

with open("static/index.html", "r", encoding="utf-8") as f:
    html = f.read()

# First, clean up the corrupted HTML entirely.
# Let's remove ALL the <button onclick="event.stopPropagation(); window._productCache=window._productCache||{}; window._productCache['']=d; openPriceTrendModal('')"...>
# and ALL the <div class="flex items-center gap-1.5"> that were prepended.

html = re.sub(
    r'<div class="flex items-center gap-1\.5">\s*<button onclick="event\.stopPropagation\(\); window\._productCache[^>]+>.*?<\/button>\s*(<a href="[^>]+>View[^<]+<\/a>)\s*<\/div>',
    r'\1',
    html,
    flags=re.DOTALL
)

# And if there are any trailing <button>s without the wrapper:
html = re.sub(
    r'<button onclick="event\.stopPropagation\(\); (?:const pid = |window\._productCache).*?openPriceTrendModal\([^>]+>.*?<\/button>',
    r'',
    html,
    flags=re.DOTALL
)


# Now that we're back to baseline (just the View a href tag), apply the correct buttons.

# Live deals:
pattern_live = r'(<a href="\$\{escapeHtml\(d\.url\)\}"[^>]+>View[^<]+</a>)'
replacement_live = r'''<div class="flex items-center gap-1.5">
                        <button onclick="event.stopPropagation(); window._productCache=window._productCache||{}; window._productCache['${escapeJs(d.pid)}']=d; openPriceTrendModal('${escapeJs(d.pid)}')" class="px-2 py-1.5 rounded-xl bg-slate-100 dark:bg-white/[0.04] hover:bg-blue-50 dark:hover:bg-blue-950/40 text-slate-700 dark:text-slate-300 border border-slate-200/80 dark:border-white/[0.06] text-xs font-bold transition-all shadow-sm" title="Price History">📈</button>
                        \1
                      </div>'''
html = re.sub(pattern_live, replacement_live, html)

# Lenovo & Harvester cards:
pattern_lenovo = r'(<a href="\$\{escapeHtml\(p\.url\)\}"[^>]*>[^<]*View[^<]*</a>)'
replacement_lenovo = r'''<div class="flex items-center gap-1.5">
                        <button onclick="event.stopPropagation(); const pid = '${escapeJs(p.product_code || p.pid)}'; window._productCache=window._productCache||{}; window._productCache[pid]=p; openPriceTrendModal(pid)" class="px-2 py-1.5 rounded-xl bg-slate-100 dark:bg-white/[0.04] hover:bg-blue-50 dark:hover:bg-blue-950/40 text-slate-700 dark:text-slate-300 border border-slate-200/80 dark:border-white/[0.06] text-xs font-bold transition-all shadow-sm" title="Price History">📈</button>
                        \1
                      </div>'''
html = re.sub(pattern_lenovo, replacement_lenovo, html)

with open("static/index.html", "w", encoding="utf-8") as f:
    f.write(html)
print("Cleaned and repatched")
