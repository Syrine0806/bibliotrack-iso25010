"""Workflow d'emprunt WF-01 et règles RG-02 à RG-06, RG-11 au travers de l'API."""

from datetime import datetime

import pytest

from app.core import clock
from app.models import AuditLog, Copy, Penalty

T0 = datetime(2026, 3, 2, 10, 0)


def borrow(client, headers, user_id, barcode):
    return client.post("/api/loans", json={"user_id": user_id, "barcode": barcode}, headers=headers)


@pytest.mark.req("EF-08", "WF-01", "RG-05")
def test_emprunt_nominal(client, make, staff, member, db):
    clock.freeze(T0)
    book = make.book(copies=1)
    r = borrow(client, staff[1], member[0].id, make.barcode(book))
    assert r.status_code == 201, r.text
    loan = r.json()
    assert loan["status"] == "EN_COURS" and loan["due_date"] == "2026-03-23"
    assert loan["item"]["book"]["id"] == book.id and loan["user"]["id"] == member[0].id
    copy = db.query(Copy).filter_by(barcode=make.barcode(book)).one()
    assert copy.status == "EMPRUNTE"
    assert db.query(AuditLog).filter_by(action="LOAN_CREATED", entity_id=str(loan["id"])).count()


@pytest.mark.req("RG-04")
def test_exemplaire_deja_emprunte_refuse(client, make, staff):
    book = make.book(copies=1)
    make.loan(make.user(), book)
    r = borrow(client, staff[1], make.user().id, make.barcode(book))
    assert r.status_code == 409 and r.json()["code"] == "RG-04"


@pytest.mark.req("RG-04")
def test_code_barres_ou_adherent_inconnu(client, make, staff):
    book = make.book(copies=1)
    assert borrow(client, staff[1], make.user().id, "INCONNU-1").status_code == 404
    assert borrow(client, staff[1], 999999, make.barcode(book)).status_code == 404


@pytest.mark.req("RG-02")
def test_quota_de_cinq_emprunts(client, make, staff, member):
    books = [make.book(copies=1) for _ in range(6)]
    for b in books[:5]:
        assert borrow(client, staff[1], member[0].id, make.barcode(b)).status_code == 201
    r = borrow(client, staff[1], member[0].id, make.barcode(books[5]))
    assert r.status_code == 409 and r.json()["code"] == "RG-02"


@pytest.mark.req("RG-03")
def test_penalite_impayee_bloque_puis_paiement_debloque(client, make, staff, member):
    penalty = make.penalty(member[0], "2.00")
    book = make.book(copies=1)
    r = borrow(client, staff[1], member[0].id, make.barcode(book))
    assert r.status_code == 409 and r.json()["code"] == "RG-03"
    assert client.post(f"/api/penalties/{penalty.id}/pay", headers=staff[1]).status_code == 200
    assert borrow(client, staff[1], member[0].id, make.barcode(book)).status_code == 201


@pytest.mark.req("RG-03")
def test_emprunt_en_retard_bloque_nouvel_emprunt(client, make, staff, member):
    b1, b2 = make.book(), make.book()
    make.loan(member[0], b1, at=T0)
    clock.freeze(datetime(2026, 3, 24, 9, 0))  # échéance 23/03 dépassée
    r = borrow(client, staff[1], member[0].id, make.barcode(b2))
    assert r.status_code == 409 and r.json()["code"] == "RG-03"


@pytest.mark.req("RG-11")
def test_adherent_inactif_ne_peut_pas_emprunter(client, make, staff, db):
    user = make.user()
    user.is_active = False
    db.commit()
    r = borrow(client, staff[1], user.id, make.barcode(make.book()))
    assert r.status_code == 409 and r.json()["code"] == "RG-11"


@pytest.mark.req("EF-08", "WF-01", "RG-06")
def test_retour_a_l_heure_sans_penalite(client, make, staff, member, db):
    loan = make.loan(member[0], make.book(), at=T0)
    clock.freeze(datetime(2026, 3, 23, 18, 0))
    r = client.post(f"/api/loans/{loan.id}/return", headers=staff[1])
    assert r.status_code == 200
    body = r.json()
    assert body["loan"]["status"] == "RENDU" and body["penalty_amount"] == "0.00"
    assert body["days_late"] == 0
    assert db.query(Penalty).count() == 0
    db.expire_all()
    assert db.get(Copy, loan.copy_id).status == "DISPONIBLE"


@pytest.mark.req("EF-08", "WF-01", "RG-06", "EF-10")
def test_retour_en_retard_genere_penalite(client, make, staff, member, db):
    loan = make.loan(member[0], make.book(), at=T0)
    clock.freeze(datetime(2026, 4, 2, 9, 0))  # 10 jours après le 23/03
    r = client.post(f"/api/loans/{loan.id}/return", headers=staff[1]).json()
    assert r["days_late"] == 10 and r["penalty_amount"] == "5.00"
    penalty = db.query(Penalty).one()
    assert penalty.kind == "RETARD" and penalty.status == "IMPAYEE"
    assert penalty.user_id == member[0].id


@pytest.mark.req("RG-06")
def test_penalite_plafonnee(client, make, staff, member):
    loan = make.loan(member[0], make.book(), at=T0)
    clock.freeze(datetime(2026, 12, 1, 9, 0))
    fresh_token = make.token(staff[0])  # jeton émis à la date simulée
    r = client.post(f"/api/loans/{loan.id}/return", headers=fresh_token).json()
    assert r["penalty_amount"] == "20.00"


@pytest.mark.req("WF-01", "EQ-FIA-05")
def test_double_retour_refuse_et_pas_de_double_penalite(client, make, staff, member, db):
    loan = make.loan(member[0], make.book(), at=T0)
    clock.freeze(datetime(2026, 4, 2, 9, 0))
    assert client.post(f"/api/loans/{loan.id}/return", headers=staff[1]).status_code == 200
    r = client.post(f"/api/loans/{loan.id}/return", headers=staff[1])
    assert r.status_code == 409 and r.json()["code"] == "WF-TRANSITION"
    assert db.query(Penalty).count() == 1


@pytest.mark.req("EF-08", "RG-05")
def test_prolongation_par_l_adherent(client, make, member):
    loan = make.loan(member[0], make.book(), at=T0)
    r = client.post(f"/api/loans/{loan.id}/renew", headers=member[1])
    assert r.status_code == 200
    assert r.json()["due_date"] == "2026-04-06" and r.json()["renewals_count"] == 1
    r = client.post(f"/api/loans/{loan.id}/renew", headers=member[1])
    assert r.status_code == 409 and r.json()["code"] == "RG-05"


@pytest.mark.req("RG-05")
def test_prolongation_refusee_si_reservation_en_attente(client, make, member):
    book = make.book(copies=1)
    loan = make.loan(member[0], book, at=T0)
    other = make.user()
    client.post("/api/reservations", json={"book_id": book.id}, headers=make.token(other))
    r = client.post(f"/api/loans/{loan.id}/renew", headers=member[1])
    assert r.status_code == 409 and "réservé" in r.json()["detail"]


@pytest.mark.req("EF-08", "WF-01")
def test_declaration_de_perte(client, make, staff, member, db):
    loan = make.loan(member[0], make.book(), at=T0)
    r = client.post(f"/api/loans/{loan.id}/lost", headers=staff[1])
    assert r.status_code == 200 and r.json()["status"] == "PERDU"
    db.expire_all()
    assert db.get(Copy, loan.copy_id).status == "RETIRE"
    penalty = db.query(Penalty).one()
    assert penalty.kind == "PERTE" and str(penalty.amount) == "30.00"
    r = client.post(f"/api/loans/{loan.id}/return", headers=staff[1])
    assert r.status_code == 409


@pytest.mark.req("WF-01")
def test_maintenance_marque_les_retards_de_facon_idempotente(client, make, staff, member):
    make.loan(member[0], make.book(), at=T0)
    make.loan(member[0], make.book(), at=datetime(2026, 3, 20, 10, 0))
    clock.freeze(datetime(2026, 3, 25, 9, 0))
    first = client.post("/api/maintenance/run", headers=staff[1]).json()
    second = client.post("/api/maintenance/run", headers=staff[1]).json()
    assert first["loans_marked_overdue"] == 1 and second["loans_marked_overdue"] == 0
    loans = client.get("/api/loans?status=EN_RETARD", headers=staff[1]).json()
    assert loans["total"] == 1
    # un emprunt EN_RETARD peut toujours être rendu
    assert (
        client.post(f"/api/loans/{loans['items'][0]['id']}/return", headers=staff[1]).status_code
        == 200
    )


@pytest.mark.req("EF-08", "EF-12")
def test_liste_des_emprunts_filtres(client, make, staff, member):
    alice = make.user(email="alice@bibliotrack.example")
    book = make.book(copies=3, title="Les Misérables")
    make.loan(alice, book, 0, at=T0)
    make.loan(member[0], book, 1, at=T0)
    clock.freeze(datetime(2026, 4, 1))
    h = staff[1]
    assert client.get("/api/loans", headers=h).json()["total"] == 2
    assert client.get("/api/loans?q=alice", headers=h).json()["total"] == 1
    assert client.get("/api/loans?q=misérables", headers=h).json()["total"] == 2
    assert client.get("/api/loans?overdue_only=true", headers=h).json()["total"] == 2
    assert client.get(f"/api/loans?user_id={alice.id}", headers=h).json()["total"] == 1
