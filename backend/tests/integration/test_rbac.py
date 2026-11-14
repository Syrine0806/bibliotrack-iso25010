"""Matrice de contrôle d'accès : (endpoint × rôle) → statut attendu (EF-02 / EQ-SEC-03)."""

import pytest

from app.domain.enums import Role

ADMIN, BIB, ADH = Role.ADMIN, Role.BIBLIOTHECAIRE, Role.ADHERENT

# (méthode, url, corps, rôles autorisés)
MATRIX = [
    ("GET", "/api/books", None, {ADMIN, BIB, ADH}),
    ("GET", "/api/categories", None, {ADMIN, BIB, ADH}),
    ("POST", "/api/categories", {"name": "RBAC"}, {ADMIN, BIB}),
    ("POST", "/api/authors", {"full_name": "RBAC"}, {ADMIN, BIB}),
    ("GET", "/api/users", None, {ADMIN, BIB}),
    (
        "POST",
        "/api/users",
        {
            "email": "z@bibliotrack.example",
            "full_name": "Z",
            "password": "Password123",
            "role": "ADMIN",
        },
        {ADMIN},
    ),
    ("GET", "/api/dashboard", None, {ADMIN, BIB}),
    ("GET", "/api/audit", None, {ADMIN}),
    ("POST", "/api/maintenance/run", None, {ADMIN, BIB}),
    ("POST", "/api/loans", {"user_id": 999999, "barcode": "NOPE-1"}, {ADMIN, BIB}),
    (
        "POST",
        "/api/penalties",
        {"user_id": 999999, "amount": "1.00", "reason": "test"},
        {ADMIN, BIB},
    ),
    ("GET", "/api/loans", None, {ADMIN, BIB, ADH}),
    ("GET", "/api/penalties", None, {ADMIN, BIB, ADH}),
    ("GET", "/api/reservations", None, {ADMIN, BIB, ADH}),
]


@pytest.mark.req("EF-02", "EQ-SEC-03")
@pytest.mark.parametrize("role", [ADMIN, BIB, ADH])
@pytest.mark.parametrize(
    ("method", "url", "body", "allowed"), MATRIX, ids=[f"{m} {u}" for m, u, _, _ in MATRIX]
)
def test_matrice_rbac(client, make, role, method, url, body, allowed):
    headers = make.token(make.user(role))
    r = client.request(method, url, json=body, headers=headers)
    if role in allowed:
        assert r.status_code not in (401, 403), r.text
    else:
        assert r.status_code == 403, r.text


@pytest.mark.req("EF-02", "EQ-SEC-03")
@pytest.mark.parametrize(
    ("method", "url", "body", "allowed"), MATRIX, ids=[f"{m} {u}" for m, u, _, _ in MATRIX]
)
def test_anonyme_toujours_refuse(client, method, url, body, allowed):
    assert client.request(method, url, json=body).status_code == 401


@pytest.mark.req("EQ-SEC-10", "EQ-SEC-03")
def test_adherent_ne_voit_que_ses_propres_emprunts(client, make, member):
    other = make.user()
    book = make.book(copies=2)
    make.loan(other, book, 0)
    make.loan(member[0], book, 1)
    # Même en demandant explicitement les données d'un autre adhérent (IDOR)
    r = client.get(f"/api/loans?user_id={other.id}", headers=member[1])
    assert r.status_code == 200
    assert {loan["user"]["id"] for loan in r.json()["items"]} == {member[0].id}


@pytest.mark.req("EQ-SEC-10")
def test_adherent_ne_peut_pas_prolonger_l_emprunt_d_un_autre(client, make, member):
    other = make.user()
    loan = make.loan(other, make.book())
    r = client.post(f"/api/loans/{loan.id}/renew", headers=member[1])
    assert r.status_code == 403


@pytest.mark.req("EQ-SEC-10")
def test_adherent_ne_peut_pas_annuler_la_reservation_d_un_autre(client, make, member):
    other = make.user()
    book = make.book(copies=1)
    make.loan(make.user(), book)
    other_headers = make.token(other)
    res = client.post("/api/reservations", json={"book_id": book.id}, headers=other_headers)
    assert res.status_code == 201
    r = client.post(f"/api/reservations/{res.json()['id']}/cancel", headers=member[1])
    assert r.status_code == 403


@pytest.mark.req("EQ-SEC-10")
def test_adherent_ne_peut_pas_reserver_au_nom_d_un_autre(client, make, member):
    other = make.user()
    book = make.book(copies=1)
    make.loan(make.user(), book)
    r = client.post(
        "/api/reservations", json={"book_id": book.id, "user_id": other.id}, headers=member[1]
    )
    assert r.status_code == 201 and r.json()["user"]["id"] == member[0].id


@pytest.mark.req("EF-02")
def test_seul_l_admin_annule_une_penalite(client, make, staff, admin):
    penalty = make.penalty(make.user())
    assert client.post(f"/api/penalties/{penalty.id}/cancel", headers=staff[1]).status_code == 403
    assert client.post(f"/api/penalties/{penalty.id}/cancel", headers=admin[1]).status_code == 200
