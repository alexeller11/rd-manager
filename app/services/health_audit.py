"""
Serviço de Auditoria de Saúde de Conta RD Station.
Analisa dados sincronizados e gera diagnóstico por cliente.
A IA retorna JSON estruturado com summary, priorities, actions, risks e next_steps.
"""
import json
from datetime import datetime, timezone
from typing import Any

from app.database import db_fetch_all, db_fetch_one
from app.ai_service import generate_text


def _parse_payload(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return {}
    if isinstance(value, dict):
        return value
    return {}


def _days_since(date_str: str | None) -> int | None:
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
        return max(0, (datetime.now(timezone.utc) - dt).days)
    except Exception:
        return None


def _extract_json(raw: str) -> dict:
    """Extrai JSON de resposta da IA; fallback gracioso se falhar."""
    try:
        start = raw.index("{")
        end = raw.rindex("}") + 1
        return json.loads(raw[start:end])
    except Exception:
        return {
            "summary": raw[:500] if raw else "Diagnóstico indisponível.",
            "priorities": [],
            "actions": [],
            "risks": [],
            "next_steps": [],
        }


async def _get_snapshots(client_id: int, object_type: str) -> list[dict]:
    rows = await db_fetch_all(
        """
        SELECT object_key, payload, synced_at
        FROM rd_sync_snapshots
        WHERE client_id = $1 AND object_type = $2
        ORDER BY synced_at DESC
        """,
        client_id,
        object_type,
    ) or []
    result = []
    for row in rows:
        payload = _parse_payload(row.get("payload"))
        result.append({
            "key": row.get("object_key"),
            "synced_at": row.get("synced_at"),
            "payload": payload,
        })
    return result


async def audit_workflows(client_id: int) -> dict:
    """Audita workflows: detecta inativos, sem triggers, desatualizados."""
    workflows = await _get_snapshots(client_id, "workflow")

    active, paused, stale, no_trigger = [], [], [], []

    for wf in workflows:
        p = wf["payload"]
        status = str(p.get("status") or p.get("state") or "").lower()
        name = p.get("name") or p.get("title") or wf["key"]
        updated_raw = p.get("updated_at") or p.get("last_run_at")
        days_ago = _days_since(updated_raw)

        wf_info = {
            "name": name,
            "status": status,
            "days_since_update": days_ago,
            "trigger": p.get("trigger") or p.get("trigger_type"),
        }

        if not wf_info["trigger"]:
            no_trigger.append(wf_info)

        if status in ("paused", "inactive", "disabled"):
            paused.append(wf_info)
        elif status in ("active", "enabled", "running"):
            if days_ago is not None and days_ago > 30:
                stale.append(wf_info)
            else:
                active.append(wf_info)
        else:
            stale.append(wf_info)

    score = 100
    issues = []
    if paused:
        score -= min(30, len(paused) * 10)
        issues.append(f"{len(paused)} workflow(s) pausado(s)")
    if no_trigger:
        score -= min(20, len(no_trigger) * 7)
        issues.append(f"{len(no_trigger)} workflow(s) sem trigger definido")
    if stale:
        score -= min(20, len(stale) * 5)
        issues.append(f"{len(stale)} workflow(s) ativo(s) sem atualização há +30 dias")

    return {
        "total": len(workflows),
        "active": len(active),
        "paused": len(paused),
        "stale": len(stale),
        "no_trigger": len(no_trigger),
        "score": max(0, score),
        "issues": issues,
        "details": {"active": active, "paused": paused, "stale": stale, "no_trigger": no_trigger},
    }


async def audit_leads(client_id: int) -> dict:
    """Classifica leads por engajamento: quente, morno, frio, morto."""
    leads = await _get_snapshots(client_id, "lead")

    hot, warm, cold, dead = [], [], [], []
    no_email = 0

    for lead in leads:
        p = lead["payload"]
        email = p.get("email") or p.get("personal_email")
        if not email:
            no_email += 1

        last_raw = (
            p.get("last_interaction_at")
            or p.get("last_conversion_date")
            or p.get("updated_at")
            or p.get("created_at")
        )
        days = _days_since(last_raw)
        name = p.get("name") or (email.split("@")[0] if email else "—")

        entry = {
            "name": name,
            "email": email or "—",
            "days_inactive": days,
            "stage": p.get("lifecycle_stage") or p.get("stage") or "—",
            "source": p.get("traffic_source") or p.get("utm_source") or p.get("source") or "orgânico",
        }

        if days is None or days > 90:
            dead.append(entry)
        elif days > 30:
            cold.append(entry)
        elif days > 7:
            warm.append(entry)
        else:
            hot.append(entry)

    total = len(leads)
    engagement_rate = round(((len(hot) + len(warm)) / total * 100), 1) if total > 0 else 0
    score = min(100, int(engagement_rate + (len(hot) / max(total, 1) * 50)))

    issues = []
    if len(dead) > total * 0.5:
        issues.append(f"{len(dead)} leads mortos — base precisa de reaquecimento urgente")
    if no_email > total * 0.2:
        issues.append(f"{no_email} leads sem e-mail — qualidade da captação comprometida")
    if len(cold) > total * 0.3:
        issues.append(f"{len(cold)} leads frios — oportunidade de reengajamento")

    return {
        "total": total,
        "hot": len(hot),
        "warm": len(warm),
        "cold": len(cold),
        "dead": len(dead),
        "no_email": no_email,
        "engagement_rate": engagement_rate,
        "score": max(0, score),
        "issues": issues,
        "hot_leads": hot[:10],
        "cold_leads": cold[:10],
    }


async def audit_landing_pages(client_id: int) -> dict:
    """Classifica LPs por performance: top, médias, críticas."""
    lps = await _get_snapshots(client_id, "landing_page")

    top, average, critical = [], [], []
    unpublished = 0

    for lp in lps:
        p = lp["payload"]
        name = p.get("title") or p.get("name") or lp["key"]
        status = str(p.get("status") or "").lower()
        conv_id = p.get("conversion_identifier") or ""
        url = p.get("public_url") or (f"https://conteudo.rdstation.com/{conv_id}" if conv_id else "")
        visits = int(p.get("visits_count") or 0)
        conversions = int(p.get("conversions_count") or 0)
        conv_rate = float(p.get("conversion_rate") or 0.0)

        if conv_rate == 0 and visits > 0 and conversions > 0:
            conv_rate = conversions / visits

        if "not_published" in status or status == "draft":
            unpublished += 1
            continue

        entry = {
            "name": name,
            "url": url,
            "visits": visits,
            "conversions": conversions,
            "conversion_rate": round(conv_rate * 100, 1),
            "status": status,
        }

        if conv_rate >= 0.10:
            top.append(entry)
        elif conv_rate >= 0.03:
            average.append(entry)
        else:
            critical.append(entry)

    issues = []
    if critical:
        issues.append(f"{len(critical)} LP(s) com conversão abaixo de 3% — revisão de CTA urgente")
    if unpublished:
        issues.append(f"{unpublished} LP(s) não publicada(s) — verificar se é intencional")

    total_published = len(top) + len(average) + len(critical)
    score = 100
    if total_published > 0:
        score = int((len(top) * 100 + len(average) * 60 + len(critical) * 10) / total_published)

    return {
        "total": len(lps),
        "published": total_published,
        "unpublished": unpublished,
        "top": len(top),
        "average": len(average),
        "critical": len(critical),
        "score": max(0, min(100, score)),
        "issues": issues,
        "top_lps": sorted(top, key=lambda x: x["conversion_rate"], reverse=True)[:5],
        "critical_lps": sorted(critical, key=lambda x: x["conversion_rate"])[:5],
    }


async def generate_health_report(client_id: int) -> dict:
    """Gera relatório de saúde completo da conta."""
    wf_audit = await audit_workflows(client_id)
    lead_audit = await audit_leads(client_id)
    lp_audit = await audit_landing_pages(client_id)

    overall_score = int(
        wf_audit["score"] * 0.30 +
        lead_audit["score"] * 0.40 +
        lp_audit["score"] * 0.30
    )

    all_issues = wf_audit["issues"] + lead_audit["issues"] + lp_audit["issues"]

    if overall_score >= 75:
        health_status = "healthy"
        health_label = "Saudável ✅"
    elif overall_score >= 45:
        health_status = "warning"
        health_label = "Atenção ⚠️"
    else:
        health_status = "critical"
        health_label = "Crítico 🔴"

    return {
        "client_id": client_id,
        "overall_score": overall_score,
        "health_status": health_status,
        "health_label": health_label,
        "issues": all_issues,
        "workflows": wf_audit,
        "leads": lead_audit,
        "landing_pages": lp_audit,
    }


async def generate_ai_health_commentary(audit: dict) -> dict:
    """
    Usa IA para gerar diagnóstico consultivo em JSON estruturado.
    Retorna: summary, priorities, actions, risks, next_steps.
    """
    issues_text = ", ".join(audit["issues"]) if audit["issues"] else "Nenhum problema crítico identificado"

    prompt = f"""Você é um consultor sênior de marketing digital especializado em RD Station.
Analise esta auditoria e gere um diagnóstico executivo.

DADOS:
- Score Geral: {audit["overall_score"]}/100 ({audit["health_label"]})
- Problemas: {issues_text}
- Workflows: {audit["workflows"]["total"]} total | {audit["workflows"]["active"]} ativos | {audit["workflows"]["paused"]} pausados | {audit["workflows"]["stale"]} desatualizados
- Leads: {audit["leads"]["total"]} total | {audit["leads"]["hot"]} quentes | {audit["leads"]["warm"]} mornos | {audit["leads"]["cold"]} frios | {audit["leads"]["dead"]} mortos | engajamento: {audit["leads"]["engagement_rate"]}%
- Landing Pages: {audit["landing_pages"]["total"]} total | {audit["landing_pages"]["top"]} top | {audit["landing_pages"]["average"]} médias | {audit["landing_pages"]["critical"]} críticas

Retorne APENAS um JSON válido, sem markdown, sem texto antes ou depois:
{{
  "summary": "string — situação geral em 2-3 linhas diretas",
  "priorities": [
    {{"rank": 1, "area": "string", "problem": "string", "impact": "alto|médio|baixo"}}
  ],
  "actions": [
    {{"action": "string", "area": "workflows|leads|landing_pages", "effort": "baixo|médio|alto", "expected_gain": "string"}}
  ],
  "risks": [
    {{"risk": "string", "probability": "alta|média|baixa", "consequence": "string"}}
  ],
  "next_steps": [
    {{"step": 1, "what": "string", "when": "string", "owner": "agência|cliente"}}
  ]
}}"""

    raw = await generate_text(prompt)
    return _extract_json(raw)
