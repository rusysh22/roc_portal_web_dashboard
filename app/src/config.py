"""Application configuration loaded from environment variables."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_env: str = Field(default="development")
    app_name: str = Field(default="ROC Portal")
    app_secret_key: str
    app_base_url: str = Field(default="https://localhost:7789")
    app_default_locale: str = Field(default="id")
    app_supported_locales: str = Field(default="id,en")

    # Database
    database_url: str

    # Redis
    redis_url: str = Field(default="redis://redis:6379/0")

    # Auth
    jwt_algorithm: str = Field(default="HS256")
    access_token_ttl_min: int = Field(default=15)
    refresh_token_ttl_days: int = Field(default=7)
    password_min_length: int = Field(default=12)
    lockout_threshold: int = Field(default=5)
    lockout_duration_min: int = Field(default=15)

    # Azure / Power BI
    azure_tenant_id: str = Field(default="")
    azure_client_id: str = Field(default="")
    azure_client_secret: str = Field(default="")
    pbi_api_base: str = Field(default="https://api.powerbi.com/v1.0/myorg")
    pbi_authority: str = Field(default="https://login.microsoftonline.com")
    pbi_scope: str = Field(default="https://analysis.windows.net/powerbi/api/.default")
    pbi_embed_token_lifetime_min: int = Field(default=60)

    # SMTP
    smtp_host: str = Field(default="")
    smtp_port: int = Field(default=587)
    smtp_user: str = Field(default="")
    smtp_password: str = Field(default="")
    smtp_from: str = Field(default="no-reply@example.com")
    smtp_tls: bool = Field(default=True)

    # Multi-tenant
    tenant_resolution: str = Field(default="subdomain")
    tenant_base_domain: str = Field(default="portal.example.com")
    default_tenant_slug: str = Field(default="default")

    # Security
    allowed_hosts: str = Field(default="localhost")
    csrf_cookie_name: str = Field(default="csrftoken")
    session_cookie_secure: bool = Field(default=True)
    session_cookie_samesite: str = Field(default="strict")

    # Rate limit
    rate_limit_per_minute: int = Field(default=60)
    embed_rate_limit_per_minute: int = Field(default=30)
    export_rate_limit_per_hour: int = Field(default=5)

    @property
    def supported_locales_list(self) -> list[str]:
        return [s.strip() for s in self.app_supported_locales.split(",") if s.strip()]

    @property
    def allowed_hosts_list(self) -> list[str]:
        return [s.strip() for s in self.allowed_hosts.split(",") if s.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
