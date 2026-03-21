# RD Manager IA — v4.0

Plataforma de gerenciamento de marketing para agências usando RD Station, com análises por IA.

---

## Secrets obrigatórios no HuggingFace Space

Vá em **Settings → Variables and secrets** e adicione:

| Secret | Descrição | Obrigatório |
|--------|-----------|-------------|
| `GROQ_API_KEY` | Chave da API Groq (llama-3.3-70b) | ✅ Sim |
| `DATABASE_URL` | URL do PostgreSQL externo | ✅ Sim (senão usa SQLite volátil) |
| `SECRET_KEY` | Chave aleatória para JWT (ex: `openssl rand -hex 32`) | ✅ Sim |
| `ADMIN_USERNAME` | Usuário admin inicial | Opcional (default: `admin`) |
| `ADMIN_PASSWORD` | Senha admin inicial | ✅ Sim (troque o default!) |
| `RD_CLIENT_ID` | Client ID do app no RD Station | Para OAuth |
| `RD_CLIENT_SECRET` | Client Secret do app no RD Station | Para OAuth |
| `RD_REDIRECT_URI` | URL de callback OAuth | Para OAuth |
| `ALLOWED_ORIGINS` | Origens CORS separadas por vírgula | Opcional |

---

## Banco de dados recomendado (gratuito)

### Opção 1 — Neon (PostgreSQL serverless, grátis)
1. Crie conta em https://neon.tech
2. Crie um banco → copie a connection string
3. Cole em `DATABASE_URL` nas secrets do HuggingFace

### Opção 2 — Supabase (grátis)
1. Crie conta em https://supabase.com
2. Settings → Database → Connection string → URI mode
3. Cole em `DATABASE_URL`

O formato é: `postgresql://user:password@host/dbname`

---

## Como gerar SECRET_KEY seguro

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Login inicial

Após o primeiro deploy, acesse o app e faça login com:
- Usuário: `admin` (ou o valor de `ADMIN_USERNAME`)
- Senha: `admin123` (ou o valor de `ADMIN_PASSWORD`)

**Troque a senha após o primeiro acesso.**

---

## Variáveis de ambiente opcionais

| Variável | Default | Descrição |
|----------|---------|-----------|
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Modelo Groq a usar |
| `TOKEN_EXPIRE_MINUTES` | `1440` (24h) | Expiração do JWT |
| `DEBUG_MODE` | `false` | Liga o endpoint `/api/debug` |
| `ALLOWED_ORIGINS` | URLs do HF Space | Origens CORS permitidas |

---

## Estrutura do projeto

```
app/
├── main.py           # App FastAPI + routers
├── database.py       # Camada DB unificada (SQLite/PostgreSQL)
├── auth_core.py      # JWT + bcrypt + tokens RD Station
├── ai_service.py     # Groq API + prompts + contexto
└── routers/
    ├── auth.py       # Login/logout/register
    ├── clients.py    # CRUD de clientes
    ├── analysis.py   # Análises de marketing (360°, SEO, CRO, funil)
    ├── emails.py     # Geração de emails e estratégias
    ├── rd_station.py # Sync com RD Station Marketing
    ├── crm.py        # Sync com RD Station CRM
    ├── flows.py      # Fluxos de automação com IA
    ├── health.py     # Health score e alertas
    ├── intelligence.py # Análise semanal, A/B, calendário, concorrência
    ├── reports.py    # Relatórios executivos
    ├── campaign.py   # Planejamento de campanhas
    ├── scheduler.py  # Trigger de análises em batch
    ├── oauth.py      # OAuth2 RD Station
    └── debug.py      # Debug (só com DEBUG_MODE=true)
```

---

## Problemas corrigidos nesta versão (v4.0 vs original)

1. **Autenticação real** — JWT com bcrypt, não mais usuário hardcoded
2. **Banco de dados persistente** — PostgreSQL externo via pool, não SQLite volátil
3. **Schema consistente** — `rd_account_id` presente em todas as queries
4. **CORS correto** — sem `*` + `credentials` ao mesmo tempo
5. **Cache de token RD** — não bate na API RD a cada request
6. **Bug do refresh token** — lógica de erro corrigida
7. **Debug protegido** — só carrega com `DEBUG_MODE=true`
8. **Análises persistidas** — `analyses` table populada ao rodar análise
9. **Pool de conexões PostgreSQL** — não abre/fecha conexão por query
10. **Prompts enriquecidos** — frameworks de marketingskills + SEO integrados
