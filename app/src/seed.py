"""Seed script: create default tenant, permissions, default roles, and super admin user.

Usage:
    docker compose exec app python -m src.seed
    or:
    docker compose exec app python -m src.seed --email admin@example.com --password MyP@ssw0rd123
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import AsyncSessionLocal
from .models.config import DEFAULT_SITE_CONFIGS, SiteConfig
from .models.tenant import Tenant
from .models.user import Permission, Role, RolePermission, User, UserRole
from .core.security import hash_password

# Default permissions seeded globally (not tenant-scoped)
DEFAULT_PERMISSIONS = [
    ("user.manage", "Create, update, delete users within tenant"),
    ("role.manage", "Create, update, delete roles and assign permissions"),
    ("report.view", "View embedded Power BI reports"),
    ("report.manage", "Create, update, delete report configurations"),
    ("report.export", "Export reports to PDF or PPTX"),
    ("menu.manage", "Create, update, delete menu items"),
    ("config.edit", "Edit site configuration"),
    ("audit.view", "View audit log"),
    ("tenant.manage", "Manage tenants (super admin only)"),
]

# Default roles per tenant
DEFAULT_ROLES = [
    {
        "name": "super_admin",
        "description": "Full access across all tenants",
        "is_system": True,
        "permissions": ["*"],  # handled specially
    },
    {
        "name": "tenant_admin",
        "description": "Full admin access within tenant",
        "is_system": True,
        "permissions": [
            "user.manage", "role.manage", "report.view",
            "report.manage", "report.export", "menu.manage",
            "config.edit", "audit.view",
        ],
    },
    {
        "name": "viewer",
        "description": "Can view reports assigned to this role",
        "is_system": True,
        "permissions": ["report.view"],
    },
    {
        "name": "exporter",
        "description": "Can view and export reports",
        "is_system": True,
        "permissions": ["report.view", "report.export"],
    },
]


async def seed(db: AsyncSession, admin_email: str, admin_password: str, tenant_slug: str) -> None:
    print(f"[seed] Starting with tenant={tenant_slug}, admin={admin_email}")

    # 1. Permissions
    perm_map: dict[str, Permission] = {}
    for code, desc in DEFAULT_PERMISSIONS:
        result = await db.execute(select(Permission).where(Permission.code == code))
        perm = result.scalar_one_or_none()
        if not perm:
            perm = Permission(code=code, description=desc)
            db.add(perm)
            print(f"  [+] permission: {code}")
        perm_map[code] = perm
    await db.flush()

    # 2. Default tenant
    result = await db.execute(select(Tenant).where(Tenant.slug == tenant_slug))
    tenant = result.scalar_one_or_none()
    if not tenant:
        tenant = Tenant(slug=tenant_slug, name="ROC Portal")
        db.add(tenant)
        await db.flush()
        print(f"  [+] tenant: {tenant.slug} ({tenant.id})")
    else:
        print(f"  [=] tenant exists: {tenant.slug}")

    # 3. Site configs per tenant
    for cfg in DEFAULT_SITE_CONFIGS:
        result = await db.execute(
            select(SiteConfig).where(
                SiteConfig.tenant_id == tenant.id,
                SiteConfig.key == cfg["key"],
            )
        )
        if not result.scalar_one_or_none():
            db.add(SiteConfig(
                tenant_id=tenant.id,
                key=cfg["key"],
                value=cfg["value"],
                value_type=cfg["value_type"],
                description=cfg["description"],
            ))
            print(f"  [+] config: {cfg['key']}")
    await db.flush()

    # 4. Roles
    for role_def in DEFAULT_ROLES:
        result = await db.execute(
            select(Role).where(Role.tenant_id == tenant.id, Role.name == role_def["name"])
        )
        role = result.scalar_one_or_none()
        if not role:
            role = Role(
                tenant_id=tenant.id,
                name=role_def["name"],
                description=role_def["description"],
                is_system=role_def["is_system"],
            )
            db.add(role)
            await db.flush()
            print(f"  [+] role: {role.name}")

        # Assign permissions (skip "*" wildcard — super_admin handled via is_super_admin flag)
        if role_def["permissions"] == ["*"]:
            continue
        for pcode in role_def["permissions"]:
            perm = perm_map.get(pcode)
            if not perm:
                continue
            result = await db.execute(
                select(RolePermission).where(
                    RolePermission.role_id == role.id,
                    RolePermission.permission_id == perm.id,
                )
            )
            if not result.scalar_one_or_none():
                db.add(RolePermission(role_id=role.id, permission_id=perm.id))

    await db.flush()

    # 5. Super admin user
    result = await db.execute(
        select(User).where(User.email == admin_email.lower(), User.tenant_id == tenant.id)
    )
    admin = result.scalar_one_or_none()
    if not admin:
        admin = User(
            tenant_id=tenant.id,
            email=admin_email.lower(),
            name="Super Admin",
            password_hash=hash_password(admin_password),
            is_active=True,
            is_super_admin=True,
        )
        db.add(admin)
        await db.flush()
        print(f"  [+] super admin: {admin.email} ({admin.id})")
    else:
        print(f"  [=] super admin exists: {admin.email}")

    # Assign tenant_admin role to super admin
    result = await db.execute(
        select(Role).where(Role.tenant_id == tenant.id, Role.name == "tenant_admin")
    )
    ta_role = result.scalar_one_or_none()
    if ta_role:
        result = await db.execute(
            select(UserRole).where(
                UserRole.user_id == admin.id, UserRole.role_id == ta_role.id
            )
        )
        if not result.scalar_one_or_none():
            db.add(UserRole(user_id=admin.id, role_id=ta_role.id))

    await db.commit()
    print("[seed] Done.")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed ROC Portal database")
    parser.add_argument("--email", default="admin@example.com")
    parser.add_argument("--password", default="Admin@Portal2026!")
    parser.add_argument("--tenant", default="default")
    args = parser.parse_args()

    async with AsyncSessionLocal() as db:
        await seed(db, args.email, args.password, args.tenant)


if __name__ == "__main__":
    asyncio.run(main())
