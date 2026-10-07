import re

with open('static/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

scripts = re.findall(r'<script>(.*?)</script>', html, re.DOTALL)
if len(scripts) >= 2:
    with open('script.js', 'w', encoding='utf-8') as f:
        f.write(scripts[1])
    print("Extracted script to script.js")
