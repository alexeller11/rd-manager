import os

path = "app/templates/index.html"

html_content = """<!DOCTYPE html>
<html lang="pt-br">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>RD Manager IA - Performance</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">

  <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
  <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
  <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>

  <style>
    :root {
      --bg: #030708;
      --panel: #0b0f13;
      --panel-2: #12181f;
      --line: #1e2933;
      --text: #f8fafc;
      --muted: #94a3b8;
      --green: #10b981;
      --green-soft: rgba(16, 185, 129, 0.1);
      --yellow: #f59e0b;
      --yellow-soft: rgba(245, 158, 11, 0.1);
      --red: #ef4444;
      --red-soft: rgba(239, 68, 68, 0.1);
      --blue: #3b82f6;
      --blue-soft: rgba(59, 130, 246, 0.1);
      --accent: #10b981;
      --shadow: 0 10px 40px -10px rgba(0,0,0,0.5);
      --radius: 12px;
    }

    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: 'Inter', sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
    }

    #root:empty {
      display: flex;
      align-items: center;
      justify-content: center;
      height: 100vh;
    }
    #root:empty::after {
      content: 'Iniciando sistema...';
      color: var(--muted);
      font-size: 14px;
    }

    .app { display: flex; min-height: 100vh; }
    .sidebar {
      width: 280px; background: #0b0f13; border-right: 1px solid var(--line);
      padding: 32px 20px; display: flex; flex-direction: column;
      position: sticky; top: 0; height: 100vh;
    }
    .main { flex: 1; padding: 40px; max-width: 1200px; margin: 0 auto; width: 100%; }

    .hero {
      background: linear-gradient(135deg, var(--panel) 0%, #080b0f 100%);
      border: 1px solid var(--line); border-radius: 24px; padding: 40px; margin-bottom: 32px;
    }
    .hero h1 { margin: 0 0 12px; font-size: 38px; font-weight: 800; letter-spacing: -0.05em; }
    .hero p { margin: 0; color: var(--muted); line-height: 1.6; font-size: 16px; }

    .card {
      background: var(--panel); padding: 24px; border-radius: var(--radius);
      margin-bottom: 24px; border: 1px solid var(--line);
    }

    .btn {
      background: var(--accent); border: none; padding: 10px 18px; border-radius: 8px;
      color: #000; font-weight: 600; cursor: pointer; font-size: 14px;
      display: inline-flex; align-items: center; justify-content: center;
      transition: all 0.2s;
    }
    .btn:hover { transform: translateY(-1px); filter: brightness(1.1); }
    .btn:disabled { opacity: 0.5; cursor: not-allowed; }
    .btn.secondary { background: var(--panel-2); color: var(--text); border: 1px solid var(--line); }
    .btn.blue { background: var(--blue); color: #fff; }

    .kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 32px; }
    .kpi-card { background: var(--panel); padding: 24px; border-radius: var(--radius); border: 1px solid var(--line); }
    .kpi-label { color: var(--muted); font-size: 12px; font-weight: 600; margin-bottom: 8px; text-transform: uppercase; }
    .kpi-value { font-size: 32px; font-weight: 700; }

    .badge { padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: 700; text-transform: uppercase; }
    .badge.green { background: var(--green-soft); color: #34d399; }
    .badge.blue { background: var(--blue-soft); color: #60a5fa; }
    .badge.red { background: var(--red-soft); color: #f87171; }
    .badge.yellow { background: var(--yellow-soft); color: #fbbf24; }

    .sidebar button {
      width: 100%; padding: 10px 14px; background: transparent; border: none;
      color: var(--muted); text-align: left; cursor: pointer; border-radius: 10px;
      font-size: 14px; font-weight: 500; margin-bottom: 4px;
    }
    .sidebar button:hover { background: rgba(255,255,255,0.05); color: var(--text); }
    .sidebar button.active { background: var(--green-soft); color: var(--accent); font-weight: 600; }

    .nav-title { color: var(--muted); font-size: 11px; font-weight: 700; text-transform: uppercase; margin: 24px 0 12px 12px; opacity: 0.6; }

    input, textarea, select {
      display: block; width: 100%; max-width: 400px; padding: 12px; margin-bottom: 16px;
      background: #080b0f; border: 1px solid var(--line); border-radius: 8px; color: white;
    }

    .error-box { background: var(--red-soft); border: 1px solid var(--red); padding: 16px; border-radius: 8px; color: #fca5a5; margin-bottom: 20px; }

    @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
    .animate-in { animation: fadeIn 0.4s ease forwards; }

    @media (max-width: 768px) {
      .app { flex-direction: column; }
      .sidebar { width: 100%; height: auto; position: relative; }
    }
  </style>
</head>
<body>
  <div id="root"></div>

  <script type="text/babel">
    const API = "";

    const getToken = () => localStorage.getItem("rd_manager_token");
    const saveSession = (data) => {
      if (data?.access_token) localStorage.setItem("rd_manager_token", data.access_token);
      if (data?.username) localStorage.setItem("rd_manager_username", data.username);
    };
    const clearSession = () => {
      localStorage.removeItem("rd_manager_token");
      localStorage.removeItem("rd_manager_username");
    };

    async function api(url, options = {}) {
      const token = getToken();
      const headers = {
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(options.headers || {})
      };
      const res = await fetch(API + url, { ...options, headers });
      const text = await res.text();
      if (!res.ok) {
        if (res.status === 401) clearSession();
        throw new Error(text || "Erro no servidor");
      }
      try { return text ? JSON.parse(text) : null; } catch { return text; }
    }

    function Sidebar({ section, setSection, logout }) {
      return (
        <div className="sidebar">
          <div style={{ marginBottom: 40 }}>
            <h2 style={{ margin: 0, fontSize: 20, fontWeight: 800 }}>RD Manager</h2>
            <p style={{ margin: 0, fontSize: 12, color: "var(--muted)" }}>Agência Performance IA</p>
          </div>
          <div className="nav-title">Operação</div>
          <button className={section === "dashboard" ? "active" : ""} onClick={() => setSection("dashboard")}>Dashboard</button>
          <button className={section === "clients" ? "active" : ""} onClick={() => setSection("clients")}>Clientes</button>

          <div className="nav-title">Módulos</div>
          <button className={section === "leads" ? "active" : ""} onClick={() => setSection("leads")}>Leads & CRM</button>

          <div className="nav-title">Sessão</div>
          <button onClick={logout}>Sair</button>
        </div>
      );
    }

    function LoginPage({ onLogin }) {
      const [username, setUsername] = React.useState("admin");
      const [password, setPassword] = React.useState("");
      const [loading, setLoading] = React.useState(false);
      const [error, setError] = React.useState("");

      const submit = async (e) => {
        e.preventDefault();
        setLoading(true); setError("");
        try {
          const body = new URLSearchParams({ username, password });
          const res = await fetch(API + "/api/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: body.toString()
          });
          const data = await res.json();
          if (!res.ok) throw new Error(data.detail || "Falha no login");
          saveSession(data);
          onLogin();
        } catch (err) { setError(err.message); }
        finally { setLoading(false); }
      };

      return (
        <div className="main" style={{ maxWidth: 400, margin: "100px auto" }}>
          <div className="card">
            <h2 style={{ marginTop: 0 }}>Login</h2>
            {error && <div className="error-box">{error}</div>}
            <form onSubmit={submit}>
              <input value={username} onChange={e => setUsername(e.target.value)} placeholder="Usuário" />
              <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Senha" />
              <button className="btn" style={{ width: "100%" }} disabled={loading}>{loading ? "Acessando..." : "Entrar"}</button>
            </form>
          </div>
        </div>
      );
    }

    function Dashboard({ data, reload }) {
      const stats = {
        total_clients: data?.stats?.total_clients || 0,
        active_tokens: data?.stats?.active_tokens || 0,
        total_leads: data?.stats?.total_leads || 0,
        avg_score: data?.stats?.avg_score || 0
      };

      return (
        <div className="animate-in">
          <div className="hero">
            <h1>Performance Global</h1>
            <p>Visão estratégica de todos os clientes monitorados.</p>
          </div>
          <div className="kpi-grid">
            <div className="kpi-card">
              <div className="kpi-label">Clientes</div>
              <div className="kpi-value">{stats.total_clients}</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">Base Total</div>
              <div className="kpi-value">{stats.total_leads.toLocaleString()}</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">Score Médio</div>
              <div className="kpi-value">{stats.avg_score}%</div>
            </div>
          </div>
          <button className="btn" onClick={reload}>🔄 Atualizar Dados</button>
        </div>
      );
    }

    function Clients({ reload }) {
      const [clients, setClients] = React.useState([]);
      const load = async () => {
        const res = await api("/api/clients/");
        setClients(Array.isArray(res) ? res : []);
      };
      React.useEffect(() => { load(); }, []);

      return (
        <div className="animate-in">
          <div className="hero"><h1>Clientes</h1><p>Gerenciamento de conexões e sincronização.</p></div>
          <div className="card">
            <h3>Lista de Clientes</h3>
            {clients.map(c => (
              <div key={c.id} style={{ padding: "12px 0", borderBottom: "1px solid var(--line)" }}>
                <strong>{c.name}</strong> - <span className={c.rd_connected ? "badge green" : "badge red"}>{c.rd_connected ? "Conectado" : "Offline"}</span>
              </div>
            ))}
          </div>
        </div>
      );
    }

    function App() {
      const [authed, setAuthed] = React.useState(!!getToken());
      const [section, setSection] = React.useState("dashboard");
      const [data, setData] = React.useState(null);

      const loadData = async () => {
        try {
          const res = await api("/api/agency/overview");
          setData(res);
        } catch (e) { console.error(e); }
      };

      React.useEffect(() => { if (authed) loadData(); }, [authed]);

      if (!authed) return <LoginPage onLogin={() => setAuthed(true)} />;

      return (
        <div className="app">
          <Sidebar section={section} setSection={setSection} logout={() => { clearSession(); setAuthed(false); }} />
          <div className="main">
            {section === "dashboard" && <Dashboard data={data} reload={loadData} />}
            {section === "clients" && <Clients reload={loadData} />}
            {section !== "dashboard" && section !== "clients" && (
                <div className="card"><h3>Em desenvolvimento</h3><p>Módulo {section} em breve.</p></div>
            )}
          </div>
        </div>
      );
    }

    const root = ReactDOM.createRoot(document.getElementById("root"));
    root.render(<App />);
  </script>
</body>
</html>
"""

with open(path, "w", encoding="utf-8") as f:
    f.write(html_content)
