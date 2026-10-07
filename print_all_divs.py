import re
with open('script.js', 'r', encoding='utf-8') as f:
    text = f.read().replace('\n', ' ')
matches = re.finditer(r'.{0,40}<div.{0,40}', text)
for m in matches:
    print(m.group(0))
