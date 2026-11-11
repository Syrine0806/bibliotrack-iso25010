from enum import StrEnum


class Role(StrEnum):
    ADMIN = "ADMIN"
    BIBLIOTHECAIRE = "BIBLIOTHECAIRE"
    ADHERENT = "ADHERENT"


class CopyStatus(StrEnum):
    DISPONIBLE = "DISPONIBLE"
    EMPRUNTE = "EMPRUNTE"
    RESERVE = "RESERVE"
    EN_REPARATION = "EN_REPARATION"
    RETIRE = "RETIRE"


class LoanStatus(StrEnum):
    EN_COURS = "EN_COURS"
    EN_RETARD = "EN_RETARD"
    RENDU = "RENDU"
    PERDU = "PERDU"


class ReservationStatus(StrEnum):
    EN_ATTENTE = "EN_ATTENTE"
    DISPONIBLE = "DISPONIBLE"
    HONOREE = "HONOREE"
    ANNULEE = "ANNULEE"
    EXPIREE = "EXPIREE"


class PenaltyStatus(StrEnum):
    IMPAYEE = "IMPAYEE"
    PAYEE = "PAYEE"
    ANNULEE = "ANNULEE"


ACTIVE_LOAN_STATUSES = (LoanStatus.EN_COURS, LoanStatus.EN_RETARD)
ACTIVE_RESERVATION_STATUSES = (ReservationStatus.EN_ATTENTE, ReservationStatus.DISPONIBLE)
