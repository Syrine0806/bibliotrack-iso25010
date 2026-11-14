"""Workflow de réservation WF-02 : file FIFO, mise de côté, expiration (RG-07, RG-08)."""

from datetime import datetime

import pytest

from app.core import clock
from app.models import Copy, Reservation

T0 = datetime(2026, 3, 2, 10, 0)


def reserve(client, headers, book_id):
    return client.post("/api/reservations", json={"book_id": book_id}, headers=headers)


@pytest.fixture
def borrowed_book(make):
    """Ouvrage à exemplaire unique, actuellement emprunté par un tiers."""
    book = make.book(copies=1)
    loan = make.loan(make.user(), book, at=T0)
    return book, loan


@pytest.mark.req("EF-09", "WF-02", "RG-07")
def test_reservation_nominale(client, member, borrowed_book):
    book, _ = borrowed_book
    r = reserve(client, member[1], book.id)
    assert r.status_code == 201
    assert r.json()["status"] == "EN_ATTENTE" and r.json()["queue_position"] == 1


@pytest.mark.req("RG-07")
def test_reservation_refusee_si_exemplaire_disponible(client, make, member):
    r = reserve(client, member[1], make.book(copies=1).id)
    assert r.status_code == 409 and r.json()["code"] == "RG-07"


@pytest.mark.req("RG-07")
def test_double_reservation_refusee(client, member, borrowed_book):
    book, _ = borrowed_book
    reserve(client, member[1], book.id)
    r = reserve(client, member[1], book.id)
    assert r.status_code == 409 and r.json()["code"] == "RG-07"


@pytest.mark.req("RG-07")
def test_reservation_refusee_si_deja_emprunteur(client, make, member):
    book = make.book(copies=1)
    make.loan(member[0], book)
    r = reserve(client, member[1], book.id)
    assert r.status_code == 409 and "empruntez déjà" in r.json()["detail"]


@pytest.mark.req("RG-07")
def test_maximum_trois_reservations_actives(client, make, member):
    books = []
    for _ in range(4):
        b = make.book(copies=1)
        make.loan(make.user(), b)
        books.append(b)
    for b in books[:3]:
        assert reserve(client, member[1], b.id).status_code == 201
    r = reserve(client, member[1], books[3].id)
    assert r.status_code == 409 and "3" in r.json()["detail"]


@pytest.mark.req("EF-09", "WF-02", "RG-08")
def test_file_fifo_retour_puis_emprunt_par_le_premier(client, make, staff, borrowed_book, db):
    book, loan = borrowed_book
    first, second = make.user(), make.user()
    clock.freeze(datetime(2026, 3, 3, 9, 0))
    reserve(client, make.token(first), book.id)
    clock.freeze(datetime(2026, 3, 3, 9, 5))
    reserve(client, make.token(second), book.id)
    positions = {
        r["user"]["id"]: r["queue_position"]
        for r in client.get(f"/api/reservations?book_id={book.id}", headers=staff[1]).json()[
            "items"
        ]
    }
    assert positions == {first.id: 1, second.id: 2}

    clock.freeze(datetime(2026, 3, 10, 14, 0))
    ret = client.post(f"/api/loans/{loan.id}/return", headers=staff[1]).json()
    assert ret["reserved_for_user_id"] == first.id
    copy = db.get(Copy, loan.copy_id)
    db.refresh(copy)
    assert copy.status == "RESERVE"
    held = db.query(Reservation).filter_by(user_id=first.id).one()
    assert held.status == "DISPONIBLE" and held.available_until == datetime(2026, 3, 13, 14, 0)

    # Le second adhérent ne peut pas prendre l'exemplaire mis de côté
    r = client.post(
        "/api/loans", json={"user_id": second.id, "barcode": make.barcode(book)}, headers=staff[1]
    )
    assert r.status_code == 409 and r.json()["code"] == "RG-04"
    # Le premier, oui : la réservation est honorée
    r = client.post(
        "/api/loans", json={"user_id": first.id, "barcode": make.barcode(book)}, headers=staff[1]
    )
    assert r.status_code == 201
    db.refresh(held)
    assert held.status == "HONOREE"


@pytest.mark.req("WF-02", "RG-08")
def test_expiration_de_la_mise_de_cote_passe_au_suivant(client, make, staff, borrowed_book, db):
    book, loan = borrowed_book
    first, second = make.user(), make.user()
    clock.freeze(datetime(2026, 3, 3, 9, 0))
    reserve(client, make.token(first), book.id)
    clock.freeze(datetime(2026, 3, 3, 9, 1))
    reserve(client, make.token(second), book.id)
    clock.freeze(datetime(2026, 3, 10, 14, 0))
    client.post(f"/api/loans/{loan.id}/return", headers=staff[1])

    clock.freeze(datetime(2026, 3, 13, 15, 0))  # délai de 3 jours dépassé
    result = client.post("/api/maintenance/run", headers=staff[1]).json()
    assert result["reservations_expired"] == 1
    statuses = {r.user_id: r.status for r in db.query(Reservation)}
    assert statuses == {first.id: "EXPIREE", second.id: "DISPONIBLE"}


@pytest.mark.req("WF-02", "RG-08")
def test_annulation_d_une_reservation_disponible_libere_l_exemplaire(
    client, make, staff, borrowed_book, db
):
    book, loan = borrowed_book
    user = make.user()
    headers = make.token(user)
    res = reserve(client, headers, book.id).json()
    client.post(f"/api/loans/{loan.id}/return", headers=staff[1])
    r = client.post(f"/api/reservations/{res['id']}/cancel", headers=headers)
    assert r.status_code == 200 and r.json()["status"] == "ANNULEE"
    copy = db.get(Copy, loan.copy_id)
    db.refresh(copy)
    assert copy.status == "DISPONIBLE"
    r = client.post(f"/api/reservations/{res['id']}/cancel", headers=headers)
    assert r.status_code == 409 and r.json()["code"] == "WF-TRANSITION"


@pytest.mark.req("RG-08", "EF-06")
def test_nouvel_exemplaire_sert_directement_la_file(client, make, staff, borrowed_book, db):
    book, _ = borrowed_book
    user = make.user()
    reserve(client, make.token(user), book.id)
    r = client.post(f"/api/books/{book.id}/copies", json={"barcode": "NEW-0001"}, headers=staff[1])
    assert r.status_code == 201
    assert db.query(Reservation).filter_by(user_id=user.id).one().status == "DISPONIBLE"


@pytest.mark.req("EF-09")
def test_bibliothecaire_reserve_pour_un_adherent(client, make, staff, borrowed_book):
    book, _ = borrowed_book
    user = make.user()
    r = client.post(
        "/api/reservations", json={"book_id": book.id, "user_id": user.id}, headers=staff[1]
    )
    assert r.status_code == 201 and r.json()["user"]["id"] == user.id
