"""Debug router — carregado APENAS se DEBUG_MODE=true."""
from fastapi import APIRouter, Depends
from app.auth_core import get_current_user
from app.database import db_fetchall, DATABASE_URL

router = APIRouter()


@router.get("/info")
async def debug_info(user=Depends(get_current_user)):
    return {
        "database_url": DATABASE_URL[:30] + "..." if len(DATABASE_URL) > 30 else DATABASE_URL,
        "db_type": "sqlite" if DATABASE_URL.startswith("sqlite") else "postgresql",
    }


@router.get("/errors")
async def get_error_logs(user=Depends(get_current_user)):
    return await db_fetchall(
        "SELECT * FROM error_logs ORDER BY created_at DESC LIMIT 50"
    )
