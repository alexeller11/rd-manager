import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.database import db_fetchone, db_fetchall, db_execute, db_fetchval

router = APIRouter()


class ClientCreate(BaseModel):
    name: str
    segment: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None
    rd_token: Optional[str] = None
    rd_account_id: Optional[str] = None
    persona: Optional[str] = None
    tone: Optional[str] = None
    main_pain: Optional[str] = None
    objections: Optional[str] = None
    rd_crm_token: Optional[str] = None


class ClientUpdate(ClientCreate):
    pass


def _sanitize(client: dict) -> dict:
    """Remove token bruto e adiciona flags de status."""
    has_mkt = bool((client.get("rd_token") or "").strip())
    has_crm = bool((client.get("rd_crm_token") or "").strip())
    
    client = dict(client)
    client["rd_token_set"] = has_mkt
    client["crm_token_set"] = has_crm
    
    # Limpa dados sensíveis
    client["rd_token"] = ""
    client["rd_refresh_token"] = ""
    client["rd_crm_token"] = ""
    return client


async def fetch_client(client_id: int) -> dict | None:
    return await db_fetchone("SELECT * FROM clients WHERE id = $1", client_id)


@router.get("/")
async def list_clients():
    clients = await db_fetchall("SELECT * FROM clients ORDER BY created_at DESC")
    return [_sanitize(c) for c in clients]


@router.get("/{client_id}")
async def get_client(client_id: int):
    client = await fetch_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return _sanitize(client)


@router.post("/")
async def create_client(data: ClientCreate):
    token = (data.rd_token or "").strip() or None
    crm_token = (data.rd_crm_token or "").strip() or None

    client_id = await db_fetchval(
        """INSERT INTO clients
           (name, segment, website, description, rd_token, rd_account_id,
            persona, tone, main_pain, objections, rd_crm_token)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) RETURNING id""",
        data.name, data.segment, data.website, data.description,
        token, data.rd_account_id,
        data.persona, data.tone, data.main_pain, data.objections, crm_token
    )
    result = data.model_dump()
    result["id"] = client_id
    result["rd_token"] = ""
    result["rd_token_set"] = bool(token)
    return result


@router.put("/{client_id}")
async def update_client(client_id: int, data: ClientUpdate):
    existing = await fetch_client(client_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    # Preserva token existente se não foi passado novo
    rd_token = (data.rd_token or "").strip()
    if not rd_token:
        rd_token = existing.get("rd_token")
    
    crm_token = (data.rd_crm_token or "").strip()
    if not crm_token:
        crm_token = existing.get("rd_crm_token")

    await db_execute(
        """UPDATE clients SET
           name=$1, segment=$2, website=$3, description=$4,
           rd_token=$5, rd_account_id=$6, persona=$7, tone=$8,
           main_pain=$9, objections=$10, rd_crm_token=$11
           WHERE id=$12""",
        data.name, data.segment, data.website, data.description,
        rd_token, data.rd_account_id, data.persona, data.tone,
        data.main_pain, data.objections, crm_token, client_id
    )
    return {"success": True}


@router.delete("/{client_id}")
async def delete_client(client_id: int):
    await db_execute("DELETE FROM clients WHERE id = $1", client_id)
    return {"success": True}


@router.post("/{client_id}/set-token")
async def set_rd_token(client_id: int, payload: dict):
    """Salva token RD Station diretamente (para quem usa token fixo sem OAuth)."""
    token = (payload.get("rd_token") or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="Token não informado")
    await db_execute(
        "UPDATE clients SET rd_token=$1, rd_refresh_token=$2 WHERE id=$3",
        token, "", client_id
    )
    return {"success": True}


@router.post("/suggest-data")
async def suggest_client_data(payload: dict):
    """Analisa o site do cliente via IA e sugere dados de cadastro."""
    from app.ai_service import call_ai, SYSTEM_STRATEGIST
    
    url = payload.get("website", "").strip()
    if not url:
        raise HTTPException(400, "URL do site não informada")
        
    if not url.startswith("http"):
        url = "https://" + url
        
    prompt = f"""Analise o site deste cliente e sugira dados para preenchimento de cadastro de marketing.
    URL: {url}
    
    Sugira os seguintes campos em Português do Brasil:
    1. Segmento (Escolha um: E-commerce, SaaS, Servicos, Educacao, Saude, Varejo, Industria, Outro)
    2. Descrição curta (máx 200 caracteres)
    3. Persona/ICP (Público-alvo ideal)
    4. Tom de voz (Ex: Profissional, Descontraído, Autoritativo)
    5. Principal dor (O que o cliente resolve?)
    6. Objeções comuns (Por que não comprariam?)
    
    Responda EXCLUSIVAMENTE em formato JSON:
    {{
      "segment": "...",
      "description": "...",
      "persona": "...",
      "tone": "...",
      "main_pain": "...",
      "objections": "..."
    }}
    """
    result = await call_ai(prompt, system=SYSTEM_STRATEGIST)
    try:
        clean_res = result.strip().replace("```json", "").replace("```", "")
        return json.loads(clean_res)
    except:
        return {"error": "IA falhou ao analisar o site", "raw": result}
