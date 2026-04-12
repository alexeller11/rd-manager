import re

path = "app/templates/index.html"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Use Production React
content = content.replace("react.development.js", "react.production.min.js")
content = content.replace("react-dom.development.js", "react-dom.production.min.js")

# 2. Add Global Error Handling
error_handler = """
<script>
  window.onerror = function(msg, url, line, col, error) {
    var div = document.getElementById('root');
    if (div) {
      div.innerHTML = '<div style="color:#ef4444; padding:40px; background:#0b0f13; border:1px solid #ef4444; margin:20px; border-radius:12px;">' +
        '<h2>Erro de Inicialização</h2>' +
        '<p style="color:#94a3b8">' + msg + '</p>' +
        '<p style="font-size:12px; color:#64748b">' + url + ' (linha ' + line + ')</p>' +
        '<button onclick="location.reload()" style="margin-top:20px; padding:10px 20px; background:#ef4444; color:white; border:none; border-radius:8px; cursor:pointer;">Recarregar Página</button>' +
        '</div>';
    }
    return false;
  };
</script>
"""
if "window.onerror" not in content:
    content = content.replace("</head>", error_handler + "</head>")

# 3. Fix potential Sidebar crash (ensure section is valid)
# In Sidebar component, if section is not one of the values, it might not render active state correctly but shouldn't crash.

# 4. Ensure App doesn't crash if dashboard is null
# Already checked data?.stats, but let's make it even safer.

# 5. Fix CSS - sometimes backdrop-filter causes issues on some browsers if not supported
content = content.replace("backdrop-filter: blur(12px);", "background: #0b0f13;")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
