"""Admin: Department CRUD endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from ...core.audit import emit as audit_emit
from ...core.rbac import require_permission
from ...deps import CurrentTenant, CurrentUser, DBSession
from ...models.department import Department, UserDepartment
from ...models.user import User
from ...schemas.department import DepartmentCreate, DepartmentListItem, DepartmentRead, DepartmentUpdate

router = APIRouter(prefix="/api/admin/departments", tags=["admin-departments"])


def _perm():
    return require_permission("user.manage")


@router.get("", response_model=list[DepartmentListItem], dependencies=[_perm()])
async def list_departments(tenant: CurrentTenant, db: DBSession) -> list[DepartmentListItem]:
    result = await db.execute(
        select(Department)
        .where(Department.tenant_id == tenant.id)
        .options(selectinload(Department.users))
        .order_by(Department.name)
    )
    depts = result.scalars().all()
    return [
        DepartmentListItem(id=d.id, name=d.name, description=d.description, user_count=len(d.users))
        for d in depts
    ]


@router.post("", response_model=DepartmentRead, status_code=status.HTTP_201_CREATED, dependencies=[_perm()])
async def create_department(
    body: DepartmentCreate,
    tenant: CurrentTenant,
    actor: CurrentUser,
    db: DBSession,
) -> DepartmentRead:
    existing = await db.execute(
        select(Department).where(Department.tenant_id == tenant.id, Department.name == body.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="department_name_taken")

    dept = Department(tenant_id=tenant.id, name=body.name, description=body.description)
    db.add(dept)
    await db.commit()
    await db.refresh(dept)
    await audit_emit(db, user_id=actor.id, tenant_id=tenant.id, action="create.department", target_type="department", target_id=dept.id, metadata={"name": dept.name})
    result = await db.execute(
        select(Department).where(Department.id == dept.id).options(selectinload(Department.users))
    )
    return DepartmentRead.model_validate(result.scalar_one())


@router.get("/{dept_id}", response_model=DepartmentRead, dependencies=[_perm()])
async def get_department(dept_id: str, tenant: CurrentTenant, db: DBSession) -> DepartmentRead:
    result = await db.execute(
        select(Department)
        .where(Department.id == dept_id, Department.tenant_id == tenant.id)
        .options(selectinload(Department.users))
    )
    dept = result.scalar_one_or_none()
    if not dept:
        raise HTTPException(status_code=404, detail="department_not_found")
    return DepartmentRead.model_validate(dept)


@router.put("/{dept_id}", response_model=DepartmentRead, dependencies=[_perm()])
async def update_department(
    dept_id: str,
    body: DepartmentUpdate,
    tenant: CurrentTenant,
    actor: CurrentUser,
    db: DBSession,
) -> DepartmentRead:
    result = await db.execute(
        select(Department).where(Department.id == dept_id, Department.tenant_id == tenant.id)
    )
    dept = result.scalar_one_or_none()
    if not dept:
        raise HTTPException(status_code=404, detail="department_not_found")

    if body.name is not None:
        dept.name = body.name
    if body.description is not None:
        dept.description = body.description

    await db.commit()
    await audit_emit(db, user_id=actor.id, tenant_id=tenant.id, action="update.department", target_type="department", target_id=dept.id)
    result2 = await db.execute(
        select(Department).where(Department.id == dept_id).options(selectinload(Department.users))
    )
    return DepartmentRead.model_validate(result2.scalar_one())


@router.delete("/{dept_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_perm()])
async def delete_department(
    dept_id: str,
    tenant: CurrentTenant,
    actor: CurrentUser,
    db: DBSession,
) -> None:
    result = await db.execute(
        select(Department).where(Department.id == dept_id, Department.tenant_id == tenant.id)
    )
    dept = result.scalar_one_or_none()
    if not dept:
        raise HTTPException(status_code=404, detail="department_not_found")
    await audit_emit(db, user_id=actor.id, tenant_id=tenant.id, action="delete.department", target_type="department", target_id=dept.id, metadata={"name": dept.name})
    await db.delete(dept)
    await db.commit()
