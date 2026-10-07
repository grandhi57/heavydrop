import re

with open('static/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Replace renderLenovoCards with minimal design
minimal_lenovo = """function renderLenovoCards(laptops) {
            const container = document.getElementById('lenovo-grid-container');
            if (!container) return;

            if (!laptops.length) {
                container.innerHTML = `
                <div class="col-span-full py-16 text-center bg-white dark:bg-[#0f1523] border border-slate-200 dark:border-white/[0.08] rounded-2xl shadow-sm">
                    <svg class="w-8 h-8 text-slate-400 mx-auto mb-2" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
                    <p class="text-sm font-bold text-slate-800 dark:text-slate-200">No hardware units matched your criteria</p>
                    <p class="text-xs text-slate-500 dark:text-slate-400 mt-1">Try resetting filters or searching a different GPU or spec.</p>
                    <button onclick="resetLenovoFilters()" class="mt-4 px-3.5 py-1.5 rounded-xl bg-slate-900 dark:bg-white text-white dark:text-slate-950 text-xs font-bold shadow-sm">Reset Filters</button>
                </div>`;
                return;
            }

            container.innerHTML = laptops.map(p => {
                let steepBadge = '';
                let steepWas = '';
                if (p.steep_drop_pct && p.steep_drop_pct > 0) {
                    steepBadge = `<span class="text-[10px] font-black px-2 py-0.5 rounded-lg bg-purple-100 dark:bg-purple-500/20 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-500/30">↓${p.steep_drop_pct}% TRUE DROP</span>`;
                    if (p.steep_mode_price > 0) {
                        steepWas = `<div class="text-[10px] text-purple-600 dark:text-purple-400 font-mono">was ${formatPrice(p.steep_mode_price)}</div>`;
                    }
                }

                let originalPrice = '';
                if (p.mrp > p.current_price) {
                    originalPrice = `<span class="text-xs text-slate-400 line-through font-mono ml-1.5">${formatPrice(p.mrp)}</span>`;
                }

                let discountPct = '';
                if (p.save_percent > 0) {
                    discountPct = `<span class="text-[10px] font-bold text-emerald-600 dark:text-emerald-400 font-mono ml-1">-${Math.round(p.save_percent)}% off</span>`;
                }

                const saveAmt = p.save_amount > 0 ? p.save_amount : (p.mrp ? (p.mrp - p.current_price) : 0);
                let savingsAmount = '';
                if (saveAmt > 0) {
                    savingsAmount = `<div class="text-[10px] text-slate-500 font-mono">Save ${formatPrice(saveAmt)}</div>`;
                }

                const specs = [p.gpu, p.cpu, p.ram, p.ssd].filter(Boolean).join(' | ');
                let specsHtml = specs ? `<p class="text-[11px] text-slate-500 dark:text-slate-400 truncate mb-3">${escapeHtml(specs)}</p>` : '';

                window._productCache = window._productCache || {};
                window._productCache[p.product_code || p.pid] = p;

                return `
                <div class="bg-white dark:bg-[#0f1523] border border-slate-200 dark:border-white/[0.08] rounded-2xl p-4 flex flex-col justify-between shadow-sm hover:shadow-md transition-all">
                  <div>
                    <div class="flex items-center justify-between mb-2">
                      <div class="flex items-center gap-1.5">
                        <span class="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-slate-100 dark:bg-white/[0.06] text-slate-600 dark:text-slate-300">Lenovo</span>
                        <span class="text-[10px] text-slate-400">${escapeHtml(p.series || 'Laptop')}</span>
                      </div>
                      ${steepBadge}
                    </div>
                    
                    <h3 class="text-xs font-bold text-slate-900 dark:text-white line-clamp-2 mb-1.5">${escapeHtml(p.name)}</h3>
                    
                    ${specsHtml}
                  </div>
                  
                  <div class="flex items-end justify-between pt-2.5 border-t border-slate-100 dark:border-white/[0.06]">
                    <div>
                      <span class="text-lg font-black font-mono text-slate-900 dark:text-white">${formatPrice(p.current_price)}</span>
                      ${originalPrice}
                      ${discountPct}
                      ${steepWas}
                      ${savingsAmount}
                    </div>
                    <div class="flex gap-1.5">
                        <button onclick="event.stopPropagation(); openPriceTrendModal('${escapeJs(p.product_code || p.pid)}')" class="px-2 py-1.5 rounded-xl bg-slate-100 dark:bg-white/[0.04] hover:bg-blue-50 dark:hover:bg-blue-950/40 text-slate-700 dark:text-slate-300 border border-slate-200/80 dark:border-white/[0.06] text-xs font-bold transition-all shadow-sm" title="Price History">📈 Chart</button>
                        <a href="${escapeHtml(p.url)}" target="_blank" class="px-3 py-1.5 rounded-xl bg-slate-900 dark:bg-white/[0.08] text-white dark:text-white text-xs font-bold hover:opacity-90 transition-all">View ↗</a>
                    </div>
                  </div>
                </div>`;
            }).join('');
        }"""
html = re.sub(r'function renderLenovoCards\(laptops\) \{.*?\n        \}\s*(?=function renderGridCards|function renderDenseList|async function triggerListingScan)', minimal_lenovo + '\n\n        ', html, flags=re.DOTALL)


# Replace renderGridCards with minimal design
minimal_grid = """function renderGridCards(items, limit = 120) {
            const container = document.getElementById('harvester-grid-container');
            if (!container) return;

            if (!items.length) {
                container.innerHTML = `<div class="col-span-full py-16 text-center text-slate-500 text-xs font-medium border border-slate-200 dark:border-white/[0.08] rounded-2xl">No items match your filters.</div>`;
                return;
            }

            container.innerHTML = items.slice(0, limit).map(p => {
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
html = re.sub(r'function renderGridCards\(items, limit = 120\) \{.*?\n        \}\s*(?=function renderDenseList|async function triggerListingScan)', minimal_grid + '\n\n        ', html, flags=re.DOTALL)

with open('static/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("Rewrote cards correctly!")
