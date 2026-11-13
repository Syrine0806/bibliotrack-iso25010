from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import admin_only, staff_only
from app.core.database import get_db
from app.schemas import AuditOut, DashboardOut, Page
from app.services import audit, dashboard
from app.services.audit import Actor

router = APIRouter(prefix="/api", tags=["Pilotage"])


@router.get("/dashboard", response_model=DashboardOut)
def get_dashboard(
    date_from: date | None = None,
    date_to: date | None = None,
    category_id: int | None = None,
    db: Session = Depends(get_db),
    _: Actor = Depends(staff_only),
) -> DashboardOut:
    return dashboard.build_dashboard(db, date_from, date_to, category_id)


@router.get("/audit", response_model=Page[AuditOut])
def search_audit(
    action: str | None = Query(default=None, max_length=60),
    entity_type: str | None = Query(default=None, max_length=40),
    user_email: str | None = Query(default=None, max_length=255),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: Actor = Depends(admin_only),
) -> Page[AuditOut]:
    rows, total = audit.search(
        db,
        action=action,
        entity_type=entity_type,
        user_email=user_email,
        date_from=date_from,
        date_to=date_to,
        page=page,
        size=size,
    )
    return Page[AuditOut](items=rows, total=total, page=page, size=size)


health_router = APIRouter(tags=["Santé"])


@health_router.get("/api/health")
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    """Sonde de disponibilité : vérifie aussi la connexion à la base."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}
