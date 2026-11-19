"""Tests de fiabilité (ISO 25010 §6.5) : atomicité, concurrence, panne, reprise, répétition."""

import threading
from datetime import datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import sessionmaker

import app.core.database as database
from app.core import clock
from app.domain.enums import LoanStatus
from app.domain.errors import BusinessRuleError
from app.main import app
from app.models import AuditLog, Copy, Loan, Penalty
from app.services import audit, circulation
from tests.conftest import ADMIN_ACTOR


@pytest.fixture
def unsafe_client():
    """Client qui renvoie la réponse 500 au lieu de relancer l'exception côté test."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _fail_on(monkeypatch, action_to_break: str):
    original = audit.record

    def flaky(db, actor, action, *args, **kwargs):
        if action == action_to_break:
            raise RuntimeError(f"Panne simulée pendant {action}")
        return original(db, actor, action, *args, **kwargs)

    monkeypatch.setattr(audit, "record", flaky)


# ------------------------------------------------------------------ atomicité
@pytest.mark.req("EQ-FIA-01")
def test_panne_pendant_un_emprunt_aucune_donnee_partielle(
    unsafe_client, make, staff, member, db, monkeypatch
):
    book = make.book(copies=1)
    _fail_on(monkeypatch, "LOAN_CREATED")  # panne APRÈS le changement de statut
    r = unsafe_client.post(
        "/api/loans",
        json={"user_id": member[0].id, "barcode": make.barcode(book)},
        headers=staff[1],
    )
    assert r.status_code == 500 and r.json() == {"detail": "Erreur interne."}
    db.expire_all()
    copy = db.scalar(select(Copy).where(Copy.book_id == book.id))
    assert copy.status == "DISPONIBLE"  # rollback complet
    assert db.scalar(select(func.count(Loan.id))) == 0
    monkeypatch.undo()
    # Le système reste utilisable : l'opération réussit à la tentative suivante
    r = unsafe_client.post(
        "/api/loans",
        json={"user_id": member[0].id, "barcode": make.barcode(book)},
        headers=staff[1],
    )
    assert r.status_code == 201


@pytest.mark.req("EQ-FIA-01")
def test_panne_pendant_un_retour_ni_penalite_ni_changement(
    unsafe_client, make, staff, member, db, monkeypatch
):
    loan = make.loan(member[0], make.book(), at=datetime(2026, 3, 1, 10))
    clock.freeze(datetime(2026, 4, 15, 10))  # en retard → une pénalité serait créée
    _fail_on(monkeypatch, "LOAN_RETURNED")
    r = unsafe_client.post(f"/api/loans/{loan.id}/return", headers=staff[1])
    assert r.status_code == 500
    db.expire_all()
    assert db.get(Loan, loan.id).status == LoanStatus.EN_COURS
    assert db.get(Copy, loan.copy_id).status == "EMPRUNTE"
    assert db.scalar(select(func.count(Penalty.id))) == 0
    assert db.scalar(select(func.count(AuditLog.id)).where(AuditLog.action == "LOAN_RETURNED")) == 0


@pytest.mark.req("EQ-FIA-01")
def test_erreur_metier_ne_laisse_aucune_trace(client, make, staff, member, db):
    make.penalty(member[0])
    book = make.book()
    before = db.scalar(select(func.count(AuditLog.id)))
    r = client.post(
        "/api/loans",
        json={"user_id": member[0].id, "barcode": make.barcode(book)},
        headers=staff[1],
    )
    assert r.status_code == 409
    assert db.scalar(select(func.count(AuditLog.id))) == before
    assert db.scalar(select(func.count(Loan.id))) == 0


# ------------------------------------------------------------------ concurrence
@pytest.mark.req("EQ-FIA-02")
def test_emprunts_concurrents_du_meme_exemplaire_un_seul_gagnant(make, db):
    book = make.book(copies=1)
    members = [make.user() for _ in range(10)]
    barcode = make.barcode(book)
    barrier = threading.Barrier(len(members))
    outcomes: list[str] = []
    lock = threading.Lock()

    def attempt(user_id: int) -> None:
        session = database.SessionLocal()
        try:
            barrier.wait()
            circulation.create_loan(session, ADMIN_ACTOR, user_id, barcode)
            result = "ok"
        except BusinessRuleError as exc:
            result = exc.code
        except (IntegrityError, OperationalError):
            result = "rejet-base"
        finally:
            session.rollback()
            session.close()
        with lock:
            outcomes.append(result)

    threads = [threading.Thread(target=attempt, args=(m.id,)) for m in members]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert outcomes.count("ok") == 1, outcomes
    db.expire_all()
    active = db.scalar(select(func.count(Loan.id)).where(Loan.status == LoanStatus.EN_COURS))
    assert active == 1  # invariant : jamais deux prêts actifs pour un exemplaire


@pytest.mark.req("EQ-FIA-02", "EQ-FIA-05")
def test_contrainte_base_un_seul_pret_actif_par_exemplaire(make, db):
    """Défense en profondeur : même en contournant le service, la base refuse."""
    book = make.book(copies=1)
    loan = make.loan(make.user(), book)
    db.add(
        Loan(
            copy_id=loan.copy_id,
            user_id=make.user().id,
            due_date=loan.due_date,
            status=LoanStatus.EN_COURS,
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


@pytest.mark.req("EQ-FIA-05")
def test_contrainte_base_une_seule_penalite_de_retard_par_emprunt(make, db):
    loan = make.loan(make.user(), make.book())
    for _ in range(2):
        db.add(
            Penalty(
                user_id=loan.user_id,
                loan_id=loan.id,
                kind="RETARD",
                amount=Decimal("1.00"),
                reason="doublon",
            )
        )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


# ------------------------------------------------------------------ panne / reprise
@pytest.mark.req("EQ-FIA-03")
def test_base_indisponible_reponse_503_puis_reprise(unsafe_client, monkeypatch, member):
    broken_engine = create_engine("sqlite:////chemin/inexistant/biblio.db")
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=broken_engine))
    r = unsafe_client.get("/api/health")
    assert r.status_code == 503
    assert "indisponible" in r.json()["detail"]
    assert "sqlite" not in r.text.lower()  # pas de fuite d'information technique
    r = unsafe_client.get("/api/books", headers=member[1])
    assert r.status_code == 503
    monkeypatch.undo()  # la base « revient »
    assert unsafe_client.get("/api/health").status_code == 200
    assert unsafe_client.get("/api/books", headers=member[1]).status_code == 200


@pytest.mark.req("EQ-FIA-05")
def test_cycles_repetes_emprunt_retour_etat_coherent(client, make, staff, db):
    book = make.book(copies=1)
    members = [make.user() for _ in range(5)]
    for i in range(30):
        r = client.post(
            "/api/loans",
            json={"user_id": members[i % 5].id, "barcode": make.barcode(book)},
            headers=staff[1],
        )
        assert r.status_code == 201, r.text
        assert (
            client.post(f"/api/loans/{r.json()['id']}/return", headers=staff[1]).status_code == 200
        )
    db.expire_all()
    assert db.scalar(select(func.count(Loan.id)).where(Loan.status == LoanStatus.RENDU)) == 30
    assert db.scalar(select(Copy.status).where(Copy.book_id == book.id)) == "DISPONIBLE"
    assert db.scalar(select(func.count(Penalty.id))) == 0


@pytest.mark.req("EQ-FIA-05")
def test_maintenance_idempotente_sans_effet_de_bord(make, db):
    make.loan(make.user(), make.book(), at=datetime(2026, 1, 1))
    clock.freeze(datetime(2026, 3, 1))
    results = [circulation.run_maintenance(db) for _ in range(3)]
    assert [r["loans_marked_overdue"] for r in results] == [1, 0, 0]
    assert (
        db.scalar(select(func.count(AuditLog.id)).where(AuditLog.action == "MAINTENANCE_RUN")) == 1
    )
