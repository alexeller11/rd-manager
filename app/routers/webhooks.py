"""
Webhook receiver para eventos em tempo real do RD Station.
Recebe notificações de conversão, criação de contato, tags, etc.
"""
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from app.database import db_execute
from app.services.cache_rd import rd_cache

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

WEBHOOK_SECRET = os.getenv("RD_WEBHOOK_SECRET", "")


def _verify_signature(body: bytes, signature: str | None) -> bool:
    if not WEBHOOK_SECRET or not signature:
        return True  # sem secret configurado, aceita tudo (dev)
    expected = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/rd-station")
async def rd_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-RD-Signature")

    if not _verify_signature(body, signature):
        raise HTTPException(status_code=401, detail="Assinatura inválida")

    try:
        payload = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="Payload inválido")

    event_type = payload.get("event_type", "UNKNOWN")
    contact_data = payload.get("contacts", [{}])
    if isinstance(contact_data, list) and contact_data:
        contact = contact_data[0]
    else:
        contact = payload.get("data", {})

    contact_uuid = contact.get("uuid") or contact.get("id") or ""
    email = contact.get("email") or ""

    # Persiste evento
    await db_execute(
        """
        INSERT INTO rd_webhook_events (event_type, contact_uuid, email, payload, received_at)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT DO NOTHING
        """,
        event_type,
        contact_uuid,
        email,
        json.dumps(payload, ensure_ascii=False),
        datetime.now(timezone.utc).isoformat(),
    )

    # Invalida cache de contatos para forçar refresh na próxima sync
    # (não sabemos o client_id direto, então invalidamos globalmente o path de contacts)
    for key in list(rd_cache._cache.keys()):
        if "/platform/contacts" in key or "/platform/segmentations" in key:
            rd_cache.delete(key)

    return {"status": "received", "event": event_type, "uuid": contact_uuid}


@router.get("/rd-station/events")
async def list_webhook_events(limit: int = 50):
    """Lista os últimos eventos recebidos via webhook."""
    from app.database import db_fetchall
    rows = await db_fetchall(
        """
        SELECT event_type, contact_uuid, email, received_at
        FROM rd_webhook_events
        ORDER BY received_at DESC
        LIMIT $1
        """,
        limit,
    )
    return {"events": [dict(r) for r in (rows or [])], "total": len(rows or [])}
