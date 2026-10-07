import sys
import io
import re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open('static/index.html', 'r', encoding='utf-8') as f:
    html = f.read()
m = re.search(r'function renderDenseList.*?function setViewMode', html, re.DOTALL)
if m:
    print(m.group(0))
