import json
from datetime import datetime, timezone
from typing import Any

from app.database import db_fetch_all, db_fetch_one


def _parse_json(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    text = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _days_since(dt: datetime | None) -> int | None:
    if not dt:
        return None
    return max(0, (_now() - dt).days)


def _pick(payload: dict, keys: list[str], default: Any = None) -> Any:
    for key in keys:
        if key in payload and payload.get(key) not in (None, ""):
            return payload.get(key)
    return default


def _lead_last_interaction(payload: dict) -> datetime | None:
    candidate_keys = [
        "last_conversion_date",
        "last_conversion_at",
        "last_interaction_at",
        "last_activity_at",
        "updated_at",
        "created_at",
    ]
    for key in candidate_keys:
        dt = _parse_dt(payload.get(key))
        if dt:
            return dt
    return None


def _lead_email(payload: dict) -> str:
    return str(_pick(payload, ["email", "contact_email", "lead_email"], "") or "").strip()


def _lead_name(payload: dict) -> str:
    return str(_pick(payload, ["name", "first_name", "full_name"], "Sem nome") or "Sem nome").strip()


def _lead_source(payload: dict) -> str:
    return str(_pick(payload, ["traffic_source", "source", "conversion_origin", "utm_source"], "desconhecida"))


def _lead_stage(payload: dict) -> str:
    return str(_pick(payload, ["lifecycle_stage", "stage", "lead_stage"], "indefinido"))


async def get_inactive_leads(client_id: int, min_days: int = 60, limit: int = 200) -> dict:
    rows = await db_fetch_all(
        """
        SELECT id, object_key, payload, synced_at
        FROM rd_sync_snapshots
        WHERE client_id = $1 AND object_type = 'lead'
        ORDER BY synced_at DESC
        LIMIT $2
        """,
        client_id,
        limit,
    ) or []

    inactive = []
    active = []

    for row in rows:
        payload = _parse_json(row.get("payload")) or {}
        if not isinstance(payload, dict):
            continue

        last_interaction = _lead_last_interaction(payload)
        days = _days_since(last_interaction)

        lead_item = {
            "snapshot_id": row.get("id"),
            "email": _lead_email(payload),
            "name": _lead_name(payload),
            "source": _lead_source(payload),
            "stage": _lead_stage(payload),
            "last_interaction_at": last_interaction.isoformat() if last_interaction else None,
            "days_without_interaction": days,
            "payload": payload,
        }

        if days is None or days >= min_days:
            inactive.append(lead_item)
        else:
            active.append(lead_item)

    return {
        "client_id": client_id,
        "min_days": min_days,
        "inactive_total": len(inactive),
        "active_total": len(active),
        "inactive_leads": inactive,
    }


async def get_base_segments(client_id: int, limit: int = 300) -> dict:
    rows = await db_fetch_all(
        """
        SELECT id, object_key, payload, synced_at
        FROM rd_sync_snapshots
        WHERE client_id = $1 AND object_type = 'lead'
        ORDER BY synced_at DESC
        LIMIT $2
        """,
        client_id,
        limit,
    ) or []

    buckets = {
        "inactive_30_plus": [],
        "inactive_60_plus": [],
        "inactive_90_plus": [],
        "by_source": {},
        "by_stage": {},
    }

    for row in rows:
        payload = _parse_json(row.get("payload")) or {}
        if not isinstance(payload, dict):
            continue

        email = _lead_email(payload)
        name = _lead_name(payload)
        source = _lead_source(payload)
        stage = _lead_stage(payload)
        last_interaction = _lead_last_interaction(payload)
        days = _days_since(last_interaction)

        item = {
            "email": email,
            "name": name,
            "source": source,
            "stage": stage,
            "days_without_interaction": days,
        }

        if days is None or days >= 30:
            buckets["inactive_30_plus"].append(item)
        if days is None or days >= 60:
            buckets["inactive_60_plus"].append(item)
        if days is None or days >= 90:
            buckets["inactive_90_plus"].append(item)

        buckets["by_source"].setdefault(source, 0)
        buckets["by_source"][source] += 1

        buckets["by_stage"].setdefault(stage, 0)
        buckets["by_stage"][stage] += 1

    return {
        "client_id": client_id,
        "segments": buckets,
    }


async def build_automation_plan(client_id: int) -> dict:
    client = await db_fetch_one(
        """
        SELECT id, name, segment, website, description
        FROM clients
        WHERE id = $1
        """,
        client_id,
    )

    if not client:
        raise Exception("Cliente não encontrado")

    segments = await get_base_segments(client_id)
    inactive = await get_inactive_leads(client_id, min_days=60)

    recommended_flows = []

    if inactive["inactive_total"] > 0:
        recommended_flows.append({
            "id": "reengajamento-base-fria",
            "title": "Reengajamento de base fria",
            "objective": "reengajamento",
            "audience": f"Leads com 60+ dias sem interação ({inactive['inactive_total']})",
            "trigger": "Entrada em segmento de inatividade 60+ dias",
            "exit_rule": "Sai ao clicar, responder ou converter",
            "emails": [
                {
                    "delay_days": 0,
                    "subject": f"{client['name']}: ainda faz sentido continuarmos?",
                    "preheader": "Estamos retomando contato com quem já demonstrou interesse.",
                    "body": "Percebemos que você demonstrou interesse anteriormente e queremos retomar essa conversa de forma útil e objetiva.",
                    "cta": "Responder este e-mail",
                },
                {
                    "delay_days": 3,
                    "subject": f"{client['name']}: uma oportunidade prática para você",
                    "preheader": "Uma sugestão rápida para voltar a avançar.",
                    "body": "Há espaço para retomar esse tema com mais clareza e um próximo passo simples.",
                    "cta": "Quero ver a oportunidade",
                },
            ],
        })

    recommended_flows.append({
        "id": "nutricao-novos-leads",
        "title": "Nutrição de novos leads",
        "objective": "nutricao",
        "audience": "Leads recém-captados",
        "trigger": "Conversão em landing page ou formulário",
        "exit_rule": "Sai ao virar oportunidade",
        "emails": [
            {
                "delay_days": 0,
                "subject": f"{client['name']}: conteúdo inicial para te ajudar",
                "preheader": "Primeiro passo para avançar com mais clareza.",
                "body": "Preparamos um conteúdo objetivo para ajudar você a enxergar o melhor próximo passo.",
                "cta": "Acessar conteúdo",
            }
        ],
    })

    return {
        "client": client,
        "segments": segments["segments"],
        "inactive_base": {
            "threshold_days": inactive["min_days"],
            "total": inactive["inactive_total"],
        },
        "recommended_flows": recommended_flows,
        "ai_insights": (
            "1) Priorizar reengajamento da base fria.\n"
            "2) Criar nutrição de novos leads.\n"
            "3) Estruturar campanhas e automações por estágio."
        ),
    }


async def build_reengagement_plan(client_id: int, min_days: int = 60) -> dict:
    client = await db_fetch_one(
        """
        SELECT id, name, segment, website, description
        FROM clients
        WHERE id = $1
        """,
        client_id,
    )

    if not client:
        raise Exception("Cliente não encontrado")

    inactive = await get_inactive_leads(client_id, min_days=min_days, limit=400)

    sources = {}
    stages = {}

    for lead in inactive["inactive_leads"]:
        sources.setdefault(lead["source"], 0)
        sources[lead["source"]] += 1

        stages.setdefault(lead["stage"], 0)
        stages[lead["stage"]] += 1

    sequence = [
        {
            "delay_days": 0,
            "subject": f"{client['name']}: retomando esse contato",
            "preheader": "Estamos organizando um novo contato com quem já demonstrou interesse.",
            "body": "Queremos retomar essa conversa de um jeito objetivo e útil.",
            "cta": "Retomar contato",
        },
        {
            "delay_days": 4,
            "subject": f"{client['name']}: ainda faz sentido para você?",
            "preheader": "Última tentativa antes de encerrar esse fluxo.",
            "body": "Se ainda fizer sentido, basta responder este e-mail e retomamos com prioridade.",
            "cta": "Responder agora",
        },
    ]

    return {
        "client": client,
        "threshold_days": min_days,
        "inactive_total": len(inactive["inactive_leads"]),
        "top_sources": sorted(sources.items(), key=lambda x: x[1], reverse=True)[:10],
        "top_stages": sorted(stages.items(), key=lambda x: x[1], reverse=True)[:10],
        "recommended_sequence": sequence,
        "execution_notes": [
            "Criar segmento dinâmico por inatividade.",
            "Excluir quem converteu recentemente.",
            "Ramificar clique vs não clique.",
            "Encerrar fluxo ao responder, converter ou reaquecer.",
        ],
    }
