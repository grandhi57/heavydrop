with open('static/index.html', 'r', encoding='utf-8') as f:
    html = f.read()
import re
print("Single" in html)
m = re.search(r'//.*?Single Product Tracker.*', html)
if m:
    print(m.group(0))
