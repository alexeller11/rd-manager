from fastapi import APIRouter
from app.services.rd_fullsync import run_full_sync
from app.services.scoring import calculate_score
from app.services.insights_ai import generate_insight

router = APIRouter()


@router.get("/overview")
async def overview():
    data = await run_full_sync(1)

    score = calculate_score(data["summary"])
    insight = generate_insight(data["summary"])

    return {
        "total_clients": 1,
        "score": score,
        "insight": insight,
        "data": data["summary"]
    }
