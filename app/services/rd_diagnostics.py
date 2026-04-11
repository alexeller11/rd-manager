from app.database import db_fetch_one
import app.auth_core as auth_core
from app.services.rd_fullsync import get_last_run, get_last_summary


async def _missing_get_valid_mkt_token(*args, **kwargs):
    raise RuntimeError("Função get_valid_mkt_token indisponível")


get_valid_mkt_token = getattr(auth_core, "get_valid_mkt_token", _missing_get_valid_mkt_token)


async def build_rd_diagnostics(client_id: int) -> dict:
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
            END AS rd_connected
        FROM clients c
        LEFT JOIN rd_credentials rc
            ON rc.client_id = c.id
        WHERE c.id = $1
        """,
        client_id,
    )

    if not client:
        raise Exception("Cliente não encontrado")

    token_status = {
        "valid": False,
        "message": "Token não testado",
    }

    try:
        token = await get_valid_mkt_token(client_id)
        token_status = {
            "valid": bool(token),
            "message": "Token válido e disponível" if token else "Token vazio",
        }
    except Exception as e:
        token_status = {
            "valid": False,
            "message": str(e),
        }

    last_run = await get_last_run(client_id)
    last_summary_row = await get_last_summary(client_id)

    summary_payload = last_summary_row["summary"] if last_summary_row and last_summary_row.get("summary") else {}
    counts = summary_payload.get("counts", {}) if isinstance(summary_payload, dict) else {}
    module_errors = summary_payload.get("module_errors", {}) if isinstance(summary_payload, dict) else {}
    module_debug = summary_payload.get("module_debug", {}) if isinstance(summary_payload, dict) else {}

    diagnosis = []

    if not client["rd_connected"]:
        diagnosis.append("A conta ainda não está conectada à RD.")
    if not token_status["valid"]:
        diagnosis.append("O token da RD está inválido, ausente ou não pôde ser renovado.")
    if counts.get("landing_pages", 0) == 0:
        diagnosis.append("Nenhuma landing page foi retornada pela integração.")
    if counts.get("leads", 0) == 0:
        diagnosis.append("Nenhum lead foi carregado na leitura atual.")
    if counts.get("segmentations", 0) == 0:
        diagnosis.append("Nenhuma segmentação foi retornada pela conta.")
    if counts.get("workflows", 0) == 0:
        diagnosis.append("Nenhum workflow foi retornado pela integração.")
    if counts.get("campaigns", 0) == 0:
        diagnosis.append("Nenhuma campanha foi retornada pela integração.")

    if not diagnosis:
        diagnosis.append("A integração está respondendo e os principais módulos trouxeram dados.")

    return {
        "client": client,
        "token_status": token_status,
        "last_run": last_run,
        "last_summary": summary_payload,
        "counts": counts,
        "module_errors": module_errors,
        "module_debug": module_debug,
        "diagnosis": diagnosis,
    }
