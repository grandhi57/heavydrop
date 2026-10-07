import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open('static/index.html', 'r', encoding='utf-8') as f:
    html = f.read()
import re
m = re.search(r'async function loadLenovoData.*?async function loadProducts', html, re.DOTALL)
if m:
    print(m.group(0))
