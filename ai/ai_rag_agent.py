"""
RAG + Memory AI Agent — inspirado em Shubhamsaboo/awesome-llm-apps
Análise inteligente de leads e contatos do RD Station com busca semântica e memória

Uso:
    agent = RDStationRagAgent(api_key=os.environ['OPENAI_API_KEY'])
    agent.index_leads(leads)
    resposta = agent.query('Quais leads estão prontos para abordagem?')
"""

import os
import json
import math
from openai import OpenAI


class RDStationRagAgent:
    """
    Agente RAG com memória para análise de leads do RD Station.
    Indexa contatos/leads como embeddings e responde perguntas contextualizadas.
    """

    def __init__(self, api_key: str, model: str = "gpt-4o-mini", embed_model: str = "text-embedding-3-small"):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.embed_model = embed_model
        self.store: list[dict] = []  # {text, embedding, metadata}
        self.memory: list[dict] = []  # histórico de conversações

    def _embed(self, text: str) -> list[float]:
        res = self.client.embeddings.create(model=self.embed_model, input=text)
        return res.data[0].embedding

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x ** 2 for x in a))
        norm_b = math.sqrt(sum(x ** 2 for x in b))
        return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0

    def index_leads(self, leads: list[dict]) -> None:
        """
        Indexa leads do RD Station para busca semântica.

        Args:
            leads: Lista de leads com campos como nome, email, empresa,
                   estagio_funil, score, origem, ultima_conversao
        """
        self.store = []
        for lead in leads:
            text = (
                f"Lead: {lead.get('nome', '')} | "
                f"Empresa: {lead.get('empresa', '')} | "
                f"Estágio: {lead.get('estagio_funil', '')} | "
                f"Score: {lead.get('score', '')} | "
                f"Origem: {lead.get('origem', '')} | "
                f"Última conversão: {lead.get('ultima_conversao', '')} | "
                f"Tags: {', '.join(lead.get('tags', []))}"
            )
            embedding = self._embed(text)
            self.store.append({
                "text": text,
                "embedding": embedding,
                "metadata": lead
            })
        print(f"\u2705 {len(self.store)} leads indexados.")

    def _retrieve(self, query: str, top_k: int = 5) -> list[str]:
        query_embedding = self._embed(query)
        scored = [
            {**chunk, "score": self._cosine_similarity(query_embedding, chunk["embedding"])}
            for chunk in self.store
        ]
        scored.sort(key=lambda x: x["score"], reverse=True)
        return [chunk["text"] for chunk in scored[:top_k]]

    def query(self, question: str) -> str:
        """
        Responde perguntas sobre leads usando RAG + memória da conversação.

        Args:
            question: Pergunta sobre leads, funil, performance ou estratégia

        Returns:
            Resposta contextualizada baseada nos leads indexados
        """
        context_chunks = self._retrieve(question)
        context_text = "\n\n".join(context_chunks)

        # Adiciona pergunta ao histórico
        self.memory.append({"role": "user", "content": question})

        messages = [
            {
                "role": "system",
                "content": (
                    "Você é um especialista em CRM e inbound marketing focado em RD Station. "
                    "Responda à pergunta baseando-se APENAS nos leads fornecidos como contexto. "
                    "Identifique padrões, prioridades de abordagem e sugira ações práticas. "
                    "Se não houver informação suficiente, diga claramente.\n\n"
                    f"Contexto (leads relevantes):\n{context_text}"
                )
            },
            *self.memory
        ]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages
        )

        answer = response.choices[0].message.content or ""

        # Salva resposta na memória
        self.memory.append({"role": "assistant", "content": answer})

        return answer

    def generate_pipeline_report(self) -> dict:
        """
        Gera relatório completo do funil de vendas com recomendações.

        Returns:
            Dict com análise do funil, leads prioritários e ações recomendadas
        """
        all_leads = "\n\n".join(chunk["text"] for chunk in self.store)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Analise todos os leads e gere um relatório do funil em JSON com: "
                        "totalLeads, distribuicaoPorEstagio, leadsQuentes (lista), "
                        "leadsFrios (lista), principaisOrigens, acoesRecomendadas e "
                        "scoresMedio."
                    )
                },
                {"role": "user", "content": all_leads}
            ],
            response_format={"type": "json_object"}
        )

        return json.loads(response.choices[0].message.content or "{}")

    def suggest_next_actions(self, lead_email: str) -> dict:
        """
        Sugere próximas ações para um lead específico.

        Args:
            lead_email: Email do lead para buscar no índice

        Returns:
            Dict com ações recomendadas, canal ideal e mensagem sugerida
        """
        # Busca lead pelo email no store
        lead_data = next(
            (c["text"] for c in self.store if lead_email in c.get("metadata", {}).get("email", "")),
            None
        )

        if not lead_data:
            return {"erro": f"Lead {lead_email} não encontrado no índice."}

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Você é um consultor de vendas inbound. Analise o perfil do lead e sugira "
                        "as próximas ações em JSON com: proximaAcao, canalIdeal, mensagemSugerida, "
                        "urgencia (alta/media/baixa) e justificativa."
                    )
                },
                {"role": "user", "content": f"Lead:\n{lead_data}"}
            ],
            response_format={"type": "json_object"}
        )

        return json.loads(response.choices[0].message.content or "{}")

    def clear_memory(self) -> None:
        """Limpa o histórico de conversações mantendo o índice de leads."""
        self.memory = []
        print("\u2705 Memória limpa.")
