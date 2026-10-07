
        const API = '';
        let currentTab = 'live';
        let allLenovoLaptops = [];
        let allListings = [];
        let activeListingId = null;

        // Theme Toggle (Light / Dark)
        function initTheme() {
            const saved = localStorage.getItem('hw_studio_theme');
            if (saved === 'dark') {
                document.documentElement.classList.add('dark');
            } else if (saved === 'light') {
                document.documentElement.classList.remove('dark');
            } else {
                // Default to Clean, Modern Light Studio
                document.documentElement.classList.remove('dark');
            }
        }

        function toggleTheme() {
            const isDark = document.documentElement.classList.toggle('dark');
            localStorage.setItem('hw_studio_theme', isDark ? 'dark' : 'light');
            showToast(isDark ? 'Dark Studio theme enabled' : 'Light Studio theme enabled', 'info');
        }

        initTheme();

        // Active Lenovo Filter State
        let lenovoFilter = {
            search: '',
            gpuTier: 'all',
            vram: 'all',
            series: 'all',
            discountMin: 0,
            inStockOnly: false,
            sort: 'steepest',
            view: 'cards',
        };

        // Active Live Deals Command Center State
        let allLiveDeals = [];
        let liveFilter = {
    search: '',
    platform: 'all',
    category: 'all',
    ram: 'all',
    gpu: 'all',
    sort: 'steepest'
};
        let liveSearchDebounceTimer = null;

        function applyLiveFiltersDebounced() {
            clearTimeout(liveSearchDebounceTimer);
            liveSearchDebounceTimer = setTimeout(() => {
                liveFilter.search = (document.getElementById('live-search')?.value || '').trim();
                loadLiveDeals();
            }, 300);
        }

        async function loadLiveDeals(forceRefresh = false) {
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
        }

        function setLiveCategory(cat) {
            liveFilter.category = cat;
            ['all', 'laptops', 'ssd', 'ram', 'dish_washer', 'sofas'].forEach(c => {
                const b = document.getElementById(`btn-live-cat-${c}`);
                if (!b) return;
                if (c === cat) {
                    b.className = 'px-2 py-1 rounded-lg bg-slate-900 dark:bg-white text-white dark:text-slate-950 font-bold text-xs shadow-sm';
                } else {
                    b.className = 'px-2 py-1 rounded-lg text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/[0.06] font-medium text-xs';
                }
            });
            loadLiveDeals();
        }

        function setLiveRam(ram) {
            liveFilter.ram = ram;
            ['all', '8gb', '16gb', '24gb', '32gb'].forEach(c => {
                const b = document.getElementById(`btn-live-ram-${c}`);
                if (!b) return;
                if (c === ram) {
                    b.className = 'px-2 py-1 rounded-lg bg-slate-900 dark:bg-white text-white dark:text-slate-950 font-bold text-xs shadow-sm';
                } else {
                    b.className = 'px-2 py-1 rounded-lg text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/[0.06] font-medium text-xs';
                }
            });
            loadLiveDeals();
        }

        function setLiveGpu(gpu) {
            liveFilter.gpu = gpu;
            ['all', 'rtx_30', 'rtx_40', 'rtx_50', 'amd'].forEach(c => {
                const b = document.getElementById(`btn-live-gpu-${c}`);
                if (!b) return;
                if (c === gpu) {
                    b.className = 'px-2 py-1 rounded-lg bg-slate-900 dark:bg-white text-white dark:text-slate-950 font-bold text-xs shadow-sm';
                } else {
                    b.className = 'px-2 py-1 rounded-lg text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/[0.06] font-medium text-xs';
                }
            });
            loadLiveDeals();
        }

        function updateLiveMetrics(data) {
            const deals = data.deals || [];
            const total = data.total ?? deals.length;
            const badgeLive = document.getElementById('badge-live-count');
            if (badgeLive) badgeLive.textContent = `${total}`;
        }

        function setLiveFilterType(type) {
            liveFilter.filterType = type;
            ['all', 'fresh_drops', 'bangers', 'major_cuts'].forEach(t => {
                const b = document.getElementById(`btn-live-filter-${t}`);
                if (!b) return;
                if (t === type) {
                    b.className = 'px-3 py-1.5 rounded-xl text-xs font-bold transition-all shadow-sm bg-slate-900 dark:bg-white text-white dark:text-slate-950';
                } else if (t === 'fresh_drops') {
                    b.className = 'px-3 py-1.5 rounded-xl text-xs font-semibold transition-all hover:bg-slate-100 dark:hover:bg-white/[0.06] text-emerald-800 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-500/30 bg-emerald-50/50 dark:bg-emerald-950/20';
                } else if (t === 'bangers') {
                    b.className = 'px-3 py-1.5 rounded-xl text-xs font-semibold transition-all hover:bg-slate-100 dark:hover:bg-white/[0.06] text-rose-800 dark:text-rose-300 border border-rose-200 dark:border-rose-500/30 bg-rose-50/50 dark:bg-rose-950/20';
                } else if (t === 'major_cuts') {
                    b.className = 'px-3 py-1.5 rounded-xl text-xs font-semibold transition-all hover:bg-slate-100 dark:hover:bg-white/[0.06] text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-500/30 bg-amber-50/50 dark:bg-amber-950/20';
                } else {
                    b.className = 'px-3 py-1.5 rounded-xl text-xs font-semibold transition-all hover:bg-slate-100 dark:hover:bg-white/[0.06] text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-white/[0.08]';
                }
            });
            loadLiveDeals();
        }

        function setLivePlatform(plat) {
            liveFilter.platform = plat;
            ['all', 'lenovo', 'flipkart', 'ikea'].forEach(p => {
                const b = document.getElementById(`btn-live-plat-${p}`);
                if (!b) return;
                if (p === plat) {
                    b.className = 'px-2.5 py-1 rounded-lg font-bold bg-slate-900 dark:bg-white text-white dark:text-slate-950 text-xs shadow-sm';
                } else {
                    b.className = 'px-2.5 py-1 rounded-lg font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/[0.06] border border-slate-200 dark:border-white/[0.08] text-xs';
                }
            });
            loadLiveDeals();
        }

        function setLiveCategory(cat) {
            liveFilter.category = cat;
            ['all', 'laptops', 'ssd', 'ram', 'dish_washer', 'sofas'].forEach(c => {
                const b = document.getElementById(`btn-live-cat-${c}`);
                if (!b) return;
                if (c === cat) {
                    b.className = 'px-2 py-1 rounded-lg bg-slate-900 dark:bg-white text-white dark:text-slate-950 font-bold text-xs shadow-sm';
                } else {
                    b.className = 'px-2 py-1 rounded-lg text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/[0.06] font-medium text-xs';
                }
            });
            loadLiveDeals();
        }

        function setLiveSort(sort) {
            liveFilter.sort = sort;
            loadLiveDeals();
        }

        

        

        function renderLiveCards(deals) {
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
                    steepBadge = `<span class="text-[10px] font-black px-2 py-0.5 rounded-lg bg-purple-100 dark:bg-purple-500/20 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-500/30">↓${d.steep_drop_pct}% TRUE DROP</span>`;
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

                window._productCache = window._productCache || {};
                  window._productCache[d.pid] = d;
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
                    <div class="flex items-center gap-1.5">
                        <button onclick="event.stopPropagation(); openPriceTrendModal('${escapeJs(d.pid)}')" class="px-2 py-1.5 rounded-xl bg-slate-100 dark:bg-white/[0.04] hover:bg-blue-50 dark:hover:bg-blue-950/40 text-slate-700 dark:text-slate-300 border border-slate-200/80 dark:border-white/[0.06] text-xs font-bold transition-all shadow-sm" title="Price History">📈</button>
                        <a href="${escapeHtml(d.url)}" target="_blank" class="px-3 py-1.5 rounded-xl bg-slate-900 dark:bg-white/[0.08] text-white dark:text-white text-xs font-bold hover:opacity-90 transition-all">View ↗</a>
                      </div>
                      </div>
                  </div>
                </div>`;
            }).join('');
        }

        // Tab Switching
        function switchTab(tab) {
            currentTab = tab;
            ['live', 'lenovo', 'listings', 'single'].forEach(t => {
                const el = document.getElementById(`tab-${t}`);
                const btn = document.getElementById(`tab-btn-${t}`);
                if (t === tab) {
                    if (el) el.classList.remove('hidden');
                    if (btn) btn.className = 'px-3 py-1.5 rounded-lg bg-white dark:bg-white/[0.12] text-slate-900 dark:text-white border border-slate-200/60 dark:border-white/[0.08] flex items-center gap-1.5 transition-all shadow-sm font-bold shrink-0';
                } else {
                    if (el) el.classList.add('hidden');
                    if (btn) btn.className = 'px-3 py-1.5 rounded-lg text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white flex items-center gap-1.5 transition-all font-semibold shrink-0';
                }
            });

            if (tab === 'live') loadLiveDeals();
            if (tab === 'lenovo') loadLenovoData();
            if (tab === 'listings') loadListings();
            if (tab === 'single') loadProducts();
        }

        function computeSteepDropInline(p) {
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
        }

        // ── LENOVO OUTLET STUDIO LOGIC ───────────────────────────────────────
        async function loadLenovoData() {
            try {
                if (!allLenovoLaptops.length) { const grid = document.getElementById("lenovo-grid-container"); if(grid) grid.innerHTML = `<div class="col-span-full py-16 flex flex-col items-center justify-center text-slate-400"><svg class="animate-spin h-8 w-8 mb-4 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg><span class="text-sm font-bold text-slate-500">Loading deals...</span></div>`; }

                const res = await fetch(API + '/api/lenovo-outlet');
                allLenovoLaptops = await res.json();
                
                updateLenovoMetrics(allLenovoLaptops);
                updateFacetCounts(allLenovoLaptops);
                applyLenovoFilters();
            } catch (e) {
                console.error('Lenovo error:', e);
                showToast('Failed to load Lenovo telemetry: ' + (e.message || String(e)), 'error');
            }
        }

        function updateLenovoMetrics(laptops) {
            const total = laptops.length;
            const dedicated = laptops.filter(l => l.is_dedicated_gpu).length;
            const rtx = laptops.filter(l => (l.gpu || '').toUpperCase().includes('RTX')).length;
            const bangers = laptops.filter(l => l.save_percent >= 50.0).length;
            const maxDisc = Math.max(0, ...laptops.map(l => l.save_percent || 0));

            const elTotal = document.getElementById('metric-total-laptops'); if (elTotal) elTotal.textContent = total;
            const elDed = document.getElementById('metric-dedicated-gpus'); if (elDed) elDed.textContent = dedicated;
            const elRtx = document.getElementById('metric-rtx-gpus'); if (elRtx) elRtx.textContent = rtx;
            const elBangers = document.getElementById('metric-banger-deals'); if (elBangers) elBangers.textContent = bangers;
            const elMaxDisc = document.getElementById('metric-max-discount'); if (elMaxDisc) elMaxDisc.textContent = `${Math.round(maxDisc)}%`;

            const bangerBadge = document.getElementById('badge-lenovo-bangers');
            if (bangerBadge) bangerBadge.textContent = `${bangers} Cuts`;
        }


        function updateFacetCounts(laptops) {
            const countAll = laptops.length;
            const countDed = laptops.filter(l => l.is_dedicated_gpu).length;
            const countRtx50 = laptops.filter(l => {
                const g = (l.gpu || '').toUpperCase();
                return g.includes('RTX 50') || g.includes('RTX50') || g.includes('5060') || g.includes('5070') || g.includes('5080') || g.includes('5090');
            }).length;
            const countAda = laptops.filter(l => {
                const g = (l.gpu || '').toUpperCase();
                return g.includes('ADA') || g.includes('RTX A') || g.includes('QUADRO');
            }).length;
            const countRtx40 = laptops.filter(l => (l.gpu || '').toUpperCase().includes('RTX 40') || (l.gpu || '').toUpperCase().includes('RTX40')).length;
            const countRtx30 = laptops.filter(l => (l.gpu || '').toUpperCase().includes('RTX 30') || (l.gpu || '').toUpperCase().includes('RTX30')).length;
            const countGtx = laptops.filter(l => {
                const g = (l.gpu || '').toUpperCase();
                return g.includes('GTX') || g.includes('MX') || g.includes('ARC A');
            }).length;

            const elAll = document.getElementById('count-tier-all'); if (elAll) elAll.textContent = countAll;
            const elDed = document.getElementById('count-tier-dedicated'); if (elDed) elDed.textContent = countDed;
            const elRtx50 = document.getElementById('count-tier-rtx50'); if (elRtx50) elRtx50.textContent = countRtx50;
            const elAda = document.getElementById('count-tier-ada'); if (elAda) elAda.textContent = countAda;
            const elRtx40 = document.getElementById('count-tier-rtx40'); if (elRtx40) elRtx40.textContent = countRtx40;
            const elRtx30 = document.getElementById('count-tier-rtx30'); if (elRtx30) elRtx30.textContent = countRtx30;
            const elGtx = document.getElementById('count-tier-gtx_mx'); if (elGtx) elGtx.textContent = countGtx;

            const metricRtx50 = document.getElementById('metric-rtx50-gpus'); if (metricRtx50) metricRtx50.textContent = countRtx50;
            const metricAda = document.getElementById('metric-ada-gpus'); if (metricAda) metricAda.textContent = countAda;
        }

        function setGpuTier(tier) {
            lenovoFilter.gpuTier = tier;
            ['all', 'dedicated', 'rtx50', 'ada', 'rtx40', 'rtx30', 'gtx_mx'].forEach(t => {
                const b = document.getElementById(`btn-tier-${t}`);
                if (b) {
                    if (t === tier) {
                        b.className = 'px-3 py-1.5 rounded-xl text-xs font-bold transition-all shadow-sm bg-slate-900 dark:bg-white text-white dark:text-slate-950';
                    } else if (t === 'dedicated') {
                        b.className = 'px-3 py-1.5 rounded-xl text-xs font-semibold transition-all hover:bg-slate-100 dark:hover:bg-white/[0.06] text-emerald-800 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-500/30 bg-emerald-50/50 dark:bg-emerald-950/20';
                    } else if (t === 'rtx50') {
                        b.className = 'px-3 py-1.5 rounded-xl text-xs font-semibold transition-all hover:bg-slate-100 dark:hover:bg-white/[0.06] text-purple-800 dark:text-purple-300 border border-purple-200 dark:border-purple-500/30 bg-purple-50/50 dark:bg-purple-950/20';
                    } else if (t === 'ada') {
                        b.className = 'px-3 py-1.5 rounded-xl text-xs font-semibold transition-all hover:bg-slate-100 dark:hover:bg-white/[0.06] text-cyan-800 dark:text-cyan-300 border border-cyan-200 dark:border-cyan-500/30 bg-cyan-50/50 dark:bg-cyan-950/20';
                    } else {
                        b.className = 'px-3 py-1.5 rounded-xl text-xs font-semibold transition-all hover:bg-slate-100 dark:hover:bg-white/[0.06] text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-white/[0.08]';
                    }
                }
            });
            applyLenovoFilters();
        }

        function setVramFilter(vram) {
            lenovoFilter.vram = vram;
            ['all', '16gb', '8gb+', '6gb+'].forEach(v => {
                const b = document.getElementById(`btn-vram-${v}`);
                if (b) {
                    if (v === vram) {
                        b.className = 'px-2 py-1 rounded-lg bg-slate-900 dark:bg-white text-white dark:text-slate-950 font-bold text-xs shadow-sm';
                    } else {
                        b.className = 'px-2 py-1 rounded-lg text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/[0.06] font-mono font-medium text-xs';
                    }
                }
            });
            applyLenovoFilters();
        }

        function setSeriesFilter(series) {
            lenovoFilter.series = series;
            ['all', 'Legion', 'ThinkPad', 'Yoga', 'LOQ', 'IdeaPad'].forEach(s => {
                const b = document.getElementById(`btn-series-${s}`);
                if (b) {
                    if (s === series) {
                        b.className = 'px-2 py-1 rounded-lg font-bold bg-slate-900 dark:bg-white text-white dark:text-slate-950 text-xs shadow-sm';
                    } else {
                        b.className = 'px-2 py-1 rounded-lg font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/[0.06] text-xs';
                    }
                }
            });
            applyLenovoFilters();
        }

        function setDiscountFilter(pct) {
            lenovoFilter.discountMin = pct;
            [0, 50, 40, 30].forEach(p => {
                const b = document.getElementById(`btn-disc-${p}`);
                if (b) {
                    if (p === pct) {
                        b.className = 'px-2.5 py-1 rounded-lg font-bold bg-slate-900 dark:bg-white text-white dark:text-slate-950 text-xs shadow-sm';
                    } else if (p === 50) {
                        b.className = 'px-2.5 py-1 rounded-lg font-semibold text-rose-700 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/30 border border-rose-200 dark:border-rose-500/20 text-xs';
                    } else if (p === 40) {
                        b.className = 'px-2.5 py-1 rounded-lg font-semibold text-amber-700 dark:text-amber-400 hover:bg-amber-50 dark:hover:bg-amber-950/30 border border-amber-200 dark:border-amber-500/20 text-xs';
                    } else {
                        b.className = 'px-2.5 py-1 rounded-lg font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/[0.06] text-xs';
                    }
                }
            });
            applyLenovoFilters();
        }

        function setLenovoView(mode) {
            lenovoFilter.view = mode;
            const grid = document.getElementById('lenovo-grid-container');
            const table = document.getElementById('lenovo-table-container');
            const btnCards = document.getElementById('view-mode-cards');
            const btnTable = document.getElementById('view-mode-table');

            if (mode === 'cards') {
                grid.classList.remove('hidden');
                table.classList.add('hidden');
                btnCards.className = 'px-2.5 py-1 rounded-lg bg-white dark:bg-white/[0.12] text-slate-900 dark:text-white font-bold flex items-center gap-1.5 transition-all shadow-sm';
                btnTable.className = 'px-2.5 py-1 rounded-lg text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white font-medium flex items-center gap-1.5 transition-all';
            } else {
                grid.classList.add('hidden');
                table.classList.remove('hidden');
                btnTable.className = 'px-2.5 py-1 rounded-lg bg-white dark:bg-white/[0.12] text-slate-900 dark:text-white font-bold flex items-center gap-1.5 transition-all shadow-sm';
                btnCards.className = 'px-2.5 py-1 rounded-lg text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white font-medium flex items-center gap-1.5 transition-all';
            }
        }

        function resetLenovoFilters() {
            lenovoFilter = {
                search: '',
                gpuTier: 'all',
                vram: 'all',
                series: 'all',
                discountMin: 0,
                inStockOnly: false,
                sort: 'savingPercent',
                view: lenovoFilter.view,
            };
            const searchInput = document.getElementById('lenovo-search');
            if (searchInput) searchInput.value = '';
            const sortInput = document.getElementById('lenovo-sort');
            if (sortInput) sortInput.value = 'savingPercent';
            const stockInput = document.getElementById('lenovo-stock-only');
            if (stockInput) stockInput.checked = false;

            setGpuTier('all');
            setVramFilter('all');
            setSeriesFilter('all');
            setDiscountFilter(0);
        }

        function applyLenovoFilters() {
            const query = (document.getElementById('lenovo-search')?.value || '').toLowerCase().trim();
            const sortVal = document.getElementById('lenovo-sort')?.value || 'savingPercent';
            const inStock = document.getElementById('lenovo-stock-only')?.checked || false;

            allLenovoLaptops.forEach(p => computeSteepDropInline(p));
            let filtered = allLenovoLaptops.filter(p => {
                if (query) {
                    const haystack = `${p.name} ${p.series} ${p.gpu} ${p.cpu} ${p.ram} ${p.ssd} ${p.vram} ${p.product_code}`.toLowerCase();
                    if (!haystack.includes(query)) return false;
                }

                if (inStock && !p.in_stock) return false;

                if (lenovoFilter.discountMin > 0 && (p.save_percent || 0) < lenovoFilter.discountMin) {
                    return false;
                }

                if (lenovoFilter.series !== 'all') {
                    if (!p.series || !p.series.toLowerCase().includes(lenovoFilter.series.toLowerCase())) {
                        return false;
                    }
                }

                if (lenovoFilter.gpuTier === 'dedicated' && !p.is_dedicated_gpu) return false;
                if (lenovoFilter.gpuTier === 'rtx50') {
                    const g = (p.gpu || '').toUpperCase();
                    if (!g.includes('RTX 50') && !g.includes('RTX50') && !g.includes('5060') && !g.includes('5070') && !g.includes('5080') && !g.includes('5090')) return false;
                }
                if (lenovoFilter.gpuTier === 'ada') {
                    const g = (p.gpu || '').toUpperCase();
                    if (!g.includes('ADA') && !g.includes('RTX A') && !g.includes('QUADRO')) return false;
                }
                if (lenovoFilter.gpuTier === 'rtx40') {
                    const g = (p.gpu || '').toUpperCase();
                    if (!g.includes('RTX 40') && !g.includes('RTX40')) return false;
                }
                if (lenovoFilter.gpuTier === 'rtx30') {
                    const g = (p.gpu || '').toUpperCase();
                    if (!g.includes('RTX 30') && !g.includes('RTX30')) return false;
                }
                if (lenovoFilter.gpuTier === 'gtx_mx') {
                    const g = (p.gpu || '').toUpperCase();
                    if (!g.includes('GTX') && !g.includes('MX') && !g.includes('ARC A')) return false;
                }

                if (lenovoFilter.vram !== 'all') {
                    const vramStr = (p.vram || '').toUpperCase();
                    const vramNum = parseInt(vramStr.match(/(\d+)/)?.[1] || '0', 10);
                    if (lenovoFilter.vram === '16gb' && vramNum !== 16) return false;
                    if (lenovoFilter.vram === '8gb+' && vramNum < 8) return false;
                    if (lenovoFilter.vram === '6gb+' && vramNum < 6) return false;
                }

                return true;
            });

            filtered.sort((a, b) => {
                if (sortVal === 'steepest') {
                    const steepA = a.steep_drop_pct || 0;
                    const steepB = b.steep_drop_pct || 0;
                    return (steepB - steepA) || ((b.save_percent || 0) - (a.save_percent || 0));
                }
                if (sortVal === 'latest_drop') {
                    const timeA = new Date(a.last_alerted_at || a.first_seen_at || a.last_scanned_at || 0).getTime();
                    const timeB = new Date(b.last_alerted_at || b.first_seen_at || b.last_scanned_at || 0).getTime();
                    return timeB - timeA || (b.save_percent || 0) - (a.save_percent || 0);
                }
                if (sortVal === 'savingPercent') return (b.save_percent || 0) - (a.save_percent || 0);
                if (sortVal === 'savingAmount') return (b.save_amount || 0) - (a.save_amount || 0);
                if (sortVal === 'priceAsc') return (a.current_price || 0) - (b.current_price || 0);
                if (sortVal === 'priceDesc') return (b.current_price || 0) - (a.current_price || 0);
                if (sortVal === 'vramDesc') {
                    const va = parseInt((a.vram || '').match(/(\d+)/)?.[1] || '0', 10);
                    const vb = parseInt((b.vram || '').match(/(\d+)/)?.[1] || '0', 10);
                    return vb - va;
                }
                return 0;
            });

            const countLabel = document.getElementById('filtered-count-label');
            if (countLabel) countLabel.textContent = `${filtered.length} Units Available`;
            renderLenovoCards(filtered);
            
        }


        function renderActiveFilterChips() {
            const container = document.getElementById('active-filter-chips');
            const chips = [];

            if (lenovoFilter.gpuTier !== 'all') {
                chips.push(`<span class="px-2 py-0.5 rounded-md bg-slate-100 dark:bg-white/[0.08] text-slate-800 dark:text-white border border-slate-200 dark:border-white/[0.1] font-mono text-[10px] flex items-center gap-1 font-semibold">GPU: ${lenovoFilter.gpuTier} <button onclick="setGpuTier('all')" class="hover:text-rose-500">✕</button></span>`);
            }
            if (lenovoFilter.vram !== 'all') {
                chips.push(`<span class="px-2 py-0.5 rounded-md bg-slate-100 dark:bg-white/[0.08] text-slate-800 dark:text-white border border-slate-200 dark:border-white/[0.1] font-mono text-[10px] flex items-center gap-1 font-semibold">VRAM: ${lenovoFilter.vram} <button onclick="setVramFilter('all')" class="hover:text-rose-500">✕</button></span>`);
            }
            if (lenovoFilter.series !== 'all') {
                chips.push(`<span class="px-2 py-0.5 rounded-md bg-slate-100 dark:bg-white/[0.08] text-slate-800 dark:text-white border border-slate-200 dark:border-white/[0.1] font-mono text-[10px] flex items-center gap-1 font-semibold">${lenovoFilter.series} <button onclick="setSeriesFilter('all')" class="hover:text-rose-500">✕</button></span>`);
            }
            if (lenovoFilter.discountMin > 0) {
                chips.push(`<span class="px-2 py-0.5 rounded-md bg-rose-100 dark:bg-rose-500/20 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-500/30 font-mono text-[10px] flex items-center gap-1 font-bold">≥${lenovoFilter.discountMin}% Cuts <button onclick="setDiscountThreshold(0)" class="hover:text-rose-500">✕</button></span>`);
            }

            const countLabel = `<span id="filtered-count-label" class="font-bold text-slate-900 dark:text-white">${document.getElementById('filtered-count-label')?.textContent || ''}</span>`;
            container.innerHTML = countLabel + (chips.length ? ' ' + chips.join('') : '');
        }

        function renderLenovoCards(laptops) {
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
        }

        function renderGridCards(products, container) {
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
        }

        function renderDenseList(products, container) {
            if (!container) return;
            container.innerHTML = products.map(p => {
                const isIkea = (p.url || '').toLowerCase().includes('ikea.com') || (p.pid || '').startsWith('IKEA_') || p.ssd === 'IKEA Family Offer';
                const showImg = !isIkea && p.image_url;
                return `
            <tr class="hover:bg-slate-50 dark:hover:bg-white/[0.03] border-b border-slate-200/80 dark:border-white/[0.04] transition-colors">
                <td class="py-3 px-4">
                    <div class="flex items-center gap-3">
                        ${showImg ? `<img src="${escapeHtml(p.image_url)}" class="w-9 h-9 object-cover rounded-lg border border-slate-200/80 dark:border-white/[0.06] shrink-0" loading="lazy">` : ''}
                        <div>
                            <div class="font-bold text-slate-900 dark:text-white line-clamp-1">${escapeHtml(p.name)}</div>
                            <div class="text-[10px] text-slate-500 dark:text-slate-400">${escapeHtml(p.cpu || '')} · ${escapeHtml(p.ram || '')}</div>
                        </div>
                    </div>
                </td>
                <td class="py-3 px-3 font-black text-slate-900 dark:text-white font-mono text-sm tabular-nums">${formatPrice(p.effective_price)}</td>
                <td class="py-3 px-3 font-mono text-blue-700 dark:text-cyan-400 text-xs tabular-nums font-bold">${p.wow_price ? formatPrice(p.wow_price) : '—'}</td>
                <td class="py-3 px-3 font-mono text-emerald-600 dark:text-emerald-400 font-bold text-xs">${p.discount_pct ? `−${p.discount_pct}%` : '—'}</td>
                <td class="py-3 px-3">${renderTrendButton(p)}</td>
                <td class="py-3 px-4 text-right">
                    <div class="flex items-center gap-1.5">
                        
                        <div class="flex items-center gap-1.5">
                        
                        <div class="flex items-center gap-1.5">
                        <button onclick="event.stopPropagation(); openPriceTrendModal(\'${escapeJs(p.product_code || p.pid)}\')" class="px-2 py-1.5 rounded-xl bg-slate-100 dark:bg-white/[0.04] hover:bg-blue-50 dark:hover:bg-blue-950/40 text-slate-700 dark:text-slate-300 border border-slate-200/80 dark:border-white/[0.06] text-xs font-bold transition-all shadow-sm" title="Price History">📈</button>
                        <a href="${escapeHtml(p.url)}" target="_blank" rel="noopener noreferrer" class="bg-slate-100 hover:bg-slate-200 dark:bg-white/[0.08] dark:hover:bg-white/[0.14] text-slate-900 dark:text-white px-2.5 py-1 rounded-lg font-bold text-[11px] transition-all">View ↗</a>
                      </div>
                      </div>
                      </div>
                </td>
            </tr>`;
            }).join('');
        }

        function escapeJs(str) {
            if (!str) return '';
            return String(str).replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '&quot;');
        }

        function formatTimeDetailed(iso) {
            if (!iso) return 'Recent Scan';
            try {
                const d = new Date(iso);
                return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: true }) + ' (' + timeAgo(iso) + ')';
            } catch {
                return timeAgo(iso);
            }
        }

        function renderTrendButton(p) {
            const rawHistory = p.price_history || [];
            const curPrice = p.effective_price ?? p.current_price ?? 0;
            const history = rawHistory.length ? rawHistory : (curPrice ? [{ effective_price: curPrice, recorded_at: p.last_updated || p.last_scanned_at }] : []);
            const sparkline = generateSparklineSvg(history, 55, 16);
            const pId = p.pid || p.product_code || String(p.id);
            window._productCache = window._productCache || {};
            window._productCache[pId] = p;

            return `
            <button onclick="event.stopPropagation(); openPriceTrendModal('${escapeJs(pId)}')" class="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-slate-100/80 dark:bg-white/[0.04] hover:bg-blue-50 dark:hover:bg-blue-950/40 border border-slate-200/80 dark:border-white/[0.06] hover:border-blue-300 dark:hover:border-blue-500/40 transition-all cursor-pointer group shadow-2xs" title="Click to view Price Trend History">
                ${sparkline}
                <span class="text-[9px] text-slate-400 group-hover:text-blue-600 dark:group-hover:text-cyan-400 font-mono">📈</span>
            </button>`;
        }

        // ── Single Product Tracker ──────────────────────────────────────
        
        // --- RESTORED FUNCTIONS ---
        async function loadListings() {
            try {
                const res = await fetch(API + '/api/listings');
                allListings = await res.json();
                renderListingsSidebar();
                if (currentListingId) {
                    loadListingProducts(currentListingId);
                } else if (allListings.length > 0) {
                    selectListing(allListings[0].id);
                }
            } catch (err) {
                console.error(err);
            }
        }

        function renderListingsSidebar() {
            const container = document.getElementById('listings-sidebar');
            if (!container) return;
            container.innerHTML = allListings.map(l => {
                const isActive = l.id === currentListingId;
                return 
                <button onclick="selectListing()" class="w-full text-left px-3 py-2 rounded-xl text-sm font-semibold transition-all ">
                    
                </button>;
            }).join('');
        }

        async function selectListing(id) {
            currentListingId = id;
            renderListingsSidebar();
            loadListingProducts(id);
        }

        async function loadListingProducts(id) {
            currentListingId = id;
            const grid = document.getElementById("harvester-grid-container"); 
            if(grid) grid.innerHTML = `<div class="col-span-full py-16 flex flex-col items-center justify-center text-slate-400"><svg class="animate-spin h-8 w-8 mb-4 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg><span class="text-sm font-bold text-slate-500">Loading harvester data...</span></div>`;
            
            try {
                const sort = document.getElementById('harvester-sort')?.value || 'steepest';
                const res = await fetch(API + /api/listings//products?sort_by=);
                currentListingItems = await res.json();
                applyHarvesterFilters();
            } catch (err) {
                console.error(err);
            }
        }

        function applyHarvesterFilters() {
            let items = currentListingItems || [];
            const search = (document.getElementById('harvester-search')?.value || '').toLowerCase();
            if (search) {
                items = items.filter(i => (i.title || i.name || '').toLowerCase().includes(search) || (i.sku || '').toLowerCase().includes(search));
            }
            const view = window.harvesterViewMode || 'grid';
            if (view === 'grid') {
                renderGridCards(items);
                document.getElementById('harvester-grid-container')?.classList.remove('hidden');
                document.getElementById('harvester-dense-container')?.classList.add('hidden');
            } else {
                renderDenseList(items, document.getElementById('harvester-dense-container'));
                document.getElementById('harvester-dense-container')?.classList.remove('hidden');
                document.getElementById('harvester-grid-container')?.classList.add('hidden');
            }
        }

        function setViewMode(mode) {
            window.harvesterViewMode = mode;
            applyHarvesterFilters();
        }

        async function scanActiveListing() {
            if(!currentListingId) return;
            showToast('Scanning listing...', 'info');
            try {
                await fetch(API + /api/listings//scan, {method: 'POST'});
                showToast('Scan complete!', 'success');
                loadListingProducts(currentListingId);
            } catch (e) {
                showToast('Scan failed', 'error');
            }
        }

        async function triggerLenovoScan() {
            showToast('Scanning Lenovo...', 'info');
            try {
                await fetch(API + /api/lenovo-outlet/scan, {method: 'POST'});
                showToast('Scan complete!', 'success');
                loadLenovoData();
            } catch (e) {
                showToast('Scan failed', 'error');
            }
        }
        // --- END RESTORED FUNCTIONS ---

        async function loadProducts() {
            try {
                const res = await fetch(API + '/api/products');
                const products = await res.json();
                const badge = document.getElementById('badge-single-count');
                if (badge) badge.textContent = products.length;

                const grid = document.getElementById('products-grid');
                if (!products.length) {
                    grid.innerHTML = '<div class="col-span-full text-center py-12 text-slate-500 text-xs font-medium">No direct single products monitored. Paste a product link above.</div>';
                    return;
                }

                grid.innerHTML = products.map(p => {
                    const atTarget = p.current_price && p.current_price <= p.target_price;
                    return `
                    <div class="bg-white dark:bg-[#0f1523] border border-slate-200/90 dark:border-white/[0.08] rounded-2xl p-4 flex flex-col justify-between shadow-sm hover:shadow-md">
                        <div>
                            <div class="flex items-start justify-between gap-2 mb-2">
                                <span class="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-slate-100 dark:bg-white/[0.06] text-slate-800 dark:text-white border border-slate-200 dark:border-white/[0.08]">${escapeHtml(p.platform)}</span>
                                <button onclick="deleteSingleProduct(${p.id})" class="text-slate-400 hover:text-rose-500 text-xs">✕</button>
                            </div>
                            <h3 class="text-xs font-bold text-slate-900 dark:text-slate-200 line-clamp-2 leading-snug mb-3">${escapeHtml(p.title || 'Fetching…')}</h3>
                            <div class="flex items-baseline justify-between mb-1.5">
                                <span class="text-xs text-slate-500">Current</span>
                                <span class="text-base font-black ${atTarget ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-900 dark:text-white'} font-mono tabular-nums">${formatPrice(p.current_price)}</span>
                            </div>
                            <div class="flex items-baseline justify-between text-xs text-slate-500">
                                <span>Target</span>
                                <span class="font-mono tabular-nums font-bold">${formatPrice(p.target_price)}</span>
                            </div>
                        </div>
                        <div class="mt-4 pt-2 border-t border-slate-200/80 dark:border-white/[0.06] flex items-center justify-between text-xs">
                            <span class="text-[11px] text-slate-400">${timeAgo(p.last_checked)}</span>
                            <button onclick="checkSingleOne(${p.id})" class="text-blue-600 dark:text-white hover:underline font-bold flex items-center gap-1">Check Now ↗</button>
                        </div>
                    </div>`;
                }).join('');
            } catch (e) {
                showToast('Failed to load products', 'error');
            }
        }

        async function addProduct(e) {
            e.preventDefault();
            const url = document.getElementById('product-url').value.trim();
            const target_price = parseFloat(document.getElementById('product-target-price').value);
            try {
                const res = await fetch(API + '/api/products', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url, target_price })
                });
                if (!res.ok) throw new Error((await res.json()).detail || 'Failed');
                showToast('Product added to tracking!', 'success');
                document.getElementById('product-url').value = '';
                document.getElementById('product-target-price').value = '';
                loadProducts();
            } catch (err) {
                showToast(err.message, 'error');
            }
        }

        async function deleteSingleProduct(id) {
            if (!confirm('Stop tracking this product?')) return;
            await fetch(API + `/api/products/${id}`, { method: 'DELETE' });
            loadProducts();
        }

        async function checkSingleOne(id) {
            showToast('Checking product price…', 'info');
            try {
                await fetch(API + `/api/products/${id}/check`, { method: 'POST' });
                showToast('Product checked!', 'success');
                loadProducts();
            } catch {
                showToast('Failed to check product', 'error');
            }
        }

        // ── Helper Utilities ────────────────────────────────────────────
        function escapeHtml(str) {
            if (!str) return '';
            return String(str).replace(/[&<>"']/g, m => ({
                '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
            })[m]);
        }

        function showToast(msg, type = 'info') {
            const container = document.getElementById('toast-container');
            const colors = {
                success: 'bg-emerald-600 text-white font-bold',
                error: 'bg-rose-600 text-white font-bold',
                info: 'bg-slate-900 text-white font-bold',
            };
            const t = document.createElement('div');
            t.className = `toast-enter ${colors[type] || colors.info} px-4 py-2.5 rounded-xl text-xs shadow-xl max-w-sm flex items-center gap-2 pointer-events-auto`;
            t.innerHTML = `<span>${msg}</span>`;
            container.appendChild(t);
            setTimeout(() => {
                t.style.opacity = '0';
                t.style.transform = 'translateY(-0.5rem)';
                t.style.transition = 'all 0.3s ease';
                setTimeout(() => t.remove(), 300);
            }, 3500);
        }

        function formatPrice(p) {
            if (p === null || p === undefined || isNaN(p)) return '—';
            return '₹' + Math.round(p).toLocaleString('en-IN');
        }

        function timeAgo(iso) {
            if (!iso) return 'Never';
            const diff = (Date.now() - new Date(iso).getTime()) / 1000;
            if (diff < 60) return `${Math.floor(diff)}s ago`;
            if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
            if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
            return `${Math.floor(diff / 86400)}d ago`;
        }

        function generateSparklineSvg(history, width = 70, height = 22, isDetailed = false) {
            if (!history || history.length === 0) return '';
            const prices = history.map(h => Number(h.effective_price ?? h.price ?? h.current_price)).filter(p => !isNaN(p) && p > 0);
            if (prices.length === 0) return '';

            const paddingX = isDetailed ? 6 : 4;
            const paddingY = isDetailed ? 8 : 4;
            const effWidth = width - paddingX * 2;
            const effHeight = height - paddingY * 2;

            if (prices.length <= 1) {
                const midY = height / 2;
                return `
                <svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" class="overflow-visible inline-block">
                    <line x1="2" y1="${midY}" x2="${width - 2}" y2="${midY}" stroke="#0ea5e9" stroke-width="1.8" stroke-dasharray="3,2" />
                    <circle cx="${width - 3}" cy="${midY}" r="${isDetailed ? '4' : '2.2'}" fill="#0ea5e9" />
                </svg>`;
            }

            const min = Math.min(...prices);
            const max = Math.max(...prices);
            const isFlat = min === max;
            const range = max - min || 1;

            const pts = prices.map((p, i) => {
                const x = paddingX + (i / (prices.length - 1)) * effWidth;
                const y = isFlat ? (height / 2) : (height - paddingY - ((p - min) / range) * effHeight);
                return { x, y, price: p };
            });

            const polyPts = pts.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
            const isDownward = prices[prices.length - 1] < prices[0];
            const isUpward = prices[prices.length - 1] > prices[0];
            const strokeColor = isDownward ? '#10b981' : (isUpward ? '#f43f5e' : '#0ea5e9');

            return `
            <svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" class="overflow-visible inline-block">
                <polyline points="${polyPts}" fill="none" stroke="${strokeColor}" stroke-width="${isDetailed ? '2.4' : '1.8'}" stroke-linecap="round" stroke-linejoin="round" />
                ${pts.map(pt => `<circle cx="${pt.x.toFixed(1)}" cy="${pt.y.toFixed(1)}" r="${isDetailed ? '3.5' : '2.2'}" fill="${strokeColor}" />`).join('')}
            </svg>`;
        }

                async function openPriceTrendModal(pId) {
            const p = window._productCache && window._productCache[pId];
            if (!p) return;

            const modal = document.getElementById('price-trend-modal');
            if (!modal) return;

            const titleEl = document.getElementById('trend-product-title');
            const countBadge = document.getElementById('trend-scan-count-badge');
            const statLow = document.getElementById('trend-stat-low');
            const statHigh = document.getElementById('trend-stat-high');
            const statCurrent = document.getElementById('trend-stat-current');
            const chartContainer = document.getElementById('trend-chart-container');
            const historyList = document.getElementById('trend-history-list');
            const statusPill = document.getElementById('trend-status-pill');

            const title = p.name || p.title || 'Product';
            titleEl.textContent = title;

            // SHOW LOADING STATE
            chartContainer.innerHTML = `<div class="flex flex-col items-center justify-center h-full text-slate-400"><svg class="animate-spin h-6 w-6 mb-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg><span class="text-xs font-bold">Loading price history...</span></div>`;
            statLow.textContent = '--';
            statHigh.textContent = '--';
            statCurrent.textContent = '--';
            countBadge.textContent = '...';
            historyList.innerHTML = '';
            statusPill.textContent = 'Fetching';
            statusPill.className = 'px-2 py-0.5 rounded font-mono font-bold text-[10px] bg-slate-100 dark:bg-white/[0.06] text-slate-500';

            modal.classList.remove('hidden');

            try {
                const res = await fetch(`/api/deal-history/${encodeURIComponent(pId)}`);
                if (!res.ok) throw new Error('Failed to fetch history');
                const history = await res.json();
                
                const currentPrice = p.effective_price ?? p.current_price ?? 0;
                // if API returns empty array, fallback to current price point
                const safeHistory = history.length ? history : (currentPrice ? [{ effective_price: currentPrice, recorded_at: new Date().toISOString() }] : []);

                const prices = safeHistory.map(h => Number(h.effective_price ?? h.price ?? h.current_price)).filter(x => !isNaN(x) && x > 0);
                const minPrice = prices.length ? Math.min(...prices) : currentPrice;
                const maxPrice = prices.length ? Math.max(...prices) : currentPrice;
                const latestPrice = prices.length ? prices[prices.length - 1] : currentPrice;

                statLow.textContent = formatPrice(minPrice);
                statHigh.textContent = formatPrice(maxPrice);
                statCurrent.textContent = formatPrice(latestPrice);
                countBadge.textContent = `${safeHistory.length} Scan${safeHistory.length === 1 ? '' : 's'}`;

                const isDown = prices.length > 1 && latestPrice < prices[0];
                const isUp = prices.length > 1 && latestPrice > prices[0];
                if (isDown) {
                    const drop = Math.round(((prices[0] - latestPrice) / prices[0]) * 100);
                    statusPill.className = 'px-2 py-0.5 rounded font-mono font-bold text-[10px] bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300';
                    statusPill.textContent = `−${drop}% Price Drop Detected`;
                } else if (isUp) {
                    statusPill.className = 'px-2 py-0.5 rounded font-mono font-bold text-[10px] bg-rose-100 dark:bg-rose-500/20 text-rose-700 dark:text-rose-300';
                    statusPill.textContent = `Price Increased`;
                } else {
                    statusPill.className = 'px-2 py-0.5 rounded font-mono font-bold text-[10px] bg-blue-100 dark:bg-blue-500/20 text-blue-700 dark:text-blue-300';
                    statusPill.textContent = `Price Stable across all scans`;
                }

                // High-resolution SVG Chart Rendering
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
                    const iso = safeHistory[i] ? (safeHistory[i].recorded_at || safeHistory[i].checked_at) : null;
                    return { x, y, price: pr, iso };
                });

                const strokeColor = isDown ? '#10b981' : (isUp ? '#f43f5e' : '#0ea5e9');
                const polyPoints = pts.map(pt => `${pt.x.toFixed(1)},${pt.y.toFixed(1)}`).join(' ');
                const areaPoints = `${pts[0].x.toFixed(1)},${H - 8} ` + polyPoints + ` ${pts[pts.length - 1].x.toFixed(1)},${H - 8}`;

                chartContainer.innerHTML = `
                <svg width="100%" height="${H}" viewBox="0 0 ${W} ${H}" class="overflow-visible select-none">
                    <defs>
                        <linearGradient id="trendGradModal" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stop-color="${strokeColor}" stop-opacity="0.15" />
                            <stop offset="100%" stop-color="${strokeColor}" stop-opacity="0" />
                        </linearGradient>
                    </defs>
                    <polygon points="${areaPoints}" fill="url(#trendGradModal)" />
                    <polyline points="${polyPoints}" fill="none" stroke="${strokeColor}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" />
                    ${pts.map((pt, i) => `
                        <circle cx="${pt.x}" cy="${pt.y}" r="${i === pts.length - 1 ? 3 : 2}" fill="${i === pts.length - 1 ? strokeColor : '#fff'}" stroke="${strokeColor}" stroke-width="1.5" class="hover:r-4 transition-all" />
                        ${i === 0 || i === pts.length - 1 || pt.y === Math.min(...pts.map(p => p.y)) || pt.y === Math.max(...pts.map(p => p.y)) ? `
                            <text x="${pt.x}" y="${pt.y - 8}" text-anchor="middle" class="text-[9px] fill-slate-500 dark:fill-slate-400 font-mono font-bold">${formatPrice(pt.price)}</text>
                        ` : ''}
                    `).join('')}
                </svg>`;

                // Build Log List
                if (safeHistory.length === 0) {
                    historyList.innerHTML = '<li class="py-4 text-center text-slate-400 text-xs">No scan history recorded yet</li>';
                } else {
                    const rev = [...safeHistory].reverse();
                    historyList.innerHTML = rev.map((h, i) => {
                        const date = h.recorded_at || h.checked_at;
                        const dateStr = date ? new Date(date).toLocaleString() : 'Unknown Time';
                        const pVal = h.effective_price ?? h.price ?? h.current_price;
                        const isLatest = i === 0;
                        return `
                        <li class="py-2.5 flex items-center justify-between border-b border-slate-100 dark:border-white/[0.04] last:border-0 hover:bg-slate-50/50 dark:hover:bg-white/[0.02] px-2 -mx-2 rounded-lg transition-colors">
                            <span class="text-[11px] text-slate-500 font-mono tracking-tight">${dateStr}</span>
                            <div class="flex items-center gap-3">
                                ${isLatest ? '<span class="text-[9px] font-bold text-blue-500 bg-blue-50 dark:bg-blue-500/10 px-1.5 py-0.5 rounded-sm">LATEST</span>' : ''}
                                <span class="font-mono text-xs font-bold text-slate-900 dark:text-white tabular-nums">${formatPrice(pVal)}</span>
                            </div>
                        </li>`;
                    }).join('');
                }
            } catch (err) {
                console.error('Error loading history:', err);
                chartContainer.innerHTML = `<div class="flex items-center justify-center h-full text-rose-500 text-xs font-bold">Failed to load price history</div>`;
            }
        }

        function closePriceTrendModal() {
            const modal = document.getElementById('price-trend-modal');
            if (modal) modal.classList.add('hidden');
            hideChartTooltip();
        }

        function showChartTooltip(e, priceText, timeText) {
            const tt = document.getElementById('trend-chart-tooltip');
            if (!tt) return;
            tt.innerHTML = `<b>${priceText}</b> <span class="opacity-70 text-[10px]">· ${timeText}</span>`;
            tt.classList.remove('hidden');
        }

        function hideChartTooltip() {
            const tt = document.getElementById('trend-chart-tooltip');
            if (tt) tt.classList.add('hidden');
        }

        async function testBotAlert() {
            try {
                showToast('Sending test Telegram notification…', 'info');
                const res = await fetch(API + '/api/test-alert', { method: 'POST' });
                const d = await res.json();
                if (d.success) showToast(d.message || 'Telegram test alert sent successfully!', 'success');
                else showToast('Telegram error: ' + (d.error || d.message || 'Check .env'), 'error');
            } catch (e) {
                showToast('Error: ' + e.message, 'error');
            }
        }

        async function pollAllNow() {
            const icon = document.getElementById('poll-icon');
            icon.classList.add('spin');
            showToast('Triggering full system poll across all platforms…', 'info');
            try {
                const res = await fetch(API + '/api/check-now', { method: 'POST' });
                const data = await res.json();
                showToast(data.message || 'Scans initiated in background…', 'info');
                setTimeout(() => {
                    icon.classList.remove('spin');
                    loadListings();
                    loadProducts();
                }, 4000);
            } catch (err) {
                icon.classList.remove('spin');
                showToast('Failed to start poll: ' + err.message, 'error');
            }
        }

        function updateStatusUi(data) {
            const dot = document.getElementById('status-dot');
            const text = document.getElementById('status-text');
            const pinText = document.getElementById('pincode-text');
            if (pinText && data.delivery_pincode) {
                pinText.textContent = data.delivery_pincode;
            }
            if (data.lenovo_banger_deals_count !== undefined) {
                const bangersBadge = document.getElementById('badge-lenovo-bangers');
                if (bangersBadge) bangersBadge.textContent = `${data.lenovo_banger_deals_count} Cuts`;
            }
            if (!dot || !text) return;
            if (data.is_scanning || data.is_lenovo_scanning) {
                dot.className = 'w-2 h-2 rounded-full bg-blue-500 animate-ping';
                text.textContent = data.is_lenovo_scanning ? 'Scanning Lenovo…' : 'Polling…';
            } else if (data.scheduler_active) {
                dot.className = 'w-2 h-2 rounded-full bg-emerald-500';
                text.textContent = '1m Poll Active';
            } else {
                dot.className = 'w-2 h-2 rounded-full bg-yellow-500';
                text.textContent = 'Paused';
            }
        }

        async function loadStatus() {
            try {
                const res = await fetch(API + '/api/status');
                const data = await res.json();
                updateStatusUi(data);
            } catch {
                const dot = document.getElementById('status-dot');
                const text = document.getElementById('status-text');
                if (dot) dot.className = 'w-2 h-2 rounded-full bg-rose-500';
                if (text) text.textContent = 'Offline';
            }
        }

        // ── Keyboard Shortcuts (FAANG Desktop Ergonomics) ──────────────
        // ── Keyboard Shortcuts (FAANG Desktop Ergonomics) ──────────────
        window.addEventListener('keydown', (e) => {
            if (e.key === '/' && document.activeElement.tagName !== 'INPUT') {
                e.preventDefault();
                const targetId = currentTab === 'live' ? 'live-search' : (currentTab === 'lenovo' ? 'lenovo-search' : 'filter-search');
                const s = document.getElementById(targetId);
                if (s) s.focus();
            }
            if (e.key === 'Escape') {
                closePriceTrendModal();
                ['live-search', 'lenovo-search', 'filter-search'].forEach(id => {
                    const s = document.getElementById(id);
                    if (s && document.activeElement === s) {
                        s.value = '';
                        s.blur();
                        if (id === 'live-search') { liveFilter.search = ''; loadLiveDeals(); }
                        if (id === 'lenovo-search') applyLenovoFilters();
                        if (id === 'filter-search') applyFiltersAndRender();
                    }
                });
            }
        });

        // ── Initialization ──────────────────────────────────────────────
        loadLiveDeals();
        loadLenovoData();
        loadListings();
        loadProducts();
        loadStatus();
        setInterval(loadStatus, 15000);
        setInterval(loadLiveDeals, 20000);
        setInterval(loadLenovoData, 20000);
    