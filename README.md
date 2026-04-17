# RD Manager IA

> Plataforma de gestão inteligente para agências que operam o RD Station Marketing. Integra IA (OpenRouter/GPT) para análise de leads, geração de fluxos, auditoria de saúde e relatórios executivos automáticos.

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110-green?logo=fastapi)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)
![Deploy](https://img.shields.io/badge/Deploy-Render-purple?logo=render)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## ✨ Funcionalidades

| Módulo | Descrição |
|--------|-----------|
| **Dashboard** | KPIs consolidados: clientes, tokens ativos, leads monitorados, score médio |
| **Clientes** | Cadastro, conexão OAuth RD Station e sincronização completa |
| **Carteira Inteligente** | Classificação automática por risco, expansão e manutenção |
| **Landing Pages** | Análise SEO + GEO com IA a partir da URL pública |
| **Leads** | Filtros por status, fonte e score; análise de base com IA |
| **Segmentações** | Listagem, filtros e análise estratégica com IA |
| **Workflows** | Mapa de fluxos existentes + sugestão e geração de emails por etapa |
| **Campanhas** | Relatório automático de performance com IA |
| **Flow Studio IA** | Geração de fluxos completos e emails prontos para o RD Station |
| **Auditoria de Saúde** | Diagnóstico completo da conta RD do cliente |
| **Prospecção** | Diagnóstico comercial e proposta para novas contas |
| **Relatório Executivo** | Relatório de agência com score, risco e oportunidades |
| **Alertas** | Monitoramento de anomalias e notificações de risco |

---

## 🏗️ Arquitetura

```
rd-manager/
├── app/
│   ├── main.py                  # Entry point FastAPI
│   ├── database.py              # Conexão Neon (PostgreSQL)
│   ├── models.py                # Modelos SQLAlchemy
│   ├── templates/
│   │   └── index.html           # Frontend React (SPA)
│   ├── static/
│   │   └── favicon.svg
│   └── routers/
│       ├── auth.py              # JWT login/logout
│       ├── clients.py           # CRUD de clientes
│       ├── rd_oauth.py          # OAuth RD Station
│       ├── rd_sync.py           # Sincronização de dados RD
│       ├── rd_modules.py        # Módulos: LP, leads, workflows...
│       ├── flows_advanced.py    # Flow Studio IA
│       ├── landing_pages.py     # Análise SEO/GEO de LPs
│       ├── leads.py             # Análise e segmentação de leads
│       ├── prospect.py          # Prospecção inteligente
│       ├── report.py            # Relatório executivo
│       ├── alerts.py            # Sistema de alertas
│       └── health_audit.py      # Auditoria de saúde
├── .env.example                 # Variáveis de ambiente necessárias
├── render.yaml                  # Deploy Render (web + cron)
├── requirements.txt
├── build.sh
└── DEPLOYMENT_GUIDE.md
```

---

## 🚀 Deploy Rápido (Render)

### 1. Pré-requisitos

- Conta no [Render](https://render.com)
- Banco de dados PostgreSQL no [Neon](https://neon.tech) (free tier ok)
- App criado no [RD Station](https://appstore.rdstation.com/pt-BR/publisher) com OAuth configurado
- Chave de API no [OpenRouter](https://openrouter.ai)

### 2. Variáveis de ambiente

Copie `.env.example` e configure no Render:

```bash
DATABASE_URL=postgresql://user:pass@host/dbname?sslmode=require
SECRET_KEY=sua-chave-secreta-forte
ADMIN_PASSWORD=senha-do-admin

RD_CLIENT_ID=seu-client-id-rd-station
RD_CLIENT_SECRET=seu-client-secret-rd-station
RD_REDIRECT_URI=https://seu-app.onrender.com/oauth/callback

OPENROUTER_API_KEY=sk-or-...
APP_URL=https://seu-app.onrender.com
```

### 3. Deploy via render.yaml

```bash
# No painel do Render: New > Blueprint > conectar este repositório
# O render.yaml configura automaticamente o web service e o cron job
```

Ou manualmente:
- **Build Command:** `bash build.sh`
- **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

---

## 💻 Rodar localmente

```bash
# 1. Clonar
git clone https://github.com/alexeller11/rd-manager.git
cd rd-manager

# 2. Ambiente virtual
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Configurar variáveis
cp .env.example .env
# edite o .env com suas credenciais

# 5. Iniciar
uvicorn app.main:app --reload --port 8000
```

Acesse: `http://localhost:8000`  
Login padrão: `admin` / senha definida em `ADMIN_PASSWORD`

---

## 🔐 OAuth RD Station

Veja o guia completo em [`OAUTH_SETUP_GUIDE.md`](./OAUTH_SETUP_GUIDE.md).

Fluxo resumido:
1. Cadastre o cliente no sistema
2. Clique em **Conectar RD** na listagem de clientes
3. Autorize o acesso na tela do RD Station
4. O token é salvo automaticamente e o cliente fica com status `RD conectada`
5. Execute **Sincronizar** para importar os dados

---

## 🤖 IA — Modelos Suportados

O sistema usa **OpenRouter** como gateway. Modelos recomendados (configurar em `flows_advanced.py`):

| Uso | Modelo sugerido |
|-----|----------------|
| Geração de fluxos e emails | `openai/gpt-4o-mini` |
| Análise de leads e relatórios | `google/gemini-flash-1.5` |
| Análise SEO de landing pages | `anthropic/claude-3-haiku` |

---

## 📋 Endpoints principais

```
POST /api/auth/login                         # Login JWT
GET  /api/clients/                           # Listar clientes
POST /api/clients/                           # Criar cliente
POST /api/rdsync/run/{client_id}             # Sincronizar cliente
GET  /api/rd-modules/client/{id}/overview    # Overview dos módulos
GET  /api/rd-modules/client/{id}/{module}    # Dados do módulo
POST /api/flows-advanced/generate-flow       # Gerar fluxo com IA
POST /api/flows-advanced/generate-email      # Gerar email com IA
POST /api/landing-pages/analyze              # Análise SEO de LP
POST /api/leads/analyze-base                 # Análise de base de leads
POST /api/prospect/analyze-business          # Diagnóstico de prospecção
GET  /api/report/{client_id}                 # Relatório executivo
GET  /api/alerts/{client_id}                 # Alertas do cliente
GET  /api/health-audit/{client_id}           # Auditoria de saúde
```

---

## 🛠️ Stack Tecnológica

- **Backend:** Python 3.11, FastAPI, SQLAlchemy, Alembic
- **Frontend:** React 18 (via CDN, sem build step), Babel standalone
- **Banco de dados:** PostgreSQL (Neon)
- **IA:** OpenRouter (GPT-4o-mini, Gemini, Claude)
- **Auth:** JWT (python-jose)
- **Deploy:** Render (Web Service + Cron Job)
- **Integração:** RD Station Marketing API v2

---

## 📚 Documentação adicional

- [`DEPLOYMENT_GUIDE.md`](./DEPLOYMENT_GUIDE.md) — Guia completo de deploy
- [`OAUTH_SETUP_GUIDE.md`](./OAUTH_SETUP_GUIDE.md) — Configuração OAuth RD Station
- [`CHANGELOG.md`](./CHANGELOG.md) — Histórico de versões
- [`CONTRIBUTING.md`](./CONTRIBUTING.md) — Como contribuir

---

## 📄 Licença

MIT © 2026 — Desenvolvido para uso interno de agências de marketing digital.
