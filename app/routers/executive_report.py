from fastapi import APIRouter, HTTPException

from app.services.executive_report import build_executive_report

router = APIRouter()


@router.get("/client/{client_id}")
async def executive_report(client_id: int):
    try:
        report = await build_executive_report(client_id)
        return {
            "ok": True,
            "report": report,
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
