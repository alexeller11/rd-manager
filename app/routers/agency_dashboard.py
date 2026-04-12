from fastapi import APIRouter
from app.database import db_fetch_all, db_fetch_one, db_fetchval
from app.services.scoring import calculate_score

router = APIRouter()

@router.get("/overview")
async def agency_overview():
    # Calculate stats from DB
    total_clients = await db_fetchval("SELECT COUNT(*) FROM clients") or 0
    active_tokens = await db_fetchval("SELECT COUNT(*) FROM rd_credentials") or 0

    summaries = await db_fetch_all("SELECT summary FROM rd_sync_summaries")
    total_leads = 0
    scores = []

    for s in summaries:
        if s and s.get("summary"):
            data = s["summary"]
            total_leads += data.get("counts", {}).get("leads", 0)
            score = calculate_score(data)
            scores.append(score)

    avg_score = int(sum(scores) / len(scores)) if scores else 0

    return {
        "stats": {
            "total_clients": total_clients,
            "active_tokens": active_tokens,
            "total_leads": total_leads,
            "avg_score": avg_score
        },
        "history": [45, 52, 48, 60, 65, 70, avg_score] # Mock history for now
    }
