"""Report model — all Power BI embed settings stored here (by config)."""
from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TenantScopedMixin, TimestampMixin, new_uuid


class Report(Base, TenantScopedMixin, TimestampMixin):
    """
    All fields required to embed a Power BI report are stored here.
    Admin can CRUD via UI — zero hardcode in application code.
    """
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    slug: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Power BI identifiers (admin-configured) ──────────────────────────────
    workspace_id: Mapped[str] = mapped_column(String(128), nullable=False)
    report_id: Mapped[str] = mapped_column(String(128), nullable=False)
    dataset_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # ── Embed type & display config ───────────────────────────────────────────
    # embed_type: "Report" | "Dashboard" | "Tile" | "Visual" | "PublicUrl"
    embed_type: Mapped[str] = mapped_column(String(32), default="Report", nullable=False)

    # For embed_type="PublicUrl": full public URL from Power BI "Publish to web"
    public_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # For embed_type="HTML": raw HTML embed snippet (copy-paste from Power BI embed dialog)
    html_embed: Mapped[str | None] = mapped_column(Text, nullable=True)

    # display_config keys (all optional, Power BI SDK defaults apply if omitted):
    # {
    #   "height": "600px",               -- iframe height
    #   "filterPaneEnabled": false,       -- show/hide filter pane
    #   "navContentPaneEnabled": false,   -- show/hide page nav
    #   "pageView": "fitToWidth",         -- "fitToWidth" | "actualSize" | "fitToPage"
    #   "defaultPage": "ReportSection1",  -- landing page name
    #   "settings": {}                    -- any extra powerbi-client settings
    # }
    display_config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # ── Row-Level Security ────────────────────────────────────────────────────
    is_rls: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # rls_config:
    # {
    #   "role_mapping": {
    #     "viewer": "Employees",           -- portal role → PBI RLS role
    #     "tenant_admin": "Managers"
    #   },
    #   "username_field": "email"          -- "email" | "user_id" | custom
    # }
    rls_config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # ── Export settings ───────────────────────────────────────────────────────
    # export_config:
    # {
    #   "pdf_allowed": true,
    #   "pptx_allowed": true,
    #   "pdf_settings": { "rclTimeout": "01:00:00" },
    #   "pptx_settings": {}
    # }
    export_config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # ── Status ────────────────────────────────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    order_index: Mapped[int] = mapped_column(default=0, nullable=False)

    roles: Mapped[list["Role"]] = relationship(  # type: ignore[name-defined]
        "Role", secondary="report_role_access", lazy="noload"
    )
    departments: Mapped[list["Department"]] = relationship(  # type: ignore[name-defined]
        "Department", secondary="report_department_access", lazy="noload"
    )
    users: Mapped[list["User"]] = relationship(  # type: ignore[name-defined]
        "User", secondary="report_user_access", lazy="noload"
    )


class ReportRoleAccess(Base):
    __tablename__ = "report_role_access"

    report_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("reports.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )


class ReportDepartmentAccess(Base):
    __tablename__ = "report_department_access"

    report_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("reports.id", ondelete="CASCADE"), primary_key=True
    )
    department_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("departments.id", ondelete="CASCADE"), primary_key=True
    )


class ReportUserAccess(Base):
    __tablename__ = "report_user_access"

    report_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("reports.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
