import re
path = "app/templates/index.html"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

script_match = re.search(r'<script type="text/babel">(.*?)</script>', content, re.DOTALL)
if script_match:
    print(script_match.group(1))
else:
    print("NOT_FOUND")
