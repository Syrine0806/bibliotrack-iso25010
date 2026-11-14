"""Tests unitaires des règles métier pures (aucune base de données)."""

from datetime import date, datetime
from decimal import Decimal

import pytest

from app.core.config import Settings
from app.domain import rules
from app.domain.enums import CopyStatus, LoanStatus
from app.domain.errors import BusinessRuleError

POLICY = rules.LibraryPolicy()
OK_MEMBER = rules.MemberState(
    is_active=True,
    active_loans=0,
    unpaid_penalties=Decimal("0"),
    has_overdue_loan=False,
    active_reservations=0,
)


def member(**kw) -> rules.MemberState:
    return rules.MemberState(**{**OK_MEMBER.__dict__, **kw})


def assert_rule(code: str, fn, *args):
    with pytest.raises(BusinessRuleError) as exc:
        fn(*args)
    assert exc.value.code == code
    return exc.value


# ------------------------------------------------------------------ emprunt
class TestEligibiliteEmprunt:
    @pytest.mark.req("RG-04")
    def test_adherent_eligible_peut_emprunter_un_exemplaire_disponible(self):
        rules.check_can_borrow(POLICY, OK_MEMBER, CopyStatus.DISPONIBLE)

    @pytest.mark.req("RG-02")
    def test_quota_atteint_bloque_emprunt(self):
        err = assert_rule(
            "RG-02", rules.check_can_borrow, POLICY, member(active_loans=5), CopyStatus.DISPONIBLE
        )
        assert "5" in err.message

    @pytest.mark.req("RG-02")
    def test_quota_juste_en_dessous_autorise(self):
        rules.check_can_borrow(POLICY, member(active_loans=4), CopyStatus.DISPONIBLE)

    @pytest.mark.req("RG-03")
    def test_penalite_impayee_bloque_emprunt(self):
        assert_rule(
            "RG-03",
            rules.check_can_borrow,
            POLICY,
            member(unpaid_penalties=Decimal("0.50")),
            CopyStatus.DISPONIBLE,
        )

    @pytest.mark.req("RG-03")
    def test_emprunt_en_retard_bloque_emprunt(self):
        assert_rule(
            "RG-03",
            rules.check_can_borrow,
            POLICY,
            member(has_overdue_loan=True),
            CopyStatus.DISPONIBLE,
        )

    @pytest.mark.req("RG-11")
    def test_compte_inactif_bloque_emprunt(self):
        assert_rule(
            "RG-11", rules.check_can_borrow, POLICY, member(is_active=False), CopyStatus.DISPONIBLE
        )

    @pytest.mark.req("RG-04")
    @pytest.mark.parametrize(
        "status",
        [CopyStatus.EMPRUNTE, CopyStatus.EN_REPARATION, CopyStatus.RETIRE, CopyStatus.RESERVE],
    )
    def test_exemplaire_non_disponible_refuse(self, status):
        assert_rule("RG-04", rules.check_can_borrow, POLICY, OK_MEMBER, status)

    @pytest.mark.req("RG-04", "RG-08")
    def test_exemplaire_reserve_pour_cet_adherent_autorise(self):
        rules.check_can_borrow(POLICY, OK_MEMBER, CopyStatus.RESERVE, copy_held_for_member=True)


# ------------------------------------------------------------------ durée / prolongation
class TestProlongation:
    @pytest.mark.req("RG-05")
    def test_echeance_standard_21_jours(self):
        assert rules.compute_due_date(POLICY, date(2026, 1, 1)) == date(2026, 1, 22)

    @pytest.mark.req("RG-05")
    def test_prolongation_ajoute_14_jours(self):
        new_due = rules.check_can_renew(
            POLICY,
            LoanStatus.EN_COURS,
            0,
            date(2026, 1, 22),
            date(2026, 1, 20),
            pending_reservations=0,
        )
        assert new_due == date(2026, 2, 5)

    @pytest.mark.req("RG-05")
    def test_prolongation_le_jour_de_l_echeance_autorisee(self):
        rules.check_can_renew(
            POLICY, LoanStatus.EN_COURS, 0, date(2026, 1, 22), date(2026, 1, 22), 0
        )

    @pytest.mark.req("RG-05")
    def test_seconde_prolongation_refusee(self):
        assert_rule(
            "RG-05",
            rules.check_can_renew,
            POLICY,
            LoanStatus.EN_COURS,
            1,
            date(2026, 1, 22),
            date(2026, 1, 20),
            0,
        )

    @pytest.mark.req("RG-05")
    def test_prolongation_refusee_si_retard(self):
        assert_rule(
            "RG-05",
            rules.check_can_renew,
            POLICY,
            LoanStatus.EN_COURS,
            0,
            date(2026, 1, 22),
            date(2026, 1, 23),
            0,
        )

    @pytest.mark.req("RG-05")
    def test_prolongation_refusee_si_reservation_en_attente(self):
        assert_rule(
            "RG-05",
            rules.check_can_renew,
            POLICY,
            LoanStatus.EN_COURS,
            0,
            date(2026, 1, 22),
            date(2026, 1, 20),
            2,
        )

    @pytest.mark.req("RG-05")
    @pytest.mark.parametrize("status", [LoanStatus.RENDU, LoanStatus.PERDU, LoanStatus.EN_RETARD])
    def test_prolongation_refusee_si_emprunt_non_en_cours(self, status):
        assert_rule(
            "RG-05",
            rules.check_can_renew,
            POLICY,
            status,
            0,
            date(2026, 1, 22),
            date(2026, 1, 20),
            0,
        )


# ------------------------------------------------------------------ pénalités
class TestPenalites:
    @pytest.mark.req("RG-06")
    @pytest.mark.parametrize(
        ("returned", "expected"),
        [
            (date(2026, 1, 21), "0.00"),  # en avance
            (date(2026, 1, 22), "0.00"),  # le jour même
            (date(2026, 1, 23), "0.50"),  # 1 jour
            (date(2026, 2, 1), "5.00"),  # 10 jours
            (date(2026, 3, 2), "19.50"),  # 39 jours
            (date(2026, 3, 3), "20.00"),  # 40 jours = plafond exact
            (date(2026, 12, 31), "20.00"),  # au-delà : plafonné
        ],
    )
    def test_calcul_penalite_retard(self, returned, expected):
        assert rules.compute_late_fee(POLICY, date(2026, 1, 22), returned) == Decimal(expected)

    @pytest.mark.req("RG-06")
    def test_jours_de_retard_jamais_negatifs(self):
        assert rules.days_late(date(2026, 1, 22), date(2026, 1, 1)) == 0

    @pytest.mark.req("WF-01")
    def test_detection_retard(self):
        assert rules.is_overdue(LoanStatus.EN_COURS, date(2026, 1, 22), date(2026, 1, 23))
        assert not rules.is_overdue(LoanStatus.EN_COURS, date(2026, 1, 22), date(2026, 1, 22))
        assert not rules.is_overdue(LoanStatus.RENDU, date(2026, 1, 22), date(2026, 3, 1))


# ------------------------------------------------------------------ réservation
class TestReservation:
    @pytest.mark.req("RG-07")
    def test_reservation_autorisee_si_aucun_exemplaire_disponible(self):
        rules.check_can_reserve(POLICY, OK_MEMBER, 0, False, False)

    @pytest.mark.req("RG-07")
    def test_reservation_refusee_si_exemplaire_disponible(self):
        assert_rule("RG-07", rules.check_can_reserve, POLICY, OK_MEMBER, 1, False, False)

    @pytest.mark.req("RG-07")
    def test_reservation_refusee_si_deja_reserve(self):
        assert_rule("RG-07", rules.check_can_reserve, POLICY, OK_MEMBER, 0, False, True)

    @pytest.mark.req("RG-07")
    def test_reservation_refusee_si_deja_emprunte(self):
        assert_rule("RG-07", rules.check_can_reserve, POLICY, OK_MEMBER, 0, True, False)

    @pytest.mark.req("RG-07")
    def test_maximum_trois_reservations(self):
        assert_rule(
            "RG-07", rules.check_can_reserve, POLICY, member(active_reservations=3), 0, False, False
        )

    @pytest.mark.req("RG-11")
    def test_reservation_refusee_si_compte_inactif(self):
        assert_rule(
            "RG-11", rules.check_can_reserve, POLICY, member(is_active=False), 0, False, False
        )

    @pytest.mark.req("RG-08")
    def test_delai_de_mise_de_cote_trois_jours(self):
        assert rules.hold_deadline(POLICY, datetime(2026, 1, 1, 10)) == datetime(2026, 1, 4, 10)


@pytest.mark.req("EQ-POR-02")
def test_politique_construite_depuis_la_configuration():
    settings = Settings(max_active_loans=2, late_fee_per_day="1.00", late_fee_cap="3.00")
    policy = rules.LibraryPolicy.from_settings(settings)
    assert policy.max_active_loans == 2
    assert rules.compute_late_fee(policy, date(2026, 1, 1), date(2026, 1, 10)) == Decimal("3.00")
