import sqlite3, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

db = sqlite3.connect("deal_tracker.db")
db.row_factory = sqlite3.Row

print("=" * 100)
print("1. LENOVO OUTLET — GPU Distribution & Pricing")
print("=" * 100)
rows = db.execute("""
    SELECT gpu, vram, is_dedicated_gpu, count(*) as cnt,
           min(current_price) as min_price,
           round(avg(current_price)) as avg_price,
           max(current_price) as max_price,
           min(mrp) as min_mrp,
           max(mrp) as max_mrp,
           round(avg(save_percent),1) as avg_discount
    FROM lenovo_products
    WHERE gpu != '' AND gpu IS NOT NULL
    GROUP BY gpu
    ORDER BY cnt DESC
""").fetchall()

for r in rows:
    print(f"  GPU: {r['gpu']:40s} | VRAM: {r['vram']:8s} | Dedicated: {r['is_dedicated_gpu']} | Count: {r['cnt']:3d} | Price: ₹{r['min_price']:>10,.0f} - ₹{r['max_price']:>10,.0f} (avg ₹{r['avg_price']:>10,.0f}) | MRP: ₹{r['min_mrp']:>10,.0f} - ₹{r['max_mrp']:>10,.0f} | Avg Disc: {r['avg_discount']}%")

print()
print("=" * 100)
print("2. LENOVO OUTLET — RAM Distribution & Pricing")
print("=" * 100)
rows = db.execute("""
    SELECT ram, count(*) as cnt,
           min(current_price) as min_price,
           round(avg(current_price)) as avg_price,
           max(current_price) as max_price
    FROM lenovo_products
    GROUP BY ram
    ORDER BY cnt DESC
""").fetchall()

for r in rows:
    print(f"  RAM: {r['ram']:30s} | Count: {r['cnt']:3d} | Price: ₹{r['min_price']:>10,.0f} - ₹{r['max_price']:>10,.0f} (avg ₹{r['avg_price']:>10,.0f})")

print()
print("=" * 100)
print("3. CHEAPEST DEDICATED GPU LAPTOPS (sorted by price)")
print("=" * 100)
rows = db.execute("""
    SELECT gpu, vram, name, current_price, mrp, save_percent, condition, ram, cpu, series, in_stock
    FROM lenovo_products
    WHERE is_dedicated_gpu = 1
    ORDER BY current_price ASC
    LIMIT 40
""").fetchall()

for r in rows:
    stock = "✅" if r['in_stock'] else "❌"
    print(f"  {stock} ₹{r['current_price']:>10,.0f} | -{r['save_percent']:.1f}% | {r['gpu']:30s} | {r['vram']:8s} | {r['ram']:15s} | {r['name'][:60]}")

print()
print("=" * 100)
print("4. GPU TIER SUMMARY (Dedicated GPUs grouped by tier)")
print("=" * 100)
rows = db.execute("""
    SELECT 
        CASE
            WHEN upper(gpu) LIKE '%RTX 5090%' THEN '01_RTX_5090'
            WHEN upper(gpu) LIKE '%RTX 5080%' THEN '02_RTX_5080'
            WHEN upper(gpu) LIKE '%RTX 5070%' THEN '03_RTX_5070'
            WHEN upper(gpu) LIKE '%RTX 5060%' THEN '04_RTX_5060'
            WHEN upper(gpu) LIKE '%RTX 5050%' THEN '05_RTX_5050'
            WHEN upper(gpu) LIKE '%RTX 4090%' THEN '06_RTX_4090'
            WHEN upper(gpu) LIKE '%RTX 4080%' THEN '07_RTX_4080'
            WHEN upper(gpu) LIKE '%RTX 4070%' THEN '08_RTX_4070'
            WHEN upper(gpu) LIKE '%RTX 4060%' THEN '09_RTX_4060'
            WHEN upper(gpu) LIKE '%RTX 4050%' THEN '10_RTX_4050'
            WHEN upper(gpu) LIKE '%RTX 3080%' THEN '11_RTX_3080'
            WHEN upper(gpu) LIKE '%RTX 3070%' THEN '12_RTX_3070'
            WHEN upper(gpu) LIKE '%RTX 3060%' THEN '13_RTX_3060'
            WHEN upper(gpu) LIKE '%RTX 3050%' THEN '14_RTX_3050'
            WHEN upper(gpu) LIKE '%ADA 5880%' THEN '15_ADA_5880'
            WHEN upper(gpu) LIKE '%ADA 5000%' THEN '16_ADA_5000'
            WHEN upper(gpu) LIKE '%ADA 3500%' THEN '17_ADA_3500'
            WHEN upper(gpu) LIKE '%ADA 2000%' THEN '18_ADA_2000'
            WHEN upper(gpu) LIKE '%ADA 1000%' THEN '19_ADA_1000'
            WHEN upper(gpu) LIKE '%ADA 500%' THEN '20_ADA_500'
            WHEN upper(gpu) LIKE '%A5000%' THEN '21_A5000'
            WHEN upper(gpu) LIKE '%A4500%' THEN '22_A4500'
            WHEN upper(gpu) LIKE '%A2000%' THEN '23_A2000'
            WHEN upper(gpu) LIKE '%A1000%' THEN '24_A1000'
            WHEN upper(gpu) LIKE '%A500%' THEN '25_A500'
            WHEN upper(gpu) LIKE '%T1200%' THEN '26_T1200'
            WHEN upper(gpu) LIKE '%T600%' THEN '27_T600'
            WHEN upper(gpu) LIKE '%T550%' THEN '28_T550'
            WHEN upper(gpu) LIKE '%RX 7600%' THEN '29_RX_7600'
            WHEN upper(gpu) LIKE '%RX 6700%' THEN '30_RX_6700'
            WHEN upper(gpu) LIKE '%RX 6650%' THEN '31_RX_6650'
            WHEN upper(gpu) LIKE '%RX 6500%' THEN '32_RX_6500'
            WHEN upper(gpu) LIKE '%GTX 1650%' THEN '33_GTX_1650'
            WHEN upper(gpu) LIKE '%MX%' THEN '34_MX_Series'
            ELSE '99_OTHER_' || gpu
        END as tier,
        count(*) as cnt,
        min(current_price) as min_price,
        round(avg(current_price)) as avg_price,
        max(current_price) as max_price,
        min(save_percent) as min_disc,
        max(save_percent) as max_disc,
        sum(in_stock) as in_stock_count
    FROM lenovo_products
    WHERE is_dedicated_gpu = 1
    GROUP BY tier
    ORDER BY tier ASC
""").fetchall()

for r in rows:
    print(f"  {r['tier']:20s} | Count: {r['cnt']:3d} (in-stock: {r['in_stock_count']:3d}) | Price: ₹{r['min_price']:>10,.0f} - ₹{r['max_price']:>10,.0f} (avg ₹{r['avg_price']:>10,.0f}) | Disc: {r['min_disc']:.1f}% - {r['max_disc']:.1f}%")

print()
print("=" * 100)
print("5. ALL-TIME LOW PRICES BY GPU TIER (from price history)")
print("=" * 100)
rows = db.execute("""
    SELECT gpu, vram, min(historical_low) as hist_low, min(current_price) as curr_low
    FROM lenovo_products
    WHERE is_dedicated_gpu = 1 AND historical_low IS NOT NULL
    GROUP BY gpu
    ORDER BY hist_low ASC
""").fetchall()

for r in rows:
    print(f"  {r['gpu']:40s} | Historical Low: ₹{r['hist_low']:>10,.0f} | Current Low: ₹{r['curr_low']:>10,.0f}")

print()
print("=" * 100)
print("6. HIGH-RAM LAPTOPS (>= 32GB)")
print("=" * 100)
rows = db.execute("""
    SELECT ram, gpu, name, current_price, mrp, save_percent, in_stock
    FROM lenovo_products
    WHERE (ram LIKE '%32%' OR ram LIKE '%64%' OR ram LIKE '%128%')
    ORDER BY current_price ASC
    LIMIT 30
""").fetchall()

for r in rows:
    stock = "✅" if r['in_stock'] else "❌"
    print(f"  {stock} ₹{r['current_price']:>10,.0f} | -{r['save_percent']:.1f}% | {r['ram']:20s} | {r['gpu']:30s} | {r['name'][:55]}")

db.close()
