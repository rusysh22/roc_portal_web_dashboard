"""MenuItem model for dynamic navigation."""
from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TenantScopedMixin, TimestampMixin, new_uuid


class MenuItem(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "menu_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("menu_items.id", ondelete="SET NULL"), nullable=True, index=True
    )
    label_key: Mapped[str] = mapped_column(String(128), nullable=False)
    label_override: Mapped[str | None] = mapped_column(String(255), nullable=True)
    icon: Mapped[str | None] = mapped_column(String(64), nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_slug: Mapped[str | None] = mapped_column(String(128), nullable=True)
    required_permission: Mapped[str | None] = mapped_column(String(64), nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    open_in_new_tab: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    children: Mapped[list["MenuItem"]] = relationship(
        "MenuItem", back_populates="parent", lazy="noload"
    )
    parent: Mapped["MenuItem | None"] = relationship(
        "MenuItem", back_populates="children", remote_side="MenuItem.id", lazy="noload"
    )
