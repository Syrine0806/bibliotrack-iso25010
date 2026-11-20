"""Test de charge (ISO 25010 §6.2) — exigence EQ-PERF-01 : p95 < 500 ms à 20 utilisateurs.

Exécution (stack Docker démarrée) :
  uv run locust -f tests/performance/locustfile.py --host http://localhost:8080 \
      --headless -u 20 -r 5 -t 2m --csv ../reports/performance/locust \
      --html ../reports/performance/locust-report.html
Puis : uv run python tests/performance/check_thresholds.py ../reports/performance/locust_stats.csv
"""

import random

from locust import HttpUser, between, task

SEARCH_TERMS = ["ombre", "voyage", "code", "secret", "étoile", "jardin", "nuit", "signal", "cité"]


class MemberUser(HttpUser):
    """Adhérent : consultation du catalogue (charge majoritaire)."""

    weight = 4
    wait_time = between(0.5, 2)

    def on_start(self) -> None:
        n = random.randint(1, 300)
        r = self.client.post(
            "/api/auth/login",
            json={"email": f"membre{n:04d}@bibliotrack.example", "password": "Membre1234"},
            name="POST /api/auth/login",
        )
        self.client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"

    @task(5)
    def search_catalog(self) -> None:
        term = random.choice(SEARCH_TERMS)
        self.client.get(
            f"/api/books?q={term}&page={random.randint(1, 3)}&size=20",
            name="GET /api/books?q=[terme]",
        )

    @task(2)
    def browse_category(self) -> None:
        cat = random.randint(1, 10)
        self.client.get(
            f"/api/books?category_id={cat}&available_only=true&sort=-year",
            name="GET /api/books?category_id=[id]",
        )

    @task(3)
    def book_detail(self) -> None:
        book_id = random.randint(1, 5000)
        self.client.get(f"/api/books/{book_id}", name="GET /api/books/[id]")
        self.client.get(f"/api/books/{book_id}/copies", name="GET /api/books/[id]/copies")

    @task(2)
    def my_account(self) -> None:
        self.client.get("/api/loans", name="GET /api/loans (adhérent)")
        self.client.get("/api/reservations", name="GET /api/reservations (adhérent)")


class LibrarianUser(HttpUser):
    """Bibliothécaire : pilotage et gestion des prêts (requêtes d'agrégation coûteuses)."""

    weight = 1
    wait_time = between(1, 3)

    def on_start(self) -> None:
        r = self.client.post(
            "/api/auth/login",
            json={"email": "biblio@bibliotrack.example", "password": "Biblio1234"},
            name="POST /api/auth/login",
        )
        self.client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"

    @task(3)
    def dashboard(self) -> None:
        self.client.get("/api/dashboard", name="GET /api/dashboard")

    @task(2)
    def overdue_loans(self) -> None:
        self.client.get("/api/loans?overdue_only=true&size=50", name="GET /api/loans?overdue_only")

    @task(2)
    def search_loans(self) -> None:
        self.client.get(
            f"/api/loans?q={random.choice(SEARCH_TERMS)}", name="GET /api/loans?q=[terme]"
        )

    @task(1)
    def members(self) -> None:
        self.client.get("/api/users?role=ADHERENT&q=martin", name="GET /api/users?q=[nom]")
