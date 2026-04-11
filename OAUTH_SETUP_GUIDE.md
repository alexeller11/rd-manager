# Guia de Configuração — OAuth RD Station Marketing

## 🔐 Autenticação via RD Station

O **RD Manager IA v4** suporta autenticação de clientes via **OAuth 2.0 do RD Station Marketing**. Este guia explica como configurar tudo passo-a-passo.

---

## 📋 Pré-requisitos

1. Conta no [RD Station](https://www.rdstation.com)
2. Acesso ao painel administrativo da sua conta RD Station
3. Projeto já deployado no Railway (ou rodando localmente)
4. URL pública da aplicação (ex: `https://seu-dominio.up.railway.app`)

---

## ✅ Passo 1: Criar Aplicação no RD Station

### 1.1 Acessar o Painel de Integrações

1. Acesse [RD Station](https://www.rdstation.com)
2. Faça login com sua conta
3. Vá para **Configurações** → **Integrações** → **Aplicações**
4. Clique em **+ Nova Aplicação**

### 1.2 Preencher Dados da Aplicação

| Campo | Valor |
|-------|-------|
| **Nome da Aplicação** | RD Manager IA |
| **Descrição** | Plataforma de gerenciamento de marketing com IA |
| **URL da Aplicação** | `https://seu-dominio.up.railway.app` |
| **Redirect URI** | `https://seu-dominio.up.railway.app/oauth/callback` |

### 1.3 Selecionar Permissões (Scopes)

Marque as seguintes permissões:

- ✅ **contacts:read** — Ler contatos
- ✅ **landing-pages:read** — Ler landing pages
- ✅ **emails:read** — Ler emails
- ✅ **segmentations:read** — Ler segmentações

### 1.4 Copiar Credenciais

Após criar a aplicação, você receberá:

- **Client ID** (ex: `1234567890`)
- **Client Secret** (ex: `abc123def456...`)

**Guarde essas credenciais com segurança!**

---

## 🚀 Passo 2: Configurar Variáveis no Railway

### 2.1 Acessar o Painel do Railway

1. Acesse [Railway.app](https://railway.app)
2. Selecione seu projeto **rd-manager**
3. Vá para **Settings** → **Variables**

### 2.2 Adicionar Variáveis de Ambiente

Adicione as seguintes variáveis:

| Variável | Valor | Exemplo |
|----------|-------|---------|
| `RD_CLIENT_ID` | Client ID do passo 1.4 | `1234567890` |
| `RD_CLIENT_SECRET` | Client Secret do passo 1.4 | `abc123def456...` |
| `RD_REDIRECT_URI` | URL de callback (opcional) | `https://seu-dominio.up.railway.app/oauth/callback` |

**Nota**: Se não definir `RD_REDIRECT_URI`, a aplicação detectará automaticamente usando `RAILWAY_STATIC_URL`.

### 2.3 Deploy

Após adicionar as variáveis, o Railway fará um **redeploy automático**. Aguarde até que o status fique **Active**.

---

## 🔗 Passo 3: Usar OAuth na Aplicação

### 3.1 Criar um Cliente

1. Acesse `https://seu-dominio.up.railway.app`
2. Faça login com credenciais admin
3. Vá para **Clientes** → **+ Novo Cliente**
4. Preencha os dados do cliente (nome, segmento, etc.)
5. Clique em **Salvar**

### 3.2 Conectar via OAuth

1. Edite o cliente que acabou de criar
2. Clique no botão **🔗 Conectar via OAuth RD Marketing**
3. Você será redirecionado para o RD Station
4. Clique em **Autorizar** para conceder acesso
5. Você será redirecionado de volta para a aplicação
6. Mensagem de sucesso: *"Conectado com sucesso!"*

### 3.3 Verificar Conexão

Após conectar:

1. Vá para **Sincronização** → Selecione o cliente
2. Clique em **Sincronizar RD Marketing**
3. A aplicação buscará dados de contatos, landing pages, emails e segmentações
4. Os dados aparecerão no **Dashboard** e **Health Score**

---

## 🧪 Passo 4: Testar Localmente (Desenvolvimento)

Se estiver desenvolvendo localmente, configure assim:

### 4.1 Variáveis de Ambiente Local

Crie um arquivo `.env` na raiz do projeto:

```bash
DATABASE_URL=sqlite:///./rd_manager.db
SECRET_KEY=sua_chave_super_secreta_aqui_minimo_32_caracteres
ADMIN_PASSWORD=admin123
GROQ_API_KEY=sua_chave_groq_aqui
RD_CLIENT_ID=seu_client_id_aqui
RD_CLIENT_SECRET=seu_client_secret_aqui
RD_REDIRECT_URI=http://localhost:8000/oauth/callback
```

### 4.2 Executar Localmente

```bash
cd rd-manager
export $(cat .env | xargs)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4.3 Acessar

- **Aplicação**: `http://localhost:8000`
- **Login**: `admin` / `admin123`
- **OAuth Callback**: `http://localhost:8000/oauth/callback`

---

## 🔄 Fluxo Completo de OAuth

```
┌─────────────────────────────────────────────────────────────┐
│                    RD Manager IA v4                         │
│                                                             │
│  1. Usuário clica "🔗 Conectar via OAuth RD Marketing"     │
│                          ↓                                  │
│  2. Redireciona para RD Station (https://api.rd.services)  │
│                          ↓                                  │
│  3. Usuário autoriza acesso (concede permissões)           │
│                          ↓                                  │
│  4. RD Station redireciona com código para:                │
│     https://seu-dominio/oauth/callback?code=xxx&state=yyy │
│                          ↓                                  │
│  5. RD Manager troca código por access_token               │
│                          ↓                                  │
│  6. Token salvo no banco de dados                          │
│                          ↓                                  │
│  7. Mensagem: "Conectado com sucesso!"                     │
│                          ↓                                  │
│  8. Token usado para sincronizar dados do RD Station       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Troubleshooting

### Erro: "RD_CLIENT_ID não configurado"

**Causa**: Variáveis de ambiente não definidas no Railway  
**Solução**:
1. Railway → Settings → Variables
2. Adicione `RD_CLIENT_ID` e `RD_CLIENT_SECRET`
3. Aguarde redeploy

### Erro: "Redirect URI não corresponde"

**Causa**: URL de callback configurada no RD Station não bate com a da aplicação  
**Solução**:
1. RD Station → Aplicações → Editar
2. Verifique se o **Redirect URI** é exatamente: `https://seu-dominio.up.railway.app/oauth/callback`
3. Salve e tente novamente

### Erro: "Code não recebido"

**Causa**: Falha na comunicação entre RD Station e sua aplicação  
**Solução**:
1. Verifique se a aplicação está rodando: `GET https://seu-dominio/health`
2. Confirme que o domínio está acessível publicamente
3. Verifique logs no Railway: `Railway → Logs`

### Token expirou

**Causa**: Access token do RD Station expirou  
**Solução**:
1. Edite o cliente
2. Clique novamente em **🔗 Conectar via OAuth RD Marketing**
3. Autorize novamente
4. Novo token será salvo automaticamente

---

## 📊 Endpoints Relacionados a OAuth

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/oauth/authorize/{client_id}` | GET | Inicia fluxo OAuth |
| `/oauth/callback` | GET | Recebe código e troca por token |
| `/api/clients/{id}` | PUT | Atualiza cliente (preserva tokens) |
| `/api/rd/diagnose/{client_id}` | GET | Verifica saúde do token |
| `/api/rd/sync/{client_id}` | GET | Sincroniza dados com token válido |

---

## 🔐 Segurança

### Boas Práticas

✅ **Tokens salvos com segurança**: Access tokens e refresh tokens são armazenados no banco PostgreSQL  
✅ **Refresh automático**: Tokens são renovados automaticamente quando expiram  
✅ **HTTPS obrigatório**: OAuth funciona apenas com HTTPS em produção  
✅ **State parameter**: Proteção contra CSRF usando parâmetro `state`  

### O Que NÃO Fazer

❌ Não compartilhe `RD_CLIENT_SECRET` publicamente  
❌ Não exponha tokens em logs ou URLs  
❌ Não use `http://` em produção (apenas `https://`)  

---

## 📞 Suporte

Se encontrar problemas:

1. **Verifique os logs**: Railway → Logs
2. **Ative debug mode**: Adicione `DEBUG_MODE=true` nas variáveis
3. **Acesse debug info**: `GET https://seu-dominio/api/debug/errors`
4. **Abra uma issue**: GitHub → Issues

---

## ✨ Próximos Passos

Após configurar OAuth com sucesso:

1. **Sincronize dados**: Clique em "Sincronizar RD Marketing"
2. **Visualize health score**: Vá para "Health Score"
3. **Execute análises**: Use "Análise Estratégica", "Email IA", etc.
4. **Compartilhe dashboard**: Copie URL pública do cliente

---

**Desenvolvido com ❤️ para agências de marketing**
