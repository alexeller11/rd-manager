import re

path = "app/templates/index.html"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

script_match = re.search(r'<script type="text/babel">(.*?)</script>', content, re.DOTALL)
if script_match:
    script = script_match.group(1)

    # Check balanced braces
    stack = []
    lines = script.split('\n')
    for i, line in enumerate(lines):
        for char in line:
            if char == '{':
                stack.append(('{', i+1))
            elif char == '}':
                if not stack:
                    print(f"Extra closing brace at line {i+1}")
                else:
                    stack.pop()
    if stack:
        for b, l in stack:
            print(f"Unclosed brace from line {l}")
else:
    print("Script not found")
