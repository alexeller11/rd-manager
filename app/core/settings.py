import os
import hashlib
import base64
from functools import lru_cache


def _get_env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return default


def _to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {
        "1", "true", "yes", "on", "sim", "verdadeiro"
    }


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


class Settings:
    def __init__(self) -> None:
        raw_env = _get_env("APP_ENV", default="development").lower()
        env_alias = {
            "produção": "production",
            "producao": "production",
            "prod": "production",
            "desenvolvimento": "development",
            "dev": "development",
            "homologacao": "staging",
            "homologação": "staging",
        }
        self.app_env = env_alias.get(raw_env, raw_env)
        self.is_production = self.app_env == "production"

        self.debug_mode = _to_bool(
            _get_env("DEBUG_MODE", default="false"),
            default=not self.is_production,
        )

        self.secret_key = _get_env("SECRET_KEY")
        if not self.secret_key:
            if self.is_production:
                raise RuntimeError("SECRET_KEY não configurada em produção.")
            self.secret_key = "dev-only-change-me-immediately"

        derived_key = base64.urlsafe_b64encode(
            hashlib.sha256(self.secret_key.encode("utf-8")).digest()
        ).decode("utf-8")

        self.token_encryption_key = _get_env(
            "TOKEN_ENCRYPTION_KEY",
            default=derived_key,
        )

        self.token_expire_minutes = int(_get_env("TOKEN_EXPIRE_MINUTES", default="720"))

        self.admin_username = _get_env("ADMIN_USERNAME", default="admin")
        self.admin_password = _get_env("ADMIN_PASSWORD", default="admin123")

        self.database_url = _get_env(
            "DATABASE_URL",
            default="sqlite:///./rd_manager.db",
        )

        self.rd_client_id = _get_env("RD_CLIENT_ID")
        self.rd_client_secret = _get_env("RD_CLIENT_SECRET")
        self.rd_crm_client_id = _get_env("RD_CRM_CLIENT_ID")
        self.rd_crm_client_secret = _get_env("RD_CRM_CLIENT_SECRET")
        self.rd_redirect_uri = _get_env("RD_REDIRECT_URI")

        self.groq_api_key = _get_env("GROQ_API_KEY")
        self.openai_api_key = _get_env("OPENAI_API_KEY")
        self.gemini_api_key = _get_env("GEMINI_API_KEY")

        self.groq_model = _get_env("GROQ_MODEL", default="llama-3.3-70b-versatile")
        self.openai_model = _get_env("OPENAI_MODEL", default="gpt-4o-mini")
        self.gemini_model = _get_env("GEMINI_MODEL", default="gemini-1.5-flash")

        default_origins = ["http://localhost:3000", "http://localhost:8000"]
        railway_domain = _get_env("RAILWAY_PUBLIC_DOMAIN", "RAILWAY_STATIC_URL")
        if railway_domain:
            default_origins.insert(
                0,
                railway_domain if railway_domain.startswith("http") else f"https://{railway_domain}",
            )

        self.allowed_origins = _split_csv(_get_env("ALLOWED_ORIGINS")) or default_origins
        self.invite_code = _get_env("INVITE_CODE")

        self.validate()

    def validate(self) -> None:
        if self.is_production and self.secret_key == "dev-only-change-me-immediately":
            raise RuntimeError("SECRET_KEY insegura em produção.")

        if self.is_production and len(self.secret_key) < 32:
            raise RuntimeError("SECRET_KEY muito curta para produção. Use no mínimo 32 caracteres.")

        if self.is_production and not self.database_url.startswith("postgresql"):
            raise RuntimeError("Em produção, use PostgreSQL em DATABASE_URL.")

    @property
    def has_any_ai_provider(self) -> bool:
        return bool(self.groq_api_key or self.openai_api_key or self.gemini_api_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
