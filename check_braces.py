import re

path = "app/templates/index.html"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

script_match = re.search(r'<script type="text/babel">(.*?)</script>', content, re.DOTALL)
if script_match:
    script = script_match.group(1)

    stack = []
    # Simplified parser that handles strings and comments
    i = 0
    while i < len(script):
        if script[i:i+2] == '//':
            i = script.find('\n', i)
            if i == -1: break
        elif script[i:i+2] == '/*':
            i = script.find('*/', i)
            if i == -1: break
            i += 2
        elif script[i] == '"':
            i += 1
            while i < len(script) and script[i] != '"':
                if script[i] == '\\': i += 1
                i += 1
            i += 1
        elif script[i] == "'":
            i += 1
            while i < len(script) and script[i] != "'":
                if script[i] == '\\': i += 1
                i += 1
            i += 1
        elif script[i] == '`':
            i += 1
            while i < len(script) and script[i] != '`':
                if script[i] == '\\': i += 1
                i += 1
            i += 1
        elif script[i] == '{':
            stack.append(('{', script.count('\n', 0, i) + 1))
            i += 1
        elif script[i] == '}':
            if not stack:
                print(f"Extra closing brace at line {script.count('\n', 0, i) + 1}")
            else:
                stack.pop()
            i += 1
        else:
            i += 1

    if stack:
        print(f"Total unclosed: {len(stack)}")
        for b, l in stack:
            print(f"Unclosed brace from line {l}")
else:
    print("Script not found")
