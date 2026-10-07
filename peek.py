with open('static/index.html', 'r', encoding='utf-8') as f:
    html = f.read()
import re
m = re.search(r'async function loadLenovoData.*?async function loadProducts', html, re.DOTALL)
if m:
    print(m.group(0)[:1000])
    print("--- SNIP ---")
    print(m.group(0)[-1000:])
