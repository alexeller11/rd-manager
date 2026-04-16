#!/usr/bin/env python3
"""
Script para aplicar correções de design profissional e UX no rd-manager

Execute: python apply_design_fixes.py
"""

import re

INDEX_PATH = "app/templates/index.html"

def apply_fixes():
    with open(INDEX_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("Aplicando correções de design profissional...")
    
    # 1. Atualizar cores CSS para design profissional de agência
    content = content.replace(
        "--bg: #030708",
        "--bg: #0f172a"  # slate-900 mais profissional
    )
    content = content.replace(
        "--panel: #0b0f13",
        "--panel: #1e293b"  # slate-800
    )
    content = content.replace(
        "--panel-2: #12181f",
        "--panel-2: #334155"  # slate-700
    )
    content = content.replace(
        "--line: #1e2933",
        "--line: #475569"  # slate-600
    )
    content = content.replace(
        "--accent: #10b981",
        "--accent: #6366f1"  # indigo-500 profissional
    )
    content = content.replace(
        "rgba(16, 185, 129, 0.1)",
        "rgba(99, 102, 241, 0.1)"
    )
    
    # 2. Adicionar labels no Flow Studio (linha ~1550)
    # Buscar por flowDays e emailCount e adicionar labels
    flow_studio_fix = '''
            <div className="row" style={{gap:15, marginBottom:15}}>
              <div style={{flex:1}}>
                <label className="muted" style={{fontSize:12, display:"block", marginBottom:4}}>Dias do Fluxo</label>
                <input type="number" style={{width:"100%"}} value={flowDays} onChange={e => setFlowDays(e.target.value)} placeholder="14" />
              </div>
              <div style={{flex:1}}>
                <label className="muted" style={{fontSize:12, display:"block", marginBottom:4}}>Quantidade de Emails</label>
                <input type="number" style={{width:"100%"}} value={emailCount} onChange={e => setEmailCount(e.target.value)} placeholder="5" />
              </div>
            </div>'''
    
    # Pattern antigo sem labels
    old_pattern = r'<input type="number" style={{width:100}} value={flowDays}.*?<input type="number" style={{width:100}} value={emailCount}.*?/>'
    
    # Comentar isso por enquanto para não quebrar se o pattern não bater exato
    # content = re.sub(old_pattern, flow_studio_fix, content, flags=re.DOTALL)
    
    print("✅ Cores atualizadas para design profissional")
    print("⚠️  Labels do Flow Studio: aplicar manualmente se necessário")
    print("")
    print("Próximos passos manuais rápidos:")
    print("")
    print("1. No Flow Studio (linha ~1512), adicionar no início:")
    print("   const [clients, setClients] = React.useState([]);")
    print("   const [clientId, setClientId] = React.useState(\"\");")
    print("")
    print("   React.useEffect(() => {")
    print("     api(\"/api/clients/\").then(res => {")
    print("       const list = Array.isArray(res) ? res : [];")
    print("       setClients(list);")
    print("       if (list.length > 0) setClientId(String(list[0].id));")
    print("     }).catch(() => {});")
    print("   }, []);")
    print("")
    print("2. Adicionar seletor de cliente antes dos campos:")
    print("   <select value={clientId} onChange={e => setClientId(e.target.value)}>")
    print("     <option value=\"\">Geral (sem cliente)</option>")
    print("     {clients.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}")
    print("   </select>")
    
    with open(INDEX_PATH, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("")
    print("✅ Correções aplicadas em", INDEX_PATH)
    print("")
    print("Execute 'git diff' para ver as mudanças.")
    print("Depois: git add . && git commit -m 'feat: design profissional de agência' && git push")

if __name__ == "__main__":
    apply_fixes()
