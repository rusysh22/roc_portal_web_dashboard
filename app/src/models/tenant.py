"""Tenant model."""
from __future__ import annotations

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, new_uuid


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_color: Mapped[str] = mapped_column(String(20), default="#0ea5e9", nullable=False)
    secondary_color: Mapped[str] = mapped_column(String(20), default="#1e293b", nullable=False)
    default_locale: Mapped[str] = mapped_column(String(8), default="id", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    users: Mapped[list["User"]] = relationship("User", back_populates="tenant", lazy="noload")  # type: ignore[name-defined]
    site_configs: Mapped[list["SiteConfig"]] = relationship("SiteConfig", back_populates="tenant", lazy="noload")  # type: ignore[name-defined]
