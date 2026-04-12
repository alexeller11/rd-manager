import re

path = "app/templates/index.html"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

script_match = re.search(r'<script type="text/babel">(.*?)</script>', content, re.DOTALL)
if script_match:
    script = script_match.group(1)
    # Print lines around Dashboard and PortfolioPage
    lines = script.split('\n')
    for i, line in enumerate(lines):
        if "function Dashboard" in line or "function PortfolioPage" in line:
            print(f"--- Line {i+1} ---")
            for j in range(max(0, i-5), min(len(lines), i+10)):
                print(f"{j+1}: {lines[j]}")
else:
    print("Script not found")
