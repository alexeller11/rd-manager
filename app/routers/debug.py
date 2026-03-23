"""Debug router — carregado APENAS se DEBUG_MODE=true."""
import os
import datetime
from fastapi import APIRouter
from app.database import db_fetchall, db_execute, DATABASE_URL
from app.ai_service import OPENAI_API_KEY, GEMINI_API_KEY, GROQ_API_KEY

router = APIRouter()


@router.get("/info")
async def debug_info():
    """Retorna informações de diagnóstico do ambiente."""
    return {
        "database": {
            "type": "postgresql" if "postgresql" in DATABASE_URL.lower() else "sqlite",
            "url_configured": bool(DATABASE_URL),
            "url_preview": f"{DATABASE_URL[:15]}...{DATABASE_URL[-10:]}" if DATABASE_URL and len(DATABASE_URL) > 25 else DATABASE_URL
        },
        "ai_status": {
            "openai_key_set": bool(OPENAI_API_KEY),
            "gemini_key_set": bool(GEMINI_API_KEY),
            "groq_key_set": bool(GROQ_API_KEY),
            "openai_key_preview": f"{OPENAI_API_KEY[:6]}...{OPENAI_API_KEY[-4:]}" if OPENAI_API_KEY and len(OPENAI_API_KEY) > 10 else None,
            "gemini_key_preview": f"{GEMINI_API_KEY[:6]}...{GEMINI_API_KEY[-4:]}" if GEMINI_API_KEY and len(GEMINI_API_KEY) > 10 else None,
            "openai_model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            "gemini_model": os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
        },
        "env_vars": {
            "PORT": os.environ.get("PORT"),
            "RAILWAY_PUBLIC_DOMAIN": os.environ.get("RAILWAY_PUBLIC_DOMAIN"),
            "RAILWAY_STATIC_URL": os.environ.get("RAILWAY_STATIC_URL"),
            "DEBUG_MODE": os.environ.get("DEBUG_MODE")
        }
    }


@router.get("/errors")
async def get_error_logs():
    """Retorna os erros mais recentes registrados no banco."""
    try:
        return await db_fetchall("SELECT * FROM error_logs ORDER BY created_at DESC LIMIT 50")
    except Exception as e:
        return {"error": str(e)}


@router.get("/test-db")
async def test_db_write():
    """Testa se a escrita no banco está funcionando."""
    try:
        now = datetime.datetime.utcnow()
        await db_execute(
            "INSERT INTO error_logs (endpoint, method, error_message) VALUES ($1, $2, $3)", 
            "/api/debug/test-db", "GET", f"Teste de escrita as {now}"
        )
        return {"success": True, "message": f"Registro de teste inserido com sucesso as {now}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
