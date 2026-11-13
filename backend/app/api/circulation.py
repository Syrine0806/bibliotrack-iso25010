from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import admin_only, any_role, staff_only
from app.core.database import get_db
from app.domain.enums import LoanStatus, PenaltyStatus, ReservationStatus
from app.models import Loan, Penalty
from app.schemas import (
    LoanCreate,
    LoanOut,
    Page,
    PenaltyCreate,
    PenaltyOut,
    ReservationCreate,
    ReservationOut,
    ReturnResult,
)
from app.services import circulation
from app.services.audit import Actor

router = APIRouter(prefix="/api", tags=["Circulation"])


def _scope_user(actor: Actor, requested: int | None) -> int | None:
    """Un adhérent ne voit que ses propres données, quel que soit le filtre demandé."""
    return requested if actor.is_staff else actor.id


# ------------------------------------------------------------------ emprunts
@router.get("/loans", response_model=Page[LoanOut])
def list_loans(
    user_id: int | None = None,
    status_filter: LoanStatus | None = Query(default=None, alias="status"),
    overdue_only: bool = False,
    q: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    actor: Actor = Depends(any_role),
) -> Page[LoanOut]:
    rows, total = circulation.list_loans(
        db,
        user_id=_scope_user(actor, user_id),
        status=status_filter,
        overdue_only=overdue_only,
        q=q,
        page=page,
        size=size,
    )
    return Page[LoanOut](items=rows, total=total, page=page, size=size)


@router.post("/loans", response_model=LoanOut, status_code=status.HTTP_201_CREATED)
def create_loan(
    data: LoanCreate, db: Session = Depends(get_db), actor: Actor = Depends(staff_only)
) -> Loan:
    return circulation.create_loan(db, actor, data.user_id, data.barcode)


@router.post("/loans/{loan_id}/return", response_model=ReturnResult)
def return_loan(
    loan_id: int, db: Session = Depends(get_db), actor: Actor = Depends(staff_only)
) -> ReturnResult:
    loan, fee, late, reserved_for = circulation.return_loan(db, actor, loan_id)
    return ReturnResult(
        loan=LoanOut.model_validate(loan),
        penalty_amount=fee,
        days_late=late,
        reserved_for_user_id=reserved_for,
    )


@router.post("/loans/{loan_id}/renew", response_model=LoanOut)
def renew_loan(
    loan_id: int, db: Session = Depends(get_db), actor: Actor = Depends(any_role)
) -> Loan:
    return circulation.renew_loan(db, actor, loan_id)


@router.post("/loans/{loan_id}/lost", response_model=LoanOut)
def declare_lost(
    loan_id: int, db: Session = Depends(get_db), actor: Actor = Depends(staff_only)
) -> Loan:
    return circulation.declare_lost(db, actor, loan_id)


# ------------------------------------------------------------------ réservations
@router.get("/reservations", response_model=Page[ReservationOut])
def list_reservations(
    user_id: int | None = None,
    book_id: int | None = None,
    status_filter: ReservationStatus | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    actor: Actor = Depends(any_role),
) -> Page[ReservationOut]:
    rows, total = circulation.list_reservations(
        db,
        user_id=_scope_user(actor, user_id),
        status=status_filter,
        book_id=book_id,
        page=page,
        size=size,
    )
    positions = circulation.queue_positions(db, rows)
    items = []
    for r in rows:
        out = ReservationOut.model_validate(r)
        out.queue_position = positions.get(r.id)
        items.append(out)
    return Page[ReservationOut](items=items, total=total, page=page, size=size)


@router.post("/reservations", response_model=ReservationOut, status_code=status.HTTP_201_CREATED)
def create_reservation(
    data: ReservationCreate, db: Session = Depends(get_db), actor: Actor = Depends(any_role)
) -> ReservationOut:
    user_id = data.user_id if (actor.is_staff and data.user_id) else actor.id
    reservation = circulation.create_reservation(db, actor, data.book_id, user_id)
    out = ReservationOut.model_validate(reservation)
    out.queue_position = circulation.queue_positions(db, [reservation]).get(reservation.id)
    return out


@router.post("/reservations/{reservation_id}/cancel", response_model=ReservationOut)
def cancel_reservation(
    reservation_id: int, db: Session = Depends(get_db), actor: Actor = Depends(any_role)
) -> ReservationOut:
    return ReservationOut.model_validate(circulation.cancel_reservation(db, actor, reservation_id))


# ------------------------------------------------------------------ pénalités
@router.get("/penalties", response_model=Page[PenaltyOut])
def list_penalties(
    user_id: int | None = None,
    status_filter: PenaltyStatus | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    actor: Actor = Depends(any_role),
) -> Page[PenaltyOut]:
    rows, total = circulation.list_penalties(
        db, user_id=_scope_user(actor, user_id), status=status_filter, page=page, size=size
    )
    return Page[PenaltyOut](items=rows, total=total, page=page, size=size)


@router.post("/penalties", response_model=PenaltyOut, status_code=status.HTTP_201_CREATED)
def create_penalty(
    data: PenaltyCreate, db: Session = Depends(get_db), actor: Actor = Depends(staff_only)
) -> Penalty:
    return circulation.create_penalty(db, actor, data.user_id, data.amount, data.reason)


@router.post("/penalties/{penalty_id}/pay", response_model=PenaltyOut)
def pay_penalty(
    penalty_id: int, db: Session = Depends(get_db), actor: Actor = Depends(staff_only)
) -> Penalty:
    return circulation.settle_penalty(db, actor, penalty_id, PenaltyStatus.PAYEE)


@router.post("/penalties/{penalty_id}/cancel", response_model=PenaltyOut)
def cancel_penalty(
    penalty_id: int, db: Session = Depends(get_db), actor: Actor = Depends(admin_only)
) -> Penalty:
    return circulation.settle_penalty(db, actor, penalty_id, PenaltyStatus.ANNULEE)


# ------------------------------------------------------------------ maintenance
@router.post("/maintenance/run")
def run_maintenance(
    db: Session = Depends(get_db), _: Actor = Depends(staff_only)
) -> dict[str, int]:
    return circulation.run_maintenance(db)
