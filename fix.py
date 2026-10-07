import re

with open('static/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Replace missing quotes around the loader HTML
html = re.sub(
    r'(grid\.innerHTML = )(<div class="col-span-full.*?Loading (?:deals|harvester data)\.\.\.<\/span><\/div>)(; \})',
    r'\1\2\3',
    html
)

with open('static/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
