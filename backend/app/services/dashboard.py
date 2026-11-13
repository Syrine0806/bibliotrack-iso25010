"""Tableau de bord : indicateurs agrégés, filtrables par période et catégorie."""

from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import String, cast, func, select
from sqlalchemy.orm import Session

from app.core import clock
from app.domain.enums import (
    ACTIVE_LOAN_STATUSES,
    CopyStatus,
    PenaltyStatus,
    ReservationStatus,
    Role,
)
from app.models import Book, Category, Copy, Loan, Penalty, Reservation, User
from app.schemas import CountItem, DashboardOut


def _count(db: Session, stmt) -> int:
    return int(db.scalar(stmt) or 0)


def _months_between(start: date, end: date) -> list[str]:
    months, cursor = [], date(start.year, start.month, 1)
    while cursor <= end:
        months.append(cursor.strftime("%Y-%m"))
        cursor = date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)
    return months


def build_dashboard(
    db: Session,
    date_from: date | None = None,
    date_to: date | None = None,
    category_id: int | None = None,
) -> DashboardOut:
    today = clock.today()
    date_to = date_to or today
    date_from = date_from or (date_to - timedelta(days=180))
    start, end = datetime.combine(date_from, time.min), datetime.combine(date_to, time.max)

    def scoped_books(stmt):
        return stmt.where(Book.category_id == category_id) if category_id else stmt

    total_books = _count(db, scoped_books(select(func.count(Book.id))))
    copies_q = select(func.count(Copy.id)).join(Book).where(Copy.status != CopyStatus.RETIRE)
    total_copies = _count(db, scoped_books(copies_q))
    available = _count(db, scoped_books(copies_q.where(Copy.status == CopyStatus.DISPONIBLE)))

    loans_base = select(func.count(Loan.id)).join(Copy).join(Book)
    active_loans = _count(db, scoped_books(loans_base.where(Loan.status.in_(ACTIVE_LOAN_STATUSES))))
    overdue = _count(
        db,
        scoped_books(
            loans_base.where(Loan.status.in_(ACTIVE_LOAN_STATUSES), Loan.due_date < today)
        ),
    )
    in_period = _count(db, scoped_books(loans_base.where(Loan.loaned_at.between(start, end))))

    month_expr = func.substr(cast(Loan.loaned_at, String), 1, 7)  # "AAAA-MM" (SQLite & PG)
    by_month_rows = db.execute(
        scoped_books(
            select(month_expr, func.count(Loan.id))
            .join(Copy)
            .join(Book)
            .where(Loan.loaned_at.between(start, end))
            .group_by(month_expr)
        )
    ).all()
    by_month = {m: int(c) for m, c in by_month_rows}
    loans_by_month = [
        CountItem(label=m, value=by_month.get(m, 0)) for m in _months_between(date_from, date_to)
    ]

    top_rows = db.execute(
        scoped_books(
            select(Book.title, func.count(Loan.id).label("n"))
            .join(Copy, Copy.book_id == Book.id)
            .join(Loan, Loan.copy_id == Copy.id)
            .where(Loan.loaned_at.between(start, end))
            .group_by(Book.id, Book.title)
            .order_by(func.count(Loan.id).desc(), Book.title)
            .limit(5)
        )
    ).all()

    cat_rows = db.execute(
        scoped_books(
            select(Category.name, func.count(Loan.id))
            .select_from(Loan)
            .join(Copy)
            .join(Book)
            .join(Category)
            .where(Loan.loaned_at.between(start, end))
            .group_by(Category.name)
            .order_by(func.count(Loan.id).desc())
        )
    ).all()

    status_rows = db.execute(
        scoped_books(select(Copy.status, func.count(Copy.id)).join(Book).group_by(Copy.status))
    ).all()

    unpaid = db.scalar(
        select(func.coalesce(func.sum(Penalty.amount), 0)).where(
            Penalty.status == PenaltyStatus.IMPAYEE
        )
    )
    return DashboardOut(
        total_books=total_books,
        total_copies=total_copies,
        available_copies=available,
        active_loans=active_loans,
        overdue_loans=overdue,
        active_members=_count(
            db, select(func.count(User.id)).where(User.role == Role.ADHERENT, User.is_active)
        ),
        pending_reservations=_count(
            db,
            select(func.count(Reservation.id)).where(
                Reservation.status == ReservationStatus.EN_ATTENTE
            ),
        ),
        unpaid_penalties_total=Decimal(str(unpaid or 0)).quantize(Decimal("0.01")),
        loans_in_period=in_period,
        loans_by_month=loans_by_month,
        top_books=[CountItem(label=t, value=int(n)) for t, n in top_rows],
        loans_by_category=[CountItem(label=n, value=int(c)) for n, c in cat_rows],
        copies_by_status=[CountItem(label=str(s), value=int(c)) for s, c in status_rows],
    )
