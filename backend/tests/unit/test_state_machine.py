import pytest

from app.domain.enums import CopyStatus, LoanStatus, PenaltyStatus, ReservationStatus
from app.domain.errors import InvalidTransitionError
from app.domain.state_machine import (
    COPY_WORKFLOW,
    LOAN_WORKFLOW,
    PENALTY_WORKFLOW,
    RESERVATION_WORKFLOW,
)

L, R, P = LoanStatus, ReservationStatus, PenaltyStatus


@pytest.mark.req("WF-01")
@pytest.mark.parametrize(
    ("src", "dst", "allowed"),
    [
        (L.EN_COURS, L.RENDU, True),
        (L.EN_COURS, L.EN_RETARD, True),
        (L.EN_COURS, L.PERDU, True),
        (L.EN_RETARD, L.RENDU, True),
        (L.EN_RETARD, L.PERDU, True),
        (L.RENDU, L.EN_COURS, False),
        (L.RENDU, L.PERDU, False),
        (L.PERDU, L.RENDU, False),
        (L.EN_RETARD, L.EN_COURS, False),
        (L.RENDU, L.RENDU, False),
    ],
)
def test_workflow_emprunt(src, dst, allowed):
    assert LOAN_WORKFLOW.can_transition(src, dst) is allowed


@pytest.mark.req("WF-02")
@pytest.mark.parametrize(
    ("src", "dst", "allowed"),
    [
        (R.EN_ATTENTE, R.DISPONIBLE, True),
        (R.EN_ATTENTE, R.ANNULEE, True),
        (R.DISPONIBLE, R.HONOREE, True),
        (R.DISPONIBLE, R.EXPIREE, True),
        (R.DISPONIBLE, R.ANNULEE, True),
        (R.EN_ATTENTE, R.HONOREE, False),
        (R.EN_ATTENTE, R.EXPIREE, False),
        (R.HONOREE, R.ANNULEE, False),
        (R.ANNULEE, R.EN_ATTENTE, False),
        (R.EXPIREE, R.DISPONIBLE, False),
    ],
)
def test_workflow_reservation(src, dst, allowed):
    assert RESERVATION_WORKFLOW.can_transition(src, dst) is allowed


@pytest.mark.req("WF-03")
@pytest.mark.parametrize(
    ("src", "dst", "allowed"),
    [
        (P.IMPAYEE, P.PAYEE, True),
        (P.IMPAYEE, P.ANNULEE, True),
        (P.PAYEE, P.IMPAYEE, False),
        (P.PAYEE, P.ANNULEE, False),
        (P.ANNULEE, P.PAYEE, False),
    ],
)
def test_workflow_penalite(src, dst, allowed):
    assert PENALTY_WORKFLOW.can_transition(src, dst) is allowed


@pytest.mark.req("WF-01")
def test_transition_interdite_leve_erreur_explicite():
    with pytest.raises(InvalidTransitionError) as exc:
        LOAN_WORKFLOW.assert_transition(L.RENDU, L.EN_COURS)
    assert exc.value.code == "WF-TRANSITION"
    assert "RENDU" in exc.value.message and "EN_COURS" in exc.value.message


@pytest.mark.req("WF-01", "WF-02", "WF-03")
def test_etats_terminaux():
    assert LOAN_WORKFLOW.is_terminal(L.RENDU) and LOAN_WORKFLOW.is_terminal(L.PERDU)
    assert not LOAN_WORKFLOW.is_terminal(L.EN_COURS)
    assert RESERVATION_WORKFLOW.is_terminal(R.HONOREE)
    assert PENALTY_WORKFLOW.is_terminal(P.PAYEE)
    assert COPY_WORKFLOW.is_terminal(CopyStatus.RETIRE)


@pytest.mark.req("RG-04")
def test_exemplaire_retire_ne_revient_jamais_en_circulation():
    for target in CopyStatus:
        assert not COPY_WORKFLOW.can_transition(CopyStatus.RETIRE, target)
