"""Fixtures partagées.

- Base : SQLite fichier temporaire par défaut, ou PostgreSQL si TEST_DATABASE_URL est défini.
- Isolation : toutes les tables sont vidées avant chaque test.
- Traçabilité : @pytest.mark.req("RG-02", ...) est recopié dans le rapport JUnit XML
  (propriété "req"), exploité par scripts/build_traceability.py.
"""

import os
import tempfile
from datetime import datetime
from decimal import Decimal

_tmp_db = os.path.join(tempfile.gettempdir(), f"biblio_test_{os.getpid()}.db")
os.environ["BIBLIO_DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{_tmp_db}")
os.environ["BIBLIO_BCRYPT_ROUNDS"] = "4"
os.environ["BIBLIO_SEED_ON_STARTUP"] = "false"
os.environ["BIBLIO_OPENLIBRARY_BASE_URL"] = "https://openlibrary.test"

import jwt  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core import clock  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.domain.enums import Role  # noqa: E402
from app.main import app  # noqa: E402
from app.schemas import AuthorIn, BookIn, CategoryIn, CopyIn, UserCreate  # noqa: E402
from app.services import catalog, circulation, users  # noqa: E402
from app.services.audit import Actor  # noqa: E402


# ------------------------------------------------------------------ traçabilité
def pytest_collection_modifyitems(items):
    for item in items:
        ids = [i for m in item.iter_markers("req") for i in m.args]
        if ids:
            item.user_properties.append(("req", ",".join(sorted(set(ids)))))


# ------------------------------------------------------------------ base de données
@pytest.fixture(scope="session", autouse=True)
def _schema():
    import app.models  # noqa: F401

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists(_tmp_db):
        os.remove(_tmp_db)


@pytest.fixture(autouse=True)
def _clean_tables():
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    clock.freeze(None)
    yield
    clock.freeze(None)


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ------------------------------------------------------------------ fabrique de données
ADMIN_ACTOR = Actor(id=None, email="fixture@test", role=Role.ADMIN)


class Factory:
    def __init__(self, db):
        self.db = db
        self._n = 0

    def _next(self) -> int:
        self._n += 1
        return self._n

    def user(
        self, role: Role = Role.ADHERENT, email: str | None = None, password: str = "Password123"
    ):
        n = self._next()
        return users.create_user(
            self.db,
            ADMIN_ACTOR,
            UserCreate(
                email=email or f"user{n}@bibliotrack.example",
                full_name=f"Utilisateur {n}",
                password=password,
                role=role,
            ),
        )

    def token(self, user) -> dict[str, str]:
        """Jeton de fixture valide quelle que soit la date simulée par clock.freeze().
        Les tests d'expiration utilisent explicitement create_access_token()."""
        settings = get_settings()
        payload = {
            "sub": str(user.id),
            "role": user.role.value,
            "iat": 946684800,
            "exp": 4102444800,
        }  # 2000-01-01 → 2100-01-01
        token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        return {"Authorization": f"Bearer {token}"}

    def category(self, name: str | None = None):
        return catalog.create_category(
            self.db, ADMIN_ACTOR, CategoryIn(name=name or f"Catégorie {self._next()}")
        )

    def author(self, name: str | None = None):
        return catalog.create_author(
            self.db, ADMIN_ACTOR, AuthorIn(full_name=name or f"Auteur {self._next()}")
        )

    def book(
        self,
        copies: int = 1,
        title: str | None = None,
        category=None,
        authors=None,
        year: int = 2020,
    ):
        n = self._next()
        category = category or self.category()
        authors = authors or [self.author()]
        isbn = _isbn13(n)
        book = catalog.create_book(
            self.db,
            ADMIN_ACTOR,
            BookIn(
                isbn=isbn,
                title=title or f"Livre {n}",
                category_id=category.id,
                author_ids=[a.id for a in authors],
                publication_year=year,
            ),
        )
        for k in range(copies):
            catalog.add_copy(self.db, ADMIN_ACTOR, book.id, CopyIn(barcode=f"B{book.id:05d}-{k}"))
        return book

    def barcode(self, book, k: int = 0) -> str:
        return f"B{book.id:05d}-{k}"

    def loan(self, member, book, k: int = 0, at: datetime | None = None):
        if at is not None:
            clock.freeze(at)
        loan = circulation.create_loan(self.db, ADMIN_ACTOR, member.id, self.barcode(book, k))
        return loan

    def penalty(self, member, amount: str = "5.00"):
        return circulation.create_penalty(
            self.db, ADMIN_ACTOR, member.id, Decimal(amount), "Pénalité de test"
        )


def _isbn13(n: int) -> str:
    core = f"978{n:09d}"
    total = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(core))
    return core + str((10 - total % 10) % 10)


@pytest.fixture
def make(db) -> Factory:
    return Factory(db)


@pytest.fixture
def staff(make):
    librarian = make.user(Role.BIBLIOTHECAIRE, email="staff@bibliotrack.example")
    return librarian, make.token(librarian)


@pytest.fixture
def admin(make):
    a = make.user(Role.ADMIN, email="root@bibliotrack.example")
    return a, make.token(a)


@pytest.fixture
def member(make):
    m = make.user(Role.ADHERENT, email="member@bibliotrack.example")
    return m, make.token(m)
