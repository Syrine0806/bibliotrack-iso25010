"""Pénalités (WF-03), utilisateurs (EF-07), tableau de bord (EF-11), audit (EF-13)."""

from datetime import datetime

import pytest

from app.core import clock
from app.domain.enums import Role
from app.models import AuditLog, User


# ------------------------------------------------------------------ pénalités
@pytest.mark.req("EF-10", "WF-03")
def test_cycle_de_vie_penalite(client, make, staff, admin, member):
    r = client.post(
        "/api/penalties",
        json={"user_id": member[0].id, "amount": "3.50", "reason": "Livre abîmé"},
        headers=staff[1],
    )
    assert r.status_code == 201 and r.json()["status"] == "IMPAYEE"
    pid = r.json()["id"]
    mine = client.get("/api/penalties", headers=member[1]).json()
    assert mine["total"] == 1 and mine["items"][0]["amount"] == "3.50"
    r = client.post(f"/api/penalties/{pid}/pay", headers=staff[1])
    assert r.status_code == 200 and r.json()["status"] == "PAYEE" and r.json()["settled_at"]
    r = client.post(f"/api/penalties/{pid}/cancel", headers=admin[1])
    assert r.status_code == 409 and r.json()["code"] == "WF-TRANSITION"


@pytest.mark.req("EF-10")
@pytest.mark.parametrize("amount", ["0", "-1", "1000.01", "1.234"])
def test_montant_de_penalite_invalide(client, staff, member, amount):
    r = client.post(
        "/api/penalties",
        json={"user_id": member[0].id, "amount": amount, "reason": "test"},
        headers=staff[1],
    )
    assert r.status_code == 422


@pytest.mark.req("EF-10")
def test_filtre_penalites_par_statut(client, make, staff):
    user = make.user()
    p1 = make.penalty(user)
    make.penalty(user)
    client.post(f"/api/penalties/{p1.id}/pay", headers=staff[1])
    r = client.get("/api/penalties?status=IMPAYEE", headers=staff[1]).json()
    assert r["total"] == 1


# ------------------------------------------------------------------ utilisateurs
@pytest.mark.req("EF-07", "EF-02")
def test_crud_utilisateur_par_admin(client, admin):
    h = admin[1]
    r = client.post(
        "/api/users",
        json={
            "email": "bib2@bibliotrack.example",
            "full_name": "Bib",
            "password": "Password123",
            "role": "BIBLIOTHECAIRE",
        },
        headers=h,
    )
    assert r.status_code == 201 and r.json()["role"] == "BIBLIOTHECAIRE"
    uid = r.json()["id"]
    assert client.get(f"/api/users/{uid}", headers=h).json()["email"] == "bib2@bibliotrack.example"
    assert client.get("/api/users?role=BIBLIOTHECAIRE", headers=h).json()["total"] == 1
    assert client.get("/api/users?q=bib2", headers=h).json()["total"] == 1
    r = client.patch(
        f"/api/users/{uid}", json={"role": "ADHERENT", "full_name": "Ex Bib"}, headers=h
    )
    assert r.json()["role"] == "ADHERENT" and r.json()["full_name"] == "Ex Bib"
    assert client.delete(f"/api/users/{uid}", headers=h).status_code == 204
    assert client.get(f"/api/users/{uid}", headers=h).status_code == 404


@pytest.mark.req("EF-07", "EQ-SEC-01")
def test_changement_de_mot_de_passe_par_admin(client, make, admin):
    user = make.user(email="pw@bibliotrack.example")
    r = client.patch(f"/api/users/{user.id}", json={"password": "Nouveau123"}, headers=admin[1])
    assert r.status_code == 200
    login = client.post(
        "/api/auth/login", json={"email": "pw@bibliotrack.example", "password": "Nouveau123"}
    )
    assert login.status_code == 200


@pytest.mark.req("RG-09", "EF-07")
def test_suppression_adherent_avec_emprunt_actif_refusee(client, make, admin):
    user = make.user()
    make.loan(user, make.book())
    r = client.delete(f"/api/users/{user.id}", headers=admin[1])
    assert r.status_code == 409 and r.json()["code"] == "RG-09"


@pytest.mark.req("RG-09", "EF-07")
def test_suppression_adherent_avec_historique_desactive_le_compte(client, make, staff, admin, db):
    user = make.user()
    loan = make.loan(user, make.book())
    client.post(f"/api/loans/{loan.id}/return", headers=staff[1])
    assert client.delete(f"/api/users/{user.id}", headers=admin[1]).status_code == 204
    db.refresh(user)
    assert user.is_active is False  # historique conservé


@pytest.mark.req("RG-09", "EF-07")
def test_admin_ne_peut_pas_se_retrograder_ni_se_supprimer(client, admin):
    me, h = admin
    assert (
        client.patch(f"/api/users/{me.id}", json={"role": "ADHERENT"}, headers=h).status_code == 409
    )
    assert (
        client.patch(f"/api/users/{me.id}", json={"is_active": False}, headers=h).status_code == 409
    )
    assert client.delete(f"/api/users/{me.id}", headers=h).status_code == 409


# ------------------------------------------------------------------ tableau de bord
@pytest.mark.req("EF-11")
def test_indicateurs_du_tableau_de_bord(client, make, staff):
    roman, sf = make.category("Roman"), make.category("SF")
    b1 = make.book(copies=2, category=roman, title="Best-seller")
    b2 = make.book(copies=1, category=sf)
    m1, m2, m3 = make.user(), make.user(), make.user()
    make.loan(m1, b1, 0, at=datetime(2026, 1, 10, 10))
    make.loan(m2, b1, 1, at=datetime(2026, 2, 10, 10))
    make.loan(m3, b2, 0, at=datetime(2026, 2, 11, 10))
    make.penalty(m2, "4.00")
    clock.freeze(datetime(2026, 2, 20, 10))

    d = client.get(
        "/api/dashboard?date_from=2026-01-01&date_to=2026-02-28", headers=staff[1]
    ).json()
    assert d["total_books"] == 2 and d["total_copies"] == 3 and d["available_copies"] == 0
    assert d["active_loans"] == 3 and d["overdue_loans"] == 1  # échéance 31/01 dépassée
    assert d["unpaid_penalties_total"] == "4.00" and d["loans_in_period"] == 3
    assert d["active_members"] == 3
    assert d["loans_by_month"] == [
        {"label": "2026-01", "value": 1},
        {"label": "2026-02", "value": 2},
    ]
    assert d["top_books"][0] == {"label": "Best-seller", "value": 2}
    assert {c["label"]: c["value"] for c in d["loans_by_category"]} == {"Roman": 2, "SF": 1}
    assert {s["label"]: s["value"] for s in d["copies_by_status"]} == {"EMPRUNTE": 3}


@pytest.mark.req("EF-11")
def test_filtres_du_tableau_de_bord(client, make, staff):
    roman, sf = make.category("Roman"), make.category("SF")
    b1, b2 = make.book(category=roman), make.book(category=sf)
    make.loan(make.user(), b1, at=datetime(2026, 1, 10))
    make.loan(make.user(), b2, at=datetime(2026, 2, 10))
    clock.freeze(datetime(2026, 2, 12))
    by_cat = client.get(
        f"/api/dashboard?category_id={sf.id}&date_from=2026-01-01", headers=staff[1]
    ).json()
    assert by_cat["total_books"] == 1 and by_cat["loans_in_period"] == 1
    by_period = client.get(
        "/api/dashboard?date_from=2026-02-01&date_to=2026-02-28", headers=staff[1]
    ).json()
    assert by_period["loans_in_period"] == 1


# ------------------------------------------------------------------ audit
@pytest.mark.req("EF-13")
def test_journal_d_audit_complet_et_filtrable(client, make, staff, admin):
    member = make.user()
    loan = make.loan(member, make.book())
    client.post(f"/api/loans/{loan.id}/return", headers=staff[1])
    client.post("/api/auth/login", json={"email": "x@bibliotrack.example", "password": "Bad12345"})

    r = client.get("/api/audit?action=LOAN_RETURNED", headers=admin[1]).json()
    assert r["total"] == 1
    entry = r["items"][0]
    assert entry["user_email"] == "staff@bibliotrack.example"
    assert entry["entity_type"] == "Loan" and entry["entity_id"] == str(loan.id)
    assert "days_late" in entry["details"] and entry["timestamp"]
    assert client.get("/api/audit?action=LOGIN_FAILED", headers=admin[1]).json()["total"] == 1
    assert client.get("/api/audit?user_email=staff", headers=admin[1]).json()["total"] >= 1
    assert client.get("/api/audit?entity_type=Loan", headers=admin[1]).json()["total"] == 2


@pytest.mark.req("EF-13")
def test_actions_sensibles_tracees(client, make, admin, db):
    target = make.user()
    client.patch(
        f"/api/users/{target.id}",
        json={"role": "BIBLIOTHECAIRE", "password": "Secret999"},
        headers=admin[1],
    )
    entry = db.query(AuditLog).filter_by(action="USER_UPDATED").one()
    assert entry.user_id == admin[0].id
    assert "BIBLIOTHECAIRE" in entry.details
    assert "Secret999" not in entry.details  # aucun secret dans le journal


@pytest.mark.req("EF-13", "EQ-SEC-04")
def test_echecs_de_connexion_traces_avec_ip(client, make, db):
    make.user(email="t@bibliotrack.example")
    client.post("/api/auth/login", json={"email": "t@bibliotrack.example", "password": "Mauvais1"})
    entry = db.query(AuditLog).filter_by(action="LOGIN_FAILED").one()
    assert entry.ip_address == "testclient"
    assert db.query(User).filter_by(email="t@bibliotrack.example").one().role == Role.ADHERENT
