import os
import re

path = "app/templates/index.html"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Add a non-react loading message
content = content.replace('<div id="root"></div>', '<div id="root"><div style="color:white; padding: 20px;">Carregando Interface...</div></div>')

# Fix CSS potentially hiding root
content = content.replace('overflow-x: hidden;', 'overflow-x: hidden; min-height: 100vh;')

# Ensure Sidebar doesn't have an error
# I noticed Sidebar component has some hardcoded v1.1 text.
# Let's check for any missing variables.

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
