import re

with open('static/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

missing_js = """
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
            if(grid) grid.innerHTML = <div class="col-span-full py-16 flex flex-col items-center justify-center text-slate-400"><svg class="animate-spin h-8 w-8 mb-4 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg><span class="text-sm font-bold text-slate-500">Loading harvester data...</span></div>;
            
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
"""

html = html.replace('async function loadProducts()', missing_js + '\n        async function loadProducts()')

with open('static/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("Restored based on loadProducts")
