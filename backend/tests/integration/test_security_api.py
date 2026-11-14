"""Tests de sécurité applicative (OWASP Top 10) exécutés contre l'API."""

import pytest

from app.models import Book


@pytest.mark.req("EQ-SEC-05")
@pytest.mark.parametrize(
    "payload",
    [
        "' OR '1'='1",
        "'; DROP TABLE books; --",
        "%' UNION SELECT email FROM users --",
        '" OR 1=1 --',
        "1; SELECT pg_sleep(5)",
    ],
)
def test_injection_sql_dans_la_recherche_neutralisee(client, make, member, db, payload):
    make.book(title="Livre légitime")
    r = client.get("/api/books", params={"q": payload}, headers=member[1])
    assert r.status_code == 200
    assert r.json()["total"] == 0  # traité comme du texte, pas comme du SQL
    assert db.query(Book).count() == 1  # table intacte


@pytest.mark.req("EQ-SEC-05")
def test_injection_sql_dans_la_connexion(client, make):
    make.user(email="victim@bibliotrack.example")
    r = client.post(
        "/api/auth/login", json={"email": "victim@bibliotrack.example", "password": "' OR '1'='1"}
    )
    assert r.status_code == 401


@pytest.mark.req("EQ-SEC-05")
def test_xss_stocke_renvoye_en_json_brut(client, make, staff):
    r = client.post("/api/categories", json={"name": "<script>alert(1)</script>"}, headers=staff[1])
    assert r.status_code == 201
    assert r.headers["content-type"].startswith("application/json")
    # La CSP de l'API interdit toute exécution de script
    assert "default-src 'none'" in r.headers["content-security-policy"]


@pytest.mark.req("EQ-SEC-09")
def test_en_tetes_de_securite_presents(client):
    r = client.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert r.headers["cache-control"] == "no-store"


@pytest.mark.req("EQ-SEC-09")
def test_cors_restreint_aux_origines_autorisees(client):
    ok = client.options(
        "/api/books",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    evil = client.options(
        "/api/books",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-origin" not in evil.headers


@pytest.mark.req("EQ-SEC-05", "EQ-FIA-01")
def test_erreurs_sans_fuite_d_information(client, member):
    r = client.get("/api/books/abc", headers=member[1])
    assert r.status_code == 422
    r = client.get("/api/books/999999", headers=member[1])
    assert r.status_code == 404
    assert "Traceback" not in r.text and "sqlalchemy" not in r.text.lower()


@pytest.mark.req("EQ-SEC-05")
def test_mass_assignment_ignore(client, make, staff, member):
    # Un adhérent ne peut pas modifier son rôle via l'inscription ni via /users
    r = client.patch(f"/api/users/{member[0].id}", json={"role": "ADMIN"}, headers=member[1])
    assert r.status_code == 403


@pytest.mark.req("EQ-SEC-05")
def test_taille_des_entrees_bornee(client, member):
    r = client.get("/api/books", params={"q": "x" * 500}, headers=member[1])
    assert r.status_code == 422
