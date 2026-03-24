import os
import hashlib
import base64
from functools import lru_cache


def _to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings:
    def __init__(self) -> None:
        self.app_env = os.getenv("APP_ENV", "development").strip().lower()
        self.is_production = self.app_env == "production"
        self.debug_mode = _to_bool(os.getenv("DEBUG_MODE"), default=not self.is_production)

        self.secret_key = os.getenv("SECRET_KEY", "").strip()
        if not self.secret_key:
            if self.is_production:
                raise RuntimeError("SECRET_KEY não configurada em produção.")
            self.secret_key = "dev-only-change-me-immediately"

        derived_key = base64.urlsafe_b64encode(
            hashlib.sha256(self.secret_key.encode("utf-8")).digest()
        ).decode("utf-8")
        self.token_encryption_key = os.getenv("TOKEN_ENCRYPTION_KEY", derived_key).strip()

        self.token_expire_minutes = int(os.getenv("TOKEN_EXPIRE_MINUTES", "720"))
        self.admin_username = os.getenv("ADMIN_USERNAME", "admin").strip()
        self.admin_password = os.getenv("ADMIN_PASSWORD", "admin123").strip()

        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./rd_manager.db").strip()

        self.rd_client_id = os.getenv("RD_CLIENT_ID", "").strip()
        self.rd_client_secret = os.getenv("RD_CLIENT_SECRET", "").strip()
        self.rd_redirect_uri = os.getenv("RD_REDIRECT_URI", "").strip()

        self.groq_api_key = os.getenv("GROQ_API_KEY", "").strip()
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()

        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash").strip()

        default_origins = ["http://localhost:3000", "http://localhost:8000"]
        railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN") or os.getenv("RAILWAY_STATIC_URL")
        if railway_domain:
            default_origins.insert(0, railway_domain if railway_domain.startswith("http") else f"https://{railway_domain}")

        self.allowed_origins = _split_csv(os.getenv("ALLOWED_ORIGINS")) or default_origins

        self.validate()

    def validate(self) -> None:
        if self.is_production and self.secret_key == "dev-only-change-me-immediately":
            raise RuntimeError("SECRET_KEY insegura em produção.")
        if self.is_production and self.admin_password == "admin123":
            raise RuntimeError("ADMIN_PASSWORD insegura em produção.")
        if self.is_production and self.debug_mode:
            raise RuntimeError("DEBUG_MODE não pode ficar habilitado em produção.")

    @property
    def has_any_ai_provider(self) -> bool:
        return bool(self.groq_api_key or self.openai_api_key or self.gemini_api_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
