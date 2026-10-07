import sys
import re

file_path = 'C:/Users/kotta/.gemini/antigravity/scratch/price-deal-tracker/static/index.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. REMOVE Live Deals Telemetry & Deal Freshness Strip
content = re.sub(r'<!-- Live Deals Telemetry & Deal Freshness Strip -->.*?<!-- Unified Search & Discovery Command Deck -->', '<!-- Unified Search & Discovery Command Deck -->', content, flags=re.DOTALL)

# 2. Rewrite Search Deck Options and Filters
search_deck_replacement = r'''<!-- Primary Search + View Controls Row -->
                <div class="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
                    <!-- Search Bar -->
                    <div class="relative flex-1">
                        <span class="absolute inset-y-0 left-0 flex items-center pl-3.5 text-slate-400 pointer-events-none">
                            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
                        </span>
                        <input
                            type="text"
                            id="live-search"
                            placeholder="Universal search (e.g. RTX 4070, Samsung 990 Pro, Kingston 1TB, Bosch Dishwasher, SÖDERHAMN)..."
                            oninput="applyLiveFiltersDebounced()"
                            class="w-full pl-10 pr-10 py-2.5 rounded-xl bg-slate-50 dark:bg-[#090d16] border border-slate-200 dark:border-white/[0.08] text-xs text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:border-blue-500 font-medium"
                        >
                    </div>

                    <!-- Sort -->
                    <div class="flex items-center gap-2.5 shrink-0">
                        <div class="relative">
                            <select
                                id="live-sort"
                                onchange="setLiveSort(this.value)"
                                class="appearance-none bg-slate-50 dark:bg-[#090d16] border border-slate-200 dark:border-white/[0.08] text-slate-900 dark:text-white text-xs font-semibold py-2 pl-3 pr-8 rounded-xl focus:outline-none focus:border-blue-500 cursor-pointer shadow-sm"
                            >
                                <option value="steepest" selected>🔥 Biggest True Drop</option>
                                <option value="discount">💰 MRP Discount %</option>
                                <option value="savings">💎 Highest ₹ Savings</option>
                                <option value="price_asc">Price: Low → High</option>
                                <option value="price_desc">Price: High → Low</option>
                            </select>
                            <span class="absolute inset-y-0 right-0 flex items-center pr-2.5 pointer-events-none text-slate-400">
                                <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m6 9 6 6 6-6"/></svg>
                            </span>
                        </div>
                    </div>
                </div>

                <!-- Unified Filters Row -->
                <div class="flex items-center gap-2 flex-wrap pt-2 border-t border-slate-200/80 dark:border-white/[0.06] text-xs">
                    <button onclick="setLivePlatform('all')" id="btn-live-plat-all" class="px-2.5 py-1 rounded-lg font-bold bg-slate-900 dark:bg-white text-white dark:text-slate-950 text-xs shadow-sm">All Stores</button>
                    <button onclick="setLivePlatform('lenovo')" id="btn-live-plat-lenovo" class="px-2.5 py-1 rounded-lg font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/[0.06] border border-slate-200 dark:border-white/[0.08] text-xs">Lenovo Outlet</button>
                    <button onclick="setLivePlatform('flipkart')" id="btn-live-plat-flipkart" class="px-2.5 py-1 rounded-lg font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/[0.06] border border-slate-200 dark:border-white/[0.08] text-xs">Flipkart</button>
                    <button onclick="setLivePlatform('ikea')" id="btn-live-plat-ikea" class="px-2.5 py-1 rounded-lg font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/[0.06] border border-slate-200 dark:border-white/[0.08] text-xs">IKEA</button>

                    <div class="w-px h-4 bg-slate-300 dark:bg-slate-700 mx-1 hidden sm:block"></div>

                    <button onclick="setLiveCategory('all')" id="btn-live-cat-all" class="px-2 py-1 rounded-lg bg-slate-900 dark:bg-white text-white dark:text-slate-950 font-bold text-xs shadow-sm">All</button>
                    <button onclick="setLiveCategory('laptops')" id="btn-live-cat-laptops" class="px-2 py-1 rounded-lg text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/[0.06] font-medium text-xs">💻 Laptops</button>
                    <button onclick="setLiveCategory('ssd')" id="btn-live-cat-ssd" class="px-2 py-1 rounded-lg text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/[0.06] font-medium text-xs">⚡ SSDs</button>
                    <button onclick="setLiveCategory('ram')" id="btn-live-cat-ram" class="px-2 py-1 rounded-lg text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/[0.06] font-medium text-xs">🧠 RAM</button>
                    <button onclick="setLiveCategory('dish_washer')" id="btn-live-cat-dish_washer" class="px-2 py-1 rounded-lg text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/[0.06] font-medium text-xs">🍽️ Dishwashers</button>
                    <button onclick="setLiveCategory('sofas')" id="btn-live-cat-sofas" class="px-2 py-1 rounded-lg text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/[0.06] font-medium text-xs">🛋️ IKEA Sofas</button>

                    <div class="w-px h-4 bg-slate-300 dark:bg-slate-700 mx-1 hidden lg:block"></div>

                    <button onclick="setLiveRam('all')" id="btn-live-ram-all" class="px-2 py-1 rounded-lg bg-slate-900 dark:bg-white text-white dark:text-slate-950 font-bold text-xs shadow-sm">All</button>
                    <button onclick="setLiveRam('8gb')" id="btn-live-ram-8gb" class="px-2 py-1 rounded-lg text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/[0.06] font-medium text-xs">8GB</button>
                    <button onclick="setLiveRam('16gb')" id="btn-live-ram-16gb" class="px-2 py-1 rounded-lg text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/[0.06] font-medium text-xs">16GB</button>
                    <button onclick="setLiveRam('24gb')" id="btn-live-ram-24gb" class="px-2 py-1 rounded-lg text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/[0.06] font-medium text-xs">24GB</button>
                    <button onclick="setLiveRam('32gb')" id="btn-live-ram-32gb" class="px-2 py-1 rounded-lg text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/[0.06] font-medium text-xs">32GB+</button>

                    <div class="w-px h-4 bg-slate-300 dark:bg-slate-700 mx-1 hidden xl:block"></div>

                    <button onclick="setLiveGpu('all')" id="btn-live-gpu-all" class="px-2 py-1 rounded-lg bg-slate-900 dark:bg-white text-white dark:text-slate-950 font-bold text-xs shadow-sm">All</button>
                    <button onclick="setLiveGpu('rtx_3050')" id="btn-live-gpu-rtx_3050" class="px-2 py-1 rounded-lg text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/[0.06] font-medium text-xs">RTX 3050</button>
                    <button onclick="setLiveGpu('rtx_4050')" id="btn-live-gpu-rtx_4050" class="px-2 py-1 rounded-lg text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/[0.06] font-medium text-xs">RTX 4050</button>
                    <button onclick="setLiveGpu('rtx_4060')" id="btn-live-gpu-rtx_4060" class="px-2 py-1 rounded-lg text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/[0.06] font-medium text-xs">RTX 4060</button>
                    <button onclick="setLiveGpu('rtx_4070')" id="btn-live-gpu-rtx_4070" class="px-2 py-1 rounded-lg text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/[0.06] font-medium text-xs">RTX 4070+</button>
                </div>'''

content = re.sub(r'<!-- Primary Search \+ View Controls Row -->.*?<div id="live-filter-chips".*?</div>\s*</div>', search_deck_replacement + '\n            </div>', content, flags=re.DOTALL)

# Remove Dense Table View
content = re.sub(r'<!-- Dense Table View -->.*?<!-- ═══════════════════════════════════════════════════════════════════ -->\s*<!-- TAB 1:', '<!-- ═══════════════════════════════════════════════════════════════════ -->\n        <!-- TAB 1:', content, flags=re.DOTALL)

# Lenovo Outlet - Remove Telemetry Strip
content = re.sub(r'<!-- Sleek Compact Telemetry & Action Bar -->.*?<!-- Unified Search & Quick Filter Command Deck -->', '<!-- Unified Search & Quick Filter Command Deck -->', content, flags=re.DOTALL)

# Lenovo Outlet - Sort Dropdown & Scan button injection
lenovo_sort_inject = r'''<!-- Sort, In-Stock, Scan -->
                    <div class="flex items-center gap-2.5 shrink-0 flex-wrap sm:flex-nowrap">
                        <button onclick="triggerLenovoScan()" id="btn-scan-lenovo" class="bg-blue-600 hover:bg-blue-700 dark:bg-white dark:hover:bg-slate-200 text-white dark:text-slate-950 font-bold py-1.5 px-3.5 rounded-xl text-xs transition-all flex items-center gap-1.5 shadow-sm active:scale-95 shrink-0">
                            <svg id="lenovo-scan-icon" class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 16h5v5"/></svg>
                            <span id="lenovo-scan-label">Scan Outlet</span>
                        </button>
                        <label class="flex items-center gap-1.5 cursor-pointer text-xs font-semibold text-slate-700 dark:text-slate-300 select-none px-2 py-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-white/[0.05] transition-colors">
                            <input type="checkbox" id="lenovo-stock-only" onchange="applyLenovoFilters()" class="rounded border-slate-300 dark:border-slate-700 text-blue-600 focus:ring-blue-500 w-3.5 h-3.5">
                            <span>In Stock</span>
                        </label>

                        <!-- Sort Dropdown -->
                        <div class="relative">
                            <select
                                id="lenovo-sort"
                                onchange="applyLenovoFilters()"
                                class="appearance-none bg-slate-50 dark:bg-[#090d16] border border-slate-200 dark:border-white/[0.08] text-slate-900 dark:text-white text-xs font-semibold py-2 pl-3 pr-8 rounded-xl focus:outline-none focus:border-blue-500 cursor-pointer shadow-sm"
                            >
                                <option value="steepest" selected>🔥 Biggest True Drop</option>
                                <option value="savingPercent">Deepest Discount %</option>
                                <option value="savingAmount">Highest ₹ Savings</option>
                                <option value="priceAsc">Price: Low to High</option>
                                <option value="priceDesc">Price: High to Low</option>
                                <option value="vramDesc">VRAM: High to Low</option>
                            </select>'''
content = re.sub(r'<!-- Sort, In-Stock & View Modes -->.*?<option value="steepest" selected>🔥 Steepest TRUE Drop \(Default\)</option>.*?<option value="vramDesc">VRAM: High to Low</option>\s*</select>', lenovo_sort_inject, content, flags=re.DOTALL)

# Harvester Sort Options update
content = content.replace('<option value="steepest" selected>🔥 Steepest Drop</option>', '<option value="steepest" selected>🔥 Biggest True Drop</option>')
content = content.replace('<option value="discount">Highest Discount %</option>', '<option value="discount">Deepest Discount %</option>')

# Update liveFilter State
content = re.sub(r'let liveFilter = \{[^\}]+\};', "let liveFilter = {\n    search: '',\n    platform: 'all',\n    category: 'all',\n    ram: 'all',\n    gpu: 'all',\n    sort: 'steepest'\n};", content)

# Rewrite loadLiveDeals
load_live_deals_new = r'''async function loadLiveDeals(forceRefresh = false) {
            const refreshIcon = document.getElementById('live-refresh-icon');
            if (forceRefresh && refreshIcon) refreshIcon.classList.add('spin');

            try {
                const params = new URLSearchParams({
                    sort_by: liveFilter.sort,
                    platform: liveFilter.platform,
                    category: liveFilter.category,
                    ram: liveFilter.ram,
                    gpu: liveFilter.gpu,
                    q: liveFilter.search,
                    limit: 160
                });

                const res = await fetch(API + '/api/all-deals?' + params.toString());
                const data = await res.json();
                allLiveDeals = data.deals || [];

                updateLiveMetrics(data);
                renderLiveCards(allLiveDeals);

                if (forceRefresh) showToast(`Live feed updated: ${allLiveDeals.length} active deals found`, 'success');
            } catch (err) {
                console.error('Error loading live deals:', err);
                showToast('Failed to load live deals feed', 'error');
            } finally {
                if (refreshIcon) refreshIcon.classList.remove('spin');
            }
        }'''
content = re.sub(r'async function loadLiveDeals\(.*?\).*?finally\s*{[^}]+}\s*}', load_live_deals_new, content, flags=re.DOTALL)

# Update Live Metrics
update_live_metrics_new = r'''function updateLiveMetrics(data) {
            const deals = data.deals || [];
            const total = data.total ?? deals.length;
            const badgeLive = document.getElementById('badge-live-count');
            if (badgeLive) badgeLive.textContent = `${total}`;
        }'''
content = re.sub(r'function updateLiveMetrics\(data\)\s*{.*?const activeSummary = document.getElementById\(\'live-active-summary\'\);\s*if \(activeSummary\) activeSummary.textContent = `\$\{deals.length\} Deals Shown`;\s*}', update_live_metrics_new, content, flags=re.DOTALL)

# Remove setLiveFilterType, setLiveView, renderLiveFilterChips
content = re.sub(r'function setLiveFilterType\(type\)\s*{[^}]*loadLiveDeals\(\);\s*}', '', content, flags=re.DOTALL)
content = re.sub(r'function setLiveView\(mode\)\s*{.*?}\s*}', '', content, flags=re.DOTALL)
content = re.sub(r'function renderLiveFilterChips\(\)\s*{.*?container.innerHTML.*?;.*?}', '', content, flags=re.DOTALL)

# Rewrite renderLiveCards
render_live_cards_new = r'''function renderLiveCards(deals) {
            const container = document.getElementById('live-deals-grid');
            if (!container) return;

            if (!deals.length) {
                container.innerHTML = `
                <div class="col-span-full py-16 text-center bg-white dark:bg-[#0f1523] border border-slate-200 dark:border-white/[0.08] rounded-2xl shadow-sm">
                    <svg class="w-8 h-8 text-slate-400 mx-auto mb-2" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
                    <p class="text-sm font-bold text-slate-800 dark:text-slate-200">No live deals matched your criteria</p>
                    <p class="text-xs text-slate-500 dark:text-slate-400 mt-1">Try switching categories, clearing search filters, or selecting All Active Deals.</p>
                </div>`;
                return;
            }

            container.innerHTML = deals.map(d => {
                let steepBadge = '';
                let steepWas = '';
                if (d.steep_drop_pct && d.steep_drop_pct > 0) {
                    steepBadge = `<span class="text-[10px] font-black px-2 py-0.5 rounded-lg bg-purple-100 dark:bg-purple-500/20 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-500/30">↓${d.steep_drop_pct}%</span>`;
                    if (d.steep_mode_price > 0) {
                        steepWas = `<div class="text-[10px] text-purple-600 dark:text-purple-400 font-mono">was ${formatPrice(d.steep_mode_price)}</div>`;
                    }
                }

                let originalPrice = '';
                if (d.original_price > d.current_price) {
                    originalPrice = `<span class="text-xs text-slate-400 line-through font-mono ml-1.5">${formatPrice(d.original_price)}</span>`;
                }

                let discountPct = '';
                if (d.discount_pct > 0) {
                    discountPct = `<span class="text-[10px] font-bold text-emerald-600 dark:text-emerald-400 font-mono ml-1">-${d.discount_pct}% off</span>`;
                }

                let savingsAmount = '';
                if (d.savings_amount > 0) {
                    savingsAmount = `<div class="text-[10px] text-slate-500 font-mono">Save ${formatPrice(d.savings_amount)}</div>`;
                }

                const specs = [d.gpu, d.cpu, d.ram, d.ssd].filter(Boolean).join(' · ');
                let specsHtml = specs ? `<p class="text-[11px] text-slate-500 dark:text-slate-400 truncate mb-3">${escapeHtml(specs)}</p>` : '';

                return `
                <div class="bg-white dark:bg-[#0f1523] border border-slate-200 dark:border-white/[0.08] rounded-2xl p-4 flex flex-col justify-between shadow-sm hover:shadow-md transition-all">
                  <div>
                    <div class="flex items-center justify-between mb-2">
                      <div class="flex items-center gap-1.5">
                        <span class="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-slate-100 dark:bg-white/[0.06] text-slate-600 dark:text-slate-300">${escapeHtml(d.platform_label)}</span>
                        <span class="text-[10px] text-slate-400">${escapeHtml(d.category_label)}</span>
                      </div>
                      ${steepBadge}
                    </div>
                    
                    <h3 class="text-xs font-bold text-slate-900 dark:text-white line-clamp-2 mb-1.5">${escapeHtml(d.name)}</h3>
                    
                    ${specsHtml}
                  </div>
                  
                  <div class="flex items-end justify-between pt-2.5 border-t border-slate-100 dark:border-white/[0.06]">
                    <div>
                      <span class="text-lg font-black font-mono text-slate-900 dark:text-white">${formatPrice(d.current_price)}</span>
                      ${originalPrice}
                      ${discountPct}
                      ${steepWas}
                      ${savingsAmount}
                    </div>
                    <a href="${escapeHtml(d.url)}" target="_blank" class="px-3 py-1.5 rounded-xl bg-slate-900 dark:bg-white/[0.08] text-white dark:text-white text-xs font-bold hover:opacity-90 transition-all">View ↗</a>
                  </div>
                </div>`;
            }).join('');
        }'''
content = re.sub(r'function renderLiveCards\(deals\)\s*{.*?}\s*function renderLiveTable\(deals\)', render_live_cards_new + '\n\n        function renderLiveTable(deals)', content, flags=re.DOTALL)

# Remove renderLiveTable, enrichWithTrueDrop
content = re.sub(r'function renderLiveTable\(deals\)\s*{.*?}\s*function enrichWithTrueDrop\(products\)', 'function enrichWithTrueDrop(products)', content, flags=re.DOTALL)
content = re.sub(r'function enrichWithTrueDrop\(products\)\s*{.*?}\s*// Tab Switching', '// Tab Switching', content, flags=re.DOTALL)

# Inject inline steep_drop_pct computation
compute_steep = r'''function computeSteepDropInline(p) {
            let steep_drop_pct = 0;
            let steep_mode_price = 0;
            if (p.price_history && p.price_history.length > 0) {
                const recent = p.price_history.map(h => Number(h.effective_price ?? h.price ?? h.current_price)).filter(x => !isNaN(x) && x > 0);
                if (recent.length > 0) {
                    const counts = {};
                    let maxCount = 0;
                    let mode = null;
                    for (const v of recent) {
                        counts[v] = (counts[v] || 0) + 1;
                        if (counts[v] > maxCount) {
                            maxCount = counts[v];
                            mode = v;
                        }
                    }
                    const current = Number(p.effective_price ?? p.current_price ?? 0);
                    if (mode && current > 0 && mode > current) {
                        steep_drop_pct = ((mode - current) / mode) * 100.0;
                        steep_mode_price = mode;
                    }
                }
            }
            p.steep_drop_pct = steep_drop_pct;
            p.steep_mode_price = steep_mode_price;
        }'''
content = content.replace('// ── LENOVO OUTLET STUDIO LOGIC ───────────────────────────────────────', compute_steep + '\n\n        // ── LENOVO OUTLET STUDIO LOGIC ───────────────────────────────────────')

# Add inline computation to applyLenovoFilters
content = content.replace('let filtered = allLenovoLaptops.filter(p => {', 'allLenovoLaptops.forEach(p => computeSteepDropInline(p));\n            let filtered = allLenovoLaptops.filter(p => {')
# Add inline computation to applyFiltersAndRender
content = content.replace('let items = currentListingItems.filter(p => {', 'currentListingItems.forEach(p => computeSteepDropInline(p));\n            let items = currentListingItems.filter(p => {')

# Remove enrichWithTrueDrop calls
content = content.replace('enrichWithTrueDrop(allLenovoLaptops);', '')
content = content.replace('enrichWithTrueDrop(currentListingItems);', '')

# Remove renderDealGistBanner, renderPriceHistorySection, renderTrendButton
content = re.sub(r'function renderDealGistBanner\(p\)\s*{.*?}\s*function renderGridCards\(products, container\)', 'function renderGridCards(products, container)', content, flags=re.DOTALL)
content = re.sub(r'function renderPriceHistorySection\(p\)\s*{.*?}\s*// ── Single Product Tracker ──────────────────────────────────────', '// ── Single Product Tracker ──────────────────────────────────────', content, flags=re.DOTALL)

# Remove references to renderPriceHistorySection and renderDealGistBanner from Harvester
content = content.replace('const gistBanner = renderDealGistBanner(p);', '')
content = content.replace('${gistBanner}', '')
content = content.replace('const historySection = renderPriceHistorySection(p);', '')
content = content.replace('${historySection}', '')

# Rewrite Price Trend Modal logic
price_trend_new = r'''async function openPriceTrendModal(pid) {
            const modal = document.getElementById('price-trend-modal');
            modal.classList.remove('hidden');
            
            document.getElementById('trend-product-title').innerHTML = 'Loading price history <span class="spin inline-block ml-2">⏳</span>';
            document.getElementById('trend-scan-count-badge').textContent = '... Scans';
            document.getElementById('trend-stat-low').textContent = '...';
            document.getElementById('trend-stat-high').textContent = '...';
            document.getElementById('trend-stat-current').textContent = '...';
            document.getElementById('trend-status-pill').textContent = 'Loading...';
            document.getElementById('trend-chart-container').innerHTML = '';
            document.getElementById('trend-history-list').innerHTML = '';

            try {
                const res = await fetch(API + '/api/deal-history/' + encodeURIComponent(pid));
                if (!res.ok) throw new Error('Failed to fetch history');
                const data = await res.json();
                
                const p = data.product || window._productCache[pid] || { id: pid, name: 'Product' };
                const history = data.history || [];
                
                document.getElementById('trend-product-title').textContent = escapeHtml(p.name || p.title || 'Product');
                const prices = history.map(h => Number(h.effective_price ?? h.price ?? h.current_price)).filter(x => !isNaN(x) && x > 0);
                
                if (!prices.length) {
                    document.getElementById('trend-chart-container').innerHTML = '<div class="py-12 text-center text-slate-500 text-xs">No history recorded</div>';
                    return;
                }

                const minPrice = Math.min(...prices);
                const maxPrice = Math.max(...prices);
                const curPrice = prices[prices.length - 1];
                
                document.getElementById('trend-scan-count-badge').textContent = `${history.length} Scans`;
                document.getElementById('trend-stat-low').textContent = formatPrice(minPrice);
                document.getElementById('trend-stat-high').textContent = formatPrice(maxPrice);
                document.getElementById('trend-stat-current').textContent = formatPrice(curPrice);

                const isDown = prices.length > 1 && curPrice < prices[0];
                const isUp = prices.length > 1 && curPrice > prices[0];
                const statusPill = document.getElementById('trend-status-pill');
                if (isDown) {
                    const drop = Math.round(((prices[0] - curPrice) / prices[0]) * 100);
                    statusPill.className = 'px-2 py-0.5 rounded font-mono font-bold text-[10px] bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300';
                    statusPill.textContent = `−${drop}% Price Drop Detected`;
                } else if (isUp) {
                    statusPill.className = 'px-2 py-0.5 rounded font-mono font-bold text-[10px] bg-rose-100 dark:bg-rose-500/20 text-rose-700 dark:text-rose-300';
                    statusPill.textContent = `Price Increased`;
                } else {
                    statusPill.className = 'px-2 py-0.5 rounded font-mono font-bold text-[10px] bg-blue-100 dark:bg-blue-500/20 text-blue-700 dark:text-blue-300';
                    statusPill.textContent = `Price Stable across all scans`;
                }

                const W = 460;
                const H = 130;
                const padX = 28;
                const padY = 22;
                const effW = W - padX * 2;
                const effH = H - padY * 2;
                const isFlat = minPrice === maxPrice;
                const range = maxPrice - minPrice || 1;

                const pts = prices.map((pr, i) => {
                    const x = padX + (prices.length === 1 ? effW / 2 : (i / (prices.length - 1)) * effW);
                    const y = isFlat ? (H / 2) : (H - padY - ((pr - minPrice) / range) * effH);
                    return { x, y, price: pr, iso: history[i] ? (history[i].recorded_at || history[i].checked_at) : null };
                });

                const strokeColor = isDown ? '#10b981' : (isUp ? '#f43f5e' : '#0ea5e9');
                const polyPoints = pts.map(pt => `${pt.x.toFixed(1)},${pt.y.toFixed(1)}`).join(' ');
                const areaPoints = `${pts[0].x.toFixed(1)},${H - 8} ` + polyPoints + ` ${pts[pts.length - 1].x.toFixed(1)},${H - 8}`;

                document.getElementById('trend-chart-container').innerHTML = `
                <svg width="100%" height="${H}" viewBox="0 0 ${W} ${H}" class="overflow-visible select-none">
                    <defs>
                        <linearGradient id="trendGradModal" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stop-color="${strokeColor}" stop-opacity="0.25" />
                            <stop offset="100%" stop-color="${strokeColor}" stop-opacity="0.0" />
                        </linearGradient>
                    </defs>
                    <line x1="${padX}" y1="${padY}" x2="${W - padX}" y2="${padY}" stroke="currentColor" class="text-slate-200 dark:text-white/[0.06]" stroke-dasharray="3,3" />
                    <line x1="${padX}" y1="${H / 2}" x2="${W - padX}" y2="${H / 2}" stroke="currentColor" class="text-slate-200 dark:text-white/[0.06]" stroke-dasharray="3,3" />
                    <line x1="${padX}" y1="${H - padY}" x2="${W - padX}" y2="${H - padY}" stroke="currentColor" class="text-slate-200 dark:text-white/[0.06]" stroke-dasharray="3,3" />
                    <text x="${padX - 6}" y="${padY + 4}" text-anchor="end" class="text-[9px] font-mono fill-slate-400">${formatPrice(maxPrice)}</text>
                    <text x="${padX - 6}" y="${H - padY + 3}" text-anchor="end" class="text-[9px] font-mono fill-slate-400">${formatPrice(minPrice)}</text>
                    <polygon points="${areaPoints}" fill="url(#trendGradModal)" />
                    <polyline points="${polyPoints}" fill="none" stroke="${strokeColor}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
                    ${pts.map((pt, i) => `
                        <g class="cursor-pointer group/node" onmouseenter="showChartTooltip(event, '${formatPrice(pt.price)}', '${formatTimeDetailed(pt.iso)}')" onmouseleave="hideChartTooltip()">
                            <circle cx="${pt.x.toFixed(1)}" cy="${pt.y.toFixed(1)}" r="5.5" fill="var(--bg-canvas, #ffffff)" stroke="${strokeColor}" stroke-width="2.5" class="transition-transform group-hover/node:scale-125" />
                            <circle cx="${pt.x.toFixed(1)}" cy="${pt.y.toFixed(1)}" r="2.5" fill="${strokeColor}" />
                        </g>
                    `).join('')}
                </svg>`;

                const revHistory = [...history].reverse();
                document.getElementById('trend-history-list').innerHTML = revHistory.map((h, idx) => {
                    const pr = Number(h.effective_price ?? h.price ?? h.current_price ?? 0);
                    const iso = h.recorded_at || h.checked_at || p.last_updated;
                    const isFirst = idx === revHistory.length - 1;
                    return `
                    <div class="flex items-center justify-between p-2 rounded-xl bg-slate-50 dark:bg-white/[0.02] border border-slate-200/60 dark:border-white/[0.04] text-xs">
                        <div class="flex items-center gap-2">
                            <span class="w-1.5 h-1.5 rounded-full ${idx === 0 ? 'bg-emerald-500 ring-2 ring-emerald-500/20' : 'bg-slate-300 dark:bg-slate-600'}"></span>
                            <span class="font-medium text-slate-700 dark:text-slate-300">${formatTimeDetailed(iso)}</span>
                        </div>
                        <div class="flex items-center gap-2">
                            <span class="font-mono font-bold text-slate-900 dark:text-white tabular-nums">${formatPrice(pr)}</span>
                            ${isFirst ? `<span class="text-[9px] font-mono px-1.5 py-0.2 rounded bg-slate-200 dark:bg-white/[0.08] text-slate-600 dark:text-slate-300">Baseline</span>` : (idx === 0 ? `<span class="text-[9px] font-mono px-1.5 py-0.2 rounded bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 font-bold">Latest</span>` : '')}
                        </div>
                    </div>`;
                }).join('');
            } catch (err) {
                console.error(err);
                document.getElementById('trend-product-title').innerHTML = '<span class="text-rose-500">Failed to load price history</span>';
            }
        }'''
content = re.sub(r'async function openPriceTrendModal\(pid\)\s*{.*?}\s*function closePriceTrendModal\(\)', price_trend_new + '\n\n        function closePriceTrendModal()', content, flags=re.DOTALL)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("SUCCESS")
