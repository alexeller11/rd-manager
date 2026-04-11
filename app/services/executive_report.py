import json

from app.database import db_fetch_one
from app.services.scoring import build_client_score


def _parse_summary(value):
    if not value:
        return {}
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return {}
    if isinstance(value, dict):
        return value
    return {}


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

    summary = _parse_summary(summary_row["summary"] if summary_row else {})
    if summary_row and summary_row.get("updated_at") and not summary.get("synced_at"):
        summary["synced_at"] = str(summary_row["updated_at"])

    score_data = build_client_score(client, summary)
    counts = score_data["counts"]
    module_errors = summary.get("module_errors", {})

    strategic_diagnosis = []
    next_steps = []

    if counts["landing_pages"] > 0:
        strategic_diagnosis.append(f"A operação já possui {counts['landing_pages']} landing pages sincronizadas.")
    else:
        strategic_diagnosis.append("A operação ainda não demonstra landing pages sincronizadas.")

    if counts["leads"] > 0:
        strategic_diagnosis.append(f"A base atual conta com {counts['leads']} leads sincronizados.")
    else:
        strategic_diagnosis.append("A base atual não demonstrou leads carregados.")

    if counts["segmentations"] > 0:
        strategic_diagnosis.append(f"A conta possui {counts['segmentations']} segmentações sincronizadas.")
    else:
        strategic_diagnosis.append("A conta não demonstrou segmentações úteis.")

    if counts["workflows"] > 0:
        strategic_diagnosis.append(f"A conta possui {counts['workflows']} workflows sincronizados.")
    else:
        strategic_diagnosis.append("A operação ainda não demonstrou automações ativas.")

    if counts["campaigns"] > 0:
        strategic_diagnosis.append(f"A conta possui {counts['campaigns']} campanhas sincronizadas.")
    elif module_errors.get("campaigns"):
        strategic_diagnosis.append("A leitura de campanhas retornou erro de permissão/plano.")
    else:
        strategic_diagnosis.append("A operação não demonstrou campanhas ativas.")

    next_steps.extend(score_data["actions"])

    if not next_steps:
        next_steps.append("Manter acompanhamento da operação e evoluir performance com base nos dados reais.")

    risk_flags = []
    if counts["leads"] > 0 and counts["segmentations"] == 0:
        risk_flags.append("Base com leads sem segmentação acionável.")
    if counts["leads"] > 0 and counts["workflows"] == 0:
        risk_flags.append("Base com leads sem workflow de nutrição ativo.")
    if module_errors.get("campaigns"):
        risk_flags.append("Módulo de campanhas com restrição de acesso/plano.")

    opportunity_flags = []
    if counts["landing_pages"] > 0 and counts["leads"] == 0:
        opportunity_flags.append("Existe tráfego potencial sem captação convertida em leads.")
    if counts["segmentations"] > 0 and counts["workflows"] > 0:
        opportunity_flags.append("Base pronta para orquestração avançada de automações.")
    if counts["campaigns"] > 0:
        opportunity_flags.append("Há histórico de campanhas para otimização orientada por dados.")

    executive_resume = (
        f"{client['name']} está com score {score_data['score']}/100 e prioridade {score_data['priority']}. "
        f"O relatório considera dados reais sincronizados da RD, incluindo landing pages, leads, segmentações e workflows."
    )

    return {
        "client": client,
        "score_data": score_data,
        "sync_summary": summary,
        "executive_resume": executive_resume,
        "strategic_diagnosis": strategic_diagnosis,
        "next_steps": next_steps,
        "risk_flags": risk_flags,
        "opportunity_flags": opportunity_flags,
    }
