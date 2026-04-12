import re

path = "app/templates/index.html"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# I need to separate JS from CSS because CSS also uses {}
script_match = re.search(r'<script type="text/babel">(.*?)</script>', content, re.DOTALL)
if script_match:
    script = script_match.group(1)

    # Check balanced braces in JS
    stack = []
    lines = script.split('\n')
    for i, line in enumerate(lines):
        # Ignore comments and strings as much as possible
        clean_line = re.sub(r'".*?"', '', line)
        clean_line = re.sub(r"'.*?'", '', clean_line)
        clean_line = re.sub(r'//.*', '', clean_line)

        for char in clean_line:
            if char == '{':
                stack.append(('{', i+1))
            elif char == '}':
                if not stack:
                    print(f"Extra closing brace at line {i+1}")
                else:
                    stack.pop()
    if stack:
        print(f"Total unclosed: {len(stack)}")
        for b, l in stack[:10]:
            print(f"Unclosed brace from line {l}")
else:
    print("Script not found")
