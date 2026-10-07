import re

with open('static/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

minimal_grid = """function renderGridCards(products, container) {
            if (!container) return;
            if (!products.length) {
                container.innerHTML = `<div class="col-span-full py-16 text-center text-slate-500 text-xs font-medium border border-slate-200 dark:border-white/[0.08] rounded-2xl">No items match your active filters.</div>`;
                return;
            }

            container.innerHTML = products.map(p => {
                let steepBadge = '';
                let steepWas = '';
                if (p.steep_drop_pct && p.steep_drop_pct > 0) {
                    steepBadge = `<span class="text-[10px] font-black px-2 py-0.5 rounded-lg bg-purple-100 dark:bg-purple-500/20 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-500/30">↓${p.steep_drop_pct}% TRUE DROP</span>`;
                    if (p.steep_mode_price > 0) {
                        steepWas = `<div class="text-[10px] text-purple-600 dark:text-purple-400 font-mono">was ${formatPrice(p.steep_mode_price)}</div>`;
                    }
                }

                const curPrice = p.effective_price ?? p.current_price;
                const origPrice = p.mrp || p.regular_price;
                const discPct = p.discount_pct || (origPrice > curPrice ? Math.round(((origPrice - curPrice) / origPrice) * 100) : 0);
                const saveAmt = origPrice > curPrice ? (origPrice - curPrice) : 0;

                let originalPriceHtml = '';
                if (origPrice > curPrice) {
                    originalPriceHtml = `<span class="text-xs text-slate-400 line-through font-mono ml-1.5">${formatPrice(origPrice)}</span>`;
                }

                let discountPctHtml = '';
                if (discPct > 0) {
                    discountPctHtml = `<span class="text-[10px] font-bold text-emerald-600 dark:text-emerald-400 font-mono ml-1">-${discPct}% off</span>`;
                }

                let savingsAmountHtml = '';
                if (saveAmt > 0) {
                    savingsAmountHtml = `<div class="text-[10px] text-slate-500 font-mono">Save ${formatPrice(saveAmt)}</div>`;
                }

                const specs = [p.gpu, p.cpu, p.ram, p.ssd].filter(Boolean).join(' | ');
                let specsHtml = specs ? `<p class="text-[11px] text-slate-500 dark:text-slate-400 truncate mb-3">${escapeHtml(specs)}</p>` : '';

                window._productCache = window._productCache || {};
                window._productCache[p.pid] = p;

                return `
                <div class="bg-white dark:bg-[#0f1523] border border-slate-200 dark:border-white/[0.08] rounded-2xl p-4 flex flex-col justify-between shadow-sm hover:shadow-md transition-all">
                  <div>
                    <div class="flex items-center justify-between mb-2">
                      <div class="flex items-center gap-1.5">
                        <span class="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-slate-100 dark:bg-white/[0.06] text-slate-600 dark:text-slate-300">Listing</span>
                      </div>
                      ${steepBadge}
                    </div>
                    
                    <h3 class="text-xs font-bold text-slate-900 dark:text-white line-clamp-2 mb-1.5">${escapeHtml(p.title || p.name)}</h3>
                    
                    ${specsHtml}
                  </div>
                  
                  <div class="flex items-end justify-between pt-2.5 border-t border-slate-100 dark:border-white/[0.06]">
                    <div>
                      <span class="text-lg font-black font-mono text-slate-900 dark:text-white">${formatPrice(curPrice)}</span>
                      ${originalPriceHtml}
                      ${discountPctHtml}
                      ${steepWas}
                      ${savingsAmountHtml}
                    </div>
                    <div class="flex gap-1.5">
                        <button onclick="event.stopPropagation(); openPriceTrendModal('${escapeJs(p.pid)}')" class="px-2 py-1.5 rounded-xl bg-slate-100 dark:bg-white/[0.04] hover:bg-blue-50 dark:hover:bg-blue-950/40 text-slate-700 dark:text-slate-300 border border-slate-200/80 dark:border-white/[0.06] text-xs font-bold transition-all shadow-sm" title="Price History">📈 Chart</button>
                        <a href="${escapeHtml(p.url)}" target="_blank" class="px-3 py-1.5 rounded-xl bg-slate-900 dark:bg-white/[0.08] text-white dark:text-white text-xs font-bold hover:opacity-90 transition-all">View ↗</a>
                    </div>
                  </div>
                </div>`;
            }).join('');
        }"""

# Since renderGridCards is completely broken, we need a robust regex to find it and replace it.
# It starts with "function renderGridCards(items, limit = 120)" because rewrite_cards_2.py injected it!
# Wait! rewrite_cards_2.py DID inject it! It just missed the backticks!
# So it DOES start with function renderGridCards(items, limit = 120)!
# Wait, if rewrite_cards_2.py injected it, then it starts with (items, limit = 120).
# Let's replace whatever renderGridCards is there with the correct one.
html = re.sub(r'function renderGridCards\(.*?\s*(?=function renderDenseList)', minimal_grid + '\n\n        ', html, flags=re.DOTALL)

with open('static/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("Rewrote renderGridCards completely!")
