# RD Manager IA v4 — Guia de Deploy e Finalização

## Status do Projeto

O **RD Manager IA v4** é uma plataforma completa de gerenciamento de marketing para agências que integram com **RD Station Marketing** e **RD Station CRM**, com análises potenciadas por IA.

### Versão: 4.0.0
### Última atualização: 22 de março de 2026

---

## Correções Finais Aplicadas

### 1. **Protocolo HTTPS nas URLs de Redirecionamento (OAuth)**
   - **Arquivo**: `app/routers/oauth.py`
   - **Problema**: URLs de callback do OAuth não incluíam `https://` quando usando Railway
   - **Solução**: Construção dinâmica de `REDIRECT_URI` com `https://` para Railway
   - **Impacto**: Fluxo OAuth agora funciona corretamente em produção

### 2. **CORS com Suporte a Railway**
   - **Arquivo**: `app/main.py`
   - **Problema**: Variável `RAILWAY_STATIC_URL` não era prefixada com `https://`
   - **Solução**: Adicionar prefixo `https://` ao construir a lista de `ALLOWED_ORIGINS`
   - **Impacto**: Requisições cross-origin funcionam corretamente em produção

### 3. **Autenticação Robusta**
   - **Arquivo**: `app/auth_core.py`
   - **Recurso**: Uso de bcrypt para hash de senhas (seguro e compatível)
   - **Recurso**: Criação automática de usuário admin no primeiro boot
   - **Recurso**: Tokens JWT com expiração configurável (padrão: 24 horas)

---

## Variáveis de Ambiente Necessárias

Para deploy no **Railway** ou qualquer servidor em produção, configure as seguintes variáveis:

### Obrigatórias

| Variável | Descrição | Exemplo |
|----------|-----------|---------|
| `DATABASE_URL` | URL de conexão PostgreSQL (Neon.tech recomendado) | `postgresql://user:pass@host/db` |
| `SECRET_KEY` | Chave secreta para JWT (mínimo 32 caracteres) | `sua_chave_super_secreta_aqui` |
| `ADMIN_PASSWORD` | Senha do usuário admin criado automaticamente | `SenhaForte123!` |
| `GROQ_API_KEY` | Chave da API Groq para IA | `gsk_...` |
| `RD_CLIENT_ID` | ID da aplicação RD Station Marketing | `seu_client_id` |
| `RD_CLIENT_SECRET` | Secret da aplicação RD Station Marketing | `seu_client_secret` |

### Opcionais

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `RD_REDIRECT_URI` | URL de callback OAuth (auto-detectada se não definida) | `https://{RAILWAY_STATIC_URL}/oauth/callback` |
| `ALLOWED_ORIGINS` | Origens CORS permitidas (separadas por vírgula) | `https://{RAILWAY_STATIC_URL},http://localhost:3000,http://localhost:8000` |
| `TOKEN_EXPIRE_MINUTES` | Expiração do token JWT em minutos | `1440` (24 horas) |
| `DEBUG_MODE` | Ativa router `/api/debug` para troubleshooting | `false` |
| `ADMIN_USERNAME` | Nome de usuário do admin | `admin` |

---

## Arquitetura da Aplicação

### Stack Tecnológico

- **Backend**: FastAPI 0.115.0 + Uvicorn
- **Banco de Dados**: PostgreSQL (produção) / SQLite (desenvolvimento)
- **Autenticação**: JWT + bcrypt
- **IA**: Groq API (LLaMA 3.3 70B)
- **Frontend**: React 18 (vanilla, sem build step)
- **Integração**: RD Station Marketing + RD Station CRM

### Estrutura de Diretórios

```
rd-manager/
├── app/
│   ├── main.py                 # Entrypoint FastAPI
│   ├── auth_core.py            # Lógica de autenticação (JWT + bcrypt)
│   ├── database.py             # Camada de BD (PostgreSQL/SQLite)
│   ├── ai_service.py           # Integração com Groq
│   ├── routers/
│   │   ├── auth.py             # Endpoints de login/logout
│   │   ├── clients.py          # CRUD de clientes
│   │   ├── oauth.py            # Fluxo OAuth RD Station
│   │   ├── rd_station.py       # Sync com RD Marketing
│   │   ├── crm.py              # Sync com RD CRM
│   │   ├── analysis.py         # Análises estratégicas
│   │   ├── emails.py           # Geração de copy de email
│   │   ├── flows.py            # Geração de fluxos de automação
│   │   ├── intelligence.py     # IA avançada (semanal, A/B, calendário)
│   │   ├── reports.py          # Relatórios executivos
│   │   ├── campaign.py         # Planejamento de campanhas
│   │   ├── health.py           # Health Score
│   │   ├── scheduler.py        # Disparo manual de análises
│   │   └── debug.py            # Debug (apenas se DEBUG_MODE=true)
│   └── templates/
│       ├── index.html          # Dashboard principal (React)
│       └── public_dashboard.html # Dashboard público (vanilla JS)
├── requirements.txt            # Dependências Python
├── Dockerfile                  # Build para Railway
├── railway.json                # Configuração Railway
└── README.md                   # Documentação básica
```

---

## Endpoints Principais

### Autenticação
- `POST /api/auth/login` — Login com usuário/senha
- `GET /api/auth/me` — Retorna usuário autenticado
- `GET /api/auth/check` — Verifica se existem usuários
- `POST /api/auth/logout` — Logout (client-side)

### Clientes
- `GET /api/clients/` — Lista todos os clientes
- `POST /api/clients/` — Criar novo cliente
- `PUT /api/clients/{id}` — Atualizar cliente
- `DELETE /api/clients/{id}` — Deletar cliente
- `POST /api/clients/{id}/set-token` — Definir token RD fixo

### RD Station Marketing
- `GET /api/rd/sync/{client_id}` — Sincronizar dados de marketing
- `GET /api/rd/snapshot/{client_id}` — Retorna último snapshot
- `GET /api/rd/diagnose/{client_id}` — Diagnostica token
- `POST /api/rd/analyze` — Análise de marketing com IA

### RD Station CRM
- `GET /api/crm/sync/{client_id}` — Sincronizar dados de vendas
- `GET /api/crm/snapshot/{client_id}` — Retorna snapshot CRM
- `POST /api/crm/analyze` — Análise de pipeline com IA

### Análises com IA
- `POST /api/analysis/run` — Análise estratégica 360°
- `POST /api/emails/generate` — Gerar copy de email
- `POST /api/flows/generate` — Gerar fluxo de automação
- `POST /api/intel/weekly/run/{client_id}` — Análise semanal
- `POST /api/reports/generate` — Gerar relatório executivo
- `POST /api/campaign/plan` — Planejar campanha

### Health Score
- `GET /api/health/score/{client_id}` — Score de saúde do cliente
- `GET /api/health/all` — Score de todos os clientes
- `GET /api/health/alerts/{client_id}` — Alertas do cliente

### Dashboard Público
- `GET /dashboard/{client_id}` — Dashboard público (sem autenticação)
- `GET /api/intel/public/{client_id}` — Dados para dashboard público

### Health Check
- `GET /health` — Status da aplicação

---

## Fluxo de Uso Típico

### 1. **Setup Inicial**
   1. Fazer login com credenciais admin
   2. Acessar **Clientes** → **+ Novo Cliente**
   3. Preencher dados do cliente (nome, segmento, persona, etc.)

### 2. **Conectar RD Station**
   1. Editar cliente → **🔗 Conectar via OAuth RD Marketing**
   2. Autorizar acesso no RD Station
   3. Voltar ao app (token salvo automaticamente)

### 3. **Sincronizar Dados**
   1. Ir para **Sincronização**
   2. Selecionar cliente
   3. Clicar **Sincronizar RD Marketing**
   4. Aguardar conclusão

### 4. **Visualizar Análises**
   - **Dashboard**: Visão consolidada de todos os clientes
   - **Health Score**: Diagnóstico de saúde de marketing
   - **Análise Estratégica**: Diagnósticos 360°, SEO, CRO, Funil
   - **Email IA**: Gerar copy de email por tipo
   - **Fluxos**: Criar fluxos de automação
   - **Inteligência**: A/B tests, calendário editorial, análise de concorrência
   - **Relatórios**: Relatórios mensais, executivos, de campanha, ROI

### 5. **Dashboard Público**
   - Compartilhar URL: `https://seu-dominio.com/dashboard/{client_id}`
   - Exibe: Health Score, métricas, insights semanais
   - Sem autenticação necessária

---

## Deploy no Railway

### Pré-requisitos
1. Conta no [Railway.app](https://railway.app)
2. Repositório GitHub conectado
3. Banco de dados PostgreSQL (Neon.tech recomendado)
4. Chaves da API Groq e RD Station

### Passos

1. **Conectar repositório**
   - Railway → New Project → GitHub
   - Selecionar `alexeller11/rd-manager`

2. **Adicionar banco de dados**
   - Railway → Add Service → PostgreSQL
   - Copiar `DATABASE_URL` gerada

3. **Configurar variáveis de ambiente**
   - Railway → Variables
   - Adicionar todas as variáveis obrigatórias (veja tabela acima)

4. **Deploy automático**
   - Railway detecta `Dockerfile` e `railway.json`
   - Build e deploy automáticos a cada push

5. **Verificar saúde**
   - Acessar `https://seu-dominio.com/health`
   - Deve retornar `{"status": "ok", "version": "4.0.0"}`

---

## Troubleshooting

### Erro: "RD_CLIENT_ID não configurado"
**Causa**: Variáveis de ambiente não definidas  
**Solução**: Verificar Railway → Variables e adicionar `RD_CLIENT_ID` e `RD_CLIENT_SECRET`

### Erro: "Token inválido ou expirado"
**Causa**: Token JWT expirou ou foi corrompido  
**Solução**: Fazer login novamente

### Erro: "Falha ao conectar com RD Station"
**Causa**: Token RD inválido ou expirado  
**Solução**: 
1. Editar cliente
2. Clicar **🔗 Conectar via OAuth RD Marketing**
3. Autorizar novamente

### Erro: "Sem dados para sincronizar"
**Causa**: Cliente não tem token RD configurado  
**Solução**: Conectar via OAuth primeiro (veja "Fluxo de Uso")

### Ativar Debug Mode
**Para troubleshooting avançado**:
1. Railway → Variables
2. Adicionar `DEBUG_MODE=true`
3. Acessar `GET /api/debug/info` e `GET /api/debug/errors`

---

## Segurança

### Boas Práticas Implementadas
✅ Senhas hasheadas com bcrypt (4 rounds)  
✅ Tokens JWT com expiração  
✅ CORS configurável por origem  
✅ Validação de entrada com Pydantic  
✅ Logs de erro estruturados  
✅ Suporte a HTTPS obrigatório em produção  

### Recomendações Adicionais
- Usar `SECRET_KEY` com mínimo 32 caracteres aleatórios
- Rotacionar `ADMIN_PASSWORD` regularmente
- Monitorar logs em `/api/debug/errors` (se DEBUG_MODE=true)
- Fazer backup regular do banco PostgreSQL

---

## Próximas Melhorias Sugeridas

1. **Autenticação Social**: Integrar login com Google/GitHub
2. **Webhooks**: Receber eventos do RD Station em tempo real
3. **Agendamento Real**: Implementar cron jobs para análises automáticas
4. **Exportação de Relatórios**: PDF/Excel dos relatórios gerados
5. **Integração com Slack**: Notificações de alertas
6. **Multi-tenancy**: Suporte a múltiplas agências

---

## Contato e Suporte

Para dúvidas ou problemas:
1. Verificar logs: `GET /api/debug/errors` (com DEBUG_MODE=true)
2. Consultar documentação: README.md
3. Abrir issue no GitHub: https://github.com/alexeller11/rd-manager/issues

---

## Licença

Propriedade privada. Todos os direitos reservados.

---

**Desenvolvido com ❤️ para agências de marketing**
