from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def health_router():
    return {"status": "ok", "service": "rd-manager"}
