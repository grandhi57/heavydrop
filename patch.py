import re

with open("static/index.html", "r", encoding="utf-8") as f:
    html = f.read()

# First, undo the broken buttons
broken_btn1 = """<button onclick="event.stopPropagation(); window._productCache=window._productCache||{}; window._productCache['']=d; openPriceTrendModal('')" class="px-2 py-1.5 rounded-xl bg-slate-100 dark:bg-white/[0.04] hover:bg-blue-50 dark:hover:bg-blue-950/40 text-slate-700 dark:text-slate-300 border border-slate-200/80 dark:border-white/[0.06] text-xs font-bold transition-all shadow-sm" title="Price History">📈</button>"""
broken_btn2 = """<button onclick="event.stopPropagation(); const pid = ''; window._productCache=window._productCache||{}; window._productCache[pid]=p; openPriceTrendModal(pid)" class="px-2 py-1.5 rounded-xl bg-slate-100 dark:bg-white/[0.04] hover:bg-blue-50 dark:hover:bg-blue-950/40 text-slate-700 dark:text-slate-300 border border-slate-200/80 dark:border-white/[0.06] text-xs font-bold transition-all shadow-sm" title="Price History">📈</button>"""

# Fix broken btn 1 (live cards)
fixed_btn1 = """<button onclick="event.stopPropagation(); window._productCache=window._productCache||{}; window._productCache['${escapeJs(d.pid)}']=d; openPriceTrendModal('${escapeJs(d.pid)}')" class="px-2 py-1.5 rounded-xl bg-slate-100 dark:bg-white/[0.04] hover:bg-blue-50 dark:hover:bg-blue-950/40 text-slate-700 dark:text-slate-300 border border-slate-200/80 dark:border-white/[0.06] text-xs font-bold transition-all shadow-sm" title="Price History">📈</button>"""

# Fix broken btn 2 (lenovo/harvester cards)
fixed_btn2 = """<button onclick="event.stopPropagation(); const pid = '${escapeJs(p.product_code || p.pid)}'; window._productCache=window._productCache||{}; window._productCache[pid]=p; openPriceTrendModal(pid)" class="px-2 py-1.5 rounded-xl bg-slate-100 dark:bg-white/[0.04] hover:bg-blue-50 dark:hover:bg-blue-950/40 text-slate-700 dark:text-slate-300 border border-slate-200/80 dark:border-white/[0.06] text-xs font-bold transition-all shadow-sm" title="Price History">📈</button>"""

html = html.replace(broken_btn1, fixed_btn1)
html = html.replace(broken_btn2, fixed_btn2)

with open("static/index.html", "w", encoding="utf-8") as f:
    f.write(html)
print("Patched correctly this time")
