from app.database import db_fetch_one
from app.services.scoring import build_client_score


async def build_executive_report(client_id: int) -> dict:
    client = await db_fetch_one(
        """
        SELECT
            c.id,
            c.name,
            c.segment,
            c.website,
            c.description,
            CASE
                WHEN rc.access_token IS NOT NULL AND TRIM(rc.access_token) <> '' THEN TRUE
                WHEN c.rd_token IS NOT NULL AND TRIM(c.rd_token) <> '' THEN TRUE
                ELSE FALSE
            END AS rd_connected,
            CASE
                WHEN rc.access_token IS NOT NULL AND TRIM(rc.access_token) <> '' THEN TRUE
                WHEN c.rd_token IS NOT NULL AND TRIM(c.rd_token) <> '' THEN TRUE
                ELSE FALSE
            END AS rd_token_set
        FROM clients c
        LEFT JOIN rd_credentials rc
            ON rc.client_id = c.id
        WHERE c.id = $1
        """,
        client_id,
    )

    if not client:
        raise Exception("Cliente não encontrado")

    summary_row = await db_fetch_one(
        """
        SELECT summary, updated_at
        FROM rd_sync_summaries
        WHERE client_id = $1
        """,
        client_id,
    )

    summary_payload = summary_row["summary"] if summary_row and summary_row.get("summary") else {}
    score_data = build_client_score(client, summary_payload)

    score = score_data["score"]
    priority = score_data["priority"]
    counts = score_data["counts"]

    strategic_diagnosis = []
    next_steps = []

    if counts["landing_pages"] == 0:
        strategic_diagnosis.append("A operação ainda não mostra landing pages sincronizadas, o que reduz previsibilidade na captação.")
        next_steps.append("Mapear e estruturar páginas de captação alinhadas às ofertas prioritárias.")

    if counts["segmentations"] == 0:
        strategic_diagnosis.append("A base ainda não demonstra segmentação suficiente para comunicação mais precisa.")
        next_steps.append("Criar segmentações mínimas por perfil, origem e estágio do lead.")

    if counts["workflows"] == 0:
        strategic_diagnosis.append("A ausência de automações aumenta dependência de esforço manual e reduz escala.")
        next_steps.append("Implementar fluxo de nutrição e fluxo de reativação.")

    if counts["campaigns"] == 0:
        strategic_diagnosis.append("Sem campanhas recentes, a geração de demanda tende a ficar irregular.")
        next_steps.append("Ativar uma rotina de campanhas com objetivo e calendário definidos.")

    if not strategic_diagnosis:
        strategic_diagnosis.append("A operação mostra sinais de estrutura mais consistente, com espaço para otimização contínua.")
        next_steps.append("Refinar campanhas, automações e páginas com base nos dados atuais.")

    executive_resume = (
        f"{client['name']} está com score {score}/100 e prioridade {priority}. "
        f"O cenário atual indica {('necessidade de estruturação' if priority == 'alta' else 'espaço de evolução controlada')}. "
        f"O foco deve estar em transformar gargalos em plano de ação recorrente."
    )

    return {
        "client": client,
        "score_data": score_data,
        "sync_summary": summary_payload,
        "executive_resume": executive_resume,
        "strategic_diagnosis": strategic_diagnosis,
        "next_steps": next_steps,
    }
