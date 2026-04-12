import re

path = "app/templates/index.html"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Find the end of Dashboard component
# It ends with:
#       </div>
#     </div>
#   );
# }

# Find the start of PortfolioPage component
# It starts with:
# function PortfolioPage({ data }) {

pattern = r"(function Dashboard\(.*?\}\n)\s*;\s*const ranking = agency\?.ranking \|\| \[\];.*?function PortfolioPage"
# Wait, let's be more precise.
# I want to delete everything between the end of Dashboard and start of PortfolioPage.

# Re-identifying markers
end_marker = "Evolução do Score Médio de Performance - Últimos 7 dias</div>\n      </div>\n    </div>\n  );\n}"
start_marker = "function PortfolioPage({ data }) {"

parts = content.split(end_marker)
if len(parts) > 1:
    second_part = parts[1].split(start_marker)
    if len(second_part) > 1:
        # We found both. parts[0] is everything before Dashboard ends.
        # second_part[1] is everything after PortfolioPage starts.
        new_content = parts[0] + end_marker + "\n\n" + start_marker + second_part[1]
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print("Fixed HTML successfully")
    else:
        print("Start marker not found")
else:
    print("End marker not found")
