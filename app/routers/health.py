from fastapi import APIRouter

router = APIRouter()


def calc_health_score(data: dict) -> float:
    """
    Calcula um score simples de saúde com base em métricas de marketing.
    Faixa final: 0 a 100.
    """

    if not data:
        return 0.0

    open_rate = float(data.get("open_rate", 0) or 0)
    click_rate = float(data.get("click_rate", 0) or 0)
    conversion_rate = float(data.get("conversion_rate", 0) or 0)

    # Limites de referência simples
    open_score = min((open_rate / 25) * 100, 100) if open_rate > 0 else 0
    click_score = min((click_rate / 4) * 100, 100) if click_rate > 0 else 0
    conversion_score = min((conversion_rate / 10) * 100, 100) if conversion_rate > 0 else 0

    final_score = (open_score * 0.4) + (click_score * 0.3) + (conversion_score * 0.3)
    return round(final_score, 2)


@router.get("/")
async def health_router():
    return {
        "status": "ok",
        "service": "rd-manager"
    }
