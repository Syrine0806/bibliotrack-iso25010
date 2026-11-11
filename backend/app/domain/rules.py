"""Règles métier pures (sans I/O) — référentiel : docs/REGLES_METIER.md.

Chaque fonction lève `BusinessRuleError` avec le code de la règle violée,
ce qui permet de tracer exigence ↔ test ↔ résultat.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from app.core.config import Settings
from app.domain.enums import CopyStatus, LoanStatus
from app.domain.errors import BusinessRuleError

CENT = Decimal("0.01")


@dataclass(frozen=True)
class LibraryPolicy:
    max_active_loans: int = 5
    loan_duration_days: int = 21
    renewal_days: int = 14
    max_renewals: int = 1
    late_fee_per_day: Decimal = Decimal("0.50")
    late_fee_cap: Decimal = Decimal("20.00")
    lost_item_fee: Decimal = Decimal("30.00")
    max_active_reservations: int = 3
    reservation_hold_days: int = 3

    @classmethod
    def from_settings(cls, s: Settings) -> "LibraryPolicy":
        return cls(
            max_active_loans=s.max_active_loans,
            loan_duration_days=s.loan_duration_days,
            renewal_days=s.renewal_days,
            max_renewals=s.max_renewals,
            late_fee_per_day=Decimal(s.late_fee_per_day),
            late_fee_cap=Decimal(s.late_fee_cap),
            lost_item_fee=Decimal(s.lost_item_fee),
            max_active_reservations=s.max_active_reservations,
            reservation_hold_days=s.reservation_hold_days,
        )


@dataclass(frozen=True)
class MemberState:
    """Photographie de la situation d'un adhérent au moment de la décision."""

    is_active: bool
    active_loans: int
    unpaid_penalties: Decimal
    has_overdue_loan: bool
    active_reservations: int = 0


# --------------------------------------------------------------------------- emprunt
def check_can_borrow(
    policy: LibraryPolicy,
    member: MemberState,
    copy_status: CopyStatus,
    copy_held_for_member: bool = False,
) -> None:
    """RG-02, RG-03, RG-04, RG-11 : éligibilité d'un adhérent à l'emprunt d'un exemplaire."""
    if not member.is_active:
        raise BusinessRuleError("RG-11", "Compte adhérent inactif : emprunt impossible.")
    if member.unpaid_penalties > 0:
        raise BusinessRuleError(
            "RG-03",
            f"Pénalités impayées ({member.unpaid_penalties} €) : régularisation requise.",
        )
    if member.has_overdue_loan:
        raise BusinessRuleError(
            "RG-03", "Un emprunt est en retard : retour requis avant tout prêt."
        )
    if member.active_loans >= policy.max_active_loans:
        raise BusinessRuleError(
            "RG-02", f"Quota atteint : {policy.max_active_loans} emprunts simultanés maximum."
        )
    if copy_status == CopyStatus.RESERVE and copy_held_for_member:
        return
    if copy_status != CopyStatus.DISPONIBLE:
        raise BusinessRuleError(
            "RG-04", f"Exemplaire non empruntable (statut actuel : {copy_status})."
        )


def compute_due_date(policy: LibraryPolicy, loaned_on: date) -> date:
    """RG-05 : durée de prêt standard."""
    return loaned_on + timedelta(days=policy.loan_duration_days)


def check_can_renew(
    policy: LibraryPolicy,
    status: LoanStatus,
    renewals_count: int,
    due_date: date,
    today: date,
    pending_reservations: int,
) -> date:
    """RG-05 : prolongation unique, refusée si retard ou réservation en attente.

    Retourne la nouvelle date d'échéance.
    """
    if status != LoanStatus.EN_COURS or today > due_date:
        raise BusinessRuleError("RG-05", "Prolongation impossible : emprunt en retard ou clos.")
    if renewals_count >= policy.max_renewals:
        raise BusinessRuleError(
            "RG-05", f"Nombre maximal de prolongations atteint ({policy.max_renewals})."
        )
    if pending_reservations > 0:
        raise BusinessRuleError(
            "RG-05", "Prolongation impossible : l'ouvrage est réservé par un autre adhérent."
        )
    return due_date + timedelta(days=policy.renewal_days)


# --------------------------------------------------------------------------- pénalités
def days_late(due_date: date, returned_on: date) -> int:
    return max(0, (returned_on - due_date).days)


def compute_late_fee(policy: LibraryPolicy, due_date: date, returned_on: date) -> Decimal:
    """RG-06 : 0,50 €/jour de retard, plafonné à 20 €."""
    fee = policy.late_fee_per_day * days_late(due_date, returned_on)
    return min(fee, policy.late_fee_cap).quantize(CENT, rounding=ROUND_HALF_UP)


def is_overdue(status: LoanStatus, due_date: date, today: date) -> bool:
    return status in (LoanStatus.EN_COURS, LoanStatus.EN_RETARD) and today > due_date


# --------------------------------------------------------------------------- réservation
def check_can_reserve(
    policy: LibraryPolicy,
    member: MemberState,
    available_copies: int,
    already_borrowing_book: bool,
    already_reserved_book: bool,
) -> None:
    """RG-07 : conditions de réservation d'un ouvrage."""
    if not member.is_active:
        raise BusinessRuleError("RG-11", "Compte adhérent inactif : réservation impossible.")
    if already_reserved_book:
        raise BusinessRuleError("RG-07", "Vous avez déjà une réservation active pour cet ouvrage.")
    if already_borrowing_book:
        raise BusinessRuleError("RG-07", "Vous empruntez déjà un exemplaire de cet ouvrage.")
    if available_copies > 0:
        raise BusinessRuleError(
            "RG-07", "Un exemplaire est disponible : empruntez-le directement au comptoir."
        )
    if member.active_reservations >= policy.max_active_reservations:
        raise BusinessRuleError(
            "RG-07",
            f"Maximum {policy.max_active_reservations} réservations actives par adhérent.",
        )


def hold_deadline(policy: LibraryPolicy, made_available_at: datetime) -> datetime:
    """RG-08 : un exemplaire mis de côté est conservé N jours."""
    return made_available_at + timedelta(days=policy.reservation_hold_days)
