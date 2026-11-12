"""Catalogue : catégories, auteurs, ouvrages (recherche paginée à fort volume), exemplaires."""

from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.domain.enums import ACTIVE_LOAN_STATUSES, CopyStatus
from app.domain.errors import BusinessRuleError, NotFoundError
from app.domain.state_machine import COPY_WORKFLOW
from app.models import Author, Book, Category, Copy, Loan, book_authors
from app.schemas import AuthorIn, BookIn, BookOut, CategoryIn, CopyIn
from app.services import audit, circulation
from app.services.audit import Actor


def _get[T](db: Session, model: type[T], entity_id: int, label: str) -> T:
    obj = db.get(model, entity_id)
    if obj is None:
        raise NotFoundError(label, entity_id)
    return obj


def _flush_unique(db: Session, code: str, message: str) -> None:
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise BusinessRuleError(code, message) from exc


# ------------------------------------------------------------------ catégories
def list_categories(db: Session) -> list[Category]:
    return list(db.scalars(select(Category).order_by(Category.name)).all())


def create_category(db: Session, actor: Actor, data: CategoryIn) -> Category:
    cat = Category(**data.model_dump())
    db.add(cat)
    _flush_unique(db, "RG-12", f"La catégorie « {data.name} » existe déjà.")
    audit.record(db, actor, "CATEGORY_CREATED", "Category", cat.id, name=cat.name)
    db.commit()
    return cat


def update_category(db: Session, actor: Actor, cat_id: int, data: CategoryIn) -> Category:
    cat = _get(db, Category, cat_id, "Catégorie")
    cat.name, cat.description = data.name, data.description
    _flush_unique(db, "RG-12", f"La catégorie « {data.name} » existe déjà.")
    audit.record(db, actor, "CATEGORY_UPDATED", "Category", cat.id, name=cat.name)
    db.commit()
    return cat


def delete_category(db: Session, actor: Actor, cat_id: int) -> None:
    cat = _get(db, Category, cat_id, "Catégorie")
    if db.scalar(select(func.count()).where(Book.category_id == cat_id)):
        raise BusinessRuleError(
            "RG-09", "Catégorie utilisée par des ouvrages : suppression refusée."
        )
    audit.record(db, actor, "CATEGORY_DELETED", "Category", cat.id, name=cat.name)
    db.delete(cat)
    db.commit()


# ------------------------------------------------------------------ auteurs
def list_authors(db: Session, q: str | None = None, limit: int = 200) -> list[Author]:
    stmt = select(Author).order_by(Author.full_name).limit(limit)
    if q:
        stmt = stmt.where(Author.full_name.ilike(f"%{q}%"))
    return list(db.scalars(stmt).all())


def create_author(db: Session, actor: Actor, data: AuthorIn) -> Author:
    author = Author(**data.model_dump())
    db.add(author)
    db.flush()
    audit.record(db, actor, "AUTHOR_CREATED", "Author", author.id, name=author.full_name)
    db.commit()
    return author


def update_author(db: Session, actor: Actor, author_id: int, data: AuthorIn) -> Author:
    author = _get(db, Author, author_id, "Auteur")
    for key, value in data.model_dump().items():
        setattr(author, key, value)
    audit.record(db, actor, "AUTHOR_UPDATED", "Author", author.id)
    db.commit()
    return author


def delete_author(db: Session, actor: Actor, author_id: int) -> None:
    author = _get(db, Author, author_id, "Auteur")
    if db.scalar(select(func.count()).where(book_authors.c.author_id == author_id)):
        raise BusinessRuleError("RG-09", "Auteur associé à des ouvrages : suppression refusée.")
    audit.record(db, actor, "AUTHOR_DELETED", "Author", author.id, name=author.full_name)
    db.delete(author)
    db.commit()


# ------------------------------------------------------------------ ouvrages
def _copy_counts(db: Session, book_ids: list[int]) -> dict[int, tuple[int, int]]:
    if not book_ids:
        return {}
    rows = db.execute(
        select(
            Copy.book_id,
            func.count(Copy.id),
            func.sum(case((Copy.status == CopyStatus.DISPONIBLE, 1), else_=0)),
        )
        .where(Copy.book_id.in_(book_ids), Copy.status != CopyStatus.RETIRE)
        .group_by(Copy.book_id)
    ).all()
    return {book_id: (int(total), int(avail or 0)) for book_id, total, avail in rows}


def to_book_out(db: Session, books: list[Book]) -> list[BookOut]:
    counts = _copy_counts(db, [b.id for b in books])
    result = []
    for b in books:
        total, avail = counts.get(b.id, (0, 0))
        out = BookOut.model_validate(b)
        out.total_copies, out.available_copies = total, avail
        result.append(out)
    return result


def search_books(
    db: Session,
    *,
    q: str | None = None,
    category_id: int | None = None,
    author_id: int | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    available_only: bool = False,
    sort: str = "title",
    page: int = 1,
    size: int = 20,
) -> tuple[list[Book], int]:
    """Recherche multi-critères paginée (entité à fort volume, index sur titre/ISBN/année)."""
    stmt = select(Book)
    if q:
        pattern = f"%{q.strip()}%"
        author_match = (
            select(book_authors.c.book_id)
            .join(Author, Author.id == book_authors.c.author_id)
            .where(Author.full_name.ilike(pattern))
        )
        stmt = stmt.where(
            or_(Book.title.ilike(pattern), Book.isbn.ilike(pattern), Book.id.in_(author_match))
        )
    if category_id:
        stmt = stmt.where(Book.category_id == category_id)
    if author_id:
        stmt = stmt.where(
            Book.id.in_(select(book_authors.c.book_id).where(book_authors.c.author_id == author_id))
        )
    if year_from:
        stmt = stmt.where(Book.publication_year >= year_from)
    if year_to:
        stmt = stmt.where(Book.publication_year <= year_to)
    if available_only:
        stmt = stmt.where(
            Book.id.in_(select(Copy.book_id).where(Copy.status == CopyStatus.DISPONIBLE))
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    order = {
        "title": Book.title.asc(),
        "-year": Book.publication_year.desc(),
        "year": Book.publication_year.asc(),
        "-created": Book.created_at.desc(),
    }.get(sort, Book.title.asc())
    rows = db.scalars(
        stmt.options(selectinload(Book.authors), selectinload(Book.category))
        .order_by(order, Book.id)
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return list(rows), total


def get_book(db: Session, book_id: int) -> Book:
    return _get(db, Book, book_id, "Ouvrage")


def _resolve_relations(db: Session, data: BookIn) -> tuple[Category, list[Author]]:
    category = _get(db, Category, data.category_id, "Catégorie")
    authors = list(db.scalars(select(Author).where(Author.id.in_(data.author_ids))).all())
    if len(authors) != len(set(data.author_ids)):
        raise NotFoundError("Auteur", data.author_ids)
    return category, authors


def create_book(db: Session, actor: Actor, data: BookIn) -> Book:
    category, authors = _resolve_relations(db, data)
    book = Book(
        **data.model_dump(exclude={"author_ids", "category_id"}),
        category=category,
        authors=authors,
    )
    db.add(book)
    _flush_unique(db, "RG-01", f"Un ouvrage avec l'ISBN {data.isbn} existe déjà.")
    audit.record(db, actor, "BOOK_CREATED", "Book", book.id, isbn=book.isbn, title=book.title)
    db.commit()
    return book


def update_book(db: Session, actor: Actor, book_id: int, data: BookIn) -> Book:
    book = get_book(db, book_id)
    category, authors = _resolve_relations(db, data)
    for key, value in data.model_dump(exclude={"author_ids", "category_id"}).items():
        setattr(book, key, value)
    book.category, book.authors = category, authors
    _flush_unique(db, "RG-01", f"Un ouvrage avec l'ISBN {data.isbn} existe déjà.")
    audit.record(db, actor, "BOOK_UPDATED", "Book", book.id, isbn=book.isbn)
    db.commit()
    return book


def delete_book(db: Session, actor: Actor, book_id: int) -> None:
    """RG-09 : un ouvrage ayant des exemplaires ou un historique ne peut être supprimé."""
    book = get_book(db, book_id)
    if db.scalar(select(func.count()).where(Copy.book_id == book_id)):
        raise BusinessRuleError(
            "RG-09", "Ouvrage possédant des exemplaires : retirez-les avant suppression."
        )
    audit.record(db, actor, "BOOK_DELETED", "Book", book.id, isbn=book.isbn, title=book.title)
    db.delete(book)
    db.commit()


# ------------------------------------------------------------------ exemplaires
def list_copies(db: Session, book_id: int) -> list[Copy]:
    get_book(db, book_id)
    return list(db.scalars(select(Copy).where(Copy.book_id == book_id).order_by(Copy.barcode)))


def add_copy(db: Session, actor: Actor, book_id: int, data: CopyIn) -> Copy:
    get_book(db, book_id)
    copy = Copy(book_id=book_id, barcode=data.barcode, shelf_location=data.shelf_location)
    db.add(copy)
    _flush_unique(db, "RG-12", f"Le code-barres {data.barcode} est déjà attribué.")
    audit.record(db, actor, "COPY_ADDED", "Copy", copy.id, barcode=copy.barcode, book_id=book_id)
    circulation.assign_copy_to_queue(db, copy)  # RG-08 : sert la file d'attente éventuelle
    db.commit()
    return copy


def change_copy_status(db: Session, actor: Actor, copy_id: int, target: CopyStatus) -> Copy:
    """Changement manuel (réparation, retrait). Les statuts EMPRUNTE/RESERVE sont pilotés
    exclusivement par les workflows d'emprunt et de réservation."""
    copy = _get(db, Copy, copy_id, "Exemplaire")
    if target in (CopyStatus.EMPRUNTE, CopyStatus.RESERVE) or copy.status in (
        CopyStatus.EMPRUNTE,
        CopyStatus.RESERVE,
    ):
        raise BusinessRuleError(
            "RG-04", "Statut géré par les prêts/réservations : modification manuelle interdite."
        )
    COPY_WORKFLOW.assert_transition(copy.status, target)
    previous = copy.status
    copy.status = target
    audit.record(db, actor, "COPY_STATUS_CHANGED", "Copy", copy.id, before=previous, after=target)
    if target == CopyStatus.DISPONIBLE:
        circulation.assign_copy_to_queue(db, copy)
    db.commit()
    return copy


def delete_copy(db: Session, actor: Actor, copy_id: int) -> None:
    copy = _get(db, Copy, copy_id, "Exemplaire")
    if db.scalar(select(func.count()).where(Loan.copy_id == copy_id)):
        raise BusinessRuleError(
            "RG-09", "Exemplaire avec historique de prêts : utilisez le statut RETIRE."
        )
    audit.record(db, actor, "COPY_DELETED", "Copy", copy.id, barcode=copy.barcode)
    db.delete(copy)
    db.commit()


def active_loan_for_copy(db: Session, copy_id: int) -> Loan | None:
    return db.scalar(
        select(Loan).where(Loan.copy_id == copy_id, Loan.status.in_(ACTIVE_LOAN_STATUSES))
    )
