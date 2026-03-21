import json
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from app.database import db_fetchone, db_fetchall, db_fetchval, db_execute, parse_json_field
from app.auth_core import get_current_user
from app.ai_service import call_ai, build_client_context, SYSTEM_EXPERT
from app.routers.clients import fetch_client

router = APIRouter()


class FlowNode(BaseModel):
    id: str
    type: str
    label: str
    config: dict = {}
    x: float = 0
    y: float = 0


class FlowEdge(BaseModel):
    id: str
    source: str
    target: str
    label: str = ""


class FlowSave(BaseModel):
    client_id: int
    name: str
    description: str = ""
    nodes: List[FlowNode]
    edges: List[FlowEdge]


class FlowGenerate(BaseModel):
    client_id: int
    objective: str
    flow_type: str = "nurturing"


@router.post("/generate")
async def generate_flow(req: FlowGenerate, user=Depends(get_current_user)):
    client = await fetch_client(req.client_id)
    if not client:
        raise HTTPException(404, "Cliente não encontrado")

    flow_labels = {
        "nurturing":    "fluxo de nutrição de leads desde a captura até a conversão",
        "welcome":      "sequência de boas-vindas para novos leads",
        "reengagement": "fluxo de reengajamento para leads inativos",
        "post_purchase": "automação pós-compra para aumentar LTV",
        "lead_scoring": "fluxo de qualificação e lead scoring automático",
        "onboarding":   "onboarding de novos clientes",
    }
    context = build_client_context(client)
    flow_label = flow_labels.get(req.flow_type, req.flow_type)

    prompt = f"""Crie um {flow_label} para: "{req.objective}"

DADOS DO CLIENTE:
{context}

Responda APENAS com JSON válido (sem markdown, sem texto fora do JSON):
{{
  "name": "Nome do fluxo",
  "description": "Descrição breve",
  "nodes": [
    {{"id": "n1", "type": "trigger", "label": "Gatilho", "config": {{"event": "form_submitted"}}}},
    {{"id": "n2", "type": "wait", "label": "Aguardar 1 dia", "config": {{"days": 1}}}},
    {{"id": "n3", "type": "email", "label": "Nome do email", "config": {{"subject": "Assunto", "preview": "Preview...", "goal": "objetivo"}}}},
    {{"id": "n4", "type": "condition", "label": "Abriu email?", "config": {{"condition": "opened_email", "yes_label": "Sim", "no_label": "Não"}}}},
    {{"id": "n5", "type": "tag", "label": "Tag: engajado", "config": {{"tag": "engajado", "action": "add"}}}},
    {{"id": "n6", "type": "end", "label": "Fim do fluxo", "config": {{}}}}
  ],
  "edges": [
    {{"id": "e1", "source": "n1", "target": "n2", "label": ""}},
    {{"id": "e2", "source": "n2", "target": "n3", "label": ""}},
    {{"id": "e3", "source": "n3", "target": "n4", "label": ""}},
    {{"id": "e4", "source": "n4", "target": "n5", "label": "Sim"}},
    {{"id": "e5", "source": "n4", "target": "n6", "label": "Não"}}
  ],
  "rd_station_steps": ["Passo 1: ...", "Passo 2: ..."]
}}

Crie 6-10 nós com pelo menos 1 condition e emails com assuntos reais."""

    result = await call_ai(prompt, system=SYSTEM_EXPERT, max_tokens=2000)

    try:
        clean = result.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        flow_data = json.loads(clean.strip())
    except Exception:
        flow_data = {
            "name": f"Fluxo: {req.objective[:40]}",
            "description": req.objective,
            "nodes": [
                {"id": "n1", "type": "trigger",   "label": "Lead capturado",       "config": {"event": "form_submitted"}},
                {"id": "n2", "type": "email",     "label": "Email de boas-vindas", "config": {"subject": "Bem-vindo!", "preview": "Obrigado por se cadastrar...", "goal": "apresentar a empresa"}},
                {"id": "n3", "type": "wait",      "label": "Aguardar 3 dias",      "config": {"days": 3}},
                {"id": "n4", "type": "condition", "label": "Abriu email?",          "config": {"condition": "opened_email", "yes_label": "Sim", "no_label": "Não"}},
                {"id": "n5", "type": "email",     "label": "Conteúdo de valor",    "config": {"subject": "Dica exclusiva", "preview": "Separamos algo especial...", "goal": "engajar"}},
                {"id": "n6", "type": "email",     "label": "Reengajamento",        "config": {"subject": "Ainda por aqui?", "preview": "Notamos que você não abriu...", "goal": "reativar"}},
                {"id": "n7", "type": "tag",       "label": "Tag: engajado",        "config": {"tag": "engajado", "action": "add"}},
                {"id": "n8", "type": "end",       "label": "Fim do fluxo",         "config": {}},
            ],
            "edges": [
                {"id": "e1", "source": "n1", "target": "n2", "label": ""},
                {"id": "e2", "source": "n2", "target": "n3", "label": ""},
                {"id": "e3", "source": "n3", "target": "n4", "label": ""},
                {"id": "e4", "source": "n4", "target": "n5", "label": "Sim"},
                {"id": "e5", "source": "n4", "target": "n6", "label": "Não"},
                {"id": "e6", "source": "n5", "target": "n7", "label": ""},
                {"id": "e7", "source": "n7", "target": "n8", "label": ""},
                {"id": "e8", "source": "n6", "target": "n8", "label": ""},
            ],
            "rd_station_steps": [
                "1. Acesse RD Station > Automações > Nova automação",
                "2. Configure o gatilho conforme o primeiro nó",
                "3. Adicione as ações na ordem definida",
            ]
        }

    return flow_data


@router.post("/save")
async def save_flow(req: FlowSave, user=Depends(get_current_user)):
    flow_json = json.dumps({
        "nodes": [n.model_dump() for n in req.nodes],
        "edges": [e.model_dump() for e in req.edges],
    }, ensure_ascii=False)
    flow_id = await db_fetchval(
        "INSERT INTO flows (client_id, name, description, flow_data) VALUES ($1,$2,$3,$4) RETURNING id",
        req.client_id, req.name, req.description, flow_json
    )
    return {"id": flow_id, "success": True}


@router.get("/list/{client_id}")
async def list_flows(client_id: int, user=Depends(get_current_user)):
    return await db_fetchall(
        "SELECT id, name, description, created_at FROM flows WHERE client_id=$1 ORDER BY created_at DESC",
        client_id
    )


@router.get("/detail/{flow_id}")
async def get_flow(flow_id: int, user=Depends(get_current_user)):
    row = await db_fetchone("SELECT * FROM flows WHERE id=$1", flow_id)
    if not row:
        raise HTTPException(404, "Fluxo não encontrado")
    d = dict(row)
    d["flow_data"] = parse_json_field(d.get("flow_data"))
    return d


@router.delete("/{flow_id}")
async def delete_flow(flow_id: int, user=Depends(get_current_user)):
    await db_execute("DELETE FROM flows WHERE id=$1", flow_id)
    return {"success": True}
