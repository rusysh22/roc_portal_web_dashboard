"""SiteConfig — per-tenant key/value configuration store."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, new_uuid


class SiteConfig(Base):
    __tablename__ = "site_configs"
    __table_args__ = (UniqueConstraint("tenant_id", "key", name="uq_siteconfig_tenant_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    value: Mapped[dict | str | int | bool | None] = mapped_column(JSONB, nullable=True)
    value_type: Mapped[str] = mapped_column(String(16), default="string", nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="site_configs", lazy="noload")  # type: ignore[name-defined]


# Default config keys and their initial values (seeded per tenant on creation)
DEFAULT_SITE_CONFIGS: list[dict] = [
    {"key": "site.name", "value": "ROC Portal", "value_type": "string", "description": "Portal display name"},
    {"key": "site.logo_url", "value": None, "value_type": "string", "description": "Logo URL (leave null to use initials)"},
    {"key": "site.favicon_url", "value": None, "value_type": "string", "description": "Favicon URL"},
    {"key": "site.primary_color", "value": "#0ea5e9", "value_type": "string", "description": "Primary brand color (hex)"},
    {"key": "site.secondary_color", "value": "#1e293b", "value_type": "string", "description": "Secondary brand color (hex)"},
    {"key": "site.footer_text", "value": "© 2026 ROC Portal", "value_type": "string", "description": "Footer text"},
    {"key": "site.login_bg_url", "value": None, "value_type": "string", "description": "Login page background image URL"},
    {"key": "site.announcement", "value": None, "value_type": "string", "description": "Banner announcement (null = hidden)"},
    {"key": "auth.session_timeout_min", "value": 60, "value_type": "int", "description": "Idle session timeout (minutes)"},
    {"key": "auth.password_min_len", "value": 12, "value_type": "int", "description": "Minimum password length"},
    {"key": "auth.lockout_threshold", "value": 5, "value_type": "int", "description": "Failed login attempts before lockout"},
    {"key": "auth.lockout_duration_min", "value": 15, "value_type": "int", "description": "Lockout duration (minutes)"},
    {"key": "auth.enable_2fa_admin", "value": True, "value_type": "bool", "description": "Require 2FA for admin roles"},
    {"key": "pbi.token_lifetime_min", "value": 60, "value_type": "int", "description": "Power BI embed token lifetime (minutes)"},
    {"key": "pbi.watermark_enabled", "value": True, "value_type": "bool", "description": "Show email watermark over report"},
    {"key": "pbi.watermark_template", "value": "{email} • {datetime}", "value_type": "string", "description": "Watermark text template"},
    {"key": "feature.audit_log_enabled", "value": True, "value_type": "bool", "description": "Enable audit logging"},
    {"key": "feature.allow_export", "value": False, "value_type": "bool", "description": "Allow users to export reports"},
    {"key": "feature.allow_dark_mode", "value": True, "value_type": "bool", "description": "Allow users to switch to dark mode"},
    {"key": "i18n.default_locale", "value": "id", "value_type": "string", "description": "Default UI language (id | en)"},
]
