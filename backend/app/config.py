"""Configuración centralizada con pydantic-settings.

Todas las variables de entorno se leen desde aquí.
Nunca importar os.environ directamente en el código de la aplicación.
"""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración de la aplicación leída desde variables de entorno."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # === Entorno ===
    environment: str = "development"
    log_level: str = "INFO"

    # === Base de datos ===
    database_url: str = (
        "postgresql+asyncpg://radar:radar_dev_password@localhost:5432/radar"
    )
    database_url_sync: str = (
        "postgresql://radar:radar_dev_password@localhost:5432/radar"
    )

    # === Redis / Celery ===
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # === Seguridad ===
    jwt_secret: str = "change_me_in_production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    password_reset_token_expire_minutes: int = 30
    encryption_key: str = "change_me_32_bytes_long_min____"

    # === Email (SMTP) ===
    smtp_host: str = "mailhog"
    smtp_port: int = 1025
    email_from: str = "alertas@radarpublico.cl"

    # === CORS ===
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str) -> str:
        """Valida que CORS_ORIGINS no sea wildcard en producción."""
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        """Devuelve CORS_ORIGINS como lista."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    # === IA ===
    anthropic_api_key: str = ""
    voyage_api_key: str = ""
    llm_provider: str = "anthropic"
    llm_model_reasoning: str = "claude-opus-4-7"
    llm_model_fast: str = "claude-haiku-4-5-20251001"

    # === Notificaciones ===
    resend_api_key: str = ""
    resend_from_email: str = "alertas@radarpublico.cl"
    whatsapp_provider_api_key: str = ""

    # === Storage (Cloudflare R2) ===
    r2_access_key: str = ""
    r2_secret_key: str = ""
    r2_bucket: str = "radar-publico-dev"
    r2_endpoint: str = ""

    # === Observabilidad ===
    sentry_dsn: str = ""

    @property
    def is_production(self) -> bool:
        """Retorna True si el entorno es producción."""
        return self.environment == "production"


settings = Settings()
