from fastapi import APIRouter, HTTPException, Query

from app.services.health_audit import (
    generate_health_report,
    generate_ai_health_commentary,
    audit_workflows,
    audit_leads,
    audit_landing_pages,
)

router = APIRouter()


@router.get("/client/{client_id}")
async def get_health_report(client_id: int, ai: bool = Query(default=False)):
    """Gera relatório de saúde completo da conta. ai=true para incluir diagnóstico da IA."""
    try:
        report = await generate_health_report(client_id)
        if ai:
            report["ai_commentary"] = await generate_ai_health_commentary(report)
        return {"ok": True, "data": report}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/client/{client_id}/workflows")
async def get_workflow_audit(client_id: int):
    try:
        data = await audit_workflows(client_id)
        return {"ok": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/client/{client_id}/leads")
async def get_lead_audit(client_id: int):
    try:
        data = await audit_leads(client_id)
        return {"ok": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/client/{client_id}/landing-pages")
async def get_lp_audit(client_id: int):
    try:
        data = await audit_landing_pages(client_id)
        return {"ok": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
