# 📊 RD Manager IA v4

> Plataforma inteligente de gestão de marketing para agências — integração nativa com RD Station Marketing e CRM, análises por IA (Groq/LLaMA), Health Score de clientes e geração automática de conteúdo.

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green?logo=fastapi)
![License](https://img.shields.io/badge/license-MIT-lightgrey)
![Status](https://img.shields.io/badge/status-production--ready-brightgreen)

---

## ✨ Funcionalidades

- 🔐 **Autenticação JWT** com bcrypt e criação automática de admin
- 🔗 **Integração OAuth** com RD Station Marketing e CRM
- 🤖 **Análises por IA** (Groq — LLaMA 3.3 70B): estratégia, emails, fluxos, relatórios
- 📊 **Health Score** visual por cliente com alertas automáticos
- 📧 **Geração de emails** personalizados com IA
- ⚙️ **Geração de fluxos** de automação
- 📅 **Planejamento de campanhas** e calendário editorial
- 📈 **Relatórios executivos** e análises semanais
- 🌐 **Dashboard público** compartilhável por cliente
- 🔄 **Sincronização automática** de dados Marketing + CRM
- 🪝 **Webhooks** do RD Station

---

## 🏗️ Arquitetura

```
rd-manager/
├── app/
│   ├── main.py              # Entry point FastAPI
│   ├── auth_core.py         # JWT + bcrypt + admin
│   ├── database.py          # PostgreSQL / SQLite async
│   ├── ai_service.py        # Groq AI (LLaMA 3.3 70B)
│   ├── core/                # Settings, config
│   ├── routers/             # Endpoints REST
│   ├── services/            # Lógica de negócio
│   ├── templates/           # Frontend (React SPA)
│   ├── static/              # Assets estáticos
│   ├── utils/               # Helpers, notifier
│   └── tests/               # Testes automatizados
├── .env.example             # Variáveis de ambiente
├── render.yaml              # Deploy Render
├── requirements.txt
├── DEPLOYMENT_GUIDE.md
└── OAUTH_SETUP_GUIDE.md
```

---

## 🚀 Deploy Rápido (Render)

1. Fork ou clone este repositório
2. Crie um serviço no [Render](https://render.com) conectado ao GitHub
3. Configure as variáveis de ambiente (ver abaixo)
4. O `render.yaml` cuida do resto automaticamente

---

## ⚙️ Variáveis de Ambiente

| Variável | Descrição | Obrigatório |
|---|---|---|
| `DATABASE_URL` | PostgreSQL (ex: Neon.tech) | ✅ |
| `SECRET_KEY` | String aleatória 32+ chars (JWT) | ✅ |
| `ADMIN_PASSWORD` | Senha do usuário admin | ✅ |
| `GROQ_API_KEY` | API Key do [Groq](https://console.groq.com) | ✅ |
| `RD_CLIENT_ID` | Client ID da App RD Station | ✅ |
| `RD_CLIENT_SECRET` | Client Secret da App RD Station | ✅ |
| `RD_REDIRECT_URI` | URL de callback OAuth | ✅ |
| `RD_CRM_CLIENT_ID` | Client ID RD Station CRM | Opcional |
| `RD_CRM_CLIENT_SECRET` | Client Secret RD Station CRM | Opcional |
| `ALLOWED_ORIGINS` | CORS origens permitidas | Opcional |
| `TOKEN_EXPIRE_MINUTES` | Expiração JWT (padrão: 1440) | Opcional |
| `INVITE_CODE` | Código de convite para novos usuários | Opcional |

Copie `.env.example` para `.env` e preencha os valores.

---

## 🔧 Desenvolvimento Local

```bash
# Clone o repositório
git clone https://github.com/alexeller11/rd-manager.git
cd rd-manager

# Crie o ambiente virtual
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Instale as dependências
pip install -r requirements.txt

# Configure as variáveis
cp .env.example .env
# edite o .env com suas credenciais

# Rode a aplicação
uvicorn app.main:app --reload --port 8000
```

Acesse: `http://localhost:8000`

---

## 🧪 Testes

```bash
pytest app/tests/ -v
```

---

## 📚 Documentação Adicional

- [📖 Guia de Deploy Completo](DEPLOYMENT_GUIDE.md)
- [🔐 Configuração OAuth RD Station](OAUTH_SETUP_GUIDE.md)
- [✅ Checklist de Finalização](FINALIZATION_CHECKLIST.md)

---

## 🔗 Endpoints Principais

| Método | Rota | Descrição |
|---|---|---|
| GET | `/health` | Health check da aplicação |
| POST | `/api/auth/login` | Login JWT |
| GET | `/api/clients` | Listar clientes |
| POST | `/api/clients` | Criar cliente |
| GET | `/api/agency/dashboard` | Dashboard da agência |
| POST | `/api/rdsync/{client_id}` | Sincronizar dados RD |
| GET | `/oauth/callback` | Callback OAuth RD Station |
| POST | `/api/executive-report/{id}` | Gerar relatório executivo |

Documentação interativa: `https://seu-dominio.com/docs`

---

## 🔐 Segurança

- Senhas com bcrypt
- Tokens JWT com expiração configurável
- CORS dinâmico por variável de ambiente
- Validação de entrada com Pydantic
- HTTPS obrigatório em produção

---

## 📄 Licença

MIT — use livremente, mas dê os créditos. 🙂

---

**Desenvolvido para agências de marketing que querem automatizar e escalar operações com IA.**
