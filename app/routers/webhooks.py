"""
Webhook receiver para eventos em tempo real do RD Station.
Recebe notificações de conversão, criação de contato, tags, etc.
"""
import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from app.database import db_execute, db_fetch_all
from app.services.cache_rd import rd_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

WEBHOOK_SECRET = os.getenv("RD_WEBHOOK_SECRET", "")


def _verify_signature(body: bytes, signature: str | None) -> bool:
    """Verifica assinatura HMAC-SHA256 do webhook RD Station."""
    if not WEBHOOK_SECRET:
        return True  # sem secret configurado, aceita tudo (dev)
    if not signature:
        return False  # secret configurado mas sem assinatura → rejeita
    expected = hmac.new(WEBHOOK_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
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

    # Persiste evento — sem ON CONFLICT pois não há constraint UNIQUE na tabela
    await db_execute(
        """
        INSERT INTO rd_webhook_events (event_type, contact_uuid, email, payload, received_at)
        VALUES ($1, $2, $3, $4, $5)
        """,
        event_type,
        contact_uuid,
        email,
        json.dumps(payload, ensure_ascii=False),
        datetime.now(timezone.utc),
    )

    # Invalida cache de contatos para forçar refresh na próxima sync
    for key in list(rd_cache._cache.keys()):
        if "/platform/contacts" in key or "/platform/segmentations" in key:
            rd_cache.delete(key)

    logger.info("Webhook recebido: event=%s uuid=%s email=%s", event_type, contact_uuid, email)
    return {"status": "received", "event": event_type, "uuid": contact_uuid}


@router.get("/rd-station/events")
async def list_webhook_events(limit: int = 50):
    """Lista os últimos eventos recebidos via webhook."""
    rows = await db_fetch_all(
        """
        SELECT event_type, contact_uuid, email, received_at
        FROM rd_webhook_events
        ORDER BY received_at DESC
        LIMIT $1
        """,
        limit,
    )
    return {"events": [dict(r) for r in (rows or [])], "total": len(rows or [])}
