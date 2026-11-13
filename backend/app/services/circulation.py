"""Circulation des documents : emprunts, retours, prolongations, pertes, réservations, pénalités.

Toutes les opérations sont transactionnelles : en cas d'erreur, rien n'est persisté
(ni le changement d'état, ni l'entrée d'audit, ni la pénalité).
"""

from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.core import clock
from app.core.config import get_settings
from app.domain import rules
from app.domain.enums import (
    ACTIVE_LOAN_STATUSES,
    ACTIVE_RESERVATION_STATUSES,
    CopyStatus,
    LoanStatus,
    PenaltyStatus,
    ReservationStatus,
)
from app.domain.errors import NotFoundError, PermissionDeniedError
from app.domain.state_machine import (
    COPY_WORKFLOW,
    LOAN_WORKFLOW,
    PENALTY_WORKFLOW,
    RESERVATION_WORKFLOW,
)
from app.models import Book, Copy, Loan, Penalty, Reservation, User
from app.services import audit
from app.services.audit import Actor
from app.services.users import unpaid_total


def policy() -> rules.LibraryPolicy:
    return rules.LibraryPolicy.from_settings(get_settings())


def _ensure_owner_or_staff(actor: Actor, owner_id: int) -> None:
    if not actor.is_staff and actor.id != owner_id:
        raise PermissionDeniedError("Accès refusé : ressource d'un autre adhérent.")


def _set_copy_status(copy: Copy, target: CopyStatus) -> None:
    COPY_WORKFLOW.assert_transition(copy.status, target)
    copy.status = target


# ------------------------------------------------------------------ état d'un adhérent
def member_state(db: Session, user: User) -> rules.MemberState:
    today = clock.today()
    active = db.scalar(
        select(func.count()).where(Loan.user_id == user.id, Loan.status.in_(ACTIVE_LOAN_STATUSES))
    )
    overdue = db.scalar(
        select(func.count()).where(
            Loan.user_id == user.id,
            Loan.status.in_(ACTIVE_LOAN_STATUSES),
            Loan.due_date < today,
        )
    )
    reservations = db.scalar(
        select(func.count()).where(
            Reservation.user_id == user.id,
            Reservation.status.in_(ACTIVE_RESERVATION_STATUSES),
        )
    )
    return rules.MemberState(
        is_active=user.is_active,
        active_loans=active or 0,
        unpaid_penalties=unpaid_total(db, user.id),
        has_overdue_loan=bool(overdue),
        active_reservations=reservations or 0,
    )


# ------------------------------------------------------------------ file de réservation
def assign_copy_to_queue(db: Session, copy: Copy) -> Reservation | None:
    """RG-08 : un exemplaire libéré est attribué au 1er adhérent de la file (FIFO)."""
    nxt = db.scalar(
        select(Reservation)
        .where(
            Reservation.book_id == copy.book_id,
            Reservation.status == ReservationStatus.EN_ATTENTE,
        )
        .order_by(Reservation.created_at, Reservation.id)
        .limit(1)
    )
    if nxt is None:
        if copy.status != CopyStatus.DISPONIBLE:
            _set_copy_status(copy, CopyStatus.DISPONIBLE)
        return None
    RESERVATION_WORKFLOW.assert_transition(nxt.status, ReservationStatus.DISPONIBLE)
    now = clock.now()
    nxt.status = ReservationStatus.DISPONIBLE
    nxt.copy_id = copy.id
    nxt.available_until = rules.hold_deadline(policy(), now)
    if copy.status != CopyStatus.RESERVE:  # déjà mis de côté : simple changement de bénéficiaire
        _set_copy_status(copy, CopyStatus.RESERVE)
    audit.record(
        db,
        audit.SYSTEM,
        "RESERVATION_AVAILABLE",
        "Reservation",
        nxt.id,
        copy=copy.barcode,
        user_id=nxt.user_id,
        until=nxt.available_until,
    )
    return nxt


# ------------------------------------------------------------------ emprunts
def _lock_copy_by_barcode(db: Session, barcode: str) -> Copy:
    # SELECT ... FOR UPDATE : empêche deux prêts concurrents du même exemplaire (PostgreSQL).
    copy = db.scalar(select(Copy).where(Copy.barcode == barcode.strip()).with_for_update())
    if copy is None:
        raise NotFoundError("Exemplaire", barcode)
    return copy


def create_loan(db: Session, actor: Actor, user_id: int, barcode: str) -> Loan:
    pol = policy()
    member = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if member is None:
        raise NotFoundError("Adhérent", user_id)
    copy = _lock_copy_by_barcode(db, barcode)
    held = db.scalar(
        select(Reservation).where(
            Reservation.copy_id == copy.id,
            Reservation.status == ReservationStatus.DISPONIBLE,
        )
    )
    held_for_member = held is not None and held.user_id == member.id
    rules.check_can_borrow(pol, member_state(db, member), copy.status, held_for_member)

    if held_for_member:
        RESERVATION_WORKFLOW.assert_transition(held.status, ReservationStatus.HONOREE)
        held.status = ReservationStatus.HONOREE
    _set_copy_status(copy, CopyStatus.EMPRUNTE)
    now = clock.now()
    loan = Loan(
        copy=copy,
        user=member,
        loaned_at=now,
        due_date=rules.compute_due_date(pol, now.date()),
        status=LoanStatus.EN_COURS,
    )
    db.add(loan)
    db.flush()
    audit.record(
        db,
        actor,
        "LOAN_CREATED",
        "Loan",
        loan.id,
        user_id=member.id,
        barcode=copy.barcode,
        due_date=loan.due_date,
    )
    db.commit()
    return loan


def get_loan(db: Session, loan_id: int, *, lock: bool = False) -> Loan:
    stmt = select(Loan).where(Loan.id == loan_id)
    if lock:
        stmt = stmt.with_for_update()
    loan = db.scalar(stmt)
    if loan is None:
        raise NotFoundError("Emprunt", loan_id)
    return loan


def _add_penalty(db: Session, loan: Loan, kind: str, amount: Decimal, reason: str) -> Penalty:
    penalty = Penalty(
        user_id=loan.user_id,
        loan_id=loan.id,
        kind=kind,
        amount=amount,
        reason=reason,
        status=PenaltyStatus.IMPAYEE,
    )
    db.add(penalty)
    return penalty


def return_loan(db: Session, actor: Actor, loan_id: int) -> tuple[Loan, Decimal, int, int | None]:
    """Retour d'un exemplaire : pénalité éventuelle (RG-06) puis remise en file (RG-08)."""
    pol = policy()
    loan = get_loan(db, loan_id, lock=True)
    LOAN_WORKFLOW.assert_transition(loan.status, LoanStatus.RENDU)
    now = clock.now()
    late = rules.days_late(loan.due_date, now.date())
    fee = rules.compute_late_fee(pol, loan.due_date, now.date())
    loan.status = LoanStatus.RENDU
    loan.returned_at = now
    if fee > 0:
        _add_penalty(db, loan, "RETARD", fee, f"Retard de {late} jour(s) — {loan.copy.barcode}")
    reservation = assign_copy_to_queue(db, loan.copy)
    audit.record(
        db,
        actor,
        "LOAN_RETURNED",
        "Loan",
        loan.id,
        days_late=late,
        fee=fee,
        reserved_for=reservation.user_id if reservation else None,
    )
    db.commit()
    return loan, fee, late, (reservation.user_id if reservation else None)


def renew_loan(db: Session, actor: Actor, loan_id: int) -> Loan:
    loan = get_loan(db, loan_id, lock=True)
    _ensure_owner_or_staff(actor, loan.user_id)
    pending = db.scalar(
        select(func.count()).where(
            Reservation.book_id == loan.copy.book_id,
            Reservation.status == ReservationStatus.EN_ATTENTE,
        )
    )
    previous = loan.due_date
    loan.due_date = rules.check_can_renew(
        policy(), loan.status, loan.renewals_count, loan.due_date, clock.today(), pending or 0
    )
    loan.renewals_count += 1
    audit.record(db, actor, "LOAN_RENEWED", "Loan", loan.id, before=previous, after=loan.due_date)
    db.commit()
    return loan


def declare_lost(db: Session, actor: Actor, loan_id: int) -> Loan:
    pol = policy()
    loan = get_loan(db, loan_id, lock=True)
    LOAN_WORKFLOW.assert_transition(loan.status, LoanStatus.PERDU)
    loan.status = LoanStatus.PERDU
    loan.returned_at = clock.now()
    _set_copy_status(loan.copy, CopyStatus.RETIRE)
    _add_penalty(db, loan, "PERTE", pol.lost_item_fee, f"Exemplaire perdu — {loan.copy.barcode}")
    audit.record(db, actor, "LOAN_LOST", "Loan", loan.id, fee=pol.lost_item_fee)
    db.commit()
    return loan


def list_loans(
    db: Session,
    *,
    user_id: int | None = None,
    status: LoanStatus | None = None,
    overdue_only: bool = False,
    q: str | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[Loan], int]:
    stmt = select(Loan).join(Loan.copy).join(Copy.book).join(Loan.user)
    if user_id:
        stmt = stmt.where(Loan.user_id == user_id)
    if status:
        stmt = stmt.where(Loan.status == status)
    if overdue_only:
        stmt = stmt.where(Loan.status.in_(ACTIVE_LOAN_STATUSES), Loan.due_date < clock.today())
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Copy.barcode.ilike(pattern),
                Book.title.ilike(pattern),
                User.full_name.ilike(pattern),
                User.email.ilike(pattern),
            )
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.options(joinedload(Loan.copy).joinedload(Copy.book), joinedload(Loan.user))
        .order_by(Loan.loaned_at.desc(), Loan.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return list(rows), total


# ------------------------------------------------------------------ réservations
def create_reservation(db: Session, actor: Actor, book_id: int, user_id: int) -> Reservation:
    _ensure_owner_or_staff(actor, user_id)
    book = db.get(Book, book_id)
    if book is None:
        raise NotFoundError("Ouvrage", book_id)
    member = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if member is None:
        raise NotFoundError("Adhérent", user_id)
    available = db.scalar(
        select(func.count()).where(Copy.book_id == book_id, Copy.status == CopyStatus.DISPONIBLE)
    )
    borrowing = db.scalar(
        select(func.count())
        .select_from(Loan)
        .join(Copy)
        .where(
            Loan.user_id == user_id, Copy.book_id == book_id, Loan.status.in_(ACTIVE_LOAN_STATUSES)
        )
    )
    reserved = db.scalar(
        select(func.count()).where(
            Reservation.user_id == user_id,
            Reservation.book_id == book_id,
            Reservation.status.in_(ACTIVE_RESERVATION_STATUSES),
        )
    )
    rules.check_can_reserve(
        policy(), member_state(db, member), available or 0, bool(borrowing), bool(reserved)
    )
    reservation = Reservation(
        book_id=book_id,
        user_id=user_id,
        created_at=clock.now(),
        status=ReservationStatus.EN_ATTENTE,
    )
    db.add(reservation)
    db.flush()
    audit.record(
        db,
        actor,
        "RESERVATION_CREATED",
        "Reservation",
        reservation.id,
        book_id=book_id,
        user_id=user_id,
    )
    db.commit()
    return reservation


def _release_held_copy(db: Session, reservation: Reservation) -> None:
    if reservation.copy is not None and reservation.copy.status == CopyStatus.RESERVE:
        copy = reservation.copy
        reservation.copy_id = None
        db.flush()
        assign_copy_to_queue(db, copy)


def cancel_reservation(db: Session, actor: Actor, reservation_id: int) -> Reservation:
    reservation = db.get(Reservation, reservation_id)
    if reservation is None:
        raise NotFoundError("Réservation", reservation_id)
    _ensure_owner_or_staff(actor, reservation.user_id)
    RESERVATION_WORKFLOW.assert_transition(reservation.status, ReservationStatus.ANNULEE)
    reservation.status = ReservationStatus.ANNULEE
    _release_held_copy(db, reservation)
    audit.record(db, actor, "RESERVATION_CANCELLED", "Reservation", reservation.id)
    db.commit()
    return reservation


def queue_positions(db: Session, reservations: list[Reservation]) -> dict[int, int]:
    """Position (1 = prochain servi) des réservations EN_ATTENTE dans la file de leur ouvrage."""
    waiting = [r for r in reservations if r.status == ReservationStatus.EN_ATTENTE]
    positions: dict[int, int] = {}
    for r in waiting:
        ahead = db.scalar(
            select(func.count()).where(
                Reservation.book_id == r.book_id,
                Reservation.status == ReservationStatus.EN_ATTENTE,
                or_(
                    Reservation.created_at < r.created_at,
                    (Reservation.created_at == r.created_at) & (Reservation.id < r.id),
                ),
            )
        )
        positions[r.id] = (ahead or 0) + 1
    return positions


def list_reservations(
    db: Session,
    *,
    user_id: int | None = None,
    status: ReservationStatus | None = None,
    book_id: int | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[Reservation], int]:
    stmt = select(Reservation)
    if user_id:
        stmt = stmt.where(Reservation.user_id == user_id)
    if status:
        stmt = stmt.where(Reservation.status == status)
    if book_id:
        stmt = stmt.where(Reservation.book_id == book_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.options(joinedload(Reservation.book), joinedload(Reservation.user))
        .order_by(Reservation.created_at.desc(), Reservation.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return list(rows), total


# ------------------------------------------------------------------ pénalités
def create_penalty(
    db: Session, actor: Actor, user_id: int, amount: Decimal, reason: str
) -> Penalty:
    if db.get(User, user_id) is None:
        raise NotFoundError("Adhérent", user_id)
    penalty = Penalty(user_id=user_id, kind="AUTRE", amount=amount, reason=reason)
    db.add(penalty)
    db.flush()
    audit.record(db, actor, "PENALTY_CREATED", "Penalty", penalty.id, amount=amount)
    db.commit()
    return penalty


def settle_penalty(db: Session, actor: Actor, penalty_id: int, target: PenaltyStatus) -> Penalty:
    penalty = db.get(Penalty, penalty_id)
    if penalty is None:
        raise NotFoundError("Pénalité", penalty_id)
    PENALTY_WORKFLOW.assert_transition(penalty.status, target)
    penalty.status = target
    penalty.settled_at = clock.now()
    action = "PENALTY_PAID" if target == PenaltyStatus.PAYEE else "PENALTY_CANCELLED"
    audit.record(db, actor, action, "Penalty", penalty.id, amount=penalty.amount)
    db.commit()
    return penalty


def list_penalties(
    db: Session,
    *,
    user_id: int | None = None,
    status: PenaltyStatus | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[Penalty], int]:
    stmt = select(Penalty)
    if user_id:
        stmt = stmt.where(Penalty.user_id == user_id)
    if status:
        stmt = stmt.where(Penalty.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.options(joinedload(Penalty.user))
        .order_by(Penalty.created_at.desc(), Penalty.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return list(rows), total


# ------------------------------------------------------------------ maintenance planifiée
def run_maintenance(db: Session) -> dict[str, int]:
    """Tâche idempotente : marque les retards (WF-01) et expire les réservations (RG-08)."""
    now = clock.now()
    overdue = db.scalars(
        select(Loan).where(Loan.status == LoanStatus.EN_COURS, Loan.due_date < now.date())
    ).all()
    for loan in overdue:
        LOAN_WORKFLOW.assert_transition(loan.status, LoanStatus.EN_RETARD)
        loan.status = LoanStatus.EN_RETARD
    expired = db.scalars(
        select(Reservation).where(
            Reservation.status == ReservationStatus.DISPONIBLE,
            Reservation.available_until < now,
        )
    ).all()
    for reservation in expired:
        RESERVATION_WORKFLOW.assert_transition(reservation.status, ReservationStatus.EXPIREE)
        reservation.status = ReservationStatus.EXPIREE
        _release_held_copy(db, reservation)
    if overdue or expired:
        audit.record(
            db,
            audit.SYSTEM,
            "MAINTENANCE_RUN",
            "System",
            None,
            overdue=len(overdue),
            expired=len(expired),
        )
    db.commit()
    return {"loans_marked_overdue": len(overdue), "reservations_expired": len(expired)}
