"""Jeu de données de démonstration, déterministe (graine fixe) et idempotent.

Usage : python -m app.seed [--books 5000]
Comptes de démonstration (domaine réservé .example, RFC 2606) :
  admin@bibliotrack.example   / Admin1234     (ADMIN)
  biblio@bibliotrack.example  / Biblio1234    (BIBLIOTHECAIRE)
  adherent@bibliotrack.example/ Adherent1234  (ADHERENT)
"""

import argparse
import random
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.security import hash_password
from app.domain.enums import CopyStatus, LoanStatus, PenaltyStatus, Role
from app.models import Author, Book, Category, Copy, Loan, Penalty, User, book_authors

DEMO_ACCOUNTS = [
    ("admin@bibliotrack.example", "Alice Admin", "Admin1234", Role.ADMIN),
    ("biblio@bibliotrack.example", "Bruno Bibliothécaire", "Biblio1234", Role.BIBLIOTHECAIRE),
    ("adherent@bibliotrack.example", "Chloé Adhérente", "Adherent1234", Role.ADHERENT),
]
CATEGORIES = [
    ("Roman", "Fiction littéraire"),
    ("Science-fiction", "Anticipation et space opera"),
    ("Policier", "Polars et thrillers"),
    ("Histoire", "Ouvrages historiques"),
    ("Sciences", "Vulgarisation scientifique"),
    ("Informatique", "Programmation et systèmes"),
    ("Jeunesse", "Albums et romans jeunesse"),
    ("Bande dessinée", "BD, mangas, comics"),
    ("Philosophie", "Essais philosophiques"),
    ("Art", "Beaux-arts, photographie, musique"),
]
FIRST = [
    "Jean",
    "Marie",
    "Luc",
    "Sophie",
    "Paul",
    "Claire",
    "Hugo",
    "Emma",
    "Louis",
    "Léa",
    "Victor",
    "Inès",
    "Jules",
    "Camille",
    "Noah",
    "Zoé",
    "Karim",
    "Yasmine",
    "Omar",
    "Nina",
]
LAST = [
    "Martin",
    "Bernard",
    "Dubois",
    "Thomas",
    "Robert",
    "Richard",
    "Petit",
    "Durand",
    "Leroy",
    "Moreau",
    "Simon",
    "Laurent",
    "Lefebvre",
    "Michel",
    "Garcia",
    "Benali",
    "Haddad",
    "Rousseau",
    "Fontaine",
    "Chevalier",
]
WORDS = [
    "Ombre",
    "Lumière",
    "Voyage",
    "Secret",
    "Mémoire",
    "Jardin",
    "Océan",
    "Étoile",
    "Silence",
    "Royaume",
    "Algorithme",
    "Horizon",
    "Cité",
    "Nuit",
    "Fleuve",
    "Code",
    "Machine",
    "Saison",
    "Miroir",
    "Empire",
    "Archive",
    "Labyrinthe",
    "Rivage",
    "Signal",
]
PUBLISHERS = [
    "Gallimard",
    "Flammarion",
    "Actes Sud",
    "Dunod",
    "Eyrolles",
    "Hachette",
    "Le Seuil",
    "Albin Michel",
    "Casterman",
    "Dargaud",
]


def make_isbn13(n: int) -> str:
    core = f"979{10_000_000 + n:09d}"[:12]
    total = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(core))
    return core + str((10 - total % 10) % 10)


def _users(db: Session, rng: random.Random, members: int) -> list[int]:
    for email, name, pwd, role in DEMO_ACCOUNTS:
        db.add(User(email=email, full_name=name, hashed_password=hash_password(pwd), role=role))
    shared_hash = hash_password("Membre1234")  # un seul hachage : seed rapide
    db.execute(
        insert(User),
        [
            {
                "email": f"membre{i:04d}@bibliotrack.example",
                "full_name": f"{rng.choice(FIRST)} {rng.choice(LAST)}",
                "hashed_password": shared_hash,
                "role": Role.ADHERENT,
                "is_active": True,
                "failed_login_attempts": 0,
                "created_at": clock.now(),
            }
            for i in range(1, members + 1)
        ],
    )
    db.flush()
    return list(db.scalars(select(User.id).where(User.role == Role.ADHERENT)))


def _catalog(db: Session, rng: random.Random, n_books: int) -> list[int]:
    db.execute(insert(Category), [{"name": n, "description": d} for n, d in CATEGORIES])
    db.execute(
        insert(Author),
        [
            {
                "full_name": f"{rng.choice(FIRST)} {rng.choice(LAST)} {i}",
                "nationality": rng.choice(
                    ["Française", "Belge", "Canadienne", "Marocaine", "Tunisienne", "Suisse"]
                ),
                "birth_year": rng.randint(1900, 1995),
            }
            for i in range(1, 401)
        ],
    )
    cat_ids = list(db.scalars(select(Category.id)))
    author_ids = list(db.scalars(select(Author.id)))
    now = clock.now()
    db.execute(
        insert(Book),
        [
            {
                "isbn": make_isbn13(i),
                "title": f"{rng.choice(WORDS)} {rng.choice(WORDS).lower()} {i}",
                "publisher": rng.choice(PUBLISHERS),
                "publication_year": rng.randint(1950, 2025),
                "summary": "Ouvrage de démonstration généré automatiquement.",
                "category_id": rng.choice(cat_ids),
                "created_at": now - timedelta(days=rng.randint(0, 900)),
            }
            for i in range(1, n_books + 1)
        ],
    )
    book_ids = list(db.scalars(select(Book.id)))
    links = {(b, a) for b in book_ids for a in rng.sample(author_ids, rng.choice([1, 1, 1, 2]))}
    db.execute(insert(book_authors), [{"book_id": b, "author_id": a} for b, a in links])
    copies = []
    for b in book_ids:
        for k in range(rng.choice([1, 2, 2, 3])):
            copies.append(
                {
                    "book_id": b,
                    "barcode": f"BC{b:06d}-{k + 1}",
                    "status": CopyStatus.DISPONIBLE,
                    "shelf_location": f"R{rng.randint(1, 40):02d}-E{rng.randint(1, 6)}",
                    "acquired_on": (now - timedelta(days=rng.randint(30, 2000))).date(),
                }
            )
    db.execute(insert(Copy), copies)
    return list(db.scalars(select(Copy.id)))


def _history(
    db: Session, rng: random.Random, member_ids: list[int], copy_ids: list[int], n_loans: int
) -> None:
    """Historique de prêts clos + quelques prêts actifs/en retard + pénalités."""
    now = clock.now()
    closed = []
    for _ in range(n_loans):
        start = now - timedelta(days=rng.randint(30, 365), hours=rng.randint(0, 23))
        due = (start + timedelta(days=21)).date()
        back = start + timedelta(days=rng.randint(3, 30))
        closed.append(
            {
                "copy_id": rng.choice(copy_ids),
                "user_id": rng.choice(member_ids),
                "loaned_at": start,
                "due_date": due,
                "returned_at": back,
                "renewals_count": 0,
                "status": LoanStatus.RENDU,
            }
        )
    db.execute(insert(Loan), closed)

    active_copies = rng.sample(copy_ids, min(600, len(copy_ids) // 4))
    borrowers = [m for m in member_ids for _ in range(2)]
    rng.shuffle(borrowers)
    for copy_id, user_id in zip(active_copies, borrowers, strict=False):
        start = now - timedelta(days=rng.randint(0, 35))
        due = (start + timedelta(days=21)).date()
        status = LoanStatus.EN_RETARD if due < now.date() else LoanStatus.EN_COURS
        db.add(
            Loan(
                copy_id=copy_id,
                user_id=user_id,
                loaned_at=start,
                due_date=due,
                status=status,
                renewals_count=0,
            )
        )
        db.get(Copy, copy_id).status = CopyStatus.EMPRUNTE
    for user_id in rng.sample(member_ids, min(25, len(member_ids))):
        db.add(
            Penalty(
                user_id=user_id,
                kind="AUTRE",
                amount=Decimal(rng.choice(["1.50", "4.00"])),
                reason="Retard antérieur (données de démonstration)",
                status=rng.choice([PenaltyStatus.IMPAYEE, PenaltyStatus.PAYEE]),
            )
        )


def seed(db: Session, n_books: int = 5000, members: int = 300, n_loans: int = 15000) -> bool:
    """Retourne False si la base contient déjà des utilisateurs (idempotence)."""
    if db.scalar(select(func.count(User.id))):
        return False
    # Revue sécurité : générateur pseudo-aléatoire volontaire (données de démo, aucun usage crypto).
    rng = random.Random(25010)  # noqa: S311  # nosec B311
    member_ids = _users(db, rng, members)
    copy_ids = _catalog(db, rng, n_books)
    _history(db, rng, member_ids, copy_ids, n_loans)
    db.commit()
    return True


def main() -> None:
    from app.core.database import Base, SessionLocal, engine

    parser = argparse.ArgumentParser(description="Charge les données de démonstration")
    parser.add_argument("--books", type=int, default=5000)
    parser.add_argument("--members", type=int, default=300)
    parser.add_argument("--loans", type=int, default=15000)
    args = parser.parse_args()
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        done = seed(db, args.books, args.members, args.loans)
    print("Données chargées." if done else "Base déjà initialisée : rien à faire.")


if __name__ == "__main__":
    main()
