import pytest

from app.models import AuditLog


# ------------------------------------------------------------------ catégories
@pytest.mark.req("EF-03")
def test_crud_categorie(client, staff):
    h = staff[1]
    r = client.post("/api/categories", json={"name": "Poésie", "description": "Vers"}, headers=h)
    assert r.status_code == 201
    cat_id = r.json()["id"]
    assert any(c["name"] == "Poésie" for c in client.get("/api/categories", headers=h).json())
    r = client.put(f"/api/categories/{cat_id}", json={"name": "Poésie moderne"}, headers=h)
    assert r.status_code == 200 and r.json()["name"] == "Poésie moderne"
    assert client.delete(f"/api/categories/{cat_id}", headers=h).status_code == 204
    assert all(c["id"] != cat_id for c in client.get("/api/categories", headers=h).json())


@pytest.mark.req("RG-12", "EF-03")
def test_categorie_nom_unique(client, staff):
    client.post("/api/categories", json={"name": "Unique"}, headers=staff[1])
    r = client.post("/api/categories", json={"name": "Unique"}, headers=staff[1])
    assert r.status_code == 409 and r.json()["code"] == "RG-12"


@pytest.mark.req("RG-09", "EF-03")
def test_suppression_categorie_utilisee_refusee(client, make, staff):
    book = make.book()
    r = client.delete(f"/api/categories/{book.category_id}", headers=staff[1])
    assert r.status_code == 409 and r.json()["code"] == "RG-09"


# ------------------------------------------------------------------ auteurs
@pytest.mark.req("EF-04")
def test_crud_auteur(client, staff):
    h = staff[1]
    r = client.post(
        "/api/authors",
        json={"full_name": "Victor Hugo", "birth_year": 1802, "nationality": "Française"},
        headers=h,
    )
    assert r.status_code == 201
    author_id = r.json()["id"]
    assert client.get("/api/authors?q=hugo", headers=h).json()[0]["id"] == author_id
    r = client.put(f"/api/authors/{author_id}", json={"full_name": "V. Hugo"}, headers=h)
    assert r.json()["full_name"] == "V. Hugo"
    assert client.delete(f"/api/authors/{author_id}", headers=h).status_code == 204


@pytest.mark.req("RG-09", "EF-04")
def test_suppression_auteur_lie_a_un_livre_refusee(client, make, staff):
    book = make.book()
    r = client.delete(f"/api/authors/{book.authors[0].id}", headers=staff[1])
    assert r.status_code == 409


# ------------------------------------------------------------------ ouvrages (1-N, N-N)
@pytest.mark.req("EF-05")
def test_crud_ouvrage_avec_relations(client, make, staff):
    h = staff[1]
    cat = make.category("Roman")
    a1, a2 = make.author("Auteur A"), make.author("Auteur B")
    payload = {
        "isbn": "978-2-07-036822-8",
        "title": "L'Étranger",
        "category_id": cat.id,
        "author_ids": [a1.id, a2.id],
        "publication_year": 1942,
        "publisher": "Gallimard",
    }
    r = client.post("/api/books", json=payload, headers=h)
    assert r.status_code == 201, r.text
    book = r.json()
    assert book["isbn"] == "9782070368228"  # stocké sous forme canonique ISBN-13
    assert book["category"]["name"] == "Roman"
    assert {a["full_name"] for a in book["authors"]} == {"Auteur A", "Auteur B"}
    assert book["total_copies"] == 0

    payload.update(title="L'Étranger (poche)", author_ids=[a1.id])
    r = client.put(f"/api/books/{book['id']}", json=payload, headers=h)
    assert r.status_code == 200 and len(r.json()["authors"]) == 1
    assert client.get(f"/api/books/{book['id']}", headers=h).json()["title"] == "L'Étranger (poche)"
    assert client.delete(f"/api/books/{book['id']}", headers=h).status_code == 204
    assert client.get(f"/api/books/{book['id']}", headers=h).status_code == 404


@pytest.mark.req("RG-01", "EF-05")
def test_isbn_invalide_refuse(client, make, staff):
    payload = {
        "isbn": "9782070368229",
        "title": "X",
        "category_id": make.category().id,
        "author_ids": [make.author().id],
    }
    r = client.post("/api/books", json=payload, headers=staff[1])
    assert r.status_code == 422 and "RG-01" in r.text


@pytest.mark.req("RG-01", "EF-05")
def test_isbn_unique_meme_sous_forme_isbn10(client, make, staff):
    cat, author = make.category(), make.author()
    base = {"title": "X", "category_id": cat.id, "author_ids": [author.id]}
    assert (
        client.post(
            "/api/books", json={**base, "isbn": "9782070368228"}, headers=staff[1]
        ).status_code
        == 201
    )
    r = client.post("/api/books", json={**base, "isbn": "207036822X"}, headers=staff[1])
    assert r.status_code == 409 and r.json()["code"] == "RG-01"


@pytest.mark.req("EF-05")
def test_ouvrage_auteur_ou_categorie_inexistants(client, make, staff):
    payload = {
        "isbn": "9782070368228",
        "title": "X",
        "category_id": 9999,
        "author_ids": [make.author().id],
    }
    assert client.post("/api/books", json=payload, headers=staff[1]).status_code == 404
    payload.update(category_id=make.category().id, author_ids=[9999])
    assert client.post("/api/books", json=payload, headers=staff[1]).status_code == 404


@pytest.mark.req("EF-05")
@pytest.mark.parametrize(
    "patch",
    [{"title": ""}, {"author_ids": []}, {"publication_year": 1200}, {"title": "x" * 300}],
)
def test_validation_des_champs_ouvrage(client, make, staff, patch):
    payload = {
        "isbn": "9782070368228",
        "title": "X",
        "category_id": make.category().id,
        "author_ids": [make.author().id],
        **patch,
    }
    assert client.post("/api/books", json=payload, headers=staff[1]).status_code == 422


@pytest.mark.req("RG-09", "EF-05")
def test_suppression_ouvrage_avec_exemplaires_refusee(client, make, staff):
    book = make.book(copies=1)
    r = client.delete(f"/api/books/{book.id}", headers=staff[1])
    assert r.status_code == 409 and r.json()["code"] == "RG-09"


# ------------------------------------------------------------------ exemplaires
@pytest.mark.req("EF-06")
def test_crud_exemplaire_et_compteurs(client, make, staff):
    h = staff[1]
    book = make.book(copies=0)
    r = client.post(
        f"/api/books/{book.id}/copies",
        json={"barcode": "EX-0001", "shelf_location": "R01"},
        headers=h,
    )
    assert r.status_code == 201 and r.json()["status"] == "DISPONIBLE"
    copy_id = r.json()["id"]
    client.post(f"/api/books/{book.id}/copies", json={"barcode": "EX-0002"}, headers=h)
    detail = client.get(f"/api/books/{book.id}", headers=h).json()
    assert (detail["total_copies"], detail["available_copies"]) == (2, 2)

    r = client.patch(f"/api/copies/{copy_id}", json={"status": "EN_REPARATION"}, headers=h)
    assert r.status_code == 200
    detail = client.get(f"/api/books/{book.id}", headers=h).json()
    assert (detail["total_copies"], detail["available_copies"]) == (2, 1)
    assert len(client.get(f"/api/books/{book.id}/copies", headers=h).json()) == 2
    assert client.delete(f"/api/copies/{copy_id}", headers=h).status_code == 204


@pytest.mark.req("RG-12", "EF-06")
def test_code_barres_unique(client, make, staff):
    book = make.book(copies=0)
    client.post(f"/api/books/{book.id}/copies", json={"barcode": "DUP-0001"}, headers=staff[1])
    r = client.post(f"/api/books/{book.id}/copies", json={"barcode": "DUP-0001"}, headers=staff[1])
    assert r.status_code == 409


@pytest.mark.req("RG-04", "EF-06")
def test_statut_emprunte_non_modifiable_manuellement(client, make, staff):
    book = make.book(copies=1)
    loan = make.loan(make.user(), book)
    r = client.patch(f"/api/copies/{loan.copy_id}", json={"status": "DISPONIBLE"}, headers=staff[1])
    assert r.status_code == 409


@pytest.mark.req("RG-04", "EF-06")
def test_exemplaire_retire_definitif(client, make, staff):
    book = make.book(copies=1)
    copy_id = client.get(f"/api/books/{book.id}/copies", headers=staff[1]).json()[0]["id"]
    assert (
        client.patch(
            f"/api/copies/{copy_id}", json={"status": "RETIRE"}, headers=staff[1]
        ).status_code
        == 200
    )
    r = client.patch(f"/api/copies/{copy_id}", json={"status": "DISPONIBLE"}, headers=staff[1])
    assert r.status_code == 409 and r.json()["code"] == "WF-TRANSITION"


@pytest.mark.req("RG-09", "EF-06")
def test_exemplaire_avec_historique_non_supprimable(client, make, staff):
    book = make.book(copies=1)
    loan = make.loan(make.user(), book)
    assert client.delete(f"/api/copies/{loan.copy_id}", headers=staff[1]).status_code == 409


# ------------------------------------------------------------------ recherche
@pytest.mark.req("EF-12")
def test_recherche_multicritere_et_pagination(client, make, member):
    h = member[1]
    roman, sf = make.category("Roman"), make.category("SF")
    camus = make.author("Albert Camus")
    make.book(title="La Peste", category=roman, authors=[camus], year=1947)
    make.book(title="La Chute", category=roman, authors=[camus], year=1956, copies=0)
    make.book(title="Dune", category=sf, year=1965)
    for i in range(25):
        make.book(title=f"Série {i:02d}", category=sf, year=2000 + i % 5)

    assert client.get("/api/books?q=camus", headers=h).json()["total"] == 2  # par auteur
    assert client.get("/api/books?q=peste", headers=h).json()["total"] == 1  # par titre
    assert client.get(f"/api/books?category_id={roman.id}", headers=h).json()["total"] == 2
    assert client.get("/api/books?year_from=1950&year_to=1970", headers=h).json()["total"] == 2
    r = client.get(f"/api/books?author_id={camus.id}&available_only=true", headers=h).json()
    assert [b["title"] for b in r["items"]] == ["La Peste"]

    page1 = client.get("/api/books?q=série&size=10&page=1", headers=h).json()
    page3 = client.get("/api/books?q=série&size=10&page=3", headers=h).json()
    assert page1["total"] == 25 and len(page1["items"]) == 10 and len(page3["items"]) == 5
    assert page1["items"][0]["title"] == "Série 00"
    newest = client.get("/api/books?sort=-year&size=1", headers=h).json()["items"][0]
    assert newest["publication_year"] == 2004


@pytest.mark.req("EF-12")
@pytest.mark.parametrize("query", ["size=0", "size=101", "page=0", "sort=drop", "year_from=10"])
def test_parametres_de_recherche_invalides(client, member, query):
    assert client.get(f"/api/books?{query}", headers=member[1]).status_code == 422


# ------------------------------------------------------------------ audit du catalogue
@pytest.mark.req("EF-13")
def test_actions_catalogue_auditees(client, make, staff, db):
    client.post("/api/categories", json={"name": "Auditée"}, headers=staff[1])
    entry = db.query(AuditLog).filter_by(action="CATEGORY_CREATED").one()
    assert entry.user_email == "staff@bibliotrack.example" and entry.entity_type == "Category"
    assert entry.ip_address == "testclient"


@pytest.mark.req("EF-14", "EQ-COMP-02")
def test_lookup_isbn_invalide(client, staff):
    r = client.get("/api/books/lookup/123", headers=staff[1])
    assert r.status_code == 409 and r.json()["code"] == "RG-01"


@pytest.mark.req("EF-14", "EQ-FIA-04")
def test_lookup_isbn_service_tiers_injoignable_repli(client, staff):
    # BIBLIO_OPENLIBRARY_BASE_URL pointe vers un domaine .test inexistant (conftest)
    r = client.get("/api/books/lookup/9782070368228", headers=staff[1])
    assert r.status_code == 200 and r.json()["source"] == "fallback"
