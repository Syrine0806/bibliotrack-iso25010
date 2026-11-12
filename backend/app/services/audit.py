"""Journal d'audit : écrit dans la MÊME transaction que l'action auditée (atomicité)."""

import json
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.enums import Role
from app.models import AuditLog


@dataclass(frozen=True)
class Actor:
    id: int | None
    email: str | None
    role: Role | None
    ip: str | None = None

    @property
    def is_staff(self) -> bool:
        return self.role in (Role.ADMIN, Role.BIBLIOTHECAIRE)


SYSTEM = Actor(id=None, email="system", role=None)


def record(
    db: Session,
    actor: Actor,
    action: str,
    entity_type: str,
    entity_id: object = None,
    **details: object,
) -> AuditLog:
    entry = AuditLog(
        user_id=actor.id,
        user_email=actor.email,
        action=action,
        entity_type=entity_type,
        entity_id=None if entity_id is None else str(entity_id),
        details=json.dumps(details, default=str, ensure_ascii=False) if details else None,
        ip_address=actor.ip,
    )
    db.add(entry)
    return entry


def search(
    db: Session,
    *,
    action: str | None = None,
    entity_type: str | None = None,
    user_email: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = 1,
    size: int = 50,
) -> tuple[list[AuditLog], int]:
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if user_email:
        stmt = stmt.where(AuditLog.user_email.ilike(f"%{user_email}%"))
    if date_from:
        stmt = stmt.where(AuditLog.timestamp >= date_from)
    if date_to:
        stmt = stmt.where(AuditLog.timestamp <= date_to)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return list(rows), total
