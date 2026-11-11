"""Workflows à statuts : table de transitions explicite et vérifiable (WF-01..WF-03)."""

from collections.abc import Mapping
from enum import StrEnum

from app.domain.enums import CopyStatus, LoanStatus, PenaltyStatus, ReservationStatus
from app.domain.errors import InvalidTransitionError


class StateMachine[S: StrEnum]:
    def __init__(self, entity: str, transitions: Mapping[S, frozenset[S]]) -> None:
        self.entity = entity
        self.transitions = transitions

    def can_transition(self, current: S, target: S) -> bool:
        return target in self.transitions.get(current, frozenset())

    def assert_transition(self, current: S, target: S) -> None:
        if not self.can_transition(current, target):
            raise InvalidTransitionError(self.entity, str(current), str(target))

    def is_terminal(self, state: S) -> bool:
        return not self.transitions.get(state)


# WF-01 : cycle de vie d'un emprunt
LOAN_WORKFLOW = StateMachine[LoanStatus](
    "Emprunt",
    {
        LoanStatus.EN_COURS: frozenset({LoanStatus.EN_RETARD, LoanStatus.RENDU, LoanStatus.PERDU}),
        LoanStatus.EN_RETARD: frozenset({LoanStatus.RENDU, LoanStatus.PERDU}),
        LoanStatus.RENDU: frozenset(),
        LoanStatus.PERDU: frozenset(),
    },
)

# WF-02 : cycle de vie d'une réservation (file d'attente FIFO)
RESERVATION_WORKFLOW = StateMachine[ReservationStatus](
    "Réservation",
    {
        ReservationStatus.EN_ATTENTE: frozenset(
            {ReservationStatus.DISPONIBLE, ReservationStatus.ANNULEE}
        ),
        ReservationStatus.DISPONIBLE: frozenset(
            {ReservationStatus.HONOREE, ReservationStatus.ANNULEE, ReservationStatus.EXPIREE}
        ),
        ReservationStatus.HONOREE: frozenset(),
        ReservationStatus.ANNULEE: frozenset(),
        ReservationStatus.EXPIREE: frozenset(),
    },
)

# WF-03 : cycle de vie d'une pénalité
PENALTY_WORKFLOW = StateMachine[PenaltyStatus](
    "Pénalité",
    {
        PenaltyStatus.IMPAYEE: frozenset({PenaltyStatus.PAYEE, PenaltyStatus.ANNULEE}),
        PenaltyStatus.PAYEE: frozenset(),
        PenaltyStatus.ANNULEE: frozenset(),
    },
)

# Cycle de vie physique d'un exemplaire
COPY_WORKFLOW = StateMachine[CopyStatus](
    "Exemplaire",
    {
        CopyStatus.DISPONIBLE: frozenset(
            {CopyStatus.EMPRUNTE, CopyStatus.RESERVE, CopyStatus.EN_REPARATION, CopyStatus.RETIRE}
        ),
        CopyStatus.EMPRUNTE: frozenset(
            {CopyStatus.DISPONIBLE, CopyStatus.RESERVE, CopyStatus.RETIRE}
        ),
        CopyStatus.RESERVE: frozenset({CopyStatus.EMPRUNTE, CopyStatus.DISPONIBLE}),
        CopyStatus.EN_REPARATION: frozenset({CopyStatus.DISPONIBLE, CopyStatus.RETIRE}),
        CopyStatus.RETIRE: frozenset(),
    },
)
