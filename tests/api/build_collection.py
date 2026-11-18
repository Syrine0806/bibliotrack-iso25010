"""Génère la collection Postman (tests de contrat d'API) exécutée par Newman.

Usage : python3 build_collection.py  →  bibliotrack.postman_collection.json
Chaque requête porte dans son nom les exigences couvertes, ex. "[EF-08][RG-04] ...".
"""

import json

COMMON_TESTS = [
    "pm.test('[EQ-SEC-09] en-têtes de sécurité présents', () => {",
    "  pm.expect(pm.response.headers.get('X-Content-Type-Options')).to.eql('nosniff');",
    "  pm.expect(pm.response.headers.get('X-Frame-Options')).to.eql('DENY');",
    "  pm.expect(pm.response.headers.get('Content-Security-Policy')).to.include(\"frame-ancestors 'none'\");",
    "});",
    "pm.test('[EQ-PERF-01] temps de réponse < 500 ms', () => pm.expect(pm.response.responseTime).to.be.below(500));",
]


def req(name, method, path, *, token=None, body=None, tests=(), prerequest=()):
    headers = [{"key": "Content-Type", "value": "application/json"}]
    if token:
        headers.append({"key": "Authorization", "value": "Bearer {{" + token + "}}"})
    item = {
        "name": name,
        "request": {
            "method": method,
            "header": headers,
            "url": {"raw": "{{baseUrl}}" + path, "host": ["{{baseUrl}}"],
                    "path": [p for p in path.split("?")[0].split("/") if p],
                    "query": [{"key": kv.split("=")[0], "value": kv.split("=")[1]}
                              for kv in (path.split("?")[1].split("&") if "?" in path else [])]},
        },
        "event": [{"listen": "test", "script": {"type": "text/javascript",
                                                 "exec": list(tests) + COMMON_TESTS}}],
    }
    if body is not None:
        item["request"]["body"] = {"mode": "raw", "raw": json.dumps(body, ensure_ascii=False)}
    if prerequest:
        item["event"].append({"listen": "prerequest",
                              "script": {"type": "text/javascript", "exec": list(prerequest)}})
    return item


def status(code):
    return f"pm.test('statut HTTP {code}', () => pm.response.to.have.status({code}));"


def rule(code):
    return f"pm.test('code règle {code}', () => pm.expect(pm.response.json().code).to.eql('{code}'));"


ISBN_SCRIPT = [
    "const core = '979' + String(Date.now()).slice(-9);",
    "let s = 0; for (let i = 0; i < 12; i++) s += Number(core[i]) * (i % 2 ? 3 : 1);",
    "pm.collectionVariables.set('isbn', core + ((10 - s % 10) % 10));",
    "pm.collectionVariables.set('suffix', Date.now().toString(36).toUpperCase());",
]

auth = [
    req("[EQ-FIA-03] Sonde de santé", "GET", "/api/health", tests=[
        status(200), "pm.test('base OK', () => pm.expect(pm.response.json()).to.eql({status: 'ok', database: 'ok'}));"]),
    req("[EF-01][EQ-SEC-04] Connexion refusée (mauvais mot de passe)", "POST", "/api/auth/login",
        body={"email": "{{staffEmail}}", "password": "Mauvais0000"}, tests=[
            status(401), "pm.test('message générique', () => pm.expect(pm.response.json().detail).to.eql('Identifiants invalides ou compte verrouillé.'));"]),
    req("[EF-01] Connexion bibliothécaire", "POST", "/api/auth/login",
        body={"email": "{{staffEmail}}", "password": "{{staffPassword}}"}, tests=[
            status(200),
            "const b = pm.response.json();",
            "pm.test('contrat Token', () => { pm.expect(b).to.have.all.keys('access_token','token_type','role','full_name'); pm.expect(b.token_type).to.eql('bearer'); pm.expect(b.role).to.eql('BIBLIOTHECAIRE'); });",
            "pm.test('JWT à 3 segments', () => pm.expect(b.access_token.split('.')).to.have.length(3));",
            "pm.collectionVariables.set('staffToken', b.access_token);"]),
    req("[EF-01] Connexion administrateur", "POST", "/api/auth/login",
        body={"email": "{{adminEmail}}", "password": "{{adminPassword}}"}, tests=[
            status(200), "pm.collectionVariables.set('adminToken', pm.response.json().access_token);"]),
    req("[EF-01][EF-02] Inscription adhérent (rôle forcé)", "POST", "/api/auth/register",
        body={"email": "newman.{{suffix}}@bibliotrack.example", "full_name": "Newman {{suffix}}",
              "password": "Newman1234", "role": "ADMIN"},
        prerequest=ISBN_SCRIPT, tests=[
            status(201),
            "const u = pm.response.json();",
            "pm.test('rôle ADHERENT imposé', () => pm.expect(u.role).to.eql('ADHERENT'));",
            "pm.test('aucun secret exposé', () => pm.expect(u).to.not.have.any.keys('password','hashed_password'));",
            "pm.collectionVariables.set('memberId', u.id);"]),
    req("[EF-01] Connexion adhérent", "POST", "/api/auth/login",
        body={"email": "newman.{{suffix}}@bibliotrack.example", "password": "Newman1234"}, tests=[
            status(200), "pm.collectionVariables.set('memberToken', pm.response.json().access_token);"]),
    req("[EF-01] Profil courant", "GET", "/api/auth/me", token="memberToken", tests=[
        status(200),
        "pm.test('contrat User', () => pm.expect(pm.response.json()).to.include.all.keys('id','email','full_name','role','is_active','created_at'));"]),
    req("[EQ-SEC-02] Accès sans jeton", "GET", "/api/auth/me", tests=[
        status(401), "pm.test('en-tête WWW-Authenticate', () => pm.expect(pm.response.headers.get('WWW-Authenticate')).to.eql('Bearer'));"]),
]

catalog = [
    req("[EF-12] Recherche paginée", "GET", "/api/books?q=ombre&size=5&page=1", token="memberToken", tests=[
        status(200),
        "const p = pm.response.json();",
        "pm.test('contrat Page<Book>', () => { pm.expect(p).to.have.all.keys('items','total','page','size'); pm.expect(p.items.length).to.be.at.most(5); });",
        "pm.test('contrat Book', () => pm.expect(p.items[0]).to.include.all.keys('id','isbn','title','category','authors','total_copies','available_copies'));",
        "pm.test('ISBN-13 canonique', () => pm.expect(p.items[0].isbn).to.match(/^97[89]\\d{10}$/));"]),
    req("[EF-12] Paramètre de pagination invalide", "GET", "/api/books?size=1000", token="memberToken",
        tests=[status(422)]),
    req("[EF-03] Liste des catégories", "GET", "/api/categories", token="memberToken", tests=[
        status(200), "pm.test('tableau non vide', () => pm.expect(pm.response.json()).to.be.an('array').that.is.not.empty);",
        "pm.collectionVariables.set('categoryId', pm.response.json()[0].id);"]),
    req("[EF-04] Création d'un auteur", "POST", "/api/authors", token="staffToken",
        body={"full_name": "Auteur Newman {{suffix}}", "nationality": "Française"}, tests=[
            status(201), "pm.collectionVariables.set('authorId', pm.response.json().id);"]),
    req("[EF-05][RG-01] ISBN invalide refusé", "POST", "/api/books", token="staffToken",
        body={"isbn": "9782070368229", "title": "X", "category_id": "{{categoryId}}", "author_ids": ["{{authorId}}"]},
        tests=[status(422)]),
    req("[EF-05] Création d'un ouvrage", "POST", "/api/books", token="staffToken",
        body={"isbn": "{{isbn}}", "title": "Ouvrage Newman {{suffix}}", "category_id": "{{categoryId}}",
              "author_ids": ["{{authorId}}"], "publication_year": 2025}, tests=[
            status(201),
            "const b = pm.response.json();",
            "pm.test('relations 1-N et N-N renvoyées', () => { pm.expect(b.category.id).to.eql(Number(pm.collectionVariables.get('categoryId'))); pm.expect(b.authors).to.have.length(1); });",
            "pm.collectionVariables.set('bookId', b.id);"]),
    req("[EF-05][RG-01] ISBN en double refusé", "POST", "/api/books", token="staffToken",
        body={"isbn": "{{isbn}}", "title": "Doublon", "category_id": "{{categoryId}}", "author_ids": ["{{authorId}}"]},
        tests=[status(409), rule("RG-01")]),
    req("[EF-02][EQ-SEC-03] Adhérent : création d'ouvrage interdite", "POST", "/api/books", token="memberToken",
        body={"isbn": "{{isbn}}", "title": "X", "category_id": "{{categoryId}}", "author_ids": ["{{authorId}}"]},
        tests=[status(403)]),
    req("[EF-06] Ajout d'un exemplaire", "POST", "/api/books/{{bookId}}/copies", token="staffToken",
        body={"barcode": "NWM-{{suffix}}", "shelf_location": "R01-E1"}, tests=[
            status(201), "pm.test('statut initial DISPONIBLE', () => pm.expect(pm.response.json().status).to.eql('DISPONIBLE'));"]),
]

circulation = [
    req("[EF-08][WF-01][RG-05] Emprunt", "POST", "/api/loans", token="staffToken",
        body={"user_id": "{{memberId}}", "barcode": "NWM-{{suffix}}"}, tests=[
            status(201),
            "const l = pm.response.json();",
            "pm.test('statut EN_COURS', () => pm.expect(l.status).to.eql('EN_COURS'));",
            "pm.test('échéance = J+21', () => { const d = new Date(l.loaned_at.slice(0,10)); d.setUTCDate(d.getUTCDate()+21); pm.expect(l.due_date).to.eql(d.toISOString().slice(0,10)); });",
            "pm.collectionVariables.set('loanId', l.id);"]),
    req("[RG-04] Exemplaire déjà emprunté", "POST", "/api/loans", token="staffToken",
        body={"user_id": "{{memberId}}", "barcode": "NWM-{{suffix}}"}, tests=[status(409), rule("RG-04")]),
    req("[EQ-SEC-03] Adhérent : enregistrement d'emprunt interdit", "POST", "/api/loans", token="memberToken",
        body={"user_id": "{{memberId}}", "barcode": "NWM-{{suffix}}"}, tests=[status(403)]),
    req("[EF-08][RG-05] Prolongation par l'adhérent", "POST", "/api/loans/{{loanId}}/renew", token="memberToken",
        tests=[status(200), "pm.test('1 prolongation', () => pm.expect(pm.response.json().renewals_count).to.eql(1));"]),
    req("[RG-05] Seconde prolongation refusée", "POST", "/api/loans/{{loanId}}/renew", token="memberToken",
        tests=[status(409), rule("RG-05")]),
    req("[EQ-SEC-10] Adhérent : seuls ses emprunts sont visibles", "GET", "/api/loans?user_id=1", token="memberToken",
        tests=[status(200), "pm.test('aucune fuite', () => pm.response.json().items.forEach(l => pm.expect(l.user.id).to.eql(Number(pm.collectionVariables.get('memberId')))));"]),
    req("[EF-08][WF-01][RG-06] Retour à l'heure", "POST", "/api/loans/{{loanId}}/return", token="staffToken",
        tests=[status(200), "const r = pm.response.json();",
               "pm.test('contrat ReturnResult', () => pm.expect(r).to.have.all.keys('loan','penalty_amount','days_late','reserved_for_user_id'));",
               "pm.test('pas de pénalité', () => pm.expect(r.penalty_amount).to.eql('0.00'));",
               "pm.test('statut RENDU', () => pm.expect(r.loan.status).to.eql('RENDU'));"]),
    req("[WF-01][EQ-FIA-05] Double retour refusé", "POST", "/api/loans/{{loanId}}/return", token="staffToken",
        tests=[status(409), rule("WF-TRANSITION")]),
    req("[EF-10][WF-03] Pénalité manuelle", "POST", "/api/penalties", token="staffToken",
        body={"user_id": "{{memberId}}", "amount": "2.50", "reason": "Livre annoté (Newman)"},
        tests=[status(201), "pm.collectionVariables.set('penaltyId', pm.response.json().id);"]),
    req("[EF-10][WF-03] Encaissement", "POST", "/api/penalties/{{penaltyId}}/pay", token="staffToken",
        tests=[status(200), "pm.test('PAYEE', () => pm.expect(pm.response.json().status).to.eql('PAYEE'));"]),
]

pilotage = [
    req("[EF-11] Tableau de bord", "GET", "/api/dashboard", token="staffToken", tests=[
        status(200),
        "pm.test('contrat Dashboard', () => pm.expect(pm.response.json()).to.include.all.keys('total_books','active_loans','overdue_loans','loans_by_month','top_books','loans_by_category','unpaid_penalties_total'));"]),
    req("[EF-02][EQ-SEC-03] Adhérent : tableau de bord interdit", "GET", "/api/dashboard", token="memberToken",
        tests=[status(403)]),
    req("[EF-13] Journal d'audit filtré", "GET", "/api/audit?action=LOAN_RETURNED&size=5", token="adminToken", tests=[
        status(200),
        "const p = pm.response.json();",
        "pm.test('au moins une entrée', () => pm.expect(p.total).to.be.above(0));",
        "pm.test('qui/quoi/quand', () => pm.expect(p.items[0]).to.include.all.keys('timestamp','user_email','action','entity_type','entity_id','ip_address'));"]),
    req("[EF-02][EQ-SEC-03] Bibliothécaire : audit interdit", "GET", "/api/audit", token="staffToken",
        tests=[status(403)]),
    req("[EQ-COMP-02] Contrat OpenAPI publié", "GET", "/api/openapi.json", tests=[
        status(200), "pm.test('OpenAPI 3.x', () => pm.expect(pm.response.json().openapi).to.match(/^3\\./));"]),
]

collection = {
    "info": {"name": "BiblioTrack API — tests de contrat",
             "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"},
    "item": [
        {"name": "1. Authentification", "item": auth},
        {"name": "2. Catalogue", "item": catalog},
        {"name": "3. Circulation", "item": circulation},
        {"name": "4. Pilotage", "item": pilotage},
    ],
    "variable": [{"key": k, "value": ""} for k in
                 ("staffToken", "adminToken", "memberToken", "memberId", "categoryId", "authorId",
                  "bookId", "loanId", "penaltyId", "isbn", "suffix")],
}

with open("bibliotrack.postman_collection.json", "w", encoding="utf-8") as f:
    json.dump(collection, f, ensure_ascii=False, indent=2)

env = {"name": "local", "values": [
    {"key": "baseUrl", "value": "http://localhost:8000", "enabled": True},
    {"key": "staffEmail", "value": "biblio@bibliotrack.example", "enabled": True},
    {"key": "staffPassword", "value": "Biblio1234", "enabled": True},
    {"key": "adminEmail", "value": "admin@bibliotrack.example", "enabled": True},
    {"key": "adminPassword", "value": "Admin1234", "enabled": True},
]}
with open("local.postman_environment.json", "w", encoding="utf-8") as f:
    json.dump(env, f, ensure_ascii=False, indent=2)
print(f"{sum(len(g['item']) for g in collection['item'])} requêtes générées")
