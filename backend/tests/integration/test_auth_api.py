from datetime import datetime, timedelta

import pytest

from app.core import clock
from app.core.security import create_access_token
from app.domain.enums import Role
from app.models import AuditLog, User


def login(client, email, password):
    return client.post("/api/auth/login", json={"email": email, "password": password})


@pytest.mark.req("EF-01")
def test_connexion_reussie_retourne_jwt_et_role(client, make):
    make.user(Role.BIBLIOTHECAIRE, email="bib@bibliotrack.example", password="Biblio1234")
    r = login(client, "bib@bibliotrack.example", "Biblio1234")
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer" and body["role"] == "BIBLIOTHECAIRE"
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200 and me.json()["email"] == "bib@bibliotrack.example"
    assert "hashed_password" not in me.json()


@pytest.mark.req("EF-01", "EQ-SEC-04")
def test_email_insensible_a_la_casse(client, make):
    make.user(email="casse@bibliotrack.example", password="Password123")
    assert login(client, "CASSE@bibliotrack.example", "Password123").status_code == 200


@pytest.mark.req("EF-01", "EQ-SEC-04")
def test_mauvais_mot_de_passe_message_generique(client, make):
    make.user(email="a@bibliotrack.example", password="Password123")
    wrong_pwd = login(client, "a@bibliotrack.example", "Mauvais123")
    unknown = login(client, "inconnu@bibliotrack.example", "Password123")
    assert wrong_pwd.status_code == unknown.status_code == 401
    # Pas d'énumération de comptes : même message dans les deux cas
    assert wrong_pwd.json()["detail"] == unknown.json()["detail"]


@pytest.mark.req("RG-10", "EQ-SEC-04")
def test_verrouillage_apres_cinq_echecs_puis_deverrouillage_automatique(client, make, db):
    make.user(email="lock@bibliotrack.example", password="Password123")
    clock.freeze(datetime(2026, 3, 1, 10, 0))
    for _ in range(5):
        assert login(client, "lock@bibliotrack.example", "Faux12345").status_code == 401
    # Même le bon mot de passe est refusé pendant le verrouillage
    assert login(client, "lock@bibliotrack.example", "Password123").status_code == 401
    user = db.query(User).filter_by(email="lock@bibliotrack.example").one()
    db.refresh(user)
    assert user.locked_until == datetime(2026, 3, 1, 10, 15)
    actions = [a.action for a in db.query(AuditLog).filter_by(user_id=user.id)]
    assert "ACCOUNT_LOCKED" in actions and "LOGIN_REFUSED_LOCKED" in actions
    clock.freeze(datetime(2026, 3, 1, 10, 16))
    assert login(client, "lock@bibliotrack.example", "Password123").status_code == 200


@pytest.mark.req("RG-10")
def test_succes_remet_le_compteur_a_zero(client, make, db):
    user = make.user(email="reset@bibliotrack.example", password="Password123")
    for _ in range(4):
        login(client, "reset@bibliotrack.example", "Faux12345")
    assert login(client, "reset@bibliotrack.example", "Password123").status_code == 200
    db.refresh(user)
    assert user.failed_login_attempts == 0


@pytest.mark.req("RG-10", "EF-07")
def test_admin_peut_deverrouiller(client, make, admin, db):
    user = make.user(email="unl@bibliotrack.example", password="Password123")
    for _ in range(5):
        login(client, "unl@bibliotrack.example", "Faux12345")
    r = client.post(f"/api/users/{user.id}/unlock", headers=admin[1])
    assert r.status_code == 200 and r.json()["locked_until"] is None
    assert login(client, "unl@bibliotrack.example", "Password123").status_code == 200


@pytest.mark.req("EF-01", "RG-11")
def test_compte_desactive_ne_peut_pas_se_connecter(client, make, db):
    user = make.user(email="off@bibliotrack.example", password="Password123")
    user.is_active = False
    db.commit()
    assert login(client, "off@bibliotrack.example", "Password123").status_code == 401


@pytest.mark.req("EF-01", "EF-02", "EQ-SEC-03")
def test_inscription_cree_toujours_un_adherent(client):
    r = client.post(
        "/api/auth/register",
        json={
            "email": "new@bibliotrack.example",
            "full_name": "Nouveau",
            "password": "Password123",
            "role": "ADMIN",  # tentative d'élévation de privilège : champ ignoré
        },
    )
    assert r.status_code == 201 and r.json()["role"] == "ADHERENT"


@pytest.mark.req("RG-12")
def test_inscription_email_deja_utilise(client, make):
    make.user(email="dup@bibliotrack.example")
    r = client.post(
        "/api/auth/register",
        json={"email": "dup@bibliotrack.example", "full_name": "X", "password": "Password123"},
    )
    assert r.status_code == 409 and r.json()["code"] == "RG-12"


@pytest.mark.req("EQ-SEC-01")
@pytest.mark.parametrize("pwd", ["court1", "sanschiffre", "12345678"])
def test_inscription_mot_de_passe_faible_refuse(client, pwd):
    r = client.post(
        "/api/auth/register",
        json={"email": "weak@bibliotrack.example", "full_name": "X", "password": pwd},
    )
    assert r.status_code == 422


@pytest.mark.req("EQ-SEC-02")
@pytest.mark.parametrize("header", [None, "Bearer", "Bearer abc.def.ghi", "Basic YWRtaW46YWRtaW4="])
def test_acces_sans_jeton_valide_refuse(client, header):
    headers = {"Authorization": header} if header else {}
    assert client.get("/api/auth/me", headers=headers).status_code == 401


@pytest.mark.req("EQ-SEC-02")
def test_jeton_expire_refuse_par_l_api(client, make):
    user = make.user()
    clock.freeze(datetime(2026, 1, 1, 8, 0))
    headers = {"Authorization": f"Bearer {create_access_token(str(user.id), 'ADHERENT')}"}
    clock.freeze(datetime(2026, 1, 1, 8, 0) + timedelta(hours=2))
    assert client.get("/api/auth/me", headers=headers).status_code == 401


@pytest.mark.req("EQ-SEC-02")
def test_jeton_d_un_utilisateur_supprime_refuse(client, make, db):
    user = make.user()
    headers = make.token(user)
    db.delete(user)
    db.commit()
    assert client.get("/api/auth/me", headers=headers).status_code == 401


# Non-régression : anomalie détectée par le scan DAST OWASP ZAP (erreur 500 sur /register).
@pytest.mark.req("EQ-SEC-01", "EQ-SEC-05", "EQ-FIA-01")
@pytest.mark.parametrize("pwd", ["Abcdefg1" * 10, "Mot2passeé" * 8])  # 80 car. / > 72 octets UTF-8
def test_mot_de_passe_au_dela_de_72_octets_refuse_proprement(client, pwd):
    r = client.post(
        "/api/auth/register",
        json={"email": "long@bibliotrack.example", "full_name": "Long", "password": pwd},
    )
    assert r.status_code == 422  # et non 500


@pytest.mark.req("EQ-SEC-04", "EQ-FIA-01")
def test_connexion_avec_mot_de_passe_tres_long_renvoie_401(client, make):
    make.user(email="lp@bibliotrack.example")
    r = client.post(
        "/api/auth/login", json={"email": "lp@bibliotrack.example", "password": "x1" * 60}
    )
    assert r.status_code == 401
