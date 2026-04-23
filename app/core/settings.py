from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = Field(default="production", alias="APP_ENV")
    debug_mode: bool = Field(default=False, alias="DEBUG_MODE")  # False por padrão em produção

    database_url: str = Field(default="", alias="DATABASE_URL")
    secret_key: str = Field(default="", alias="SECRET_KEY")

    # SEGURANÇA: sem defaults para credenciais. Devem ser definidos via env vars.
    admin_username: str = Field(default="admin", alias="ADMIN_USERNAME")
    admin_password: str = Field(default="", alias="ADMIN_PASSWORD")

    # SEGURANÇA: sem default "*" - deve ser configurado explicitamente no Render Dashboard
    allowed_origins_raw: str = Field(default="", alias="ALLOWED_ORIGINS")

    invite_code: str = Field(default="", alias="INVITE_CODE")
    token_expire_minutes: int = Field(default=1440, alias="TOKEN_EXPIRE_MINUTES")

    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.3-70b-versatile", alias="GROQ_MODEL")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-1.5-pro", alias="GEMINI_MODEL")
    sambanova_api_key: str = Field(default="", alias="SAMBANOVA_API_KEY")
    sambanova_model: str = Field(default="meta-llama/Llama-3.1-405B-Instruct-Turbo", alias="SAMBANOVA_MODEL")

    rd_client_id: str = Field(default="", alias="RD_CLIENT_ID")
    rd_client_secret: str = Field(default="", alias="RD_CLIENT_SECRET")
    rd_crm_client_id: str = Field(default="", alias="RD_CRM_CLIENT_ID")
    rd_crm_client_secret: str = Field(default="", alias="RD_CRM_CLIENT_SECRET")
    rd_redirect_uri: str = Field(default="", alias="RD_REDIRECT_URI")

    # Telegram
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(default="", alias="TELEGRAM_CHAT_ID")

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.validate()

    @property
    def allowed_origins(self) -> List[str]:
        raw = (self.allowed_origins_raw or "").strip()
        if not raw:
            # Sem configuração explícita: bloqueia tudo em produção
            if self.app_env.lower() == "production":
                return []
            # Em dev local, permite localhost
            return ["http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:3000"]
        if raw == "*":
            return ["*"]
        return [item.strip() for item in raw.split(",") if item.strip()]

    def validate(self):
        if self.app_env.lower() == "production" and not self.debug_mode:
            db = (self.database_url or "").strip().lower()
            valid_prefixes = (
                "postgresql://",
                "postgres://",
                "postgresql+asyncpg://",
            )
            if not db.startswith(valid_prefixes):
                raise RuntimeError("Em produção, use PostgreSQL em DATABASE_URL.")
            if not self.secret_key:
                raise RuntimeError("SECRET_KEY é obrigatório em produção.")
            if not self.admin_username:
                raise RuntimeError("ADMIN_USERNAME é obrigatório em produção.")
            if not self.admin_password:
                raise RuntimeError(
                    "ADMIN_PASSWORD é obrigatório em produção. "
                    "Defina a variável de ambiente ADMIN_PASSWORD no Render Dashboard."
                )


@lru_cache
def get_settings() -> Settings:
    return Settings()
