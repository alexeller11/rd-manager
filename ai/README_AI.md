# 🤖 RAG + Memory AI Agent — RD Station Manager

Integração com o projeto [awesome-llm-apps](https://github.com/Shubhamsaboo/awesome-llm-apps) adaptada para análise inteligente de leads e funil do RD Station usando RAG com memória de conversação.

## O que faz

- **`index_leads(leads)`** — Indexa leads do RD Station gerando embeddings semânticos para busca inteligente
- **`query(question)`** — Responde perguntas sobre leads com memória de contexto (lembra do histórico da conversa)
- **`generate_pipeline_report()`** — Gera relatório completo do funil com leads quentes, distribuição por estágio e ações recomendadas
- **`suggest_next_actions(lead_email)`** — Sugere próximas ações personalizadas para um lead específico
- **`clear_memory()`** — Limpa o histórico de conversações mantendo o índice de leads

## Configuração

Adicione no `.env`:
```
OPENAI_API_KEY=sk-...
```

Dependencias já disponíveis no projeto (openai está no requirements.txt).

## Uso

```python
import os
from ai.ai_rag_agent import RDStationRagAgent

agent = RDStationRagAgent(api_key=os.environ["OPENAI_API_KEY"])

# Indexar leads vindos do RD Station
agent.index_leads(leads)

# Conversa com memória sobre o funil
print(agent.query("Quais leads estão prontos para abordagem de vendas?"))
print(agent.query("E quais têm maior score?"))  # lembra do contexto anterior

# Relatório completo do funil
relatorio = agent.generate_pipeline_report()

# Ações para um lead específico
acoes = agent.suggest_next_actions("contato@empresa.com.br")
```

## Estrutura dos leads esperada

```python
leads = [
    {
        "nome": "João Silva",
        "email": "joao@empresa.com",
        "empresa": "Empresa XYZ",
        "estagio_funil": "Oportunidade",
        "score": 87,
        "origem": "Google Ads",
        "ultima_conversao": "Solicitação de demo",
        "tags": ["quente", "B2B"]
    }
]
```

## Referência

Inspirado no **AI Travel Agent with Memory** e **RAG-as-a-Service** do repositório [Shubhamsaboo/awesome-llm-apps](https://github.com/Shubhamsaboo/awesome-llm-apps) — #1 GitHub Trending.
