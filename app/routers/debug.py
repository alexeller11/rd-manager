"""
Rotas de debug. Só devem ser carregadas se DEBUG_MODE=true.
"""
from fastapi import APIRouter

from app.core.settings import get_settings
from app.database import db_fetchall, db_execute, DATABASE_URL

router = APIRouter()
settings = get_settings()


@router.get("/info")
async def debug_info():
    return {
        "environment": settings.app_env,
        "debug_mode": settings.debug_mode,
        "database": {
            "type": "sqlite" if DATABASE_URL.startswith("sqlite") else "postgresql",
            "configured": bool(DATABASE_URL),
        },
        "ai_status": {
            "groq_configured": bool(settings.groq_api_key),
            "openai_configured": bool(settings.openai_api_key),
            "gemini_configured": bool(settings.gemini_api_key),
        },
    }


@router.get("/errors")
async def get_error_logs():
    return await db_fetchall(
        "SELECT id, client_id, endpoint, method, error_message, created_at FROM error_logs ORDER BY created_at DESC LIMIT 50"
    )


@router.post("/test-db")
async def test_db_write():
    await db_execute(
        "INSERT INTO error_logs (client_id, endpoint, method, error_message, stack_trace) VALUES ($1, $2, $3, $4, $5)",
        None,
        "/api/debug/test-db",
        "POST",
        "Teste de escrita executado com sucesso",
        "",
    )
    return {"success": True}
